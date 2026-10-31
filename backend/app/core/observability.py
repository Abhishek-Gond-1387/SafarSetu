"""Observability & Telemetry Subsystem.

Tracks endpoint latencies, request rates, error ratios, cache efficiency,
and circuit breaker states with Prometheus metric exposition.
"""
from __future__ import annotations

from collections import defaultdict
import threading
import time
from typing import Any, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.cache import route_plan_cache, station_search_cache
from app.core.circuit_breaker import gemini_ai_breaker, otd_realtime_breaker


class MetricsCollector:
    """Thread-safe Prometheus and system metrics aggregator."""

    def __init__(self):
        self._lock = threading.Lock()
        self.total_requests = 0
        self.total_errors = 0
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.status_counts: Dict[int, int] = defaultdict(int)
        self.latency_sums: Dict[str, float] = defaultdict(float)
        self.latency_counts: Dict[str, int] = defaultdict(int)

    def record_request(self, endpoint: str, status_code: int, duration_seconds: float):
        with self._lock:
            self.total_requests += 1
            if status_code >= 400:
                self.total_errors += 1
            self.request_counts[endpoint] += 1
            self.status_counts[status_code] += 1
            self.latency_sums[endpoint] += duration_seconds
            self.latency_counts[endpoint] += 1

    def to_prometheus_format(self) -> str:
        """Export metrics in standard Prometheus exposition format (v0.0.4)."""
        lines = [
            "# HELP safarsetu_http_requests_total Total HTTP requests handled.",
            "# TYPE safarsetu_http_requests_total counter",
            f"safarsetu_http_requests_total {self.total_requests}",
            "",
            "# HELP safarsetu_http_errors_total Total HTTP 4xx/5xx errors.",
            "# TYPE safarsetu_http_errors_total counter",
            f"safarsetu_http_errors_total {self.total_errors}",
            "",
            "# HELP safarsetu_http_request_duration_seconds Average latency by endpoint.",
            "# TYPE safarsetu_http_request_duration_seconds gauge",
        ]

        with self._lock:
            for ep, count in self.latency_counts.items():
                if count > 0:
                    avg_lat = self.latency_sums[ep] / count
                    lines.append(f'safarsetu_http_request_duration_seconds{{endpoint="{ep}"}} {avg_lat:.5f}')

            lines.extend([
                "",
                "# HELP safarsetu_cache_hit_ratio_percent Route plan cache hit ratio.",
                "# TYPE safarsetu_cache_hit_ratio_percent gauge",
            ])
            c_stats = route_plan_cache.get_stats()
            lines.append(f'safarsetu_cache_hit_ratio_percent{{cache="route_plan"}} {c_stats["hit_ratio_percent"]}')
            lines.append(f'safarsetu_cache_hits_total{{cache="route_plan"}} {c_stats["hits"]}')
            lines.append(f'safarsetu_cache_misses_total{{cache="route_plan"}} {c_stats["misses"]}')

            lines.extend([
                "",
                "# HELP safarsetu_circuit_breaker_state Circuit breaker state (0=closed, 1=open, 2=half_open).",
                "# TYPE safarsetu_circuit_breaker_state gauge",
            ])
            state_map = {"closed": 0, "open": 1, "half_open": 2}
            otd_val = state_map.get(otd_realtime_breaker.state.value, 0)
            ai_val = state_map.get(gemini_ai_breaker.state.value, 0)
            lines.append(f'safarsetu_circuit_breaker_state{{name="delhi_otd"}} {otd_val}')
            lines.append(f'safarsetu_circuit_breaker_state{{name="gemini_ai"}} {ai_val}')

        return "\n".join(lines) + "\n"


metrics_collector = MetricsCollector()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware measuring latency and adding diagnostics headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        t0 = time.time()
        try:
            response = await call_next(request)
        except Exception:
            duration = time.time() - t0
            metrics_collector.record_request(request.url.path, 500, duration)
            raise

        duration = time.time() - t0
        metrics_collector.record_request(request.url.path, response.status_code, duration)

        # Attach high-precision response processing time header
        response.headers["X-Process-Time"] = f"{duration * 1000:.2f}ms"
        return response
