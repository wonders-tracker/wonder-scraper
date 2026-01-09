import asyncio
import random
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select
from sqlalchemy import func, text
from sqlalchemy.exc import OperationalError, DisconnectionError, InterfaceError
from app.core.typing import col, ensure_int
from app.core.db_utils import execute_with_retry_async, is_transient_error
from app.core.config import settings
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from app.models.blokpax import BlokpaxStorefront, BlokpaxSnapshot, BlokpaxSale
from scripts.scrape_card import scrape_card as scrape_sold_data
from app.scraper.active import scrape_active_data
from app.scraper.browser import BrowserManager
from app.scraper.blokpax import (
    WOTF_STOREFRONTS,
    get_bpx_price,
    scrape_storefront_floor,
    scrape_recent_sales,
    scrape_preslab_sales,
    scrape_preslab_listings,
    is_wotf_asset,
)
from app.scraper.opensea import (
    OPENSEA_WOTF_COLLECTIONS,
    scrape_opensea_listings_to_db,
    scrape_opensea_sales_to_db,
)
from app.discord_bot.logger import (
    log_scrape_start,
    log_scrape_complete,
    log_scrape_error,
    log_market_insights,
    log_warning,
)
from app.models.market import MarketPrice
from app.core.metrics_persistent import persistent_metrics as scraper_metrics
from app.core.circuit_breaker import CircuitBreakerRegistry
from app.services.meta_sync import sync_all_meta_status
from app.services.task_queue import enqueue_task_sync, get_queue_stats_sync, cleanup_old_tasks_sync
from datetime import datetime, timedelta, timezone
from pathlib import Path

scheduler = AsyncIOScheduler()

# Global lock to prevent browser job collisions
# Only one browser-using job can run at a time to avoid resource conflicts
_browser_job_lock = asyncio.Lock()


async def scrape_single_card(card: Card):
    """Scrape a single card with full data (sold + active)."""
    try:
        search_term = f"{card.name} {card.set_name}"
        print(f"[Polling] Updating: {search_term}")

        # Scrape sold data (creates snapshot)
        await scrape_sold_data(
            card_name=card.name,
            card_id=ensure_int(card.id),
            search_term=search_term,
            set_name=card.set_name,
            product_type=card.product_type if hasattr(card, "product_type") else "Single",
        )

        # Get active data
        low_ask, inventory, high_bid = await scrape_active_data(card.name, ensure_int(card.id), search_term=search_term)

        # Update snapshot with active data (with retry for transient DB failures)
        def update_snapshot(session: Session):
            statement = (
                select(MarketSnapshot)
                .where(MarketSnapshot.card_id == card.id)
                .order_by(col(MarketSnapshot.timestamp).desc())
            )
            snapshot = session.execute(statement).scalars().first()
            if snapshot:
                snapshot.lowest_ask = low_ask
                snapshot.inventory = inventory
                snapshot.highest_bid = high_bid
                session.add(snapshot)
                session.commit()
                return True
            return False

        try:
            updated = await execute_with_retry_async(engine, update_snapshot)
            if updated:
                print(f"[Polling] Updated {card.name}: Ask=${low_ask}, Inv={inventory}")
        except (OperationalError, DisconnectionError, InterfaceError) as db_error:
            print(f"[Polling] DB error updating {card.name} (retries exhausted): {db_error}")
            return False

        return True
    except Exception as e:
        # Distinguish between DB errors and scrape errors for better diagnostics
        error_type = "DB" if is_transient_error(e) else "Scrape"
        print(f"[Polling] {error_type} error updating {card.name}: {e}")
        return False


async def job_update_market_data():
    """
    Optimized polling job - scrapes cards in batches with concurrency control.
    Includes robust error handling for browser startup and database failures.
    """
    # Acquire browser lock to prevent collision with other browser jobs
    if _browser_job_lock.locked():
        print("[Polling] Another browser job is running, skipping this run")
        return

    async with _browser_job_lock:
        await _job_update_market_data_impl()


async def _job_update_market_data_impl():
    """Implementation of market data update (called under lock)."""
    # Check circuit breaker before starting
    ebay_circuit = CircuitBreakerRegistry.get("ebay", failure_threshold=5, recovery_timeout=300.0)
    if not ebay_circuit.allow_request():
        print("[Polling] eBay circuit breaker OPEN - skipping update (recovery in ~5 min)")
        return

    print(f"[{datetime.now(timezone.utc)}] Starting Scheduled Market Update...")
    start_time = time.time()

    # Verify database connection before starting heavy work
    def check_connection(session: Session):
        session.execute(select(func.count(Card.id)))
        return True

    try:
        await execute_with_retry_async(
            engine,
            check_connection,
            max_retries=settings.SCHEDULER_DB_CHECK_MAX_RETRIES,
            base_delay=settings.SCHEDULER_DB_CHECK_BASE_DELAY,
        )
        print("[Polling] Database connection verified")
    except Exception as e:
        print(f"[Polling] CRITICAL: Database connection failed after retries: {e}")
        log_scrape_error("Market Update", f"Database connection failed: {e}")
        return

    # Fetch cards to update (with retry)
    def get_cards_to_update(session: Session):
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

        # Subquery for latest snapshot per card
        latest_snapshots = (
            select(MarketSnapshot.card_id, func.max(MarketSnapshot.timestamp).label("latest_timestamp"))
            .group_by(MarketSnapshot.card_id)
            .subquery()
        )

        # Get cards needing updates
        cards_query = (
            select(Card)
            .outerjoin(latest_snapshots, col(Card.id) == latest_snapshots.c.card_id)
            .where((latest_snapshots.c.latest_timestamp < cutoff_time) | (latest_snapshots.c.latest_timestamp is None))
        )

        # Use .scalars() to get Card objects directly, not Row tuples
        cards = list(session.execute(cards_query).scalars().all())

        # If no stale cards, update a random sample
        if not cards:
            all_cards = list(session.execute(select(Card)).scalars().all())
            cards = random.sample(all_cards, min(settings.SCHEDULER_RANDOM_SAMPLE_SIZE, len(all_cards)))

        return cards

    try:
        cards_to_update = await execute_with_retry_async(engine, get_cards_to_update)
    except Exception as e:
        print(f"[Polling] CRITICAL: Failed to fetch cards: {e}")
        log_scrape_error("Market Update", f"Failed to fetch cards: {e}")
        return

    if not cards_to_update:
        print("[Polling] No cards to update.")
        return

    print(f"[Polling] Updating {len(cards_to_update)} cards...")

    # Record metrics start
    scraper_metrics.record_start("ebay_market_update")

    # Log scrape start to Discord
    log_scrape_start(len(cards_to_update), scrape_type="scheduled")

    # Initialize browser with retry logic
    max_browser_retries = settings.SCHEDULER_MAX_BROWSER_RETRIES
    browser_started = False

    for attempt in range(max_browser_retries):
        try:
            print(f"[Polling] Browser startup attempt {attempt + 1}/{max_browser_retries}...")
            await BrowserManager.get_browser()
            browser_started = True
            print("[Polling] Browser started successfully!")
            break
        except Exception as e:
            print(f"[Polling] Browser startup failed (attempt {attempt + 1}): {type(e).__name__}: {e}")
            # Clean up any partial state
            await BrowserManager.close()
            if attempt < max_browser_retries - 1:
                wait_time = (attempt + 1) * settings.SCHEDULER_BROWSER_RETRY_BASE_DELAY
                print(f"[Polling] Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

    if not browser_started:
        print("[Polling] ERROR: Could not start browser after all retries. Skipping this update cycle.")
        return

    try:
        # Process cards with controlled concurrency
        # Batch size configured via settings (matches 2x browser semaphore)
        batch_size = settings.SCHEDULER_CARD_BATCH_SIZE
        successful = 0
        failed = 0
        db_errors = 0
        consecutive_db_failures = 0
        consecutive_scrape_failures = 0  # Circuit breaker for eBay blocking
        max_consecutive_db_failures = settings.SCHEDULER_MAX_DB_FAILURES
        max_consecutive_scrape_failures = settings.SCHEDULER_MAX_SCRAPE_FAILURES

        for i in range(0, len(cards_to_update), batch_size):
            batch = cards_to_update[i : i + batch_size]

            # Periodically verify DB connection is still healthy
            if i > 0 and i % settings.SCHEDULER_CONNECTION_CHECK_INTERVAL == 0:
                try:
                    await execute_with_retry_async(engine, check_connection, max_retries=2)
                    print(f"[Polling] Connection verified at batch {i // batch_size}")
                    consecutive_db_failures = 0  # Reset on success
                except Exception as e:
                    print(f"[Polling] WARNING: Connection check failed at batch {i // batch_size}: {e}")
                    consecutive_db_failures += 1
                    if consecutive_db_failures >= max_consecutive_db_failures:
                        print("[Polling] CRITICAL: Too many consecutive DB failures, aborting job")
                        log_scrape_error("Market Update", f"Aborted: {consecutive_db_failures} consecutive DB failures")
                        break

            # Process batch concurrently
            tasks = [scrape_single_card(card) for card in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successes/failures with detailed error tracking
            batch_db_errors = 0
            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                    if is_transient_error(result):
                        db_errors += 1
                        batch_db_errors += 1
                elif result:
                    successful += 1
                    consecutive_db_failures = 0  # Reset on any success
                else:
                    failed += 1

            # Track consecutive DB failures
            if batch_db_errors == len(batch):
                consecutive_db_failures += 1
                if consecutive_db_failures >= max_consecutive_db_failures:
                    print("[Polling] CRITICAL: All cards in batch had DB errors, aborting job")
                    log_scrape_error(
                        "Market Update", f"Aborted: {consecutive_db_failures} consecutive batch DB failures"
                    )
                    break

            # Circuit breaker: detect eBay blocking (all scrapes failed, no DB errors)
            batch_scrape_failures = len(
                [r for r in results if r is False or (isinstance(r, Exception) and not is_transient_error(r))]
            )
            if batch_scrape_failures == len(batch) and batch_db_errors == 0:
                consecutive_scrape_failures += 1
                print(
                    f"[Polling] WARNING: Entire batch failed scraping "
                    f"({consecutive_scrape_failures}/{max_consecutive_scrape_failures})"
                )
                if consecutive_scrape_failures >= max_consecutive_scrape_failures:
                    print("[Polling] CIRCUIT BREAKER: eBay likely blocking us, aborting job early")
                    # Record failure with circuit breaker - will trip after threshold
                    ebay_circuit.record_failure()
                    log_warning(
                        "🔴 eBay Scraper Blocked",
                        f"Market update aborted after {consecutive_scrape_failures} consecutive batch failures.\n"
                        f"Progress: {successful}/{len(cards_to_update)} cards successful.\n"
                        f"Circuit breaker state: {ebay_circuit.state.value}\n"
                        "eBay may be rate-limiting or blocking our requests.",
                    )
                    break
            else:
                consecutive_scrape_failures = 0  # Reset on any success
                ebay_circuit.record_success()  # Record success with circuit breaker

            # Brief delay between batches
            if i + batch_size < len(cards_to_update):
                await asyncio.sleep(settings.SCHEDULER_BATCH_DELAY)

        # Detailed results
        total_cards = len(cards_to_update)
        print(f"[Polling] Results: {successful}/{total_cards} successful, {failed} failed ({db_errors} DB errors)")

        # Alert if high DB error rate
        high_error_rate = db_errors > failed * settings.SCHEDULER_DB_ERROR_RATE_THRESHOLD
        if high_error_rate and db_errors > settings.SCHEDULER_DB_ERROR_MIN_COUNT:
            log_warning(
                "⚠️ High DB Error Rate",
                f"Market update had {db_errors} database errors out of {failed} total failures.\n"
                "This may indicate Neon connection issues or resource exhaustion.",
            )

        # Log scrape complete to Discord
        duration = time.time() - start_time
        log_scrape_complete(
            cards_processed=total_cards,
            new_listings=0,  # Scheduled scrapes don't track new listings separately
            new_sales=0,
            duration_seconds=duration,
            errors=failed,
        )

        # Record metrics
        scraper_metrics.record_complete(
            "ebay_market_update",
            cards_processed=total_cards,
            successful=successful,
            failed=failed,
            db_errors=db_errors,
        )

    except Exception as e:
        print(f"[Polling] ERROR during scraping: {type(e).__name__}: {e}")
        log_scrape_error("Scheduled Job", str(e))
        # Record failed metrics
        scraper_metrics.record_complete(
            "ebay_market_update",
            cards_processed=0,
            successful=0,
            failed=1,
            db_errors=0,
        )

    finally:
        await BrowserManager.close()

    print(f"[{datetime.now(timezone.utc)}] Scheduled Update Complete.")


async def job_update_blokpax_data():
    """
    Scheduled job to update Blokpax floor prices and sales.
    Runs on a separate interval from eBay since it's lightweight (API-based).
    """
    # Acquire browser lock (OpenSea scraping needs browser)
    if _browser_job_lock.locked():
        print("[Blokpax] Another browser job is running, skipping this run")
        return

    async with _browser_job_lock:
        await _job_update_blokpax_data_impl()


async def _job_update_blokpax_data_impl():
    """Implementation of Blokpax/OpenSea update (called under lock)."""
    # Check circuit breakers before starting
    blokpax_circuit = CircuitBreakerRegistry.get("blokpax", failure_threshold=3, recovery_timeout=600.0)
    opensea_circuit = CircuitBreakerRegistry.get("opensea", failure_threshold=3, recovery_timeout=600.0)

    print(f"[{datetime.now(timezone.utc)}] Starting Blokpax Update...")
    start_time = time.time()

    scraper_metrics.record_start("blokpax_opensea_update")
    log_scrape_start(len(WOTF_STOREFRONTS), scrape_type="blokpax")

    errors = 0
    total_sales = 0
    total_listings = 0  # Initialize outside try block to avoid UnboundLocalError

    try:
        bpx_price = await get_bpx_price()
        print(f"[Blokpax] BPX Price: ${bpx_price:.6f} USD")

        for slug in WOTF_STOREFRONTS:
            if not blokpax_circuit.allow_request():
                print("[Blokpax] Circuit breaker OPEN, skipping remaining storefronts")
                break
            try:
                # Scrape floor prices with deep_scan=True to actually compute floor from listings
                # Without deep_scan, only metadata is fetched and floor_price stays stale
                floor_data = await scrape_storefront_floor(slug, deep_scan=True)
                floor_bpx = floor_data.get("floor_price_bpx")
                floor_usd = floor_data.get("floor_price_usd")
                listed = floor_data.get("listed_count", 0)
                total = floor_data.get("total_tokens", 0)

                print(
                    f"[Blokpax] {slug}: Floor={floor_bpx:,.0f} BPX (${floor_usd:.2f})"
                    if floor_bpx
                    else f"[Blokpax] {slug}: No listings"
                )

                # Save snapshot
                with Session(engine) as session:
                    snapshot = BlokpaxSnapshot(
                        storefront_slug=slug,
                        floor_price_bpx=floor_bpx,
                        floor_price_usd=floor_usd,
                        bpx_price_usd=bpx_price,
                        listed_count=listed,
                        total_tokens=total,
                    )
                    session.add(snapshot)

                    # Update storefront record
                    storefront = (
                        session.execute(select(BlokpaxStorefront).where(BlokpaxStorefront.slug == slug))
                        .scalars()
                        .first()
                    )
                    if storefront:
                        storefront.floor_price_bpx = floor_bpx
                        storefront.floor_price_usd = floor_usd
                        storefront.listed_count = listed
                        storefront.total_tokens = total
                        storefront.updated_at = datetime.now(timezone.utc)
                        session.add(storefront)

                    session.commit()

                # Scrape recent sales (limit pages for scheduled runs)
                sales = await scrape_recent_sales(slug, max_pages=2)
                if slug == "reward-room":
                    sales = [s for s in sales if is_wotf_asset(s.asset_name)]

                # Save sales to database (deduplicate by listing_id)
                if sales:
                    with Session(engine) as sale_session:
                        saved_count = 0
                        for sale in sales:
                            # Check if already exists
                            existing = sale_session.exec(
                                select(BlokpaxSale).where(BlokpaxSale.listing_id == sale.listing_id)
                            ).first()
                            if not existing:
                                db_sale = BlokpaxSale(
                                    listing_id=sale.listing_id,
                                    asset_id=sale.asset_id,
                                    asset_name=sale.asset_name,
                                    price_bpx=sale.price_bpx,
                                    price_usd=sale.price_usd,
                                    quantity=sale.quantity,
                                    seller_address=sale.seller_address or "",
                                    buyer_address=sale.buyer_address or "",
                                    treatment=sale.treatment,
                                    filled_at=sale.filled_at,
                                )
                                sale_session.add(db_sale)
                                saved_count += 1
                        sale_session.commit()
                        if saved_count > 0:
                            print(f"[Blokpax] Saved {saved_count} new sales from {slug}")

                total_sales += len(sales)

                blokpax_circuit.record_success()
                await asyncio.sleep(1)

            except Exception as e:
                blokpax_circuit.record_failure()
                print(f"[Blokpax] Error on {slug}: {e}")
                errors += 1

        # Scrape preslab sales and link to cards
        try:
            with Session(engine) as session:
                processed, matched, saved = await scrape_preslab_sales(session, max_pages=5)
                total_sales += saved
                print(f"[Blokpax] Preslab sales: {saved} new sales linked to cards")
        except Exception as e:
            print(f"[Blokpax] Error scraping preslab sales: {e}")
            errors += 1

        # Scrape preslab active listings and sync to marketprice
        try:
            with Session(engine) as session:
                processed, matched, saved = await scrape_preslab_listings(session, save_to_db=True)
                total_listings = saved
                print(f"[Blokpax] Preslab listings: {saved} active listings synced to marketprice")
        except Exception as e:
            print(f"[Blokpax] Error scraping preslab listings: {e}")
            errors += 1

    except Exception as e:
        print(f"[Blokpax] Fatal error: {e}")
        log_scrape_error("Blokpax Scheduled", str(e))
        errors += 1

    # ===== OpenSea Listings + Sales =====
    opensea_listings = 0
    opensea_sales = 0
    if not opensea_circuit.allow_request():
        print("[OpenSea] Circuit breaker OPEN, skipping")
    else:
        try:
            print(f"[{datetime.now(timezone.utc)}] Scraping OpenSea Listings + Sales...")

            # Ensure browser is in clean state before OpenSea (may have stale state from eBay)
            try:
                await BrowserManager.close()
                await asyncio.sleep(2)
            except (asyncio.TimeoutError, RuntimeError, OSError):
                # Browser cleanup can fail if already closed or crashed - safe to ignore
                pass

            with Session(engine) as session:
                for collection_slug, card_name in OPENSEA_WOTF_COLLECTIONS.items():
                    try:
                        # Find the card in DB
                        card = session.execute(select(Card).where(Card.name == card_name)).scalars().first()

                        if not card:
                            print(f"[OpenSea] Card '{card_name}' not found in DB, skipping")
                            continue

                        card_id = ensure_int(card.id)

                        # Scrape active listings
                        scraped, saved = await scrape_opensea_listings_to_db(
                            session, collection_slug, card_id, card_name
                        )
                        opensea_listings += saved

                        # Scrape sales history (price history for NFTs)
                        sales_scraped, sales_saved = await scrape_opensea_sales_to_db(
                            session, collection_slug, card_id, card_name
                        )
                        opensea_sales += sales_saved

                        opensea_circuit.record_success()

                    except Exception as e:
                        opensea_circuit.record_failure()
                        print(f"[OpenSea] Error scraping {collection_slug}: {e}")
                        errors += 1
                        continue

            print(f"[OpenSea] Active listings: {opensea_listings}, Sales: {opensea_sales} synced to marketprice")

        except Exception as e:
            print(f"[OpenSea] Fatal error: {e}")
            log_scrape_error("OpenSea Scheduled", str(e))
            errors += 1
        finally:
            # Clean up browser after OpenSea scraping
            try:
                await BrowserManager.close()
            except (asyncio.TimeoutError, RuntimeError, OSError):
                # Browser cleanup can fail if already closed or crashed - safe to ignore
                pass

    total_listings += opensea_listings
    total_sales += opensea_sales

    duration = time.time() - start_time
    total_processed = len(WOTF_STOREFRONTS) + len(OPENSEA_WOTF_COLLECTIONS)

    log_scrape_complete(
        cards_processed=total_processed,
        new_listings=total_listings,
        new_sales=total_sales,
        duration_seconds=duration,
        errors=errors,
    )

    # Record metrics
    scraper_metrics.record_complete(
        "blokpax_opensea_update",
        cards_processed=total_processed,
        successful=total_processed - errors,
        failed=errors,
        db_errors=0,
    )

    print(
        f"[{datetime.now(timezone.utc)}] NFT Update Complete. "
        f"Duration: {duration:.1f}s, Listings: {total_listings}, Sales: {total_sales}"
    )


async def job_send_daily_digests():
    """
    Send daily market digest emails to users who have opted in.
    Runs once daily at 9 AM UTC.
    """
    print(f"[{datetime.now(timezone.utc)}] Sending Daily Digest Emails...")

    try:
        from app.models.watchlist import EmailPreferences
        from app.models.user import User
        from app.services.email import send_daily_market_digest
        from app.services.market_insights import get_insights_generator

        with Session(engine) as session:
            # Get users who want daily digests
            prefs = (
                session.execute(select(EmailPreferences).where(EmailPreferences.daily_digest == True)).scalars().all()
            )

            if not prefs:
                print("[Digest] No users subscribed to daily digest")
                return

            # Gather market data once for all users
            generator = get_insights_generator()
            data = generator.gather_market_data(days=1)

            # Format for email
            market_data = {
                "total_sales": data.get("total_sales", 0),
                "total_volume": data.get("total_volume", 0),
                "market_sentiment": "bullish"
                if data.get("volume_change", 0) > 10
                else "bearish"
                if data.get("volume_change", 0) < -10
                else "neutral",
                "top_gainers": data.get("top_gainers", []),
                "top_losers": data.get("top_losers", []),
                "hot_deals": data.get("hot_deals", []),
            }

            sent_count = 0
            for pref in prefs:
                user = session.get(User, pref.user_id)
                if user and user.email:
                    try:
                        name = user.username or user.email.split("@")[0]
                        success = send_daily_market_digest(user.email, name, market_data)
                        if success:
                            sent_count += 1
                    except Exception as e:
                        print(f"[Digest] Failed to send to {user.email}: {e}")

            print(f"[Digest] Sent daily digest to {sent_count} users")

    except Exception as e:
        print(f"[Digest] Error sending daily digests: {e}")


async def job_send_personal_welcome_emails():
    """
    Send personal welcome emails from founder to users who signed up 24-48h ago.
    Runs once daily at 10 AM UTC.
    """
    print(f"[{datetime.now(timezone.utc)}] Checking for Personal Welcome Emails...")

    try:
        from app.models.user import User
        from app.services.email import send_personal_welcome_email

        with Session(engine) as session:
            # Find users who signed up 24-48 hours ago and haven't received the personal welcome
            now = datetime.now(timezone.utc)
            cutoff_start = now - timedelta(hours=48)  # Oldest eligible
            cutoff_end = now - timedelta(hours=24)  # Newest eligible

            users = (
                session.execute(
                    select(User).where(
                        User.created_at >= cutoff_start,
                        User.created_at <= cutoff_end,
                        User.personal_welcome_sent_at == None,  # noqa: E711
                        User.is_active == True,  # noqa: E712
                    )
                )
                .scalars()
                .all()
            )

            if not users:
                print("[Personal Welcome] No eligible users")
                return

            sent_count = 0
            for user in users:
                try:
                    name = user.username or user.email.split("@")[0]
                    success = send_personal_welcome_email(user.email, name)
                    if success:
                        user.personal_welcome_sent_at = now
                        session.add(user)
                        sent_count += 1
                except Exception as e:
                    print(f"[Personal Welcome] Failed to send to {user.email}: {e}")

            session.commit()
            print(f"[Personal Welcome] Sent to {sent_count} users")

    except Exception as e:
        print(f"[Personal Welcome] Error: {e}")


async def job_send_weekly_reports():
    """
    Send weekly market report emails to users who have opted in.
    Runs once weekly on Monday at 9 AM UTC.
    """
    print(f"[{datetime.now(timezone.utc)}] Sending Weekly Report Emails...")

    try:
        from app.models.watchlist import EmailPreferences
        from app.models.user import User
        from app.services.email import send_weekly_market_report
        from app.services.market_insights import get_insights_generator

        with Session(engine) as session:
            # Get users who want weekly reports
            prefs = (
                session.execute(select(EmailPreferences).where(EmailPreferences.weekly_report == True)).scalars().all()
            )

            if not prefs:
                print("[Weekly] No users subscribed to weekly report")
                return

            # Gather market data for the week
            generator = get_insights_generator()
            data = generator.gather_market_data(days=7)

            # Format for email
            week_end = datetime.now(timezone.utc)
            week_start = week_end - timedelta(days=7)

            report_data = {
                "week_start": week_start.strftime("%b %d"),
                "week_end": week_end.strftime("%b %d"),
                "total_sales": data.get("total_sales", 0),
                "total_volume": data.get("total_volume", 0),
                "volume_change": data.get("volume_change", 0),
                "avg_sale_price": data.get("avg_price", 0),
                "daily_breakdown": data.get("daily_breakdown", []),
                "top_cards_by_volume": data.get("top_cards", []),
                "price_movers": data.get("price_movers", []),
                "market_health": {
                    "unique_buyers": data.get("unique_buyers", 0),
                    "unique_sellers": data.get("unique_sellers", 0),
                    "liquidity_score": data.get("liquidity_score", 0),
                },
            }

            sent_count = 0
            for pref in prefs:
                user = session.get(User, pref.user_id)
                if user and user.email:
                    try:
                        name = user.username or user.email.split("@")[0]
                        success = send_weekly_market_report(user.email, name, report_data)
                        if success:
                            sent_count += 1
                    except Exception as e:
                        print(f"[Weekly] Failed to send to {user.email}: {e}")

            print(f"[Weekly] Sent weekly report to {sent_count} users")

    except Exception as e:
        print(f"[Weekly] Error sending weekly reports: {e}")


async def job_check_price_alerts():
    """
    Check watchlist price alerts and send notifications.
    Runs every 30 minutes.
    """
    print(f"[{datetime.now(timezone.utc)}] Checking Price Alerts...")

    try:
        from app.models.watchlist import Watchlist
        from app.models.user import User
        from app.models.card import Card
        from app.services.email import send_price_alert

        with Session(engine) as session:
            # Get all active alerts with target prices
            alerts = (
                session.execute(
                    select(Watchlist).where(
                        Watchlist.alert_enabled == True,
                        Watchlist.target_price != None,
                        Watchlist.notify_email == True,
                    )
                )
                .scalars()
                .all()
            )

            if not alerts:
                print("[Alerts] No active price alerts")
                return

            sent_count = 0
            for alert in alerts:
                card = session.get(Card, alert.card_id)
                user = session.get(User, alert.user_id)

                if not card or not user:
                    continue

                # floor_price/latest_price are computed fields, not on Card model
                # Use getattr to safely access (will return None if not present)
                current_price: float = float(
                    getattr(card, "floor_price", None) or getattr(card, "latest_price", None) or 0
                )
                target_price: float = float(alert.target_price or 0)

                # Skip if already alerted at this price
                if alert.last_alerted_price and abs(current_price - alert.last_alerted_price) < 0.01:
                    continue

                # Check if alert should trigger
                should_alert = False
                if alert.alert_type == "below" and current_price <= target_price:
                    should_alert = True
                elif alert.alert_type == "above" and current_price >= target_price:
                    should_alert = True
                elif alert.alert_type == "any":
                    should_alert = True

                # Cooldown: don't alert more than once per hour per card
                if alert.last_alerted_at:
                    time_since_last = datetime.now(timezone.utc) - alert.last_alerted_at
                    if time_since_last.total_seconds() < 3600:
                        continue

                if should_alert:
                    name = user.username or user.email.split("@")[0]
                    alert_data = {
                        "card_name": card.name,
                        "card_slug": card.slug,
                        "alert_type": alert.alert_type,
                        "target_price": alert.target_price,
                        "current_price": current_price,
                        "treatment": alert.treatment or "Any Treatment",
                    }

                    success = send_price_alert(user.email, name, alert_data)
                    if success:
                        sent_count += 1
                        # Update alert tracking
                        alert.last_alerted_at = datetime.now(timezone.utc)
                        alert.last_alerted_price = current_price
                        session.add(alert)

            session.commit()
            print(f"[Alerts] Sent {sent_count} watchlist price alerts")

        # Also check PriceAlert model alerts
        from app.models.price_alert import PriceAlert, AlertStatus, AlertType
        from app.services.floor_price import get_floor_price_service

        with Session(engine) as session:
            # Get all active PriceAlert alerts
            price_alerts = (
                session.execute(
                    select(PriceAlert).where(
                        PriceAlert.status == AlertStatus.ACTIVE,
                    )
                )
                .scalars()
                .all()
            )

            if not price_alerts:
                print("[Alerts] No active PriceAlert alerts")
                return

            floor_service = get_floor_price_service(session)
            price_alert_sent = 0

            for alert in price_alerts:
                card = session.get(Card, alert.card_id)
                user = session.get(User, alert.user_id)

                if not card or not user:
                    continue

                # Get current floor price
                floor_result = floor_service.get_floor_price(alert.card_id, treatment=alert.treatment, days=30)
                current_price = floor_result.price

                if current_price is None:
                    continue

                # Check if alert should trigger
                should_trigger = False
                if alert.alert_type == AlertType.BELOW and current_price <= alert.target_price:
                    should_trigger = True
                elif alert.alert_type == AlertType.ABOVE and current_price >= alert.target_price:
                    should_trigger = True

                if should_trigger:
                    name = user.username or user.email.split("@")[0]
                    alert_data = {
                        "card_name": card.name,
                        "card_slug": card.slug,
                        "alert_type": alert.alert_type.value,
                        "target_price": alert.target_price,
                        "current_price": current_price,
                        "treatment": alert.treatment or "Any Treatment",
                    }

                    success = send_price_alert(user.email, name, alert_data)
                    if success:
                        price_alert_sent += 1
                        # Mark alert as triggered
                        alert.status = AlertStatus.TRIGGERED
                        alert.triggered_at = datetime.now(timezone.utc)
                        alert.triggered_price = current_price
                        alert.notification_sent = True
                        alert.notification_sent_at = datetime.now(timezone.utc)
                        session.add(alert)

            session.commit()
            print(f"[Alerts] Sent {price_alert_sent} PriceAlert notifications")

    except Exception as e:
        print(f"[Alerts] Error checking price alerts: {e}")


async def _fetch_seller_for_item(browser, item_id: str, mp_id: int, session) -> tuple[bool, str]:
    """
    Helper to fetch seller data for a single item using shared browser.
    Returns (success: bool, reason: str).
    """
    from app.scraper.seller import extract_seller_from_html

    tab = None
    try:
        tab = await browser.new_tab()
        item_url = f"https://www.ebay.com/itm/{item_id}"
        await tab.go_to(item_url, timeout=30)
        await asyncio.sleep(2)

        result = await asyncio.wait_for(
            tab.execute_script("return document.documentElement.outerHTML;", return_by_value=True),
            timeout=30,
        )

        html = None
        if isinstance(result, dict):
            inner = result.get("result", {})
            if isinstance(inner, dict):
                html = inner.get("result", {}).get("value")

        if not html:
            return False, "no_html"

        if "Pardon Our Interruption" in html or "Security Measure" in html:
            return False, "blocked"

        seller_name, feedback_score, feedback_percent = extract_seller_from_html(html)

        if seller_name:
            session.execute(
                text("""
                UPDATE marketprice
                SET seller_name = :seller,
                    seller_feedback_score = :score,
                    seller_feedback_percent = :pct
                WHERE id = :id
            """),
                {"seller": seller_name, "score": feedback_score, "pct": feedback_percent, "id": mp_id},
            )
            session.commit()
            return True, "success"
        else:
            return False, "no_seller"

    except asyncio.TimeoutError:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:30]
    finally:
        if tab:
            try:
                await tab.close()
            except (asyncio.TimeoutError, Exception):
                # Tab close can fail if browser crashed - safe to ignore
                pass


async def job_seller_priority_queue():
    """
    Priority job to fetch seller data for NEW listings (added in last 6 hours).
    Runs hourly to ensure new listings get seller data quickly.

    Uses shared BrowserManager for resource efficiency.
    """
    # Acquire browser lock to prevent collision with other browser jobs
    if _browser_job_lock.locked():
        print("[Seller Priority] Another browser job is running, skipping this run")
        return

    async with _browser_job_lock:
        await _job_seller_priority_queue_impl()


async def _job_seller_priority_queue_impl():
    """Implementation of seller priority queue (called under lock)."""
    print(f"[{datetime.now(timezone.utc)}] Starting Seller Priority Queue...")

    try:
        import re

        # Find new listings (added in last 6 hours) missing seller data
        with Session(engine) as session:
            query = text("""
                SELECT id, external_id, url, title
                FROM marketprice
                WHERE seller_name IS NULL
                AND platform = 'ebay'
                AND listing_type = 'active'
                AND listed_at >= NOW() - INTERVAL '6 hours'
                AND (url IS NOT NULL OR external_id IS NOT NULL)
                ORDER BY listed_at DESC
                LIMIT 50
            """)

            results = session.execute(query).all()

            if not results:
                print("[Seller Priority] No new listings need seller data")
                return

            print(f"[Seller Priority] Processing {len(results)} new listings...")

            # Use shared browser manager
            browser = await BrowserManager.get_browser()

            updated = 0
            failed = 0
            blocked = False

            for mp_id, external_id, url, title in results:
                item_id = external_id
                if not item_id and url:
                    match = re.search(r"/itm/(?:[^/]+/)?(\d+)", url)
                    if match:
                        item_id = match.group(1)

                if not item_id:
                    failed += 1
                    continue

                success, reason = await _fetch_seller_for_item(browser, item_id, mp_id, session)

                if success:
                    updated += 1
                else:
                    failed += 1
                    if reason == "blocked":
                        print("[Seller Priority] Blocked by eBay, stopping early")
                        blocked = True
                        break

                await asyncio.sleep(1.5)

            print(f"[Seller Priority] Complete: {updated} updated, {failed} failed" + (" (blocked)" if blocked else ""))

    except Exception as e:
        print(f"[Seller Priority] Fatal error: {e}")
        log_scrape_error("Seller Priority Queue", str(e))
    finally:
        # Always close browser to prevent resource leaks
        try:
            await BrowserManager.close()
        except (asyncio.TimeoutError, RuntimeError, OSError):
            pass


async def job_backfill_seller_data():
    """
    Background job to backfill missing seller data from eBay item pages.
    Runs every 4 hours, processing up to 100 items per run.

    Uses shared BrowserManager for resource efficiency.
    Handles backlog while job_seller_priority_queue handles new listings.
    """
    # Acquire browser lock to prevent collision with other browser jobs
    if _browser_job_lock.locked():
        print("[Seller Backfill] Another browser job is running, skipping this run")
        return

    async with _browser_job_lock:
        await _job_backfill_seller_data_impl()


async def _job_backfill_seller_data_impl():
    """Implementation of seller backfill (called under lock)."""
    print(f"[{datetime.now(timezone.utc)}] Starting Seller Data Backfill...")

    try:
        import re

        with Session(engine) as session:
            # Get listings missing seller data (exclude recent ones handled by priority queue)
            query = text("""
                SELECT id, external_id, url, title
                FROM marketprice
                WHERE seller_name IS NULL
                AND platform = 'ebay'
                AND (url IS NOT NULL OR external_id IS NOT NULL)
                AND (listed_at IS NULL OR listed_at < NOW() - INTERVAL '6 hours')
                ORDER BY
                    CASE WHEN listing_type = 'active' THEN 0 ELSE 1 END,
                    scraped_at DESC
                LIMIT 100
            """)

            results = session.execute(query).all()

            if not results:
                print("[Seller] No items to backfill")
                return

            print(f"[Seller] Found {len(results)} items to process")

            # Use shared browser manager
            browser = await BrowserManager.get_browser()

            updated = 0
            failed = 0
            blocked = False

            for mp_id, external_id, url, title in results:
                item_id = external_id
                if not item_id and url:
                    match = re.search(r"/itm/(?:[^/]+/)?(\d+)", url)
                    if match:
                        item_id = match.group(1)

                if not item_id:
                    failed += 1
                    continue

                success, reason = await _fetch_seller_for_item(browser, item_id, mp_id, session)

                if success:
                    updated += 1
                else:
                    failed += 1
                    if reason == "blocked":
                        print("[Seller] Blocked by eBay, stopping early")
                        blocked = True
                        break

                # Rate limit
                await asyncio.sleep(1)

            blocked_suffix = " (blocked)" if blocked else ""
            print(
                f"[{datetime.now(timezone.utc)}] Seller Backfill Complete: "
                f"{updated} updated, {failed} failed{blocked_suffix}"
            )

    except Exception as e:
        print(f"[Seller] Fatal error: {e}")
        log_scrape_error("Seller Backfill", str(e))
    finally:
        # Always close browser to prevent resource leaks
        try:
            await BrowserManager.close()
        except (asyncio.TimeoutError, RuntimeError, OSError):
            pass


async def job_market_insights():
    """
    Generate and post AI-powered market insights to Discord.
    Runs 2x daily (morning and evening).
    """
    print(f"[{datetime.now(timezone.utc)}] Generating Market Insights...")

    try:
        from app.services.market_insights import get_insights_generator

        generator = get_insights_generator()

        # Gather market data
        data = generator.gather_market_data()

        # Generate AI insights
        insights = generator.generate_insights(data)

        # Post to Discord
        success = log_market_insights(insights)

        if success:
            print(f"[{datetime.now(timezone.utc)}] Market insights posted to Discord")
        else:
            print(f"[{datetime.now(timezone.utc)}] Failed to post market insights")

    except Exception as e:
        print(f"[{datetime.now(timezone.utc)}] Market insights error: {e}")
        log_scrape_error("Market Insights", str(e))


async def job_scraper_health_check():
    """
    Check scraper health - alert on issues.

    Alerts on:
    1. Zero sold listings in 24h (critical)
    2. Less than 10 sold in 24h (warning - might be a partial failure)
    3. Zero active listings in 24h (critical)
    4. Multi-day gaps in scraping (checks last 7 days)

    This would have caught the Dec 19-30 gap where the sold scraper failed.
    Runs every 4 hours to detect issues early.
    """
    print(f"[{datetime.now(timezone.utc)}] Running scraper health check...")

    try:
        with Session(engine) as session:
            now = datetime.now(timezone.utc)
            cutoff_24h = now - timedelta(hours=24)

            # Count sold listings in last 24h
            sold_count_24h = (
                session.execute(
                    select(func.count(MarketPrice.id)).where(
                        MarketPrice.listing_type == "sold", MarketPrice.scraped_at >= cutoff_24h
                    )
                ).scalar()
                or 0
            )

            # Count active listings in last 24h
            active_count_24h = (
                session.execute(
                    select(func.count(MarketPrice.id)).where(
                        MarketPrice.listing_type == "active", MarketPrice.scraped_at >= cutoff_24h
                    )
                ).scalar()
                or 0
            )

            print(f"[Health] Last 24h: {sold_count_24h} sold, {active_count_24h} active")

            # Check for multi-day gaps in sold scraping (last 7 days)
            days_with_scrapes = []
            for days_ago in range(7):
                day_start = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)

                day_count = (
                    session.execute(
                        select(func.count(MarketPrice.id)).where(
                            MarketPrice.listing_type == "sold",
                            MarketPrice.scraped_at >= day_start,
                            MarketPrice.scraped_at < day_end,
                        )
                    ).scalar()
                    or 0
                )

                days_with_scrapes.append((day_start.strftime("%b %d"), day_count))

            # Find consecutive gaps
            gap_days = [d for d, c in days_with_scrapes if c == 0]
            low_volume_days = [d for d, c in days_with_scrapes if 0 < c < 10]

            # Build status report
            status_lines = [f"**{d}:** {c}" for d, c in days_with_scrapes]
            status_report = "\n".join(status_lines)

            # Determine alert level
            if sold_count_24h == 0 and active_count_24h == 0:
                # Critical - both scrapers are broken
                log_warning(
                    "🚨 Scraper Health Critical",
                    "Both sold and active scrapers appear to be broken!\n\n"
                    f"**Sold (24h):** {sold_count_24h}\n"
                    f"**Active (24h):** {active_count_24h}\n\n"
                    f"**Last 7 days:**\n{status_report}\n\n"
                    "Check server logs and Railway deployment status.",
                )
            elif sold_count_24h == 0:
                # Sold scraper down
                log_warning(
                    "🔴 Sold Scraper Down",
                    f"No sold listings scraped in the last 24 hours.\n\n"
                    f"**Sold (24h):** {sold_count_24h}\n"
                    f"**Active (24h):** {active_count_24h}\n\n"
                    f"**Last 7 days:**\n{status_report}\n\n"
                    "This may indicate a browser crash, eBay blocking, or scheduler issue.",
                )
            elif sold_count_24h < 10:
                # Low volume warning
                log_warning(
                    "⚠️ Sold Scraper Low Volume",
                    f"Only {sold_count_24h} sold listings scraped in 24 hours (expected 20+).\n\n"
                    f"**Sold (24h):** {sold_count_24h}\n"
                    f"**Active (24h):** {active_count_24h}\n\n"
                    f"**Last 7 days:**\n{status_report}\n\n"
                    "The scraper may be partially failing or running infrequently.",
                )
            elif len(gap_days) >= 2:
                # Multi-day gap detected
                log_warning(
                    "⚠️ Scraper Gap Detected",
                    f"Found {len(gap_days)} days with zero sold scrapes in the last 7 days.\n\n"
                    f"**Gap days:** {', '.join(gap_days)}\n\n"
                    f"**Last 7 days:**\n{status_report}\n\n"
                    "This suggests the scraper was down intermittently.",
                )
            elif active_count_24h == 0:
                # Active scraper down
                log_warning(
                    "🔴 Active Scraper Down",
                    f"No active listings scraped in the last 24 hours.\n\n"
                    f"**Sold (24h):** {sold_count_24h}\n"
                    f"**Active (24h):** {active_count_24h}\n\n"
                    "This may indicate a browser crash or eBay blocking.",
                )
            else:
                print(f"[Health] Scrapers healthy. Gap days: {len(gap_days)}, Low days: {len(low_volume_days)}")

            # Check seller data coverage for active listings
            seller_coverage = session.execute(
                text("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(seller_name) FILTER (WHERE seller_name IS NOT NULL) as with_seller
                    FROM marketprice
                    WHERE listing_type = 'active' AND platform = 'ebay'
                """)
            ).fetchone()

            if seller_coverage and seller_coverage[0] > 0:
                coverage_pct = (seller_coverage[1] / seller_coverage[0]) * 100
                print(f"[Health] Seller coverage: {coverage_pct:.1f}% ({seller_coverage[1]}/{seller_coverage[0]})")

                # Alert if coverage drops below 50%
                if coverage_pct < 50:
                    log_warning(
                        "⚠️ Low Seller Data Coverage",
                        f"Only {coverage_pct:.1f}% of active listings have seller data.\n\n"
                        f"**With seller:** {seller_coverage[1]}\n"
                        f"**Total active:** {seller_coverage[0]}\n\n"
                        "The seller backfill jobs may be failing or blocked by eBay.",
                    )

    except Exception as e:
        print(f"[Health] Error during health check: {e}")
        log_scrape_error("Health Check", str(e))


async def job_sync_meta_status():
    """
    Sync is_meta field for cards based on user votes.
    Lightweight job - only updates cards with vote changes.
    """
    print("[Meta] Starting meta status sync...")
    try:
        stats = sync_all_meta_status()
        print(f"[Meta] Sync complete: {stats['updated']} updated, {stats['unchanged']} unchanged")
    except Exception as e:
        print(f"[Meta] Error during sync: {e}")
        log_scrape_error("Meta Sync", str(e))


async def job_enqueue_stale_cards():
    """
    Enqueue stale cards to the persistent task queue for worker processing.

    This job runs every 30 minutes and adds cards needing updates to the
    task queue. A separate worker process (run_task_queue_worker.py) then
    processes these tasks with crash resilience.

    Benefits over inline processing:
    - Crash recovery: tasks survive worker restarts
    - Distributed processing: multiple workers can claim tasks
    - Priority handling: high-priority cards processed first
    - Retry logic: failed tasks automatically retry up to max_attempts
    """
    print(f"[{datetime.now(timezone.utc)}] Enqueuing stale cards to task queue...")

    try:
        with Session(engine) as session:
            # Same logic as job_update_market_data to find stale cards
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

            # Subquery for latest snapshot per card
            latest_snapshots = (
                select(MarketSnapshot.card_id, func.max(MarketSnapshot.timestamp).label("latest_timestamp"))
                .group_by(MarketSnapshot.card_id)
                .subquery()
            )

            # Get cards needing updates (no snapshot in last hour, or never scraped)
            cards_query = (
                select(Card)
                .outerjoin(latest_snapshots, col(Card.id) == latest_snapshots.c.card_id)
                .where(
                    (latest_snapshots.c.latest_timestamp < cutoff_time) | (latest_snapshots.c.latest_timestamp == None)  # noqa: E711
                )
            )

            cards = list(session.execute(cards_query).scalars().all())

            if not cards:
                print("[Queue] No stale cards to enqueue")
                stats = get_queue_stats_sync(session, source="ebay")
                print(f"[Queue] Current queue stats: {stats}")
                return

            enqueued = 0
            skipped = 0

            for card in cards:
                try:
                    # Enqueue with default priority (0)
                    # Higher priority cards (e.g., popular ones) could use priority=1
                    task = enqueue_task_sync(
                        session,
                        card_id=card.id,
                        source="ebay",
                        priority=0,
                        max_attempts=3,
                    )
                    # enqueue_task_sync returns existing task if already queued
                    if task.attempts == 0:
                        enqueued += 1
                    else:
                        skipped += 1
                except Exception as e:
                    print(f"[Queue] Error enqueuing card {card.name}: {e}")
                    skipped += 1

            stats = get_queue_stats_sync(session, source="ebay")
            print(f"[Queue] Enqueued {enqueued} cards ({skipped} already queued). Stats: {stats}")

    except Exception as e:
        print(f"[Queue] Error during enqueue job: {e}")
        log_scrape_error("Enqueue Stale Cards", str(e))


async def job_cleanup_task_queue():
    """
    Clean up old completed/failed tasks from the task queue.
    Runs daily at 3 AM UTC.

    Prevents the scrape_task table from growing unbounded by removing
    tasks that are no longer needed for tracking or debugging.

    Keeps tasks for 7 days to allow for:
    - Debugging recent failures
    - Analyzing completion patterns
    - Identifying recurring issues
    """
    print(f"[{datetime.now(timezone.utc)}] Cleaning up task queue...")

    try:
        with Session(engine) as session:
            result = cleanup_old_tasks_sync(session, days_to_keep=7)
            print(
                f"[Queue Cleanup] Deleted {result['completed_deleted']} completed, "
                f"{result['failed_deleted']} failed tasks"
            )
    except Exception as e:
        print(f"[Queue Cleanup] Error: {e}")
        log_scrape_error("Task Queue Cleanup", str(e))


async def job_generate_weekly_blog_post():
    """
    Generate and save weekly movers blog post to database.
    Runs every Monday at 10:00 AM UTC (after weekly report emails).

    Saves to the blog_post table with:
    - Market summary and volume trends
    - Top gainers and losers with sparklines
    - Daily activity breakdown
    - Rarity and treatment analysis
    - AI-generated market analysis (if OPENROUTER_API_KEY is set)

    The frontend fetches posts via /api/v1/blog/posts endpoint.
    """
    print(f"[{datetime.now(timezone.utc)}] Generating Weekly Blog Post...")

    try:
        # Import the generation function from the script
        import sys
        import re
        import yaml
        script_dir = Path(__file__).parent.parent.parent / "scripts"
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))

        from generate_weekly_movers_post import generate_mdx_post
        from app.models.blog_post import BlogPost

        # Generate for the current week (ending yesterday)
        content, date_string = generate_mdx_post(date_str=None, use_ai=True)

        # Parse frontmatter from the MDX content
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if frontmatter_match:
            frontmatter = yaml.safe_load(frontmatter_match.group(1))
            mdx_content = content[frontmatter_match.end():]
        else:
            frontmatter = {}
            mdx_content = content

        slug = frontmatter.get("slug", f"weekly-movers-{date_string}")
        title = frontmatter.get("title", f"Weekly Market Report: {date_string}")
        description = frontmatter.get("description", "")
        category = frontmatter.get("category", "analysis")
        tags = frontmatter.get("tags", ["market-report", "weekly-movers"])
        author = frontmatter.get("author", "system")
        read_time = frontmatter.get("readTime", 3)

        # Save to database (upsert - update if exists)
        with Session(engine) as session:
            existing = session.exec(
                select(BlogPost).where(BlogPost.slug == slug)
            ).first()

            if existing:
                # Update existing post
                existing.title = title
                existing.description = description
                existing.content = mdx_content
                existing.category = category
                existing.tags = tags
                existing.author = author
                existing.read_time = read_time
                existing.updated_at = datetime.now(timezone.utc)
                session.add(existing)
                action = "Updated"
            else:
                # Create new post
                post = BlogPost(
                    slug=slug,
                    title=title,
                    description=description,
                    content=mdx_content,
                    category=category,
                    tags=tags,
                    author=author,
                    read_time=read_time,
                    is_published=True,
                )
                session.add(post)
                action = "Created"

            session.commit()

        print(f"[Blog] {action} weekly movers post: {slug}")

        # Log success to Discord
        from app.discord_bot.logger import log_info
        log_info(
            "📝 Weekly Blog Post Generated",
            f"Weekly movers report for {date_string} has been saved to database.\n\n"
            f"**Slug:** `{slug}`\n"
            f"**Action:** {action}\n"
            "Available via `/api/v1/blog/posts/{slug}`"
        )

    except ImportError as e:
        print(f"[Blog] Import error (missing dependencies?): {e}")
        log_scrape_error("Weekly Blog Post", f"Import error: {e}")
    except Exception as e:
        print(f"[Blog] Error generating weekly blog post: {e}")
        log_scrape_error("Weekly Blog Post", str(e))


def start_scheduler():
    # Job configuration for durability:
    # - max_instances=1: Prevent overlapping runs
    # - misfire_grace_time: Allow late execution if within grace period (then skip)
    # - coalesce=True: If multiple runs were missed, only run once when catching up

    # eBay scraping: 30 min interval
    # With semaphore=4 and batch_size=8, full cycle takes ~22 min
    # Grace time of 15 min - if job is late by <15 min, still run it
    scheduler.add_job(
        job_update_market_data,
        IntervalTrigger(minutes=30),
        id="job_update_market_data",
        max_instances=1,
        misfire_grace_time=900,  # 15 minutes
        coalesce=True,
        replace_existing=True,
    )

    # Blokpax + OpenSea scraping: 8 hour interval
    # Reduced from 20 min to save resources (NFT markets move slower than eBay)
    # Grace time of 1 hour
    scheduler.add_job(
        job_update_blokpax_data,
        IntervalTrigger(hours=8),
        id="job_update_blokpax_data",
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour
        coalesce=True,
        replace_existing=True,
    )

    # AI market insights 2x daily (9 AM and 6 PM UTC)
    # Grace time of 1 hour - daily jobs should be more forgiving
    scheduler.add_job(
        job_market_insights,
        CronTrigger(hour=9, minute=0),
        id="job_market_insights_morning",
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        job_market_insights,
        CronTrigger(hour=18, minute=0),
        id="job_market_insights_evening",
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour
        coalesce=True,
        replace_existing=True,
    )

    # Daily digest emails at 9:15 AM UTC (after market insights)
    scheduler.add_job(
        job_send_daily_digests,
        CronTrigger(hour=9, minute=15),
        id="job_send_daily_digests",
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour
        coalesce=True,
        replace_existing=True,
    )

    # Personal welcome emails at 10 AM UTC (1 day after signup)
    scheduler.add_job(
        job_send_personal_welcome_emails,
        CronTrigger(hour=10, minute=0),
        id="job_send_personal_welcome_emails",
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour
        coalesce=True,
        replace_existing=True,
    )

    # Weekly report emails on Monday at 9:30 AM UTC
    scheduler.add_job(
        job_send_weekly_reports,
        CronTrigger(day_of_week="mon", hour=9, minute=30),
        id="job_send_weekly_reports",
        max_instances=1,
        misfire_grace_time=7200,  # 2 hours
        coalesce=True,
        replace_existing=True,
    )

    # Weekly blog post generation on Monday at 10:00 AM UTC (after weekly reports)
    # Creates MDX file with full market report for the week
    scheduler.add_job(
        job_generate_weekly_blog_post,
        CronTrigger(day_of_week="mon", hour=10, minute=0),
        id="job_generate_weekly_blog_post",
        max_instances=1,
        misfire_grace_time=7200,  # 2 hours
        coalesce=True,
        replace_existing=True,
    )

    # Price alert checks every 30 minutes
    scheduler.add_job(
        job_check_price_alerts,
        IntervalTrigger(minutes=30),
        id="job_check_price_alerts",
        max_instances=1,
        misfire_grace_time=900,  # 15 minutes
        coalesce=True,
        replace_existing=True,
    )

    # Seller data priority queue - processes NEW listings (hourly)
    # Ensures new listings get seller data within 1-2 hours
    # eBay removed seller info from search results, so individual page visits required
    scheduler.add_job(
        job_seller_priority_queue,
        IntervalTrigger(hours=1),
        id="job_seller_priority_queue",
        max_instances=1,
        misfire_grace_time=1800,  # 30 minutes
        coalesce=True,
        replace_existing=True,
    )

    # Seller data backfill every 4 hours (background cleanup)
    # Handles backlog of older listings missing seller data
    scheduler.add_job(
        job_backfill_seller_data,
        IntervalTrigger(hours=4),
        id="job_backfill_seller_data",
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour
        coalesce=True,
        replace_existing=True,
    )

    # Scraper health check every 2 hours
    # Alerts on: zero listings, low volume (<10), multi-day gaps
    # Would have caught the Dec 19-30 gap where sold scraper failed
    scheduler.add_job(
        job_scraper_health_check,
        IntervalTrigger(hours=2),
        id="job_scraper_health_check",
        max_instances=1,
        misfire_grace_time=1800,  # 30 minutes
        coalesce=True,
        replace_existing=True,
    )

    # Meta status sync daily at 4 AM UTC (after seller backfill)
    # Computes is_meta from user votes
    scheduler.add_job(
        job_sync_meta_status,
        CronTrigger(hour=4, minute=0),
        id="job_sync_meta_status",
        max_instances=1,
        misfire_grace_time=7200,  # 2 hours
        coalesce=True,
        replace_existing=True,
    )

    # Task queue cleanup daily at 3 AM UTC
    # Removes completed/failed tasks older than 7 days to prevent table bloat
    scheduler.add_job(
        job_cleanup_task_queue,
        CronTrigger(hour=3, minute=0),
        id="job_cleanup_task_queue",
        max_instances=1,
        misfire_grace_time=7200,  # 2 hours
        coalesce=True,
        replace_existing=True,
    )

    # Task queue enqueue job: 30 min interval
    # Alternative to job_update_market_data for distributed worker processing
    # Enqueues stale cards to the persistent task queue for crash-resilient processing
    # Use with: python scripts/run_task_queue_worker.py
    # NOTE: This is disabled by default. Enable if running separate worker processes.
    if settings.USE_TASK_QUEUE:
        scheduler.add_job(
            job_enqueue_stale_cards,
            IntervalTrigger(minutes=30),
            id="job_enqueue_stale_cards",
            max_instances=1,
            misfire_grace_time=900,  # 15 minutes
            coalesce=True,
            replace_existing=True,
        )

    scheduler.start()
    print("Scheduler started (with misfire handling):")
    print("  - job_update_market_data (eBay): 30m interval, 15m grace [batch=8, 4 concurrent tabs]")
    print("  - job_update_blokpax_data (Blokpax+OpenSea): 8h interval, 1h grace")
    print("  - job_market_insights (Discord AI): 9:00 & 18:00 UTC, 1h grace")
    print("  - job_sync_meta_status (Meta): 4:00 UTC daily, 2h grace")
    print("  - job_cleanup_task_queue (Queue Cleanup): 3:00 UTC daily, 2h grace")
    print("  - job_send_daily_digests (Email): 9:15 UTC daily, 1h grace")
    print("  - job_send_personal_welcome_emails (Email): 10:00 UTC daily, 1h grace")
    print("  - job_send_weekly_reports (Email): Mon 9:30 UTC, 2h grace")
    print("  - job_generate_weekly_blog_post (Blog): Mon 10:00 UTC, 2h grace")
    print("  - job_check_price_alerts (Email): 30m interval, 15m grace")
    print("  - job_seller_priority_queue (Seller): 1h interval, 30m grace")
    print("  - job_backfill_seller_data (Seller): 4h interval, 1h grace")
    print("  - job_scraper_health_check (Monitoring): 2h interval, 30m grace")
    if settings.USE_TASK_QUEUE:
        print("  - job_enqueue_stale_cards (Queue): 30m interval, 15m grace [requires worker process]")
