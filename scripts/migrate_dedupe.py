from sqlmodel import Session, text
from app.db import engine


def migrate():
    with Session(engine) as session:
        print("Checking for external_id column in marketprice...")
        try:
            # Try to select the column to see if it exists
            session.exec(text("SELECT external_id FROM marketprice LIMIT 1"))
            print("Column 'external_id' already exists.")
        except Exception:
            session.rollback()
            print("Column 'external_id' not found. Adding it...")
            session.exec(text("ALTER TABLE marketprice ADD COLUMN external_id VARCHAR"))
            session.exec(text("CREATE INDEX ix_marketprice_external_id ON marketprice (external_id)"))
            session.commit()
            print("Added 'external_id' column.")

        print("Checking for url column in marketprice...")
        try:
            session.exec(text("SELECT url FROM marketprice LIMIT 1"))
            print("Column 'url' already exists.")
        except Exception:
            session.rollback()
            print("Column 'url' not found. Adding it...")
            session.exec(text("ALTER TABLE marketprice ADD COLUMN url VARCHAR"))
            session.commit()
            print("Added 'url' column.")


if __name__ == "__main__":
    migrate()
