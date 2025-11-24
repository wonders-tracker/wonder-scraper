"""
Admin API endpoints for triggering maintenance tasks like backfill.
Protected by API key authentication.
"""
import os
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, BackgroundTasks, Query
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# Simple API key auth for admin endpoints
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

def verify_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """Verify the admin API key."""
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=500, detail="Admin API key not configured")
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return True

class BackfillRequest(BaseModel):
    limit: int = 100
    force_all: bool = False
    is_backfill: bool = True

class BackfillResponse(BaseModel):
    status: str
    message: str
    job_id: str
    started_at: str

# Track running jobs
_running_jobs = {}

async def run_backfill_job(job_id: str, limit: int, force_all: bool, is_backfill: bool):
    """Background task to run the backfill."""
    from sqlmodel import Session, select
    from datetime import timedelta
    from app.db import engine
    from app.models.card import Card
    from app.models.market import MarketSnapshot
    from scripts.scrape_card import scrape_card
    from app.scraper.browser import BrowserManager

    _running_jobs[job_id] = {"status": "running", "started": datetime.utcnow(), "processed": 0, "errors": 0}

    try:
        with Session(engine) as session:
            all_cards = session.exec(select(Card)).all()

            cards_to_scrape = []
            cutoff_time = datetime.utcnow() - timedelta(hours=4)

            for card in all_cards:
                if force_all:
                    cards_to_scrape.append(card)
                else:
                    snapshot = session.exec(
                        select(MarketSnapshot)
                        .where(MarketSnapshot.card_id == card.id)
                        .order_by(MarketSnapshot.timestamp.desc())
                        .limit(1)
                    ).first()

                    if not snapshot or snapshot.timestamp < cutoff_time:
                        cards_to_scrape.append(card)

                if len(cards_to_scrape) >= limit:
                    break

        if not cards_to_scrape:
            _running_jobs[job_id]["status"] = "completed"
            _running_jobs[job_id]["message"] = "No cards needed updating"
            return

        _running_jobs[job_id]["total"] = len(cards_to_scrape)

        # Initialize browser
        await BrowserManager.get_browser()

        try:
            for i, card in enumerate(cards_to_scrape):
                try:
                    await scrape_card(
                        card_name=card.name,
                        card_id=card.id,
                        search_term=f"{card.name} {card.set_name}",
                        set_name=card.set_name,
                        product_type=card.product_type if hasattr(card, 'product_type') else 'Single',
                        is_backfill=is_backfill
                    )
                    _running_jobs[job_id]["processed"] = i + 1
                except Exception as e:
                    _running_jobs[job_id]["errors"] += 1
                    print(f"[Backfill] Error on {card.name}: {e}")

                # Brief delay between cards
                await asyncio.sleep(2)
        finally:
            await BrowserManager.close()

        _running_jobs[job_id]["status"] = "completed"
        _running_jobs[job_id]["finished"] = datetime.utcnow()

    except Exception as e:
        _running_jobs[job_id]["status"] = "failed"
        _running_jobs[job_id]["error"] = str(e)

@router.post("/backfill", response_model=BackfillResponse)
async def trigger_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    x_admin_key: str = Header(..., alias="X-Admin-Key")
):
    """
    Trigger a backfill job to scrape historical data.

    - **limit**: Maximum number of cards to process (default 100)
    - **force_all**: If true, scrape all cards regardless of last update time
    - **is_backfill**: If true, use higher page limits for more historical data
    """
    verify_admin_key(x_admin_key)

    # Check if a job is already running
    for job_id, job in _running_jobs.items():
        if job.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail=f"Backfill job {job_id} is already running. Processed: {job.get('processed', 0)}/{job.get('total', '?')}"
            )

    # Create new job
    job_id = f"backfill_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    # Start background task
    background_tasks.add_task(
        run_backfill_job,
        job_id,
        request.limit,
        request.force_all,
        request.is_backfill
    )

    return BackfillResponse(
        status="started",
        message=f"Backfill job started with limit={request.limit}, force_all={request.force_all}",
        job_id=job_id,
        started_at=datetime.utcnow().isoformat()
    )

@router.get("/backfill/status")
async def get_backfill_status(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
    job_id: Optional[str] = Query(None)
):
    """Get status of backfill jobs."""
    verify_admin_key(x_admin_key)

    if job_id:
        if job_id not in _running_jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return _running_jobs[job_id]

    return _running_jobs

@router.post("/scrape/trigger")
async def trigger_scheduled_scrape(
    x_admin_key: str = Header(..., alias="X-Admin-Key"),
    background_tasks: BackgroundTasks
):
    """Manually trigger the scheduled scrape job."""
    verify_admin_key(x_admin_key)

    from app.core.scheduler import job_update_market_data

    background_tasks.add_task(job_update_market_data)

    return {"status": "triggered", "message": "Scheduled scrape job triggered"}
