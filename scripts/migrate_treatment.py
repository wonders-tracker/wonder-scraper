from sqlmodel import Session, text
from app.db import engine


def migrate_treatment():
    with Session(engine) as session:
        print("Checking for 'treatment' column in 'marketprice' table...")
        try:
            session.exec(text("SELECT treatment FROM marketprice LIMIT 1"))
            print("Column 'treatment' already exists.")
        except Exception:
            session.rollback()
            print("Column 'treatment' missing. Adding it...")
            try:
                # Add treatment column
                session.exec(text("ALTER TABLE marketprice ADD COLUMN treatment VARCHAR DEFAULT 'Classic Paper'"))
                session.commit()
                print("Successfully added 'treatment' column.")
            except Exception as e:
                session.rollback()
                print(f"Failed to add column: {e}")


if __name__ == "__main__":
    migrate_treatment()
