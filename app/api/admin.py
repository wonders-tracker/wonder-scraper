"""
Admin API endpoints for triggering maintenance tasks like backfill.
Protected by superuser authentication.
"""

import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from pydantic import BaseModel
from datetime import datetime

from app.api import deps
from app.models.user import User

router = APIRouter()


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
    from app.discord_bot.logger import log_scrape_start, log_scrape_complete, log_scrape_error

    _running_jobs[job_id] = {
        "status": "running",
        "started": datetime.utcnow(),
        "processed": 0,
        "errors": 0,
        "new_listings": 0,
    }
    start_time = datetime.utcnow()

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

        # Log scrape start to Discord
        scrape_type = "backfill" if is_backfill else "incremental"
        log_scrape_start(len(cards_to_scrape), scrape_type)

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
                        product_type=card.product_type if hasattr(card, "product_type") else "Single",
                        is_backfill=is_backfill,
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

        # Log scrape completion to Discord
        duration = (datetime.utcnow() - start_time).total_seconds()
        log_scrape_complete(
            cards_processed=_running_jobs[job_id]["processed"],
            new_listings=_running_jobs[job_id].get("new_listings", 0),
            new_sales=0,  # TODO: Track this if needed
            duration_seconds=duration,
            errors=_running_jobs[job_id]["errors"],
        )

    except Exception as e:
        _running_jobs[job_id]["status"] = "failed"
        _running_jobs[job_id]["error"] = str(e)
        # Log error to Discord
        log_scrape_error("Backfill Job", str(e)[:500])


@router.post("/backfill", response_model=BackfillResponse)
async def trigger_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_superuser),
):
    """
    Trigger a backfill job to scrape historical data.

    - **limit**: Maximum number of cards to process (default 100)
    - **force_all**: If true, scrape all cards regardless of last update time
    - **is_backfill**: If true, use higher page limits for more historical data
    """
    # Check if a job is already running
    for job_id, job in _running_jobs.items():
        if job.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail=f"Backfill job {job_id} is already running. Processed: {job.get('processed', 0)}/{job.get('total', '?')}",
            )

    # Create new job
    job_id = f"backfill_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    # Start background task
    background_tasks.add_task(run_backfill_job, job_id, request.limit, request.force_all, request.is_backfill)

    return BackfillResponse(
        status="started",
        message=f"Backfill job started with limit={request.limit}, force_all={request.force_all}",
        job_id=job_id,
        started_at=datetime.utcnow().isoformat(),
    )


@router.get("/backfill/status")
async def get_backfill_status(
    current_user: User = Depends(deps.get_current_superuser),
    job_id: Optional[str] = Query(None),
):
    """Get status of backfill jobs."""
    if job_id:
        if job_id not in _running_jobs:
            raise HTTPException(status_code=404, detail="Job not found")
        return _running_jobs[job_id]

    return _running_jobs


@router.post("/scrape/trigger")
async def trigger_scheduled_scrape(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_superuser),
):
    """Manually trigger the scheduled scrape job."""
    from app.core.scheduler import job_update_market_data

    background_tasks.add_task(job_update_market_data)

    return {"status": "triggered", "message": "Scheduled scrape job triggered"}


@router.get("/stats")
async def get_admin_stats(
    current_user: User = Depends(deps.get_current_superuser),
):
    """Get system statistics for admin dashboard."""
    from sqlmodel import Session, select, func, text
    from app.db import engine
    from app.models.user import User as UserModel
    from app.models.card import Card
    from app.models.market import MarketPrice, MarketSnapshot
    from app.models.portfolio import PortfolioCard
    from app.models.analytics import PageView
    from datetime import timedelta

    with Session(engine) as session:
        # User stats
        total_users = session.exec(select(func.count(UserModel.id))).one()
        active_users_24h = (
            session.exec(
                select(func.count(UserModel.id)).where(UserModel.last_login >= datetime.utcnow() - timedelta(hours=24))
            ).one()
            if hasattr(UserModel, "last_login")
            else 0
        )

        # Get all users with details
        all_users = session.exec(select(UserModel).order_by(UserModel.created_at.desc())).all()
        users_list = []
        for u in all_users:
            users_list.append(
                {
                    "id": u.id,
                    "email": u.email,
                    "username": getattr(u, "username", None),
                    "discord_handle": getattr(u, "discord_handle", None),
                    "is_superuser": u.is_superuser,
                    "is_active": u.is_active,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_login": u.last_login.isoformat() if hasattr(u, "last_login") and u.last_login else None,
                }
            )

        # Card stats
        total_cards = session.exec(select(func.count(Card.id))).one()

        # Market data stats
        total_listings = session.exec(select(func.count(MarketPrice.id))).one()
        sold_listings = session.exec(select(func.count(MarketPrice.id)).where(MarketPrice.listing_type == "sold")).one()
        active_listings = session.exec(
            select(func.count(MarketPrice.id)).where(MarketPrice.listing_type == "active")
        ).one()

        # Listings in last 24h
        listings_24h = session.exec(
            select(func.count(MarketPrice.id)).where(MarketPrice.scraped_at >= datetime.utcnow() - timedelta(hours=24))
        ).one()

        # Listings in last 7d
        listings_7d = session.exec(
            select(func.count(MarketPrice.id)).where(MarketPrice.scraped_at >= datetime.utcnow() - timedelta(days=7))
        ).one()

        # Portfolio stats
        total_portfolio_cards = session.exec(
            select(func.count(PortfolioCard.id)).where(PortfolioCard.deleted_at.is_(None))
        ).one()

        # Snapshot stats
        total_snapshots = session.exec(select(func.count(MarketSnapshot.id))).one()
        latest_snapshot = session.exec(
            select(MarketSnapshot).order_by(MarketSnapshot.timestamp.desc()).limit(1)
        ).first()

        # Database size (PostgreSQL)
        try:
            db_size_result = session.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            ).first()
            db_size = db_size_result[0] if db_size_result else "Unknown"
        except:
            db_size = "Unknown"

        # Top scraped cards (by listing count)
        top_cards_result = session.execute(
            text("""
            SELECT c.name, COUNT(mp.id) as listing_count
            FROM card c
            JOIN marketprice mp ON mp.card_id = c.id
            GROUP BY c.id, c.name
            ORDER BY listing_count DESC
            LIMIT 10
        """)
        ).all()
        top_cards = [{"name": row[0], "listings": row[1]} for row in top_cards_result]

        # Daily scrape volume (last 7 days)
        daily_volume_result = session.execute(
            text("""
            SELECT DATE(scraped_at) as date, COUNT(*) as count
            FROM marketprice
            WHERE scraped_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(scraped_at)
            ORDER BY date DESC
        """)
        ).all()
        daily_volume = [{"date": str(row[0]), "count": row[1]} for row in daily_volume_result]

        # Analytics - Page views
        try:
            total_pageviews = session.exec(select(func.count(PageView.id))).one()
            pageviews_24h = session.exec(
                select(func.count(PageView.id)).where(PageView.timestamp >= datetime.utcnow() - timedelta(hours=24))
            ).one()
            pageviews_7d = session.exec(
                select(func.count(PageView.id)).where(PageView.timestamp >= datetime.utcnow() - timedelta(days=7))
            ).one()

            # Unique visitors (by ip_hash) in 24h
            unique_visitors_24h = (
                session.execute(
                    text("""
                SELECT COUNT(DISTINCT ip_hash) FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
            """)
                ).scalar()
                or 0
            )

            # Unique visitors in 7d
            unique_visitors_7d = (
                session.execute(
                    text("""
                SELECT COUNT(DISTINCT ip_hash) FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days'
            """)
                ).scalar()
                or 0
            )

            # Top pages (last 7 days)
            top_pages_result = session.execute(
                text("""
                SELECT path, COUNT(*) as views
                FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                GROUP BY path
                ORDER BY views DESC
                LIMIT 10
            """)
            ).all()
            top_pages = [{"path": row[0], "views": row[1]} for row in top_pages_result]

            # Traffic by device type
            device_breakdown_result = session.execute(
                text("""
                SELECT device_type, COUNT(*) as count
                FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                GROUP BY device_type
                ORDER BY count DESC
            """)
            ).all()
            device_breakdown = [{"device": row[0] or "unknown", "count": row[1]} for row in device_breakdown_result]

            # Daily pageviews (last 7 days)
            daily_pageviews_result = session.execute(
                text("""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """)
            ).all()
            daily_pageviews = [{"date": str(row[0]), "count": row[1]} for row in daily_pageviews_result]

            # Top referrers
            top_referrers_result = session.execute(
                text("""
                SELECT referrer, COUNT(*) as count
                FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                  AND referrer IS NOT NULL
                  AND referrer != ''
                GROUP BY referrer
                ORDER BY count DESC
                LIMIT 10
            """)
            ).all()
            top_referrers = [{"referrer": row[0], "count": row[1]} for row in top_referrers_result]

            analytics_data = {
                "total_pageviews": total_pageviews,
                "pageviews_24h": pageviews_24h,
                "pageviews_7d": pageviews_7d,
                "unique_visitors_24h": unique_visitors_24h,
                "unique_visitors_7d": unique_visitors_7d,
                "top_pages": top_pages,
                "device_breakdown": device_breakdown,
                "daily_pageviews": daily_pageviews,
                "top_referrers": top_referrers,
            }
        except Exception as e:
            # Table might not exist yet
            analytics_data = {
                "total_pageviews": 0,
                "pageviews_24h": 0,
                "pageviews_7d": 0,
                "unique_visitors_24h": 0,
                "unique_visitors_7d": 0,
                "top_pages": [],
                "device_breakdown": [],
                "daily_pageviews": [],
                "top_referrers": [],
                "error": str(e),
            }

        return {
            "users": {
                "total": total_users,
                "active_24h": active_users_24h,
                "list": users_list,
            },
            "cards": {
                "total": total_cards,
            },
            "listings": {
                "total": total_listings,
                "sold": sold_listings,
                "active": active_listings,
                "last_24h": listings_24h,
                "last_7d": listings_7d,
            },
            "portfolio": {
                "total_cards": total_portfolio_cards,
            },
            "snapshots": {
                "total": total_snapshots,
                "latest": latest_snapshot.timestamp.isoformat() if latest_snapshot else None,
            },
            "database": {
                "size": db_size,
            },
            "top_cards": top_cards,
            "daily_volume": daily_volume,
            "scraper_jobs": _running_jobs,
            "analytics": analytics_data,
        }


@router.get("/scheduler/status")
async def get_scheduler_status(
    current_user: User = Depends(deps.get_current_superuser),
):
    """Get scheduler job status."""
    from app.core.scheduler import scheduler

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
        )

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }


# ============== API KEY MANAGEMENT (Admin) ==============


@router.get("/api-keys")
async def list_all_api_keys(
    current_user: User = Depends(deps.get_current_superuser),
):
    """List all API keys across all users (admin only)."""
    from sqlmodel import Session, select
    from app.db import engine
    from app.models.api_key import APIKey
    from app.models.user import User as UserModel

    with Session(engine) as session:
        # Get all API keys with user info
        keys = session.exec(select(APIKey).order_by(APIKey.created_at.desc())).all()

        result = []
        for key in keys:
            user = session.get(UserModel, key.user_id)
            result.append(
                {
                    "id": key.id,
                    "user_id": key.user_id,
                    "user_email": user.email if user else "Unknown",
                    "key_prefix": key.key_prefix,
                    "name": key.name,
                    "is_active": key.is_active,
                    "rate_limit_per_minute": key.rate_limit_per_minute,
                    "rate_limit_per_day": key.rate_limit_per_day,
                    "requests_today": key.requests_today,
                    "requests_total": key.requests_total,
                    "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                    "created_at": key.created_at.isoformat() if key.created_at else None,
                    "expires_at": key.expires_at.isoformat() if key.expires_at else None,
                }
            )

        return result


@router.get("/api-keys/stats")
async def get_api_key_stats(
    current_user: User = Depends(deps.get_current_superuser),
):
    """Get API key usage statistics (admin only)."""
    from sqlmodel import Session, select, func
    from sqlalchemy import text
    from app.db import engine
    from app.models.api_key import APIKey

    with Session(engine) as session:
        # Total keys
        total_keys = session.exec(select(func.count(APIKey.id))).one()

        # Active keys
        active_keys = session.exec(select(func.count(APIKey.id)).where(APIKey.is_active is True)).one()

        # Keys used today
        keys_used_today = session.exec(select(func.count(APIKey.id)).where(APIKey.requests_today > 0)).one()

        # Total requests today
        total_requests_today = session.exec(select(func.sum(APIKey.requests_today))).one() or 0

        # Total requests all time
        total_requests_all = session.exec(select(func.sum(APIKey.requests_total))).one() or 0

        # Top users by API usage
        top_users_result = session.execute(
            text("""
            SELECT u.email, SUM(ak.requests_total) as total_requests, COUNT(ak.id) as key_count
            FROM apikey ak
            JOIN "user" u ON ak.user_id = u.id
            GROUP BY u.id, u.email
            ORDER BY total_requests DESC
            LIMIT 10
        """)
        ).all()
        top_users = [{"email": row[0], "total_requests": row[1] or 0, "key_count": row[2]} for row in top_users_result]

        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "keys_used_today": keys_used_today,
            "total_requests_today": total_requests_today,
            "total_requests_all_time": total_requests_all,
            "top_users": top_users,
        }


@router.put("/api-keys/{key_id}/toggle")
async def admin_toggle_api_key(
    key_id: int,
    current_user: User = Depends(deps.get_current_superuser),
):
    """Enable or disable any API key (admin only)."""
    from sqlmodel import Session
    from app.db import engine
    from app.models.api_key import APIKey

    with Session(engine) as session:
        key = session.get(APIKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")

        key.is_active = not key.is_active
        session.add(key)
        session.commit()

        return {
            "id": key.id,
            "is_active": key.is_active,
            "message": f"API key {'enabled' if key.is_active else 'disabled'}",
        }


@router.delete("/api-keys/{key_id}")
async def admin_delete_api_key(
    key_id: int,
    current_user: User = Depends(deps.get_current_superuser),
):
    """Delete any API key (admin only)."""
    from sqlmodel import Session
    from app.db import engine
    from app.models.api_key import APIKey

    with Session(engine) as session:
        key = session.get(APIKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")

        key_prefix = key.key_prefix
        session.delete(key)
        session.commit()

        return {"message": "API key deleted", "key_prefix": key_prefix}


@router.put("/api-keys/{key_id}/limits")
async def admin_update_api_key_limits(
    key_id: int,
    rate_limit_per_minute: int = Query(default=60, ge=1, le=1000),
    rate_limit_per_day: int = Query(default=10000, ge=100, le=1000000),
    current_user: User = Depends(deps.get_current_superuser),
):
    """Update rate limits for an API key (admin only)."""
    from sqlmodel import Session
    from app.db import engine
    from app.models.api_key import APIKey

    with Session(engine) as session:
        key = session.get(APIKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")

        key.rate_limit_per_minute = rate_limit_per_minute
        key.rate_limit_per_day = rate_limit_per_day
        session.add(key)
        session.commit()

        return {
            "id": key.id,
            "rate_limit_per_minute": key.rate_limit_per_minute,
            "rate_limit_per_day": key.rate_limit_per_day,
            "message": "Rate limits updated",
        }


@router.post("/api-keys/reset-daily")
async def admin_reset_daily_counts(
    current_user: User = Depends(deps.get_current_superuser),
):
    """Reset daily request counts for all API keys (admin only)."""
    from sqlmodel import Session
    from sqlalchemy import text
    from app.db import engine

    with Session(engine) as session:
        result = session.execute(
            text("""
            UPDATE apikey
            SET requests_today = 0, last_reset_date = NOW()
        """)
        )
        session.commit()

        return {"message": "Daily counts reset for all API keys", "keys_affected": result.rowcount}
