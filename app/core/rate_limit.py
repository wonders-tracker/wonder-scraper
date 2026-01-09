"""
Simple in-memory rate limiter for authentication endpoints.
Protects against brute force and credential stuffing attacks.
"""

import asyncio
import time
from collections import deque
from functools import wraps
from typing import Callable, Deque, Dict, Tuple

from cachetools import TTLCache
from fastapi import HTTPException, Request, status

# Maximum IPs to track (bounds memory usage)
MAX_TRACKED_IPS = 10000
# TTL for request tracking (1 hour)
REQUEST_TTL_SECONDS = 3600
# TTL for lockouts (1 hour max)
LOCKOUT_TTL_SECONDS = 3600
# Max requests per IP to track
MAX_REQUESTS_PER_IP = 100


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.
    Uses TTLCache to prevent unbounded memory growth.
    For production with multiple workers, use Redis-based solution.
    """

    def __init__(self):
        # {ip: deque([(timestamp, count), ...])} - bounded per IP
        self._requests: TTLCache[str, Deque[Tuple[float, int]]] = TTLCache(
            maxsize=MAX_TRACKED_IPS, ttl=REQUEST_TTL_SECONDS
        )
        # {ip: lockout_until_timestamp} - auto-expires
        self._lockouts: TTLCache[str, float] = TTLCache(maxsize=MAX_TRACKED_IPS, ttl=LOCKOUT_TTL_SECONDS)
        # {ip: failed_attempts} - auto-expires
        self._failed_attempts: TTLCache[str, int] = TTLCache(maxsize=MAX_TRACKED_IPS, ttl=REQUEST_TTL_SECONDS)

    def _get_requests(self, ip: str) -> Deque[Tuple[float, int]]:
        """Get or create request deque for IP."""
        if ip not in self._requests:
            self._requests[ip] = deque(maxlen=MAX_REQUESTS_PER_IP)
        return self._requests[ip]

    def _cleanup_old_requests(self, ip: str, window_seconds: int):
        """Remove requests older than the window."""
        if ip not in self._requests:
            return
        cutoff = time.time() - window_seconds
        requests = self._requests[ip]
        # Remove from left (oldest) while older than cutoff
        while requests and requests[0][0] <= cutoff:
            requests.popleft()

    def is_rate_limited(self, ip: str, max_requests: int = 10, window_seconds: int = 60) -> Tuple[bool, int]:
        """
        Check if IP is rate limited.
        Returns (is_limited, retry_after_seconds)
        """
        now = time.time()

        # Check if IP is locked out (TTLCache auto-expires, but check timestamp too)
        if ip in self._lockouts:
            lockout_until = self._lockouts[ip]
            if now < lockout_until:
                return True, int(lockout_until - now)
            else:
                # Lockout expired, remove it
                try:
                    del self._lockouts[ip]
                except KeyError:
                    pass  # Already expired/removed
                try:
                    del self._failed_attempts[ip]
                except KeyError:
                    pass

        # Cleanup old requests
        self._cleanup_old_requests(ip, window_seconds)

        # Count requests in window
        requests = self._get_requests(ip)
        total_requests = sum(count for _, count in requests)

        if total_requests >= max_requests:
            return True, window_seconds

        return False, 0

    def record_request(self, ip: str):
        """Record a request from an IP."""
        now = time.time()
        requests = self._get_requests(ip)
        requests.append((now, 1))

    def record_failed_login(self, ip: str, lockout_threshold: int = 5, lockout_seconds: int = 300):
        """
        Record a failed login attempt.
        After threshold failures, lock out the IP.
        """
        # Get current count or 0, then increment
        current = self._failed_attempts.get(ip, 0)
        self._failed_attempts[ip] = current + 1

        if self._failed_attempts[ip] >= lockout_threshold:
            self._lockouts[ip] = time.time() + lockout_seconds
            return True, lockout_seconds

        remaining = lockout_threshold - self._failed_attempts[ip]
        return False, remaining

    def record_successful_login(self, ip: str):
        """Reset failed attempts on successful login."""
        try:
            del self._failed_attempts[ip]
        except KeyError:
            pass
        try:
            del self._lockouts[ip]
        except KeyError:
            pass

    def clear(self):
        """Clear all rate limiting state. Used for testing."""
        self._requests.clear()
        self._lockouts.clear()
        self._failed_attempts.clear()

    def get_stats(self) -> Dict[str, int]:
        """Get rate limiter stats for monitoring."""
        return {
            "tracked_ips": len(self._requests),
            "active_lockouts": len(self._lockouts),
            "tracked_failures": len(self._failed_attempts),
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_client_ip(request: Request, trust_proxy_headers: bool = True) -> str:
    """
    Extract client IP, handling proxies securely.

    Args:
        request: FastAPI request object
        trust_proxy_headers: If True, trust X-Forwarded-For headers.
            Only set True when behind a trusted proxy (Railway, Vercel, etc.)
            In production, this should be controlled by config.

    Security: Only trust proxy headers when deployed behind known infrastructure.
    Spoofed X-Forwarded-For can bypass rate limiting if trusted incorrectly.
    """
    # Only trust proxy headers when configured (behind Railway/Vercel)
    if trust_proxy_headers:
        # Check X-Forwarded-For header (set by Railway/proxies)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP in the list is the client
            # Note: Attacker can prepend fake IPs, but last IP is from proxy
            # Railway/Vercel set this correctly at the edge
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

    # Fallback to direct client - always trustworthy
    if request.client:
        return request.client.host

    return "unknown"


def rate_limit(
    max_requests: int = 10, window_seconds: int = 60, error_message: str = "Too many requests. Please try again later."
):
    """
    Rate limiting decorator for FastAPI endpoints.

    Args:
        max_requests: Maximum requests allowed in the window
        window_seconds: Time window in seconds
        error_message: Error message to return when rate limited
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, request: Request | None = None, **kwargs):
            # Find request in args or kwargs
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                # Can't rate limit without request, proceed
                return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

            ip = get_client_ip(request)
            is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests, window_seconds)

            if is_limited:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error_message,
                    headers={"Retry-After": str(retry_after)},
                )

            rate_limiter.record_request(ip)

            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator
