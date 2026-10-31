"""Asynchronous background polling service for Delhi OTD GTFS-Realtime VehiclePositions."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional
import urllib.parse

import httpx

from app.core.circuit_breaker import CircuitState, CircuitBreakerOpenException, otd_realtime_breaker
from app.core.config import settings
from app.models.realtime import ErrorCategory
from app.repositories.realtime_repository import RealtimeVehicleRepository
from app.services.realtime_feed_service import RealtimeFeedParser

logger = logging.getLogger("safarsetu.realtime")


def sanitize_url(url: str) -> str:
    """Mask sensitive query parameters (such as 'key') in URLs for safe logging."""
    parsed = urllib.parse.urlsplit(url)
    if not parsed.query:
        return url
    q_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    masked = []
    for k, v in q_pairs:
        if k.lower() in ("key", "api_key", "token", "secret", "auth"):
            masked.append((k, "REDACTED"))
        else:
            masked.append((k, v))
    new_query = urllib.parse.urlencode(masked)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment))


class OTDRealtimePoller:
    """Manages periodic asynchronous polling of the Delhi OTD VehiclePositions endpoint."""

    def __init__(self, repository: RealtimeVehicleRepository, static_dataset_provider=None):
        self.repository = repository
        self.static_dataset_provider = static_dataset_provider
        self._task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._consecutive_failures: int = 0
        self._client: Optional[httpx.AsyncClient] = None

    async def start(self):
        """Start the poller task if real-time integration is enabled."""
        if self._is_running:
            return

        self.repository.update_config_status()

        if not settings.OTD_REALTIME_ENABLED:
            logger.info("OTD Real-Time integration is disabled in settings.")
            self.repository.record_error(
                ErrorCategory.DISABLED,
                "Real-time vehicle position polling is disabled in configuration.",
            )
            return

        if not settings.OTD_REALTIME_API_KEY:
            logger.info("OTD Real-Time API key is not configured. Poller will not fetch live feeds.")
            self.repository.record_error(
                ErrorCategory.AUTH_ERROR,
                "OTD_REALTIME_API_KEY is not configured in environment.",
            )
            return

        self._is_running = True
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.OTD_REALTIME_REQUEST_TIMEOUT_SECONDS),
            headers={"User-Agent": "SafarSetu/1.0 (Delhi Multimodal Transit Assistant)"},
        )
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "OTD Real-Time poller started (interval: %ds, target: %s)",
            settings.OTD_REALTIME_POLL_INTERVAL_SECONDS,
            sanitize_url(settings.OTD_REALTIME_URL),
        )

    async def stop(self):
        """Gracefully stop background polling and close HTTP resources."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("OTD Real-Time poller stopped.")

    async def poll_once(self) -> bool:
        """Execute a single authenticated HTTP fetch and parse iteration.
        
        Returns:
            True if poll succeeded, False otherwise.
        """
        if not settings.OTD_REALTIME_API_KEY:
            self.repository.record_error(
                ErrorCategory.AUTH_ERROR,
                "OTD_REALTIME_API_KEY is missing.",
            )
            return False

        # Build authenticated URL with credentials strictly in query param
        url = settings.OTD_REALTIME_URL
        sep = "&" if "?" in url else "?"
        auth_url = f"{url}{sep}key={settings.OTD_REALTIME_API_KEY}"
        safe_url = sanitize_url(auth_url)

        fetch_time = datetime.now(timezone.utc)
        client = self._client or httpx.AsyncClient(timeout=settings.OTD_REALTIME_REQUEST_TIMEOUT_SECONDS)
        should_close_client = (client != self._client)

        try:
            # Protect external Delhi OTD endpoint with Circuit Breaker
            async def _fetch_otd():
                r = await client.get(auth_url)
                if r.status_code >= 500:
                    r.raise_for_status()
                return r

            resp = await otd_realtime_breaker.call(_fetch_otd)
            if resp.status_code == 200:
                raw_bytes = resp.content
                # Retrieve current static dataset for matching
                static_ds = self.static_dataset_provider() if self.static_dataset_provider else None

                records, feed_ts, rejected_cnt = RealtimeFeedParser.parse(
                    raw_bytes=raw_bytes,
                    server_fetch_time=fetch_time,
                    static_dataset=static_ds,
                    stale_threshold_seconds=settings.OTD_REALTIME_STALE_THRESHOLD_SECONDS,
                )

                self.repository.upsert_vehicles(
                    records=records,
                    fetch_time=fetch_time,
                    feed_timestamp=feed_ts,
                    rejected_count=rejected_cnt,
                )
                self._consecutive_failures = 0
                logger.debug(
                    "Poll successful: %d vehicles parsed (%d rejected) from %s",
                    len(records),
                    rejected_cnt,
                    safe_url,
                )
                return True

            elif resp.status_code in (401, 403):
                self._consecutive_failures += 1
                self.repository.record_error(
                    ErrorCategory.AUTH_ERROR,
                    f"Authentication failed with Delhi OTD (HTTP {resp.status_code}). Verify OTD_REALTIME_API_KEY.",
                )
                logger.warning("OTD Real-Time authentication failed: HTTP %d at %s", resp.status_code, safe_url)
                return False

            else:
                self._consecutive_failures += 1
                self.repository.record_error(
                    ErrorCategory.NETWORK_ERROR,
                    f"Delhi OTD server returned HTTP status {resp.status_code}.",
                )
                logger.warning("OTD Real-Time HTTP error %d at %s", resp.status_code, safe_url)
                return False

        except CircuitBreakerOpenException as e:
            self.repository.record_error(
                ErrorCategory.NETWORK_ERROR,
                f"Circuit breaker is OPEN: OTD service temporarily paused. Probe allowed in {round(e.retry_after_seconds, 1)}s.",
            )
            return False

        except httpx.TimeoutException as e:
            self._consecutive_failures += 1
            self.repository.record_error(
                ErrorCategory.TIMEOUT,
                f"Request timed out after {settings.OTD_REALTIME_REQUEST_TIMEOUT_SECONDS}s contacting Delhi OTD.",
            )
            logger.warning("OTD Real-Time request timed out at %s", safe_url)
            return False

        except httpx.RequestError as e:
            self._consecutive_failures += 1
            self.repository.record_error(
                ErrorCategory.NETWORK_ERROR,
                f"Network communication failure: {type(e).__name__}.",
            )
            logger.warning("OTD Real-Time network error at %s: %s", safe_url, type(e).__name__)
            return False

        except Exception as e:
            self._consecutive_failures += 1
            self.repository.record_error(
                ErrorCategory.PARSE_ERROR,
                f"Failed to process GTFS-RT feed: {type(e).__name__}.",
            )
            logger.exception("OTD Real-Time unexpected error during poll")
            return False

        finally:
            if should_close_client:
                await client.aclose()

    async def _run_loop(self):
        """Continuous background execution loop with bounded exponential backoff."""
        while self._is_running:
            try:
                success = await self.poll_once()
            except Exception as e:
                logger.exception("Uncaught exception in poller loop: %s", e)
                success = False

            # Calculate sleep interval with bounded backoff on repeated failures
            if success:
                sleep_seconds = float(settings.OTD_REALTIME_POLL_INTERVAL_SECONDS)
            else:
                backoff_factor = min(self._consecutive_failures, 4)
                sleep_seconds = min(
                    settings.OTD_REALTIME_POLL_INTERVAL_SECONDS * (1.5 ** backoff_factor),
                    120.0,
                )

            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                break

