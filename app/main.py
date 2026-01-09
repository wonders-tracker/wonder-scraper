import asyncio
import logging
import os
import resource
import sys
from contextlib import asynccontextmanager, suppress
from typing import Any, cast

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api import (
    admin,
    analytics,
    auth,
    billing,
    blog,
    blokpax,
    cards,
    market,
    meta,
    portfolio,
    price_alerts,
    users,
    watchlist,
    webhooks,
)
from app.api.billing import BILLING_AVAILABLE
from app.core.anti_scraping import AntiScrapingMiddleware
from app.core.config import settings
from app.core.saas import get_mode_info
from app.core.scheduler import start_scheduler
from app.middleware.metering import METERING_AVAILABLE, APIMeteringMiddleware
from app.middleware.timing import TimingMiddleware

logger = logging.getLogger(__name__)


def _current_rss_mb() -> float:
    """Best-effort current RSS in MiB without external dependencies."""
    try:
        with open("/proc/self/statm", "r", encoding="utf-8") as statm:
            parts = statm.readline().split()
            if len(parts) > 1:
                pages = int(parts[1])
                page_size = os.sysconf("SC_PAGE_SIZE")
                return pages * page_size / (1024 * 1024)
    except (OSError, ValueError):
        pass

    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = usage.ru_maxrss
    if sys.platform == "darwin":
        return rss / (1024 * 1024)
    return rss / 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Limit AnyIO worker threads so sync dependencies don't exhaust OS thread count.
    thread_limiter = anyio.to_thread.current_default_thread_limiter()  # type: ignore[attr-defined]
    original_tokens = thread_limiter.total_tokens
    max_workers = max(1, settings.THREADPOOL_MAX_WORKERS)
    if original_tokens != max_workers:
        logger.info(
            "Configuring AnyIO thread limiter: %s -> %s workers",
            original_tokens,
            max_workers,
        )
        thread_limiter.total_tokens = max_workers

    # Startup
    logger.info("=" * 50)
    logger.info("WondersTracker API Starting")
    logger.info(f"SaaS Features: {'ENABLED' if BILLING_AVAILABLE else 'DISABLED (OSS mode)'}")
    logger.info(f"Usage Metering: {'ENABLED' if METERING_AVAILABLE else 'DISABLED'}")
    logger.info("=" * 50)

    # Initialize Sentry error tracking (if configured)
    if settings.SENTRY_DSN:
        from app.core.errors import init_sentry

        init_sentry(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        )
    else:
        logger.info("Sentry disabled (SENTRY_DSN not set)")

    # CRITICAL: Aggressive Chrome cleanup on startup
    # Kills any orphan Chrome processes from previous crashes/restarts
    # This prevents resource exhaustion from zombie processes
    try:
        from app.scraper.browser import startup_cleanup_sync

        logger.info("Running startup Chrome cleanup...")
        cleanup_stats = startup_cleanup_sync()
        logger.info(
            f"Startup cleanup complete: killed {cleanup_stats['chrome_killed']} Chrome instances, "
            f"cleaned {cleanup_stats['profiles_cleaned']} profiles"
        )
        if cleanup_stats["errors"]:
            logger.warning(f"Cleanup errors (non-fatal): {cleanup_stats['errors']}")
    except Exception as e:
        logger.warning(f"Startup Chrome cleanup failed (non-fatal): {e}")

    # Register circuit breaker Discord notifications
    from app.core.circuit_breaker import set_notification_callback
    from app.discord_bot.logger import log_circuit_breaker_change

    set_notification_callback(log_circuit_breaker_change)
    logger.info("Circuit breaker Discord notifications enabled")

    if settings.RUN_SCHEDULER:
        start_scheduler()
    else:
        logger.info("RUN_SCHEDULER is false – skipping scheduler startup in this process.")

    memory_task = None
    if settings.MEMORY_LOG_INTERVAL_SECONDS > 0:
        interval = max(5, settings.MEMORY_LOG_INTERVAL_SECONDS)

        async def log_memory():
            while True:
                rss_mb = _current_rss_mb()
                logger.info("Process RSS: %.1f MiB", rss_mb)
                await asyncio.sleep(interval)

        memory_task = asyncio.create_task(log_memory())

    try:
        yield
    finally:
        # Graceful shutdown
        logger.info("Shutting down gracefully...")

        if memory_task:
            memory_task.cancel()
            with suppress(asyncio.CancelledError):
                await memory_task

        # Stop scheduler first to prevent new jobs
        if settings.RUN_SCHEDULER:
            from app.core.scheduler import scheduler

            if scheduler.running:
                logger.info("Stopping scheduler...")
                scheduler.shutdown(wait=False)

        # Clean up browser resources
        try:
            from app.scraper.browser import BrowserManager, kill_stale_chrome_processes

            logger.info("Closing browser...")
            await BrowserManager.close()
            # Give time for graceful close, then force kill orphans
            await asyncio.sleep(2)
            await kill_stale_chrome_processes()
            logger.info("Browser cleanup complete")
        except Exception as e:
            logger.warning(f"Browser cleanup error: {e}")

        logger.info("Shutdown complete")


app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json", lifespan=lifespan)

# Set all CORS enabled origins
origins = [
    "http://localhost:5173",  # Vite default
    "http://localhost:3000",  # React default
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "https://wonderstracker.com",  # Production
    "https://wonderstrader.com",  # Production (Correction)
    "https://www.wonderstrader.com",  # Production (WWW)
    settings.FRONTEND_URL,  # Dynamic from env
]

# Clean up duplicates and empty strings
origins = list(set([o for o in origins if o]))

# Middleware order matters! They execute in REVERSE order of addition.
# So the LAST added middleware executes FIRST on the request.
# Order: CORS -> Proxy -> GZip -> Context -> Metering -> AntiScraping -> Timing

# Timing middleware - measures request duration and records performance metrics
# Added first (runs last on request, first on response) to capture total time
app.add_middleware(cast(Any, TimingMiddleware))

# Anti-scraping middleware - detects bots, headless browsers, rate limits
# Protects /api/v1/cards, /api/v1/market, /api/v1/blokpax endpoints
app.add_middleware(cast(Any, AntiScrapingMiddleware), enabled=True)

# Request context middleware - adds request_id and correlation_id for tracing
from app.middleware.context import RequestContextMiddleware

app.add_middleware(cast(Any, RequestContextMiddleware))

# API metering middleware - tracks usage for billing (only when SaaS enabled)
# This is a no-op pass-through when saas/ module is not available
app.add_middleware(cast(Any, APIMeteringMiddleware))

# GZip compression for responses > 1KB (80-90% bandwidth reduction)
app.add_middleware(cast(Any, GZipMiddleware), minimum_size=1000)

# ProxyHeadersMiddleware to trust X-Forwarded-* headers from Railway
# This prevents FastAPI from redirecting HTTPS requests to HTTP
app.add_middleware(cast(Any, ProxyHeadersMiddleware), trusted_hosts=["*"])

# CORS middleware LAST (so it runs FIRST) to handle preflight OPTIONS requests
# before any other middleware can reject them
app.add_middleware(
    cast(Any, CORSMiddleware),
    allow_origins=origins,
    allow_credentials=True,
    # Explicitly list allowed methods instead of ["*"] for security
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    # Explicitly list allowed headers for security
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-API-Key",
        "X-CSRF-Token",
    ],
    expose_headers=["X-Bot-Warning", "X-Automation-Warning", "X-Request-ID", "X-Correlation-ID"],
)

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(cards.router, prefix=f"{settings.API_V1_STR}/cards", tags=["cards"])
app.include_router(meta.router, prefix=f"{settings.API_V1_STR}/cards", tags=["meta"])  # /cards/{id}/meta
app.include_router(portfolio.router, prefix=f"{settings.API_V1_STR}/portfolio", tags=["portfolio"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(market.router, prefix=f"{settings.API_V1_STR}/market", tags=["market"])
app.include_router(admin.router, prefix=f"{settings.API_V1_STR}/admin", tags=["admin"])
app.include_router(blokpax.router, prefix=f"{settings.API_V1_STR}/blokpax", tags=["blokpax"])
app.include_router(analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"])
app.include_router(billing.router, prefix=settings.API_V1_STR, tags=["billing"])
app.include_router(webhooks.router, prefix=settings.API_V1_STR, tags=["webhooks"])
app.include_router(watchlist.router, prefix=f"{settings.API_V1_STR}/watchlist", tags=["watchlist"])
app.include_router(blog.router, prefix=f"{settings.API_V1_STR}/blog", tags=["blog"])
app.include_router(price_alerts.router, prefix=f"{settings.API_V1_STR}/price-alerts", tags=["price-alerts"])


@app.get("/")
def root():
    return {"message": "Welcome to Wonder Scraper API"}


@app.get("/health")
def health():
    """Basic health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/detailed")
def health_detailed() -> dict:
    """
    Detailed health check for monitoring services.

    Checks:
    - Database connectivity
    - Last scrape times
    - Scheduler status
    - Memory usage

    Returns 200 if core systems healthy, 503 if critical issues.
    """
    from datetime import datetime, timedelta, timezone
    from typing import Any

    from sqlalchemy import func, text
    from sqlmodel import Session, select

    from app.core.scheduler import scheduler
    from app.db import USING_NEON_POOLER, engine
    from app.models.market import MarketPrice

    health_status: dict[str, Any] = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
    }

    # Check database connectivity
    try:
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
        health_status["checks"]["database"] = {
            "status": "healthy",
            "pooler": USING_NEON_POOLER,
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)[:100],
        }

    # Check last scrape times
    try:
        with Session(engine) as session:
            now = datetime.now(timezone.utc)

            # Last sold scrape
            last_sold = session.execute(
                select(func.max(MarketPrice.scraped_at)).where(MarketPrice.listing_type == "sold")
            ).scalar()

            # Last active scrape
            last_active = session.execute(
                select(func.max(MarketPrice.scraped_at)).where(MarketPrice.listing_type == "active")
            ).scalar()

            # Count in last 24h
            cutoff = now - timedelta(hours=24)
            sold_24h = (
                session.execute(
                    select(func.count(MarketPrice.id)).where(
                        MarketPrice.listing_type == "sold",
                        MarketPrice.scraped_at >= cutoff,
                    )
                ).scalar()
                or 0
            )

            sold_age_hours = (now - last_sold).total_seconds() / 3600 if last_sold else None
            active_age_hours = (now - last_active).total_seconds() / 3600 if last_active else None

            scraper_status = "healthy"
            if sold_age_hours and sold_age_hours > 2:
                scraper_status = "degraded"
            if sold_age_hours and sold_age_hours > 6:
                scraper_status = "unhealthy"

            health_status["checks"]["scraper"] = {
                "status": scraper_status,
                "last_sold_scrape_hours_ago": round(sold_age_hours, 1) if sold_age_hours else None,
                "last_active_scrape_hours_ago": round(active_age_hours, 1) if active_age_hours else None,
                "sold_listings_24h": sold_24h,
            }

            if scraper_status == "unhealthy":
                health_status["status"] = "degraded"

    except Exception as e:
        health_status["checks"]["scraper"] = {
            "status": "unknown",
            "error": str(e)[:100],
        }

    # Check scheduler
    try:
        if scheduler.running:
            jobs = scheduler.get_jobs()
            health_status["checks"]["scheduler"] = {
                "status": "healthy",
                "running": True,
                "job_count": len(jobs),
            }
        else:
            health_status["checks"]["scheduler"] = {
                "status": "stopped",
                "running": False,
                "note": "Scheduler may be running in separate worker process",
            }
    except Exception as e:
        health_status["checks"]["scheduler"] = {
            "status": "unknown",
            "error": str(e)[:100],
        }

    # Memory usage
    try:
        rss_mb = _current_rss_mb()
        health_status["checks"]["memory"] = {
            "rss_mb": round(rss_mb, 1),
        }
    except (OSError, ValueError, AttributeError):
        # Memory measurement can fail on some platforms - safe to ignore
        pass

    # Chrome process count - helps diagnose resource exhaustion
    try:
        from app.scraper.browser import get_chrome_process_count

        chrome_count = get_chrome_process_count()
        # Warn if too many Chrome processes (indicates leak or zombie accumulation)
        chrome_status = "healthy" if chrome_count <= 2 else "warning" if chrome_count <= 5 else "critical"
        health_status["checks"]["chrome"] = {
            "status": chrome_status,
            "process_count": chrome_count,
        }
        if chrome_status == "critical":
            health_status["status"] = "degraded"
    except Exception:
        # Chrome monitoring is optional - safe to ignore failures
        pass

    return health_status


@app.get("/health/mode")
def health_mode():
    """
    Get detailed information about the application mode.

    Useful for verifying deployment configuration.
    Returns whether running in SaaS or OSS mode and feature availability.
    """
    return get_mode_info()


@app.get("/health/metrics")
def health_metrics():
    """
    Get scraper job metrics.

    Returns metrics for recent scrape jobs including:
    - Last run timestamps
    - Success/failure counts
    - DB error counts
    - Success rates
    """
    from app.core.metrics import scraper_metrics

    return {
        "summary": scraper_metrics.get_summary(),
        "jobs": scraper_metrics.get_all_metrics(),
    }


@app.get("/health/circuits")
def health_circuits():
    """
    Get current state of all circuit breakers.

    Returns the state of each circuit breaker including:
    - state: closed (healthy), open (failing), or half_open (recovering)
    - failure_count: current consecutive failures
    - failure_threshold: failures before circuit opens
    - recovery_timeout: seconds before attempting recovery
    - all_healthy: true if all circuits are closed
    """
    from app.core.circuit_breaker import CircuitBreakerRegistry

    states = CircuitBreakerRegistry.get_all_states()

    # Add more detail for each breaker
    breakers_info = {}
    for name, state in states.items():
        breaker = CircuitBreakerRegistry.get(name)
        breakers_info[name] = {
            "state": state,
            "failure_count": breaker._failure_count,
            "failure_threshold": breaker.failure_threshold,
            "recovery_timeout": breaker.recovery_timeout,
        }

    return {
        "circuits": breakers_info,
        "all_healthy": all(s == "closed" for s in states.values()),
    }


@app.get("/health/unified")
def health_unified():
    """
    Unified health check with threshold-based alerting.

    Aggregates health from all subsystems:
    - scraper: Data freshness, job success rates
    - performance: API latency, slow request rate
    - circuits: Circuit breaker states
    - database: Connection health
    - queue: Task queue depth (if enabled)

    Returns:
    - status: "ok", "warning", or "critical"
    - components: Per-component health details
    - timestamp: Check time

    HTTP 200 for ok/warning, 503 for critical.
    """
    from fastapi.responses import JSONResponse
    from app.core.health_check import HealthCheck

    health = HealthCheck.check_overall_health()

    # Return 503 for critical status (for load balancers)
    status_code = 503 if health["status"] == "critical" else 200

    return JSONResponse(content=health, status_code=status_code)


@app.get("/health/performance")
def health_performance():
    """
    Get API performance metrics.

    Returns:
    - summary: Overall performance stats (total requests, slow %, uptime)
    - slowest_endpoints: Top 10 slowest endpoints by p95 response time
    - all_endpoints: Detailed metrics for every tracked endpoint

    Metrics per endpoint include:
    - request_count: Total requests to this endpoint
    - slow_request_count: Requests exceeding 500ms threshold
    - p50_ms, p95_ms, p99_ms: Response time percentiles
    - avg_ms, min_ms, max_ms: Basic statistics

    Note: Metrics reset on server restart.
    """
    from app.core.perf_metrics import perf_metrics

    return {
        "summary": perf_metrics.get_summary(),
        "slowest_endpoints": perf_metrics.get_slowest_endpoints(n=10, by="p95"),
        "all_endpoints": perf_metrics.get_all_metrics(),
    }
