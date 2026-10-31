"""Production Circuit Breaker with State Machine, Retry, and Fallback.

Protects SafarSetu from cascading failures when external services
(Delhi OTD real-time vehicle positions, Gemini AI, Supabase) experience latency or outages.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
import functools
import logging
import time
from typing import Any, Callable, Dict, Optional, Type, Tuple

logger = logging.getLogger("safarsetu.circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "closed"        # Normal operations: requests pass through
    OPEN = "open"            # Failing: requests fail immediately with fallback
    HALF_OPEN = "half_open"  # Trial: allows a single probe request to check recovery


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    def __init__(self, name: str, retry_after_seconds: float):
        self.name = name
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. External service is currently degraded. "
            f"Retry probe allowed in {round(retry_after_seconds, 1)}s."
        )


class CircuitBreaker:
    """Thread-safe and async-compatible Circuit Breaker."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_time_seconds: float = 30.0,
        expected_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        fallback: Optional[Callable[..., Any]] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds
        self.expected_exceptions = expected_exceptions
        self.fallback = fallback

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change: float = time.time()
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        # Check if OPEN circuit can transition to HALF_OPEN
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_time_seconds:
                self._state = CircuitState.HALF_OPEN
                self._last_state_change = time.time()
                logger.info(
                    "CircuitBreaker '%s' transitioned to HALF_OPEN after %.1fs. Allowing trial request.",
                    self.name, elapsed
                )
        return self._state

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic metrics for observability / monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_time_seconds": self.recovery_time_seconds,
            "last_failure_time": (
                datetime.fromtimestamp(self._last_failure_time, tz=timezone.utc).isoformat()
                if self._last_failure_time else None
            ),
        }

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute an asynchronous function wrapped with Circuit Breaker protection."""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            time_remaining = max(0.0, self.recovery_time_seconds - (time.time() - (self._last_failure_time or 0)))
            logger.warning(
                "CircuitBreaker '%s' is OPEN. Fast-failing with fallback (recovery in %.1fs).",
                self.name, time_remaining
            )
            if self.fallback:
                return self.fallback(*args, **kwargs)
            raise CircuitBreakerOpenException(self.name, time_remaining)

        try:
            res = await func(*args, **kwargs)
            await self._on_success()
            return res
        except self.expected_exceptions as exc:
            await self._on_failure(exc)
            if self.fallback:
                logger.info("CircuitBreaker '%s': Executing fallback after error: %s", self.name, exc)
                return self.fallback(*args, **kwargs)
            raise exc

    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info("CircuitBreaker '%s': Trial probe succeeded. Resetting circuit to CLOSED.", self.name)
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._last_failure_time = None
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def _on_failure(self, exc: Exception):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            logger.warning(
                "CircuitBreaker '%s': Failure %d/%d (Error: %s)",
                self.name, self._failure_count, self.failure_threshold, exc
            )

            if self._state == CircuitState.HALF_OPEN:
                logger.error("CircuitBreaker '%s': Trial probe failed. Re-opening circuit for %.1fs.", self.name, self.recovery_time_seconds)
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold and self._state == CircuitState.CLOSED:
                logger.error(
                    "CircuitBreaker '%s': Failure threshold %d exceeded. Circuit is now OPEN (fast-failing for %.1fs).",
                    self.name, self.failure_threshold, self.recovery_time_seconds
                )
                self._state = CircuitState.OPEN


# Shared Singleton Circuit Breakers
otd_realtime_breaker = CircuitBreaker(
    name="delhi_otd_realtime_feed",
    failure_threshold=4,
    recovery_time_seconds=25.0,
)

gemini_ai_breaker = CircuitBreaker(
    name="google_gemini_voice_assistant",
    failure_threshold=3,
    recovery_time_seconds=30.0,
)

