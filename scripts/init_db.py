from app.db import create_db_and_tables
from app.models import *  # Import all models to ensure they are registered with SQLModel

if __name__ == "__main__":
    print("Creating tables in Neon DB...")
    try:
        create_db_and_tables()
        print("Tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")
