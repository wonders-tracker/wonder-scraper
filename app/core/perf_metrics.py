"""
API Performance Metrics.

Tracks request latencies and provides percentile calculations for health checks.

Usage:
    from app.core.perf_metrics import perf_metrics

    # Record a request
    perf_metrics.record_request("/api/v1/cards", 150.5, 200)

    # Get summary
    summary = perf_metrics.get_summary()
    # Returns: {"total_requests": 100, "slow_request_pct": 5.0, ...}

    # Get slowest endpoints
    slowest = perf_metrics.get_slowest_endpoints(n=5, by="p95")
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Deque, List, Any, Optional, Literal
from threading import Lock

# Configuration
SLOW_REQUEST_THRESHOLD_MS = 500  # Threshold for "slow" requests


@dataclass
class EndpointMetrics:
    """Metrics for a single endpoint."""

    endpoint: str
    # Use deque for FIFO - keeps most recent latencies, not highest
    latencies: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    status_codes: Dict[int, int] = field(default_factory=dict)
    last_request_at: Optional[datetime] = None

    # Keep only last N latencies to prevent unbounded memory growth
    MAX_LATENCIES: int = 1000

    def record(self, latency_ms: float, status_code: int) -> None:
        """Record a request."""
        # Append to deque (FIFO - oldest dropped when maxlen exceeded)
        self.latencies.append(latency_ms)

        # Track status codes
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
        self.last_request_at = datetime.now(timezone.utc)

    def percentile(self, p: float) -> Optional[float]:
        """Calculate percentile (0-100)."""
        if not self.latencies:
            return None
        # Sort a copy for percentile calculation (deque maintains insertion order)
        sorted_latencies = sorted(self.latencies)
        n = len(sorted_latencies)
        # Clamp percentile to valid range
        p = max(0, min(100, p))
        idx = int((p / 100) * n)
        idx = min(idx, n - 1)
        return sorted_latencies[idx]

    @property
    def p50(self) -> Optional[float]:
        return self.percentile(50)

    @property
    def p95(self) -> Optional[float]:
        return self.percentile(95)

    @property
    def p99(self) -> Optional[float]:
        return self.percentile(99)

    @property
    def total_requests(self) -> int:
        return sum(self.status_codes.values())


class PerformanceMetrics:
    """
    In-memory API performance metrics.

    Thread-safe tracking of request latencies per endpoint.
    """

    # Latency threshold for "slow" requests (500ms)
    SLOW_THRESHOLD_MS: float = 500.0

    def __init__(self):
        self._endpoints: Dict[str, EndpointMetrics] = {}
        self._lock = Lock()

    def record_request(
        self, endpoint: str, latency_ms: float, status_code: int = 200
    ) -> None:
        """
        Record a request.

        Args:
            endpoint: API endpoint path (e.g., "/api/v1/cards")
            latency_ms: Request latency in milliseconds
            status_code: HTTP status code
        """
        with self._lock:
            if endpoint not in self._endpoints:
                self._endpoints[endpoint] = EndpointMetrics(endpoint=endpoint)
            self._endpoints[endpoint].record(latency_ms, status_code)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall performance summary.

        Returns:
            Dict with total_requests, slow_request_pct, etc.
        """
        with self._lock:
            if not self._endpoints:
                return {
                    "total_requests": 0,
                    "slow_request_pct": 0.0,
                    "endpoints_tracked": 0,
                }

            total_requests = 0
            slow_requests = 0
            all_latencies: List[float] = []

            for metrics in self._endpoints.values():
                total_requests += metrics.total_requests
                all_latencies.extend(metrics.latencies)

            # Count slow requests
            for latency in all_latencies:
                if latency >= self.SLOW_THRESHOLD_MS:
                    slow_requests += 1

            slow_pct = (slow_requests / total_requests * 100) if total_requests > 0 else 0

            # Calculate overall percentiles
            all_latencies.sort()
            n = len(all_latencies)

            def pct(p: float) -> Optional[float]:
                if not all_latencies:
                    return None
                idx = min(int((p / 100) * n), n - 1)
                return all_latencies[idx]

            return {
                "total_requests": total_requests,
                "slow_request_pct": round(slow_pct, 1),
                "slow_threshold_ms": self.SLOW_THRESHOLD_MS,
                "endpoints_tracked": len(self._endpoints),
                "p50_ms": round(pct(50) or 0, 1),
                "p95_ms": round(pct(95) or 0, 1),
                "p99_ms": round(pct(99) or 0, 1),
            }

    def get_slowest_endpoints(
        self, n: int = 5, by: Literal["p50", "p95", "p99", "count"] = "p95"
    ) -> List[Dict[str, Any]]:
        """
        Get the N slowest endpoints.

        Args:
            n: Number of endpoints to return
            by: Metric to sort by ("p50", "p95", "p99", "count")

        Returns:
            List of endpoint metrics sorted by the specified metric.
        """
        with self._lock:
            if not self._endpoints:
                return []

            def sort_key(metrics: EndpointMetrics) -> float:
                if by == "count":
                    return float(metrics.total_requests)
                elif by == "p50":
                    return metrics.p50 or 0.0
                elif by == "p99":
                    return metrics.p99 or 0.0
                else:  # p95
                    return metrics.p95 or 0.0

            sorted_endpoints = sorted(
                self._endpoints.values(), key=sort_key, reverse=True
            )[:n]

            return [
                {
                    "endpoint": m.endpoint,
                    "total_requests": m.total_requests,
                    "p50_ms": round(m.p50 or 0, 1),
                    "p95_ms": round(m.p95 or 0, 1),
                    "p99_ms": round(m.p99 or 0, 1),
                }
                for m in sorted_endpoints
            ]

    def get_endpoint_metrics(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific endpoint."""
        with self._lock:
            metrics = self._endpoints.get(endpoint)
            if not metrics:
                return None

            return {
                "endpoint": endpoint,
                "total_requests": metrics.total_requests,
                "p50_ms": round(metrics.p50 or 0, 1),
                "p95_ms": round(metrics.p95 or 0, 1),
                "p99_ms": round(metrics.p99 or 0, 1),
                "status_codes": dict(metrics.status_codes),
                "last_request_at": metrics.last_request_at.isoformat()
                if metrics.last_request_at
                else None,
            }

    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._endpoints.clear()


# Global instance
perf_metrics = PerformanceMetrics()
