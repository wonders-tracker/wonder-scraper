from typing import Optional
from sqlmodel import Field, SQLModel, UniqueConstraint
from datetime import datetime

from app.core.typing import utc_now


class CardMetaVote(SQLModel, table=True):
    """
    User votes on whether a card is 'meta' (competitively viable).
    Only applies to single cards, not sealed products.
    """

    __tablename__ = "card_meta_vote"

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    vote: str = Field(index=True)  # 'yes', 'no', 'unsure'
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    __table_args__ = (UniqueConstraint("card_id", "user_id", name="unique_card_user_meta_vote"),)


class CardMetaVoteReaction(SQLModel, table=True):
    """
    Thumbs up/down reactions on meta votes.
    Future enhancement - not implemented in initial version.
    """

    __tablename__ = "card_meta_vote_reaction"

    id: Optional[int] = Field(default=None, primary_key=True)
    vote_id: int = Field(foreign_key="card_meta_vote.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    reaction: str  # 'up' or 'down'
    created_at: datetime = Field(default_factory=utc_now)

    __table_args__ = (UniqueConstraint("vote_id", "user_id", name="unique_vote_user_reaction"),)
