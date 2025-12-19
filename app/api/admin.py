"""
Admin API endpoints for triggering maintenance tasks like backfill.
Protected by superuser authentication.
"""

import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from pydantic import BaseModel
from datetime import datetime, timezone

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
        "started": datetime.now(timezone.utc),
        "processed": 0,
        "errors": 0,
        "new_listings": 0,
    }
    start_time = datetime.now(timezone.utc)

    try:
        with Session(engine) as session:
            all_cards = session.exec(select(Card)).all()

            cards_to_scrape = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=4)

            for card in all_cards:
                if force_all:
                    cards_to_scrape.append(card)
                else:
                    snapshot = session.exec(
                        select(MarketSnapshot)
                        .where(MarketSnapshot.card_id == card.id)
                        .order_by(MarketSnapshot.timestamp.desc(), MarketSnapshot.id.desc())
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
        _running_jobs[job_id]["finished"] = datetime.now(timezone.utc)

        # Log scrape completion to Discord
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
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
    job_id = f"backfill_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # Start background task
    background_tasks.add_task(run_backfill_job, job_id, request.limit, request.force_all, request.is_backfill)

    return BackfillResponse(
        status="started",
        message=f"Backfill job started with limit={request.limit}, force_all={request.force_all}",
        job_id=job_id,
        started_at=datetime.now(timezone.utc).isoformat(),
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
    from datetime import timedelta

    with Session(engine) as session:
        # User stats
        total_users = session.exec(select(func.count(UserModel.id))).one()
        active_users_24h = (
            session.exec(
                select(func.count(UserModel.id)).where(UserModel.last_login >= datetime.now(timezone.utc) - timedelta(hours=24))
            ).one()
            if hasattr(UserModel, "last_login")
            else 0
        )

        # Get all users with details and activity data
        all_users = session.exec(select(UserModel).order_by(UserModel.created_at.desc())).all()

        # Get user activity stats in bulk for efficiency
        user_activity_result = session.execute(
            text("""
                SELECT
                    user_id,
                    MAX(timestamp) as last_active,
                    COUNT(*) as pageview_count,
                    COUNT(DISTINCT path) as unique_pages
                FROM pageview
                WHERE user_id IS NOT NULL
                GROUP BY user_id
            """)
        ).all()
        user_activity_map = {
            row[0]: {"last_active": row[1], "pageview_count": row[2], "unique_pages": row[3]}
            for row in user_activity_result
        }

        users_list = []
        for u in all_users:
            activity = user_activity_map.get(u.id, {})
            last_active = activity.get("last_active")
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
                    "last_active": last_active.isoformat() if last_active else None,
                    "pageview_count": activity.get("pageview_count", 0),
                    "unique_pages": activity.get("unique_pages", 0),
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
            select(func.count(MarketPrice.id)).where(MarketPrice.scraped_at >= datetime.now(timezone.utc) - timedelta(hours=24))
        ).one()

        # Listings in last 7d
        listings_7d = session.exec(
            select(func.count(MarketPrice.id)).where(MarketPrice.scraped_at >= datetime.now(timezone.utc) - timedelta(days=7))
        ).one()

        # Portfolio stats
        total_portfolio_cards = session.exec(
            select(func.count(PortfolioCard.id)).where(PortfolioCard.deleted_at.is_(None))
        ).one()

        # Snapshot stats
        total_snapshots = session.exec(select(func.count(MarketSnapshot.id))).one()
        latest_snapshot = session.exec(
            select(MarketSnapshot).order_by(MarketSnapshot.timestamp.desc(), MarketSnapshot.id.desc()).limit(1)
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
        # Filter out: admin users (superusers) and localhost traffic
        try:
            # Get superuser IDs to exclude
            superuser_ids = session.exec(
                select(UserModel.id).where(UserModel.is_superuser.is_(True))
            ).all()
            superuser_ids_list = list(superuser_ids) if superuser_ids else []

            # Base filter: exclude admin users and localhost referrers
            def exclude_admin_localhost_pv(query_text: str) -> str:
                """Add WHERE clause to exclude admin/localhost from pageview queries."""
                exclusions = []
                if superuser_ids_list:
                    ids_str = ",".join(str(id) for id in superuser_ids_list)
                    exclusions.append(f"(user_id IS NULL OR user_id NOT IN ({ids_str}))")
                exclusions.append("(referrer IS NULL OR referrer NOT LIKE '%localhost%')")
                exclusions.append("path NOT LIKE '%/auth/callback%'")
                return " AND ".join(exclusions)

            def exclude_admin_localhost_ev(query_text: str) -> str:
                """Add WHERE clause to exclude admin/localhost from event queries."""
                exclusions = []
                if superuser_ids_list:
                    ids_str = ",".join(str(id) for id in superuser_ids_list)
                    exclusions.append(f"(user_id IS NULL OR user_id NOT IN ({ids_str}))")
                return " AND ".join(exclusions) if exclusions else "1=1"

            pv_filter = exclude_admin_localhost_pv("")
            ev_filter = exclude_admin_localhost_ev("")

            total_pageviews = session.execute(
                text(f"SELECT COUNT(*) FROM pageview WHERE {pv_filter}")
            ).scalar() or 0
            pageviews_24h = session.execute(
                text(f"SELECT COUNT(*) FROM pageview WHERE timestamp >= NOW() - INTERVAL '24 hours' AND {pv_filter}")
            ).scalar() or 0
            pageviews_7d = session.execute(
                text(f"SELECT COUNT(*) FROM pageview WHERE timestamp >= NOW() - INTERVAL '7 days' AND {pv_filter}")
            ).scalar() or 0

            # Unique visitors (by ip_hash) in 24h
            unique_visitors_24h = (
                session.execute(
                    text(f"""
                SELECT COUNT(DISTINCT ip_hash) FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '24 hours' AND {pv_filter}
            """)
                ).scalar()
                or 0
            )

            # Unique visitors in 7d
            unique_visitors_7d = (
                session.execute(
                    text(f"""
                SELECT COUNT(DISTINCT ip_hash) FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days' AND {pv_filter}
            """)
                ).scalar()
                or 0
            )

            # Top pages (last 7 days)
            top_pages_result = session.execute(
                text(f"""
                SELECT path, COUNT(*) as views
                FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days' AND {pv_filter}
                GROUP BY path
                ORDER BY views DESC
                LIMIT 10
            """)
            ).all()
            top_pages = [{"path": row[0], "views": row[1]} for row in top_pages_result]

            # Traffic by device type
            device_breakdown_result = session.execute(
                text(f"""
                SELECT device_type, COUNT(*) as count
                FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days' AND {pv_filter}
                GROUP BY device_type
                ORDER BY count DESC
            """)
            ).all()
            device_breakdown = [{"device": row[0] or "unknown", "count": row[1]} for row in device_breakdown_result]

            # Daily pageviews (last 7 days)
            daily_pageviews_result = session.execute(
                text(f"""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days' AND {pv_filter}
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """)
            ).all()
            daily_pageviews = [{"date": str(row[0]), "count": row[1]} for row in daily_pageviews_result]

            # Top referrers (exclude localhost)
            top_referrers_result = session.execute(
                text(f"""
                SELECT referrer, COUNT(*) as count
                FROM pageview
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                  AND referrer IS NOT NULL
                  AND referrer != ''
                  AND referrer NOT LIKE '%localhost%'
                  AND {pv_filter}
                GROUP BY referrer
                ORDER BY count DESC
                LIMIT 10
            """)
            ).all()
            top_referrers = [{"referrer": row[0], "count": row[1]} for row in top_referrers_result]

            # Popular cards (from pageviews to /cards/{id} routes)
            popular_cards_result = session.execute(
                text(f"""
                SELECT
                    pv.path,
                    c.id as card_id,
                    c.name as card_name,
                    c.image_url,
                    COUNT(*) as views
                FROM pageview pv
                LEFT JOIN card c ON c.id = CAST(
                    CASE
                        WHEN pv.path ~ '^/cards/[0-9]+$'
                        THEN regexp_replace(pv.path, '^/cards/', '')
                        ELSE NULL
                    END AS INTEGER
                )
                WHERE pv.timestamp >= NOW() - INTERVAL '7 days'
                  AND pv.path ~ '^/cards/[0-9]+$'
                  AND {pv_filter}
                GROUP BY pv.path, c.id, c.name, c.image_url
                ORDER BY views DESC
                LIMIT 10
            """)
            ).all()
            popular_cards = [
                {
                    "path": row[0],
                    "card_id": row[1],
                    "card_name": row[2],
                    "image_url": row[3],
                    "views": row[4],
                }
                for row in popular_cards_result
            ]

            # Events summary (exclude admin users)
            total_events = session.execute(
                text(f"SELECT COUNT(*) FROM analytics_event WHERE {ev_filter}")
            ).scalar() or 0
            events_24h = session.execute(
                text(f"SELECT COUNT(*) FROM analytics_event WHERE timestamp >= NOW() - INTERVAL '24 hours' AND {ev_filter}")
            ).scalar() or 0
            events_7d = session.execute(
                text(f"SELECT COUNT(*) FROM analytics_event WHERE timestamp >= NOW() - INTERVAL '7 days' AND {ev_filter}")
            ).scalar() or 0

            # Top events by name (exclude admin users)
            top_events_result = session.execute(
                text(f"""
                SELECT event_name, COUNT(*) as count
                FROM analytics_event
                WHERE timestamp >= NOW() - INTERVAL '7 days' AND {ev_filter}
                GROUP BY event_name
                ORDER BY count DESC
                LIMIT 10
            """)
            ).all()
            top_events = [{"event_name": row[0], "count": row[1]} for row in top_events_result]

            # Daily events (last 7 days, exclude admin users)
            daily_events_result = session.execute(
                text(f"""
                SELECT DATE(timestamp) as date, COUNT(*) as count
                FROM analytics_event
                WHERE timestamp >= NOW() - INTERVAL '7 days' AND {ev_filter}
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """)
            ).all()
            daily_events = [{"date": str(row[0]), "count": row[1]} for row in daily_events_result]

            # Top external link clicks by platform (exclude admin users)
            external_clicks_result = session.execute(
                text(f"""
                SELECT platform, COUNT(*) as count
                FROM analytics_event
                WHERE event_name = 'external_link_click'
                  AND timestamp >= NOW() - INTERVAL '7 days'
                  AND platform IS NOT NULL
                  AND {ev_filter}
                GROUP BY platform
                ORDER BY count DESC
                LIMIT 5
            """)
            ).all()
            external_clicks = [{"platform": row[0], "count": row[1]} for row in external_clicks_result]

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
                "popular_cards": popular_cards,
                "total_events": total_events,
                "events_24h": events_24h,
                "events_7d": events_7d,
                "top_events": top_events,
                "daily_events": daily_events,
                "external_clicks": external_clicks,
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
                "popular_cards": [],
                "total_events": 0,
                "events_24h": 0,
                "events_7d": 0,
                "top_events": [],
                "daily_events": [],
                "external_clicks": [],
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


# ============== USER ACTIVITY (Admin) ==============


@router.get("/users/{user_id}/activity")
async def get_user_activity(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_superuser),
):
    """Get detailed activity for a specific user."""
    from sqlmodel import Session, select, text
    from app.db import engine
    from app.models.user import User as UserModel
    from app.models.analytics import PageView

    with Session(engine) as session:
        # Verify user exists
        user = session.get(UserModel, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get recent page views
        pageviews = session.exec(
            select(PageView)
            .where(PageView.user_id == user_id)
            .order_by(PageView.timestamp.desc())
            .limit(limit)
        ).all()

        # Get top pages for this user
        top_pages_result = session.execute(
            text("""
                SELECT path, COUNT(*) as views
                FROM pageview
                WHERE user_id = :user_id
                GROUP BY path
                ORDER BY views DESC
                LIMIT 10
            """),
            {"user_id": user_id}
        ).all()

        # Get activity by day (last 30 days)
        daily_activity_result = session.execute(
            text("""
                SELECT DATE(timestamp) as date, COUNT(*) as views
                FROM pageview
                WHERE user_id = :user_id
                AND timestamp >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """),
            {"user_id": user_id}
        ).all()

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "username": getattr(user, "username", None),
            },
            "recent_pageviews": [
                {
                    "path": pv.path,
                    "timestamp": pv.timestamp.isoformat(),
                    "device_type": pv.device_type,
                    "referrer": pv.referrer,
                }
                for pv in pageviews
            ],
            "top_pages": [
                {"path": row[0], "views": row[1]}
                for row in top_pages_result
            ],
            "daily_activity": [
                {"date": str(row[0]), "views": row[1]}
                for row in daily_activity_result
            ],
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


@router.get("/blocked-ips")
async def admin_get_blocked_ips(
    current_user: User = Depends(deps.get_current_superuser),
):
    """Get info about blocked IPs (admin only)."""
    return {
        "message": "Blocked IPs are stored in-memory per worker instance.",
        "solution": "Redeploy the application to clear all blocks.",
        "note": "The anti-scraping middleware now checks sec-fetch headers to allow browser requests.",
    }
