from sqlmodel import Session, text
from app.db import engine

def migrate_models():
    with Session(engine) as session:
        print("Migrating database schema...")
        
        # 1. Update User table
        try:
            print("Checking 'user' table for new columns...")
            # This is a simplified check, ideally we'd use alembic
            # We'll try to add columns and catch errors if they exist
            session.exec(text("ALTER TABLE \"user\" ADD COLUMN username VARCHAR"))
            print("Added 'username' column.")
        except Exception:
            session.rollback()
            print("'username' column likely exists.")

        try:
            session.exec(text("ALTER TABLE \"user\" ADD COLUMN discord_handle VARCHAR"))
            print("Added 'discord_handle' column.")
        except Exception:
            session.rollback()
            print("'discord_handle' column likely exists.")

        try:
            session.exec(text("ALTER TABLE \"user\" ADD COLUMN bio VARCHAR"))
            print("Added 'bio' column.")
        except Exception:
            session.rollback()
            print("'bio' column likely exists.")
            
        session.commit()
        
        # 2. Create PortfolioItem table
        # SQLModel's create_db_and_tables usually handles this for new tables
        # But we'll run it here to be safe
        from app.models import PortfolioItem
        from sqlmodel import SQLModel
        print("Ensuring all tables exist...")
        SQLModel.metadata.create_all(engine)
        print("Migration complete.")

if __name__ == "__main__":
    migrate_models()

