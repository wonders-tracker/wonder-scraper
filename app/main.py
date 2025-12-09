from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from app.core.config import settings
from app.api import auth, cards, portfolio, users, market, admin, blokpax, analytics, meta, billing, webhooks, watchlist
from contextlib import asynccontextmanager
from app.core.scheduler import start_scheduler
from app.core.anti_scraping import AntiScrapingMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    start_scheduler()
    yield
    # Shutdown (scheduler stops automatically usually or we can stop it)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set all CORS enabled origins
origins = [
    "http://localhost:5173", # Vite default
    "http://localhost:3000", # React default
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "https://wonderstracker.com", # Production
    "https://wonderstrader.com", # Production (Correction)
    "https://www.wonderstrader.com", # Production (WWW)
    settings.FRONTEND_URL, # Dynamic from env
]

# Clean up duplicates and empty strings
origins = list(set([o for o in origins if o]))

# CRITICAL: Add ProxyHeadersMiddleware FIRST to trust X-Forwarded-* headers from Railway
# This prevents FastAPI from redirecting HTTPS requests to HTTP
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Anti-scraping middleware - detects bots, headless browsers, rate limits
# Protects /api/v1/cards, /api/v1/market, /api/v1/blokpax endpoints
app.add_middleware(AntiScrapingMiddleware, enabled=True)

# GZip compression for responses > 1KB (80-90% bandwidth reduction)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
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

@app.get("/")
def root():
    return {"message": "Welcome to Wonder Scraper API"}
