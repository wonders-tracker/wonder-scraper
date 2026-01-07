from sqlmodel import Session, text
from app.db import engine


def migrate_marketprice():
    with Session(engine) as session:
        print("Checking for missing columns in 'marketprice' table...")

        # Check if listing_type column exists
        try:
            session.exec(text("SELECT listing_type FROM marketprice LIMIT 1"))
            print("Column 'listing_type' already exists.")
        except Exception:
            session.rollback()
            print("Column 'listing_type' missing. Adding it...")
            try:
                # Add listing_type column
                session.exec(text("ALTER TABLE marketprice ADD COLUMN listing_type VARCHAR DEFAULT 'sold'"))
                session.commit()
                print("Successfully added 'listing_type' column.")
            except Exception as e:
                session.rollback()
                print(f"Failed to add column: {e}")


if __name__ == "__main__":
    migrate_marketprice()
