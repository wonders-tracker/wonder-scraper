import asyncio
import random
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select
from sqlalchemy import func
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from app.models.blokpax import BlokpaxStorefront, BlokpaxSnapshot
from scripts.scrape_card import scrape_card as scrape_sold_data
from app.scraper.active import scrape_active_data
from app.scraper.browser import BrowserManager
from app.scraper.blokpax import (
    WOTF_STOREFRONTS,
    get_bpx_price,
    scrape_storefront_floor,
    scrape_recent_sales,
    scrape_preslab_sales,
    is_wotf_asset,
)
from app.discord_bot.logger import log_scrape_start, log_scrape_complete, log_scrape_error, log_market_insights
from datetime import datetime, timedelta
import concurrent.futures

scheduler = AsyncIOScheduler()

async def scrape_single_card(card: Card):
    """Scrape a single card with full data (sold + active)."""
    try:
        search_term = f"{card.name} {card.set_name}"
        print(f"[Polling] Updating: {search_term}")
        
        # Scrape sold data (creates snapshot)
        await scrape_sold_data(
            card_name=card.name,
            card_id=card.id,
            search_term=search_term,
            set_name=card.set_name,
            product_type=card.product_type if hasattr(card, 'product_type') else 'Single'
        )
        
        # Get active data
        low_ask, inventory, high_bid = await scrape_active_data(card.name, card.id, search_term=search_term)
        
        # Update snapshot with active data
        with Session(engine) as session:
            statement = select(MarketSnapshot).where(
                MarketSnapshot.card_id == card.id
            ).order_by(MarketSnapshot.timestamp.desc())
            snapshot = session.exec(statement).first()
            if snapshot:
                snapshot.lowest_ask = low_ask
                snapshot.inventory = inventory
                snapshot.highest_bid = high_bid
                session.add(snapshot)
                session.commit()
                print(f"[Polling] Updated {card.name}: Ask=${low_ask}, Inv={inventory}")
        
        return True
    except Exception as e:
        print(f"[Polling] Error updating {card.name}: {e}")
        return False

async def job_update_market_data():
    """
    Optimized polling job - scrapes cards in batches with concurrency control.
    Includes robust error handling for browser startup failures.
    """
    print(f"[{datetime.utcnow()}] Starting Scheduled Market Update...")
    start_time = time.time()

    with Session(engine) as session:
        # Get cards that haven't been updated in the last hour (or all if none)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        # Subquery for latest snapshot per card
        latest_snapshots = (
            select(
                MarketSnapshot.card_id,
                func.max(MarketSnapshot.timestamp).label('latest_timestamp')
            )
            .group_by(MarketSnapshot.card_id)
            .subquery()
        )

        # Get cards needing updates
        cards_query = (
            select(Card)
            .outerjoin(latest_snapshots, Card.id == latest_snapshots.c.card_id)
            .where(
                (latest_snapshots.c.latest_timestamp < cutoff_time) |
                (latest_snapshots.c.latest_timestamp == None)
            )
        )

        cards_to_update = session.exec(cards_query).all()

        # If no stale cards, update a random sample
        if not cards_to_update:
            all_cards = session.exec(select(Card)).all()
            cards_to_update = random.sample(all_cards, min(10, len(all_cards)))

    if not cards_to_update:
        print("[Polling] No cards to update.")
        return

    print(f"[Polling] Updating {len(cards_to_update)} cards...")

    # Log scrape start to Discord
    log_scrape_start(len(cards_to_update), scrape_type="scheduled")

    # Initialize browser with retry logic
    max_browser_retries = 3
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
                wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                print(f"[Polling] Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

    if not browser_started:
        print("[Polling] ERROR: Could not start browser after all retries. Skipping this update cycle.")
        return

    try:
        # Process cards with controlled concurrency (max 3 concurrent)
        batch_size = 3
        successful = 0
        failed = 0

        for i in range(0, len(cards_to_update), batch_size):
            batch = cards_to_update[i:i+batch_size]

            # Process batch concurrently
            tasks = [scrape_single_card(card) for card in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successes/failures
            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                elif result:
                    successful += 1
                else:
                    failed += 1

            # Brief delay between batches
            if i + batch_size < len(cards_to_update):
                await asyncio.sleep(5)

        print(f"[Polling] Results: {successful} successful, {failed} failed out of {len(cards_to_update)} cards")

        # Log scrape complete to Discord
        duration = time.time() - start_time
        log_scrape_complete(
            cards_processed=len(cards_to_update),
            new_listings=0,  # Scheduled scrapes don't track new listings separately
            new_sales=0,
            duration_seconds=duration,
            errors=failed
        )

    except Exception as e:
        print(f"[Polling] ERROR during scraping: {type(e).__name__}: {e}")
        log_scrape_error("Scheduled Job", str(e))

    finally:
        await BrowserManager.close()

    print(f"[{datetime.utcnow()}] Scheduled Update Complete.")


async def job_update_blokpax_data():
    """
    Scheduled job to update Blokpax floor prices and sales.
    Runs on a separate interval from eBay since it's lightweight (API-based).
    """
    print(f"[{datetime.utcnow()}] Starting Blokpax Update...")
    start_time = time.time()

    log_scrape_start(len(WOTF_STOREFRONTS), scrape_type="blokpax")

    errors = 0
    total_sales = 0

    try:
        bpx_price = await get_bpx_price()
        print(f"[Blokpax] BPX Price: ${bpx_price:.6f} USD")

        for slug in WOTF_STOREFRONTS:
            try:
                # Scrape floor prices with deep_scan=True to actually compute floor from listings
                # Without deep_scan, only metadata is fetched and floor_price stays stale
                floor_data = await scrape_storefront_floor(slug, deep_scan=True)
                floor_bpx = floor_data.get("floor_price_bpx")
                floor_usd = floor_data.get("floor_price_usd")
                listed = floor_data.get("listed_count", 0)
                total = floor_data.get("total_tokens", 0)

                print(f"[Blokpax] {slug}: Floor={floor_bpx:,.0f} BPX (${floor_usd:.2f})" if floor_bpx else f"[Blokpax] {slug}: No listings")

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
                    storefront = session.exec(
                        select(BlokpaxStorefront).where(BlokpaxStorefront.slug == slug)
                    ).first()
                    if storefront:
                        storefront.floor_price_bpx = floor_bpx
                        storefront.floor_price_usd = floor_usd
                        storefront.listed_count = listed
                        storefront.total_tokens = total
                        storefront.updated_at = datetime.utcnow()
                        session.add(storefront)

                    session.commit()

                # Scrape recent sales (limit pages for scheduled runs)
                sales = await scrape_recent_sales(slug, max_pages=2)
                if slug == "reward-room":
                    sales = [s for s in sales if is_wotf_asset(s.asset_name)]
                total_sales += len(sales)

                await asyncio.sleep(1)

            except Exception as e:
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

    except Exception as e:
        print(f"[Blokpax] Fatal error: {e}")
        log_scrape_error("Blokpax Scheduled", str(e))
        errors += 1

    duration = time.time() - start_time
    log_scrape_complete(
        cards_processed=len(WOTF_STOREFRONTS),
        new_listings=0,
        new_sales=total_sales,
        duration_seconds=duration,
        errors=errors
    )

    print(f"[{datetime.utcnow()}] Blokpax Update Complete. Duration: {duration:.1f}s")


async def job_send_daily_digests():
    """
    Send daily market digest emails to users who have opted in.
    Runs once daily at 9 AM UTC.
    """
    print(f"[{datetime.utcnow()}] Sending Daily Digest Emails...")

    try:
        from app.models.watchlist import EmailPreferences
        from app.models.user import User
        from app.services.email import send_daily_market_digest
        from app.services.market_insights import get_insights_generator

        with Session(engine) as session:
            # Get users who want daily digests
            prefs = session.exec(
                select(EmailPreferences).where(EmailPreferences.daily_digest == True)
            ).all()

            if not prefs:
                print("[Digest] No users subscribed to daily digest")
                return

            # Gather market data once for all users
            generator = get_insights_generator()
            data = generator.gather_market_data(days=1)

            # Format for email
            market_data = {
                'total_sales': data.get('total_sales', 0),
                'total_volume': data.get('total_volume', 0),
                'market_sentiment': 'bullish' if data.get('volume_change', 0) > 10 else 'bearish' if data.get('volume_change', 0) < -10 else 'neutral',
                'top_gainers': data.get('top_gainers', []),
                'top_losers': data.get('top_losers', []),
                'hot_deals': data.get('hot_deals', []),
            }

            sent_count = 0
            for pref in prefs:
                user = session.get(User, pref.user_id)
                if user and user.email:
                    try:
                        name = user.username or user.email.split('@')[0]
                        success = send_daily_market_digest(user.email, name, market_data)
                        if success:
                            sent_count += 1
                    except Exception as e:
                        print(f"[Digest] Failed to send to {user.email}: {e}")

            print(f"[Digest] Sent daily digest to {sent_count} users")

    except Exception as e:
        print(f"[Digest] Error sending daily digests: {e}")


async def job_send_weekly_reports():
    """
    Send weekly market report emails to users who have opted in.
    Runs once weekly on Monday at 9 AM UTC.
    """
    print(f"[{datetime.utcnow()}] Sending Weekly Report Emails...")

    try:
        from app.models.watchlist import EmailPreferences
        from app.models.user import User
        from app.services.email import send_weekly_market_report
        from app.services.market_insights import get_insights_generator

        with Session(engine) as session:
            # Get users who want weekly reports
            prefs = session.exec(
                select(EmailPreferences).where(EmailPreferences.weekly_report == True)
            ).all()

            if not prefs:
                print("[Weekly] No users subscribed to weekly report")
                return

            # Gather market data for the week
            generator = get_insights_generator()
            data = generator.gather_market_data(days=7)

            # Format for email
            week_end = datetime.utcnow()
            week_start = week_end - timedelta(days=7)

            report_data = {
                'week_start': week_start.strftime('%b %d'),
                'week_end': week_end.strftime('%b %d'),
                'total_sales': data.get('total_sales', 0),
                'total_volume': data.get('total_volume', 0),
                'volume_change': data.get('volume_change', 0),
                'avg_sale_price': data.get('avg_price', 0),
                'daily_breakdown': data.get('daily_breakdown', []),
                'top_cards_by_volume': data.get('top_cards', []),
                'price_movers': data.get('price_movers', []),
                'market_health': {
                    'unique_buyers': data.get('unique_buyers', 0),
                    'unique_sellers': data.get('unique_sellers', 0),
                    'liquidity_score': data.get('liquidity_score', 0),
                },
            }

            sent_count = 0
            for pref in prefs:
                user = session.get(User, pref.user_id)
                if user and user.email:
                    try:
                        name = user.username or user.email.split('@')[0]
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
    print(f"[{datetime.utcnow()}] Checking Price Alerts...")

    try:
        from app.models.watchlist import Watchlist
        from app.models.user import User
        from app.models.card import Card
        from app.services.email import send_price_alert

        with Session(engine) as session:
            # Get all active alerts with target prices
            alerts = session.exec(
                select(Watchlist).where(
                    Watchlist.alert_enabled == True,
                    Watchlist.target_price != None,
                    Watchlist.notify_email == True
                )
            ).all()

            if not alerts:
                print("[Alerts] No active price alerts")
                return

            sent_count = 0
            for alert in alerts:
                card = session.get(Card, alert.card_id)
                user = session.get(User, alert.user_id)

                if not card or not user:
                    continue

                current_price = card.floor_price or card.latest_price or 0

                # Skip if already alerted at this price
                if alert.last_alerted_price and abs(current_price - alert.last_alerted_price) < 0.01:
                    continue

                # Check if alert should trigger
                should_alert = False
                if alert.alert_type == "below" and current_price <= alert.target_price:
                    should_alert = True
                elif alert.alert_type == "above" and current_price >= alert.target_price:
                    should_alert = True
                elif alert.alert_type == "any":
                    should_alert = True

                # Cooldown: don't alert more than once per hour per card
                if alert.last_alerted_at:
                    time_since_last = datetime.utcnow() - alert.last_alerted_at
                    if time_since_last.total_seconds() < 3600:
                        continue

                if should_alert:
                    name = user.username or user.email.split('@')[0]
                    alert_data = {
                        'card_name': card.name,
                        'card_slug': card.slug,
                        'alert_type': alert.alert_type,
                        'target_price': alert.target_price,
                        'current_price': current_price,
                        'treatment': alert.treatment or 'Any Treatment',
                    }

                    success = send_price_alert(user.email, name, alert_data)
                    if success:
                        sent_count += 1
                        # Update alert tracking
                        alert.last_alerted_at = datetime.utcnow()
                        alert.last_alerted_price = current_price
                        session.add(alert)

            session.commit()
            print(f"[Alerts] Sent {sent_count} price alerts")

    except Exception as e:
        print(f"[Alerts] Error checking price alerts: {e}")


async def job_backfill_seller_data():
    """
    Periodic job to backfill missing seller data from eBay item pages.
    Runs daily at 3 AM UTC (off-peak hours).
    Processes up to 100 items per run to avoid overloading eBay.
    """
    print(f"[{datetime.utcnow()}] Starting Seller Data Backfill...")

    try:
        from pydoll.browser import Chrome
        from pydoll.browser.options import ChromiumOptions
        from app.scraper.seller import extract_seller_from_html
        import re

        # Setup browser
        options = ChromiumOptions()
        options.headless = True
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        browser = Chrome(options=options)
        await browser.start()
        print("[Seller] Browser started")

        with Session(engine) as session:
            # Get listings missing seller data (prioritize recent sold items)
            from sqlalchemy import text
            query = text("""
                SELECT id, external_id, url, title
                FROM marketprice
                WHERE listing_type = 'sold'
                AND seller_name IS NULL
                AND platform = 'ebay'
                AND (url IS NOT NULL OR external_id IS NOT NULL)
                ORDER BY sold_date DESC NULLS LAST
                LIMIT 100
            """)

            results = session.execute(query).all()
            print(f"[Seller] Found {len(results)} items to process")

            updated = 0
            failed = 0

            for mp_id, external_id, url, title in results:
                # Extract item ID
                item_id = external_id
                if not item_id and url:
                    match = re.search(r'/itm/(?:[^/]+/)?(\d+)', url)
                    if match:
                        item_id = match.group(1)

                if not item_id:
                    failed += 1
                    continue

                try:
                    # Fetch page
                    tab = await browser.new_tab()
                    item_url = f"https://www.ebay.com/itm/{item_id}"
                    await tab.go_to(item_url, timeout=30)
                    await asyncio.sleep(2)

                    result = await tab.execute_script(
                        "return document.documentElement.outerHTML;",
                        return_by_value=True
                    )

                    html = None
                    if isinstance(result, dict):
                        inner = result.get('result', {})
                        if isinstance(inner, dict):
                            html = inner.get('result', {}).get('value')

                    await tab.close()

                    if not html:
                        failed += 1
                        continue

                    # Check for block
                    if "Pardon Our Interruption" in html or "Security Measure" in html:
                        print("[Seller] Blocked by eBay, stopping early")
                        break

                    # Extract seller info
                    seller_name, feedback_score, feedback_percent = extract_seller_from_html(html)

                    if seller_name:
                        session.execute(text("""
                            UPDATE marketprice
                            SET seller_name = :seller,
                                seller_feedback_score = :score,
                                seller_feedback_percent = :pct
                            WHERE id = :id
                        """), {
                            "seller": seller_name,
                            "score": feedback_score,
                            "pct": feedback_percent,
                            "id": mp_id
                        })
                        session.commit()
                        updated += 1
                    else:
                        failed += 1

                    # Rate limit
                    await asyncio.sleep(1)

                except Exception as e:
                    print(f"[Seller] Error on ID {mp_id}: {e}")
                    failed += 1
                    try:
                        await tab.close()
                    except:
                        pass

        await browser.stop()
        print(f"[{datetime.utcnow()}] Seller Backfill Complete: {updated} updated, {failed} failed")

    except Exception as e:
        print(f"[Seller] Fatal error: {e}")
        log_scrape_error("Seller Backfill", str(e))


async def job_market_insights():
    """
    Generate and post AI-powered market insights to Discord.
    Runs 2x daily (morning and evening).
    """
    print(f"[{datetime.utcnow()}] Generating Market Insights...")

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
            print(f"[{datetime.utcnow()}] Market insights posted to Discord")
        else:
            print(f"[{datetime.utcnow()}] Failed to post market insights")

    except Exception as e:
        print(f"[{datetime.utcnow()}] Market insights error: {e}")
        log_scrape_error("Market Insights", str(e))


def start_scheduler():
    # Job configuration for durability:
    # - max_instances=1: Prevent overlapping runs
    # - misfire_grace_time: Allow late execution if within grace period (then skip)
    # - coalesce=True: If multiple runs were missed, only run once when catching up

    # eBay scraping: 45 min interval (realistic for full card scan)
    # Grace time of 30 min - if job is late by <30 min, still run it
    scheduler.add_job(
        job_update_market_data,
        IntervalTrigger(minutes=45),
        id="job_update_market_data",
        max_instances=1,
        misfire_grace_time=1800,  # 30 minutes
        coalesce=True,
        replace_existing=True
    )

    # Blokpax scraping: 20 min interval (API-based, faster)
    # Grace time of 10 min
    scheduler.add_job(
        job_update_blokpax_data,
        IntervalTrigger(minutes=20),
        id="job_update_blokpax_data",
        max_instances=1,
        misfire_grace_time=600,  # 10 minutes
        coalesce=True,
        replace_existing=True
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
        replace_existing=True
    )
    scheduler.add_job(
        job_market_insights,
        CronTrigger(hour=18, minute=0),
        id="job_market_insights_evening",
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour
        coalesce=True,
        replace_existing=True
    )

    # Daily digest emails at 9:15 AM UTC (after market insights)
    scheduler.add_job(
        job_send_daily_digests,
        CronTrigger(hour=9, minute=15),
        id="job_send_daily_digests",
        max_instances=1,
        misfire_grace_time=3600,  # 1 hour
        coalesce=True,
        replace_existing=True
    )

    # Weekly report emails on Monday at 9:30 AM UTC
    scheduler.add_job(
        job_send_weekly_reports,
        CronTrigger(day_of_week='mon', hour=9, minute=30),
        id="job_send_weekly_reports",
        max_instances=1,
        misfire_grace_time=7200,  # 2 hours
        coalesce=True,
        replace_existing=True
    )

    # Price alert checks every 30 minutes
    scheduler.add_job(
        job_check_price_alerts,
        IntervalTrigger(minutes=30),
        id="job_check_price_alerts",
        max_instances=1,
        misfire_grace_time=900,  # 15 minutes
        coalesce=True,
        replace_existing=True
    )

    # Seller data backfill daily at 3 AM UTC (off-peak hours)
    # Grace time of 2 hours - not time-critical
    scheduler.add_job(
        job_backfill_seller_data,
        CronTrigger(hour=3, minute=0),
        id="job_backfill_seller_data",
        max_instances=1,
        misfire_grace_time=7200,  # 2 hours
        coalesce=True,
        replace_existing=True
    )

    scheduler.start()
    print("Scheduler started (with misfire handling):")
    print("  - job_update_market_data (eBay): 45m interval, 30m grace")
    print("  - job_update_blokpax_data (Blokpax): 20m interval, 10m grace")
    print("  - job_market_insights (Discord AI): 9:00 & 18:00 UTC, 1h grace")
    print("  - job_send_daily_digests (Email): 9:15 UTC daily, 1h grace")
    print("  - job_send_weekly_reports (Email): Mon 9:30 UTC, 2h grace")
    print("  - job_check_price_alerts (Email): 30m interval, 15m grace")
    print("  - job_backfill_seller_data (Seller): 3:00 UTC daily, 2h grace")

