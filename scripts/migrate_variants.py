from sqlmodel import Session, text
from app.db import engine


def migrate_variants():
    with Session(engine) as session:
        print("Migrating 'marketprice' table for variants...")

        try:
            session.exec(text("ALTER TABLE marketprice ADD COLUMN variant VARCHAR DEFAULT 'Classic Paper'"))
            session.commit()
            print("Successfully added 'variant' column.")
        except Exception as e:
            session.rollback()
            print(f"Column 'variant' likely exists or error: {e}")


if __name__ == "__main__":
    migrate_variants()
