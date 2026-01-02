from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy import event
from sqlalchemy.engine import Engine
from urllib.parse import urlparse
import os
import logging
from dotenv import load_dotenv
from app.core.config import settings

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback construction if DATABASE_URL is missing (though it should be there)
    host = os.getenv("PGHOST")
    db = os.getenv("PGDATABASE")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")
    ssl_mode = os.getenv("PGSSLMODE", "require")

    DATABASE_URL = f"postgresql://{user}:{password}@{host}/{db}?sslmode={ssl_mode}"


def _is_neon_pooler(url: str) -> bool:
    """Check if using Neon's connection pooler (pgBouncer)."""
    try:
        parsed = urlparse(url)
        return parsed.hostname is not None and "-pooler" in parsed.hostname
    except Exception:
        return False


# Detect if using Neon pooler for optimized settings
USING_NEON_POOLER = _is_neon_pooler(DATABASE_URL)

# When using Neon pooler (pgBouncer), we need different settings:
# - Smaller local pool (pooler handles connection reuse)
# - Shorter recycle time (pooler manages long-lived connections)
# - Can use more aggressive keepalives
if USING_NEON_POOLER:
    _pool_size = min(settings.DB_POOL_SIZE, 5)  # Smaller local pool with external pooler
    _max_overflow = min(settings.DB_MAX_OVERFLOW, 3)
    _pool_recycle = 180  # 3 min - pooler handles persistence
    logger.info("Using Neon Pooler - optimized connection settings")
else:
    _pool_size = settings.DB_POOL_SIZE
    _max_overflow = settings.DB_MAX_OVERFLOW
    _pool_recycle = 300  # 5 min for direct connections
    logger.info("Using direct Neon connection (consider enabling pooler for stability)")

# Neon requires sslmode=require
# Add connection pooling for better performance with Neon serverless
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Disable query logging in production
    pool_size=_pool_size,
    max_overflow=_max_overflow,
    pool_pre_ping=True,  # Verify connections before use - critical for Neon
    pool_recycle=_pool_recycle,
    pool_timeout=30,  # Wait up to 30s for a connection
    connect_args={
        "connect_timeout": 10,  # Connection timeout
        "keepalives": 1,  # Enable TCP keepalives
        "keepalives_idle": 30,  # Send keepalive after 30s idle
        "keepalives_interval": 10,  # Retry keepalive every 10s
        "keepalives_count": 5,  # Drop connection after 5 failed keepalives
        # Note: statement_timeout set via event listener below (Neon pooler doesn't support it in options)
    },
)


# Database security: Set statement timeout and restrict dangerous operations
@event.listens_for(Engine, "connect")
def set_database_security(dbapi_connection, connection_record):
    """Set security-related connection parameters."""
    cursor = dbapi_connection.cursor()
    try:
        # Set statement timeout (30 seconds max query time)
        cursor.execute("SET statement_timeout = '30s'")
        # Prevent accidental table drops/truncates from app
        # Note: This requires database-level role restrictions
        # For app-level, we rely on SQLAlchemy's parameterized queries
    except Exception as e:
        logger.warning(f"Could not set database security parameters: {e}")
    finally:
        cursor.close()


def get_session():
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
