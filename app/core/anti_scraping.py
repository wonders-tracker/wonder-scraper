"""
Anti-scraping middleware and utilities.
Detects bots, headless browsers, and enforces rate limits.
"""

import time
import re
import hashlib
from collections import defaultdict
from typing import Tuple, Dict, Set
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AntiScrapingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and block scraping attempts.

    Features:
    - Headless browser detection
    - Bot User-Agent blocking
    - Rate limiting per IP
    - Burst detection (too many requests too fast)
    - Missing header detection
    - Fingerprint tracking
    """

    # Paths that require protection (data endpoints)
    PROTECTED_PATHS = [
        "/api/v1/cards",
        "/api/v1/market",
        "/api/v1/blokpax",
    ]

    # Paths to always allow (auth, static, health)
    ALLOWED_PATHS = [
        "/api/v1/auth",
        "/api/v1/portfolio",  # Already requires auth
        "/api/v1/admin",  # Already requires superuser
        "/api/v1/users",  # User management
        "/api/v1/analytics",  # Analytics tracking
        "/api/v1/billing",  # Billing endpoints
        "/api/v1/webhooks",  # Webhook endpoints
        "/",
        "/docs",
        "/openapi.json",
        "/health",
        "/healthz",
        "/ready",
    ]

    # IPs to never block (localhost, internal)
    TRUSTED_IPS = [
        "127.0.0.1",
        "localhost",
        "::1",
    ]

    # Known bot/scraper User-Agents (case-insensitive patterns)
    BOT_PATTERNS = [
        r"bot",
        r"crawl",
        r"spider",
        r"scrape",
        r"wget",
        r"curl",
        r"python-requests",
        r"python-urllib",
        r"java/",
        r"httpclient",
        r"libwww",
        r"httpunit",
        r"nutch",
        r"phpcrawl",
        r"msnbot",
        r"slurp",
        r"baiduspider",
        r"semrush",
        r"ahrefs",
        r"dotbot",
        r"petalbot",
        r"bytespider",
        r"gptbot",
        r"ccbot",
        r"facebookexternalhit",  # Allow if needed for sharing
        r"twitterbot",  # Allow if needed for sharing
    ]

    # Headless browser indicators
    HEADLESS_INDICATORS = [
        r"headless",
        r"phantomjs",
        r"nightmare",
        r"puppeteer",
        r"playwright",
        r"selenium",
        r"webdriver",
        r"chromedriver",
        r"geckodriver",
    ]

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

        # Rate limiting storage (in-memory, use Redis for multi-worker)
        self._requests: Dict[str, list] = defaultdict(list)  # {ip: [(timestamp, path), ...]}
        self._blocked_ips: Dict[str, float] = {}  # {ip: blocked_until_timestamp}
        self._fingerprints: Dict[str, Set[str]] = defaultdict(set)  # {ip: {fingerprint1, ...}}
        self._suspicious_ips: Dict[str, int] = defaultdict(int)  # {ip: violation_count}

        # Compile patterns
        self._bot_pattern = re.compile("|".join(self.BOT_PATTERNS), re.IGNORECASE)
        self._headless_pattern = re.compile("|".join(self.HEADLESS_INDICATORS), re.IGNORECASE)

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP from headers."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        if request.client:
            return request.client.host
        return "unknown"

    def _get_fingerprint(self, request: Request) -> str:
        """Generate a fingerprint from request characteristics."""
        components = [
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.headers.get("accept-encoding", ""),
            request.headers.get("accept", ""),
            # Don't include IP - fingerprint should identify the browser, not location
        ]
        fingerprint_str = "|".join(components)
        return hashlib.md5(fingerprint_str.encode()).hexdigest()[:16]

    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires protection."""
        # Check allowed paths first (exact match for "/" root)
        for allowed in self.ALLOWED_PATHS:
            if allowed == "/":
                if path == "/":
                    return False
            elif path.startswith(allowed):
                return False

        # Check protected paths
        for protected in self.PROTECTED_PATHS:
            if path.startswith(protected):
                return True

        return False

    def _is_bot_user_agent(self, user_agent: str) -> bool:
        """Check if User-Agent matches known bot patterns."""
        if not user_agent:
            return True  # No UA is suspicious
        return bool(self._bot_pattern.search(user_agent))

    def _is_headless_browser(self, request: Request) -> Tuple[bool, str]:
        """
        Detect headless browsers and automation tools.
        Returns (is_headless, reason).
        """
        user_agent = request.headers.get("user-agent", "")

        # Check UA for headless indicators
        if self._headless_pattern.search(user_agent):
            return True, "headless_ua"

        # Check for webdriver header (Selenium sets this)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            # This alone isn't suspicious, but combined with other signals...
            pass

        # Check for missing common browser headers
        # Real browsers always send these
        required_headers = ["accept", "accept-language", "accept-encoding"]
        missing_headers = [h for h in required_headers if not request.headers.get(h)]

        if len(missing_headers) >= 2:
            return True, f"missing_headers:{','.join(missing_headers)}"

        # Check for suspicious Accept header (bots often use */*)
        accept = request.headers.get("accept", "")
        if accept == "*/*" and "Mozilla" in user_agent:
            # Real browsers don't send Accept: */* alone
            return True, "suspicious_accept"

        # Chrome headless detection
        if "HeadlessChrome" in user_agent:
            return True, "headless_chrome"

        # Firefox headless (harder to detect, but sometimes has tells)
        if "Firefox" in user_agent and not request.headers.get("accept-language"):
            return True, "headless_firefox"

        return False, ""

    def _check_rate_limit(self, ip: str, path: str) -> Tuple[bool, int]:
        """
        Check rate limits. Returns (is_limited, retry_after_seconds).

        Limits:
        - 60 requests per minute per IP
        - 10 requests per 5 seconds (burst protection)
        """
        now = time.time()

        # Check if IP is blocked
        if ip in self._blocked_ips:
            if now < self._blocked_ips[ip]:
                return True, int(self._blocked_ips[ip] - now)
            else:
                del self._blocked_ips[ip]

        # Clean old requests (older than 1 minute)
        self._requests[ip] = [(ts, p) for ts, p in self._requests[ip] if now - ts < 60]

        requests_list = self._requests[ip]

        # Check per-minute limit (60 req/min)
        if len(requests_list) >= 60:
            return True, 60

        # Check burst limit (10 req/5sec)
        recent_requests = [ts for ts, p in requests_list if now - ts < 5]
        if len(recent_requests) >= 10:
            return True, 5

        return False, 0

    def _record_request(self, ip: str, path: str):
        """Record a request for rate limiting."""
        self._requests[ip].append((time.time(), path))

    def _record_violation(self, ip: str, reason: str, block_seconds: int = 300):
        """Record a violation and potentially block the IP."""
        self._suspicious_ips[ip] += 1

        # Block after 3 violations
        if self._suspicious_ips[ip] >= 3:
            self._blocked_ips[ip] = time.time() + block_seconds
            return True
        return False

    def clear(self):
        """Clear all rate limiting state. Used for testing."""
        self._requests.clear()
        self._blocked_ips.clear()
        self._fingerprints.clear()
        self._suspicious_ips.clear()

    def unblock_ip(self, ip: str) -> bool:
        """Manually unblock an IP address."""
        if ip in self._blocked_ips:
            del self._blocked_ips[ip]
        if ip in self._suspicious_ips:
            del self._suspicious_ips[ip]
        return True

    def get_blocked_ips(self) -> Dict[str, float]:
        """Get list of currently blocked IPs."""
        now = time.time()
        # Return only IPs that are still blocked
        return {ip: until for ip, until in self._blocked_ips.items() if until > now}

    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch."""
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        # Skip non-protected paths
        if not self._is_protected_path(path):
            return await call_next(request)

        ip = self._get_client_ip(request)

        # Skip for trusted IPs (localhost, internal services)
        if ip in self.TRUSTED_IPS or ip.startswith("10.") or ip.startswith("172.") or ip.startswith("192.168."):
            return await call_next(request)

        # Skip rate limiting for authenticated users
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)
        user_agent = request.headers.get("user-agent", "")

        # 1. Check if IP is blocked
        if ip in self._blocked_ips and time.time() < self._blocked_ips[ip]:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Access temporarily blocked due to suspicious activity."},
            )

        # 2. Check rate limits
        is_limited, retry_after = self._check_rate_limit(ip, path)
        if is_limited:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please slow down."},
                headers={"Retry-After": str(retry_after)},
            )

        # 3. Detect bots
        if self._is_bot_user_agent(user_agent):
            # Allow some bots for SEO, but rate limit heavily
            # For now, just log and allow with warning header
            response = await call_next(request)
            response.headers["X-Bot-Warning"] = "Automated access detected"
            self._record_request(ip, path)
            return response

        # 4. Detect headless browsers
        is_headless, reason = self._is_headless_browser(request)
        if is_headless:
            blocked = self._record_violation(ip, reason)
            if blocked:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Automated browser access is not permitted."},
                )
            # First couple violations: allow but warn
            response = await call_next(request)
            response.headers["X-Automation-Warning"] = "Suspicious browser detected"
            self._record_request(ip, path)
            return response

        # 5. Track fingerprints (detect rotating IPs with same fingerprint)
        fingerprint = self._get_fingerprint(request)
        self._fingerprints[ip].add(fingerprint)

        # If IP has many fingerprints, it's suspicious (but not blocked)
        # This could indicate proxy rotation

        # 6. All checks passed - proceed
        self._record_request(ip, path)
        return await call_next(request)


# Rate limiter for API key validation
class APIKeyRateLimiter:
    """Rate limiter specifically for API key-based access."""

    def __init__(self):
        self._minute_requests: Dict[str, list] = defaultdict(list)  # {key_hash: [timestamps]}
        self._day_requests: Dict[str, int] = defaultdict(int)  # {key_hash: count}
        self._day_reset: Dict[str, float] = {}  # {key_hash: reset_timestamp}

    def check_limit(self, key_hash: str, per_minute: int = 60, per_day: int = 10000) -> Tuple[bool, str]:
        """
        Check if API key is within rate limits.
        Returns (allowed, reason).
        """
        now = time.time()

        # Check daily reset
        if key_hash in self._day_reset:
            if now > self._day_reset[key_hash]:
                self._day_requests[key_hash] = 0
                self._day_reset[key_hash] = now + 86400
        else:
            self._day_reset[key_hash] = now + 86400

        # Check daily limit
        if self._day_requests[key_hash] >= per_day:
            return False, "daily_limit"

        # Clean minute requests
        self._minute_requests[key_hash] = [ts for ts in self._minute_requests[key_hash] if now - ts < 60]

        # Check per-minute limit
        if len(self._minute_requests[key_hash]) >= per_minute:
            return False, "minute_limit"

        return True, ""

    def record_request(self, key_hash: str):
        """Record a request for an API key."""
        self._minute_requests[key_hash].append(time.time())
        self._day_requests[key_hash] += 1


# Global instances
api_key_limiter = APIKeyRateLimiter()
