from sqlmodel import Session, text
from app.db import engine


def migrate():
    with Session(engine) as session:
        print("Checking for product_type column in card table...")
        try:
            session.exec(text("SELECT product_type FROM card LIMIT 1"))
            print("Column 'product_type' already exists.")
        except Exception:
            session.rollback()
            print("Column 'product_type' not found. Adding it...")
            session.exec(text("ALTER TABLE card ADD COLUMN product_type VARCHAR DEFAULT 'Single'"))
            session.commit()
            print("Added 'product_type' column.")


if __name__ == "__main__":
    migrate()
