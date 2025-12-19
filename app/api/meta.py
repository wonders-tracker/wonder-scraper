from typing import Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func

from app.api import deps
from app.db import get_session
from app.models.meta_vote import CardMetaVote
from app.models.card import Card
from app.models.user import User
from app.schemas import MetaVoteCreate, MetaVoteResponse, MetaVoteSummary

router = APIRouter()


def get_vote_summary(session: Session, card_id: int) -> MetaVoteSummary:
    """Get vote counts for a card."""
    votes = session.exec(
        select(CardMetaVote.vote, func.count(CardMetaVote.id))
        .where(CardMetaVote.card_id == card_id)
        .group_by(CardMetaVote.vote)
    ).all()

    summary = MetaVoteSummary()
    for vote_type, count in votes:
        if vote_type == "yes":
            summary.yes = count
        elif vote_type == "no":
            summary.no = count
        elif vote_type == "unsure":
            summary.unsure = count

    summary.total = summary.yes + summary.no + summary.unsure
    return summary


def get_consensus(summary: MetaVoteSummary) -> Optional[str]:
    """Determine the consensus vote (highest count, or None if tie/empty)."""
    if summary.total == 0:
        return None

    max_count = max(summary.yes, summary.no, summary.unsure)
    if max_count == 0:
        return None

    # Check for ties
    leaders = []
    if summary.yes == max_count:
        leaders.append("yes")
    if summary.no == max_count:
        leaders.append("no")
    if summary.unsure == max_count:
        leaders.append("unsure")

    # Return None if tie, otherwise return the leader
    return leaders[0] if len(leaders) == 1 else None


@router.get("/{card_id}/meta", response_model=MetaVoteResponse)
def get_meta_votes(
    card_id: int,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(deps.get_current_user_optional),
) -> Any:
    """
    Get meta vote summary for a card.
    Returns vote counts and user's current vote (if authenticated).
    """
    # Verify card exists
    card = session.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    summary = get_vote_summary(session, card_id)

    # Get user's vote if authenticated
    user_vote = None
    if current_user:
        vote = session.exec(
            select(CardMetaVote).where(CardMetaVote.card_id == card_id).where(CardMetaVote.user_id == current_user.id)
        ).first()
        if vote:
            user_vote = vote.vote

    return MetaVoteResponse(summary=summary, user_vote=user_vote, consensus=get_consensus(summary))


@router.post("/{card_id}/meta", response_model=MetaVoteResponse)
def cast_meta_vote(
    card_id: int,
    vote_in: MetaVoteCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Cast or update a meta vote for a card.
    Requires authentication.
    """
    # Validate vote value
    if vote_in.vote not in ("yes", "no", "unsure"):
        raise HTTPException(status_code=400, detail="Vote must be 'yes', 'no', or 'unsure'")

    # Verify card exists
    card = session.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if user already voted - update if so, create if not
    existing_vote = session.exec(
        select(CardMetaVote).where(CardMetaVote.card_id == card_id).where(CardMetaVote.user_id == current_user.id)
    ).first()

    if existing_vote:
        existing_vote.vote = vote_in.vote
        existing_vote.updated_at = datetime.now(timezone.utc)
        session.add(existing_vote)
    else:
        new_vote = CardMetaVote(card_id=card_id, user_id=current_user.id, vote=vote_in.vote)
        session.add(new_vote)

    session.commit()

    # Return updated summary
    summary = get_vote_summary(session, card_id)
    return MetaVoteResponse(summary=summary, user_vote=vote_in.vote, consensus=get_consensus(summary))


@router.delete("/{card_id}/meta", response_model=MetaVoteResponse)
def delete_meta_vote(
    card_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Remove user's meta vote for a card.
    Requires authentication.
    """
    # Verify card exists
    card = session.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Find and delete the vote
    vote = session.exec(
        select(CardMetaVote).where(CardMetaVote.card_id == card_id).where(CardMetaVote.user_id == current_user.id)
    ).first()

    if vote:
        session.delete(vote)
        session.commit()

    # Return updated summary
    summary = get_vote_summary(session, card_id)
    return MetaVoteResponse(summary=summary, user_vote=None, consensus=get_consensus(summary))
