from sqlmodel import Session, text
from app.db import engine


def migrate():
    with Session(engine) as session:
        print("Checking for 'platform' column in 'marketprice' table...")
        try:
            session.exec(text("SELECT platform FROM marketprice LIMIT 1"))
            print("Column 'platform' already exists.")
        except Exception:
            session.rollback()
            print("Column 'platform' missing. Adding it...")
            try:
                # Add platform column, default to 'ebay' for existing records
                session.exec(text("ALTER TABLE marketprice ADD COLUMN platform VARCHAR DEFAULT 'ebay'"))
                session.commit()
                print("Successfully added 'platform' column.")
            except Exception as e:
                session.rollback()
                print(f"Failed to add column: {e}")


if __name__ == "__main__":
    migrate()
