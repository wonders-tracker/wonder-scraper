from sqlmodel import Session, text
from app.db import engine


def migrate():
    with Session(engine) as session:
        print("Checking for 'bid_count' column in 'marketprice' table...")
        try:
            # Attempt to query the column to see if it exists
            session.exec(text("SELECT bid_count FROM marketprice LIMIT 1"))
            print("Column 'bid_count' already exists.")
        except Exception:
            print("Column 'bid_count' missing. Adding it now...")
            session.rollback()  # Reset transaction after error
            try:
                session.exec(text("ALTER TABLE marketprice ADD COLUMN bid_count INTEGER DEFAULT 0"))
                session.commit()
                print("Successfully added 'bid_count' column.")
            except Exception as e:
                print(f"Failed to add column: {e}")


if __name__ == "__main__":
    migrate()
