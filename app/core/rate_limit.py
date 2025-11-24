"""
Simple in-memory rate limiter for authentication endpoints.
Protects against brute force and credential stuffing attacks.
"""
import time
from collections import defaultdict
from functools import wraps
from typing import Callable, Dict, Tuple
from fastapi import HTTPException, Request, status


class RateLimiter:
    """
    In-memory rate limiter using sliding window algorithm.
    For production with multiple workers, use Redis-based solution.
    """

    def __init__(self):
        # {ip: [(timestamp, count), ...]}
        self._requests: Dict[str, list] = defaultdict(list)
        # {ip: lockout_until_timestamp}
        self._lockouts: Dict[str, float] = {}
        # {ip: failed_attempts}
        self._failed_attempts: Dict[str, int] = defaultdict(int)

    def _cleanup_old_requests(self, ip: str, window_seconds: int):
        """Remove requests older than the window."""
        cutoff = time.time() - window_seconds
        self._requests[ip] = [
            (ts, count) for ts, count in self._requests[ip]
            if ts > cutoff
        ]

    def is_rate_limited(
        self,
        ip: str,
        max_requests: int = 10,
        window_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Check if IP is rate limited.
        Returns (is_limited, retry_after_seconds)
        """
        now = time.time()

        # Check if IP is locked out
        if ip in self._lockouts:
            lockout_until = self._lockouts[ip]
            if now < lockout_until:
                return True, int(lockout_until - now)
            else:
                # Lockout expired
                del self._lockouts[ip]
                self._failed_attempts[ip] = 0

        # Cleanup old requests
        self._cleanup_old_requests(ip, window_seconds)

        # Count requests in window
        total_requests = sum(count for _, count in self._requests[ip])

        if total_requests >= max_requests:
            return True, window_seconds

        return False, 0

    def record_request(self, ip: str):
        """Record a request from an IP."""
        now = time.time()
        self._requests[ip].append((now, 1))

    def record_failed_login(self, ip: str, lockout_threshold: int = 5, lockout_seconds: int = 300):
        """
        Record a failed login attempt.
        After threshold failures, lock out the IP.
        """
        self._failed_attempts[ip] += 1

        if self._failed_attempts[ip] >= lockout_threshold:
            self._lockouts[ip] = time.time() + lockout_seconds
            return True, lockout_seconds

        remaining = lockout_threshold - self._failed_attempts[ip]
        return False, remaining

    def record_successful_login(self, ip: str):
        """Reset failed attempts on successful login."""
        if ip in self._failed_attempts:
            del self._failed_attempts[ip]
        if ip in self._lockouts:
            del self._lockouts[ip]


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_client_ip(request: Request) -> str:
    """Extract client IP, handling proxies."""
    # Check X-Forwarded-For header (set by Railway/proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in the list is the client
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client
    if request.client:
        return request.client.host

    return "unknown"


def rate_limit(
    max_requests: int = 10,
    window_seconds: int = 60,
    error_message: str = "Too many requests. Please try again later."
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
        async def wrapper(*args, request: Request = None, **kwargs):
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
            is_limited, retry_after = rate_limiter.is_rate_limited(
                ip, max_requests, window_seconds
            )

            if is_limited:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error_message,
                    headers={"Retry-After": str(retry_after)}
                )

            rate_limiter.record_request(ip)

            import asyncio
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        return wrapper
    return decorator
