#!/usr/bin/env python3
"""
Database migration for BlogPost table.

Creates the blog_post table for storing generated blog posts (weekly movers, etc.)
that can be served via API instead of static MDX files.

Usage:
    python scripts/migrate_blog_post.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import text
from sqlmodel import Session

from app.db import engine

load_dotenv()


MIGRATIONS = [
    # Create the blog_post table
    """
    CREATE TABLE IF NOT EXISTS blog_post (
        id SERIAL PRIMARY KEY,
        slug VARCHAR(200) NOT NULL UNIQUE,
        title VARCHAR(500) NOT NULL,
        description VARCHAR(1000),
        content TEXT NOT NULL,
        category VARCHAR(50) NOT NULL DEFAULT 'analysis',
        tags JSONB NOT NULL DEFAULT '[]',
        author VARCHAR(100) NOT NULL DEFAULT 'system',
        read_time INTEGER NOT NULL DEFAULT 3,
        published_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        is_published BOOLEAN NOT NULL DEFAULT TRUE
    );
    """,
    # Index for slug lookups (unique constraint creates index, but be explicit)
    """
    CREATE INDEX IF NOT EXISTS ix_blogpost_slug ON blog_post(slug);
    """,
    # Composite index: category + published_at for listing by category
    """
    CREATE INDEX IF NOT EXISTS ix_blogpost_category_published ON blog_post(category, published_at DESC);
    """,
    # Composite index: is_published + published_at for public listings
    """
    CREATE INDEX IF NOT EXISTS ix_blogpost_published ON blog_post(is_published, published_at DESC);
    """,
]


def run_migrations():
    """Run all migrations."""
    print("Running BlogPost table migration...")
    print()

    with Session(engine) as session:
        for i, migration in enumerate(MIGRATIONS, 1):
            migration_name = migration.strip().split("\n")[0].strip()
            print(f"[{i}/{len(MIGRATIONS)}] {migration_name[:60]}...")

            try:
                session.exec(text(migration))
                session.commit()
                print("  OK")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print("  SKIP (already exists)")
                else:
                    print(f"  ERROR: {e}")
                    raise

    print()
    print("Migration complete!")
    print()
    print("Table created: blog_post")
    print("Indexes created:")
    print("  - ix_blogpost_slug (slug)")
    print("  - ix_blogpost_category_published (category, published_at)")
    print("  - ix_blogpost_published (is_published, published_at)")
    print()
    print("API endpoints available:")
    print("  - GET /api/v1/blog/posts - List all posts")
    print("  - GET /api/v1/blog/posts/latest - Get latest post")
    print("  - GET /api/v1/blog/posts/{slug} - Get post by slug")


if __name__ == "__main__":
    run_migrations()
