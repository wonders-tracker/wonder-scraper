"""
Blog Post Model

Stores generated blog posts (weekly movers, market analysis, etc.) in the database
for serving via API. This allows the Railway scheduler to generate posts without
needing filesystem access to the Vercel frontend.

Usage:
    from app.models.blog_post import BlogPost

    # Create a post
    post = BlogPost(
        slug="weekly-movers-2025-01-06",
        title="Weekly Market Report: January 1 - January 6, 2025",
        content="<mdx content here>",
        category="analysis",
    )
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text, Index, JSON


class BlogPost(SQLModel, table=True):
    """
    Blog post stored in database for API serving.

    Attributes:
        id: Primary key
        slug: URL-friendly unique identifier (e.g., "weekly-movers-2025-01-06")
        title: Post title
        description: Short description for SEO/previews
        content: Full MDX content
        category: Post category ("analysis", "news", "guide")
        tags: JSON array of tags
        author: Author identifier
        read_time: Estimated read time in minutes
        published_at: When the post was/should be published
        created_at: When the record was created
        updated_at: When the record was last modified
        is_published: Whether the post is visible to users
    """

    __tablename__ = "blog_post"

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True, max_length=200)
    title: str = Field(max_length=500)
    description: Optional[str] = Field(default=None, max_length=1000)
    content: str = Field(sa_column=Column(Text, nullable=False))
    category: str = Field(default="analysis", max_length=50)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
    author: str = Field(default="system", max_length=100)
    read_time: int = Field(default=3)  # minutes
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_published: bool = Field(default=True)

    __table_args__ = (
        # List posts by category + date
        Index("ix_blogpost_category_published", "category", "published_at"),
        # Find published posts efficiently
        Index("ix_blogpost_published", "is_published", "published_at"),
    )


__all__ = ["BlogPost"]
