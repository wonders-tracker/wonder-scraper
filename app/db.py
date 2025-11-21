from sqlmodel import create_engine, SQLModel, Session
import os
from dotenv import load_dotenv

load_dotenv()

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
# Add connection pooling for better performance
engine = create_engine(
    DATABASE_URL, 
    echo=False,  # Disable query logging in production
    pool_size=10,  # Connection pool
    max_overflow=20,  # Allow burst connections
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections every hour
)

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

