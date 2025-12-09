"""
Create webhook_event table for tracking processed webhook events (idempotency).
"""
import sys
sys.path.insert(0, ".")

from sqlmodel import text
from app.db import engine

def migrate():
    """Create webhook_event table."""
    with engine.connect() as conn:
        # Check if table already exists
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'webhook_event'
        """))

        if result.fetchone():
            print("Table webhook_event already exists, skipping...")
            return

        # Create the table
        conn.execute(text("""
            CREATE TABLE webhook_event (
                id SERIAL PRIMARY KEY,
                event_id VARCHAR UNIQUE NOT NULL,
                event_type VARCHAR NOT NULL,
                source VARCHAR NOT NULL DEFAULT 'polar',
                processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                status VARCHAR NOT NULL DEFAULT 'processed',
                user_id INTEGER NULL,
                subscription_id VARCHAR NULL,
                error_message TEXT NULL
            )
        """))

        # Create indexes
        conn.execute(text("""
            CREATE INDEX ix_webhook_event_event_id ON webhook_event(event_id)
        """))
        conn.execute(text("""
            CREATE INDEX ix_webhook_event_event_type ON webhook_event(event_type)
        """))
        conn.execute(text("""
            CREATE INDEX ix_webhook_event_user_id ON webhook_event(user_id)
        """))

        conn.commit()
        print("Created webhook_event table with indexes")

if __name__ == "__main__":
    migrate()
