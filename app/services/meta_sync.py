"""
Meta Sync Service

Computes and syncs the is_meta field on cards based on user votes.

Algorithm:
- Minimum 3 votes required for a signal
- Card is meta if >50% of votes are 'yes'
- Runs periodically via scheduler or on-demand
"""

import logging
from typing import Optional
from sqlmodel import Session, select, func

from app.db import engine
from app.models.card import Card
from app.models.meta_vote import CardMetaVote

logger = logging.getLogger(__name__)

# Configuration
MIN_VOTES_REQUIRED = 3
META_YES_THRESHOLD = 0.5  # 50% 'yes' votes required


def compute_meta_status(session: Session, card_id: int) -> Optional[bool]:
    """
    Compute whether a card should be marked as meta based on votes.

    Returns:
        True if meta, False if not meta, None if insufficient data
    """
    # Get vote counts
    result = session.exec(
        select(CardMetaVote.vote, func.count(CardMetaVote.id))
        .where(CardMetaVote.card_id == card_id)
        .group_by(CardMetaVote.vote)
    ).all()

    vote_counts = {"yes": 0, "no": 0, "unsure": 0}
    for vote_type, count in result:
        if vote_type in vote_counts:
            vote_counts[vote_type] = count

    total = sum(vote_counts.values())

    # Not enough votes for a signal
    if total < MIN_VOTES_REQUIRED:
        return None

    # Calculate yes percentage (excluding unsure from denominator)
    decisive_votes = vote_counts["yes"] + vote_counts["no"]
    if decisive_votes == 0:
        return None  # All unsure votes

    yes_ratio = vote_counts["yes"] / decisive_votes
    return yes_ratio > META_YES_THRESHOLD


def sync_card_meta_status(card_id: int, session: Optional[Session] = None) -> bool:
    """
    Sync a single card's is_meta field based on votes.

    Returns True if the card was updated, False otherwise.
    """
    should_close = session is None
    if session is None:
        session = Session(engine)

    try:
        card = session.get(Card, card_id)
        if not card:
            return False

        new_status = compute_meta_status(session, card_id)

        # Only update if we have a decisive result
        if new_status is not None and card.is_meta != new_status:
            card.is_meta = new_status
            session.add(card)
            session.commit()
            logger.info(f"Card {card.name} is_meta updated to {new_status}")
            return True

        return False
    finally:
        if should_close:
            session.close()


def sync_all_meta_status() -> dict:
    """
    Sync is_meta for all cards with votes.

    Returns:
        dict with counts: updated, unchanged, insufficient_votes
    """
    stats = {"updated": 0, "unchanged": 0, "insufficient_votes": 0}

    with Session(engine) as session:
        # Get all cards that have at least one vote
        cards_with_votes = session.exec(select(CardMetaVote.card_id).distinct()).all()

        for card_id in cards_with_votes:
            card = session.get(Card, card_id)
            if not card:
                continue

            new_status = compute_meta_status(session, card_id)

            if new_status is None:
                stats["insufficient_votes"] += 1
            elif card.is_meta != new_status:
                card.is_meta = new_status
                session.add(card)
                stats["updated"] += 1
                logger.info(f"Card {card.name} is_meta: {new_status}")
            else:
                stats["unchanged"] += 1

        session.commit()

    logger.info(f"Meta sync complete: {stats}")
    return stats


def get_meta_cards(session: Optional[Session] = None) -> list[Card]:
    """Get all cards marked as meta."""
    should_close = session is None
    if session is None:
        session = Session(engine)

    try:
        return list(session.exec(select(Card).where(Card.is_meta.is_(True))).all())
    finally:
        if should_close:
            session.close()


def set_meta_manually(card_id: int, is_meta: bool, session: Optional[Session] = None) -> bool:
    """
    Manually set a card's meta status (admin override).

    Returns True if updated, False if card not found.
    """
    should_close = session is None
    if session is None:
        session = Session(engine)

    try:
        card = session.get(Card, card_id)
        if not card:
            return False

        card.is_meta = is_meta
        session.add(card)
        session.commit()
        logger.info(f"Card {card.name} manually set is_meta={is_meta}")
        return True
    finally:
        if should_close:
            session.close()
