from sqlmodel import Session, text
from app.db import engine

def migrate():
    with Session(engine) as session:
        print("Checking for 'platform' column in 'marketsnapshot' table...")
        try:
            session.exec(text("SELECT platform FROM marketsnapshot LIMIT 1"))
            print("Column 'platform' already exists.")
        except Exception:
            session.rollback()
            print("Column 'platform' missing. Adding it...")
            try:
                # Add platform column, default to 'ebay'
                session.exec(text("ALTER TABLE marketsnapshot ADD COLUMN platform VARCHAR DEFAULT 'ebay'"))
                # Update primary key/indexes might be needed if we want multiple snapshots per timestamp per card
                # But for now, just adding the column is fine.
                session.commit()
                print("Successfully added 'platform' column.")
            except Exception as e:
                session.rollback()
                print(f"Failed to add column: {e}")

if __name__ == "__main__":
    migrate()

