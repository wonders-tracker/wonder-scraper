from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import auth, cards, portfolio, users, market
from contextlib import asynccontextmanager
from app.core.scheduler import start_scheduler

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(cards.router, prefix=f"{settings.API_V1_STR}/cards", tags=["cards"])
app.include_router(portfolio.router, prefix=f"{settings.API_V1_STR}/portfolio", tags=["portfolio"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(market.router, prefix=f"{settings.API_V1_STR}/market", tags=["market"])

@app.get("/")
def root():
    return {"message": "Welcome to Wonder Scraper API"}
