import asyncio
import logging
import os
import resource
import sys
from typing import Any, cast
import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.core.config import settings
from app.api import (
    auth,
    cards,
    portfolio,
    users,
    market,
    admin,
    blokpax,
    analytics,
    meta,
    billing,
    webhooks,
    watchlist,
    blog,
)
from app.api.billing import BILLING_AVAILABLE
from app.middleware.metering import APIMeteringMiddleware, METERING_AVAILABLE
from app.core.saas import get_mode_info
from contextlib import asynccontextmanager, suppress
from app.core.scheduler import start_scheduler
from app.core.anti_scraping import AntiScrapingMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

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
        if memory_task:
            memory_task.cancel()
            with suppress(asyncio.CancelledError):
                await memory_task
    # Shutdown (scheduler stops automatically usually or we can stop it)


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

# CRITICAL: Add ProxyHeadersMiddleware FIRST to trust X-Forwarded-* headers from Railway
# This prevents FastAPI from redirecting HTTPS requests to HTTP
app.add_middleware(cast(Any, ProxyHeadersMiddleware), trusted_hosts=["*"])

# Anti-scraping middleware - detects bots, headless browsers, rate limits
# Protects /api/v1/cards, /api/v1/market, /api/v1/blokpax endpoints
app.add_middleware(cast(Any, AntiScrapingMiddleware), enabled=True)

# API metering middleware - tracks usage for billing (only when SaaS enabled)
# This is a no-op pass-through when saas/ module is not available
app.add_middleware(cast(Any, APIMeteringMiddleware))

# GZip compression for responses > 1KB (80-90% bandwidth reduction)
app.add_middleware(cast(Any, GZipMiddleware), minimum_size=1000)

app.add_middleware(
    cast(Any, CORSMiddleware),
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Bot-Warning", "X-Automation-Warning"],  # Expose warning headers
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


@app.get("/")
def root():
    return {"message": "Welcome to Wonder Scraper API"}


@app.get("/health")
def health():
    """Basic health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/mode")
def health_mode():
    """
    Get detailed information about the application mode.

    Useful for verifying deployment configuration.
    Returns whether running in SaaS or OSS mode and feature availability.
    """
    return get_mode_info()
