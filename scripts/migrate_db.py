from sqlmodel import text, Session
from app.db import engine

def migrate_db():
    with Session(engine) as session:
        # Add missing columns if they don't exist
        print("Migrating database schema...")
        
        # List of columns to check/add
        columns = [
            ("lowest_ask", "FLOAT"),
            ("highest_bid", "FLOAT"),
            ("inventory", "INTEGER")
        ]
        
        for col_name, col_type in columns:
            try:
                # Try to add the column. If it exists, this will fail gracefully-ish or we can check first.
                # Postgres doesn't have "IF NOT EXISTS" for ADD COLUMN in all versions, but let's try simple ALTER.
                session.exec(text(f"ALTER TABLE marketsnapshot ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                print(f"Added column {col_name}")
            except Exception as e:
                print(f"Could not add column {col_name}: {e}")
                
        session.commit()
        print("Migration complete.")

if __name__ == "__main__":
    migrate_db()

