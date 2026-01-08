"""
Performance metrics collector for API endpoints.

Tracks per-endpoint response times with a rolling window for percentile calculations.
Thread-safe and designed for low overhead in production.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional


# Configuration
MAX_SAMPLES_PER_ENDPOINT = 1000  # Rolling window size
SLOW_REQUEST_THRESHOLD_MS = 500  # Threshold for "slow" requests


@dataclass
class EndpointMetrics:
    """Metrics for a single endpoint."""

    samples: deque = field(default_factory=lambda: deque(maxlen=MAX_SAMPLES_PER_ENDPOINT))
    request_count: int = 0
    slow_request_count: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float("inf")
    max_time_ms: float = 0.0

    def add_sample(self, duration_ms: float) -> None:
        """Add a timing sample."""
        self.samples.append(duration_ms)
        self.request_count += 1
        self.total_time_ms += duration_ms

        if duration_ms < self.min_time_ms:
            self.min_time_ms = duration_ms
        if duration_ms > self.max_time_ms:
            self.max_time_ms = duration_ms
        if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
            self.slow_request_count += 1

    def get_percentile(self, p: float) -> Optional[float]:
        """Calculate the p-th percentile (0-100) from samples."""
        if not self.samples:
            return None

        sorted_samples = sorted(self.samples)
        n = len(sorted_samples)
        idx = (p / 100) * (n - 1)

        lower = int(idx)
        upper = lower + 1 if lower + 1 < n else lower
        weight = idx - lower

        return sorted_samples[lower] * (1 - weight) + sorted_samples[upper] * weight

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        p50 = self.get_percentile(50)
        p95 = self.get_percentile(95)
        p99 = self.get_percentile(99)

        return {
            "request_count": self.request_count,
            "slow_request_count": self.slow_request_count,
            "sample_count": len(self.samples),
            "avg_ms": round(self.total_time_ms / self.request_count, 2)
            if self.request_count > 0
            else None,
            "min_ms": round(self.min_time_ms, 2)
            if self.min_time_ms != float("inf")
            else None,
            "max_ms": round(self.max_time_ms, 2) if self.max_time_ms > 0 else None,
            "p50_ms": round(p50, 2) if p50 is not None else None,
            "p95_ms": round(p95, 2) if p95 is not None else None,
            "p99_ms": round(p99, 2) if p99 is not None else None,
        }


class PerformanceMetricsCollector:
    """
    Thread-safe performance metrics collector.

    Tracks request timings per endpoint with a rolling window.
    Designed for low overhead - uses simple list operations and minimal locking.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._endpoints: dict[str, EndpointMetrics] = {}
        self._start_time = time.time()
        self._total_requests = 0
        self._slow_requests = 0

    def record(self, endpoint: str, duration_ms: float) -> None:
        """
        Record a request timing.

        Args:
            endpoint: The endpoint path (e.g., "/api/v1/cards")
            duration_ms: Request duration in milliseconds
        """
        with self._lock:
            if endpoint not in self._endpoints:
                self._endpoints[endpoint] = EndpointMetrics()

            self._endpoints[endpoint].add_sample(duration_ms)
            self._total_requests += 1
            if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
                self._slow_requests += 1

    def get_endpoint_metrics(self, endpoint: str) -> Optional[dict]:
        """Get metrics for a specific endpoint."""
        with self._lock:
            if endpoint not in self._endpoints:
                return None
            return self._endpoints[endpoint].to_dict()

    def get_all_metrics(self) -> dict:
        """Get metrics for all endpoints."""
        with self._lock:
            return {
                endpoint: metrics.to_dict()
                for endpoint, metrics in self._endpoints.items()
            }

    def get_slowest_endpoints(self, n: int = 10, by: str = "p95") -> list[dict]:
        """
        Get the N slowest endpoints sorted by a percentile metric.

        Args:
            n: Number of endpoints to return
            by: Metric to sort by ("p50", "p95", "p99", "avg")

        Returns:
            List of endpoint info sorted by the chosen metric (descending)
        """
        with self._lock:
            endpoint_data = []
            for endpoint, metrics in self._endpoints.items():
                data = metrics.to_dict()
                data["endpoint"] = endpoint

                # Get sort key
                sort_key = 0.0
                if by == "p50" and data["p50_ms"] is not None:
                    sort_key = data["p50_ms"]
                elif by == "p95" and data["p95_ms"] is not None:
                    sort_key = data["p95_ms"]
                elif by == "p99" and data["p99_ms"] is not None:
                    sort_key = data["p99_ms"]
                elif by == "avg" and data["avg_ms"] is not None:
                    sort_key = data["avg_ms"]

                data["_sort_key"] = sort_key
                endpoint_data.append(data)

            # Sort by the chosen metric descending
            endpoint_data.sort(key=lambda x: x["_sort_key"], reverse=True)

            # Remove sort key and limit
            for d in endpoint_data:
                del d["_sort_key"]

            return endpoint_data[:n]

    def get_summary(self) -> dict:
        """Get a summary of overall performance."""
        uptime_seconds = time.time() - self._start_time

        with self._lock:
            return {
                "uptime_seconds": round(uptime_seconds, 1),
                "total_requests": self._total_requests,
                "slow_requests": self._slow_requests,
                "slow_request_pct": round(
                    (self._slow_requests / self._total_requests * 100), 2
                )
                if self._total_requests > 0
                else 0,
                "endpoints_tracked": len(self._endpoints),
                "slow_threshold_ms": SLOW_REQUEST_THRESHOLD_MS,
            }

    def reset(self) -> None:
        """Reset all metrics. Useful for testing."""
        with self._lock:
            self._endpoints.clear()
            self._total_requests = 0
            self._slow_requests = 0
            self._start_time = time.time()


# Global metrics collector instance
perf_metrics = PerformanceMetricsCollector()
