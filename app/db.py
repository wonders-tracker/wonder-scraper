from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy import event
from sqlalchemy.engine import Engine
import os
import logging
from dotenv import load_dotenv

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

# Neon requires sslmode=require
# Add connection pooling for better performance with Neon serverless
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Disable query logging in production
    pool_size=5,  # Smaller pool for serverless (Neon has own pooler)
    max_overflow=10,  # Allow burst connections
    pool_pre_ping=True,  # Verify connections before use - critical for Neon
    pool_recycle=300,  # Recycle connections every 5 min (Neon drops idle connections)
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
