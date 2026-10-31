"""Unit tests for newly implemented System Design subsystems:
Circuit Breaker, Multi-Tier Caching, and Observability Metrics.
"""
import asyncio
import pytest
from app.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenException
from app.core.cache import LRUTTLCache, generate_route_plan_cache_key
from app.core.observability import metrics_collector


def test_circuit_breaker_transitions():
    """Verify circuit transitions to OPEN on failures and allows fallback."""
    async def _run_test():
        breaker = CircuitBreaker(
            name="test_breaker",
            failure_threshold=2,
            recovery_time_seconds=0.2,
            fallback=lambda: "fallback_response",
        )

        assert breaker.state == CircuitState.CLOSED

        # Failing function
        async def failing_call():
            raise ConnectionError("Service unreachable")

        # Attempt 1
        res1 = await breaker.call(failing_call)
        assert res1 == "fallback_response"
        assert breaker._failure_count == 1
        assert breaker.state == CircuitState.CLOSED

        # Attempt 2 -> Reaches threshold, circuit trips OPEN
        res2 = await breaker.call(failing_call)
        assert res2 == "fallback_response"
        assert breaker.state == CircuitState.OPEN

        # While OPEN, function is never called, fast-fails immediately with fallback
        called = False
        async def should_not_be_called():
            nonlocal called
            called = True
            return "ok"

        res3 = await breaker.call(should_not_be_called)
        assert res3 == "fallback_response"
        assert not called

        # Wait for recovery timeout -> transitions to HALF_OPEN
        await asyncio.sleep(0.25)
        assert breaker.state == CircuitState.HALF_OPEN

        # Successful call resets circuit to CLOSED
        async def successful_call():
            return "recovered"

        res4 = await breaker.call(successful_call)
        assert res4 == "recovered"
        assert breaker.state == CircuitState.CLOSED

    asyncio.run(_run_test())


def test_lru_ttl_cache():
    """Verify caching, hit ratios, and LRU eviction."""
    cache = LRUTTLCache(max_items=2, default_ttl_seconds=1.0)
    assert cache.get("a") is None

    cache.set("a", "val_a")
    cache.set("b", "val_b")
    assert cache.get("a") == "val_a"
    assert cache.get("b") == "val_b"

    # Add 3rd item -> evicts oldest
    cache.set("c", "val_c")
    assert cache.get("c") == "val_c"

    stats = cache.get_stats()
    assert stats["hits"] >= 2
    assert stats["misses"] >= 1


def test_cache_key_generation():
    """Verify 5-minute time window bucketing for cache keys."""
    k1 = generate_route_plan_cache_key("metro_1", "metro_2", "2026-10-31", "09:02:15", "fastest")
    k2 = generate_route_plan_cache_key("metro_1", "metro_2", "2026-10-31", "09:04:59", "fastest")
    k3 = generate_route_plan_cache_key("metro_1", "metro_2", "2026-10-31", "09:06:00", "fastest")

    # 09:02 and 09:04 bucket to 09:00
    assert k1 == k2
    # 09:06 buckets to 09:05
    assert k1 != k3


def test_prometheus_metrics_format():
    """Verify Prometheus metrics export contains expected counters and gauges."""
    metrics_collector.record_request("/api/v1/routes/plan", 200, 0.045)
    prom_text = metrics_collector.to_prometheus_format()

    assert "safarsetu_http_requests_total" in prom_text
    assert "safarsetu_cache_hit_ratio_percent" in prom_text
    assert "safarsetu_circuit_breaker_state" in prom_text
