from sqlmodel import text, Session
from app.db import engine


def migrate():
    print("Migrating: Adding discord_id to User table...")
    with Session(engine) as session:
        try:
            # "user" is a reserved keyword, so we must quote it.
            session.exec(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS discord_id VARCHAR UNIQUE;'))
            session.commit()
            print("Migration successful!")
        except Exception as e:
            print(f"Migration failed: {e}")


if __name__ == "__main__":
    migrate()
