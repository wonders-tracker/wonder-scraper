"""
Discord webhook logger for scrape activity and system events.
"""

import os
import requests
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


# Webhook URLs for different channels
LOGS_WEBHOOK_URL = os.getenv("DISCORD_LOGS_WEBHOOK_URL")
UPDATES_WEBHOOK_URL = os.getenv("DISCORD_UPDATES_WEBHOOK_URL")
NEW_LISTINGS_WEBHOOK_URL = os.getenv("DISCORD_NEW_LISTINGS_WEBHOOK_URL")
NEW_SALES_WEBHOOK_URL = os.getenv("DISCORD_NEW_SALES_WEBHOOK_URL")
DEALS_WEBHOOK_URL = os.getenv("DISCORD_DEALS_WEBHOOK_URL")  # Falls back to NEW_LISTINGS


def _send_log(
    title: str,
    description: str,
    color: int,
    fields: list | None = None,
    webhook_url: str | None = None,
    username: str = "Wonders Logs",
) -> bool:
    """Send a log message to Discord webhook."""
    url = webhook_url or LOGS_WEBHOOK_URL
    if not url:
        return False

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "WondersTracker"},
    }

    if fields:
        embed["fields"] = fields

    try:
        response = requests.post(url, json={"username": username, "embeds": [embed]}, timeout=5)
        return response.status_code in (200, 204)
    except Exception as e:
        print(f"Discord log failed: {e}")
        return False


def log_scrape_start(card_count: int, scrape_type: str = "full") -> bool:
    """Log when a scrape job starts."""
    type_emoji = {"full": "🔄", "scheduled": "⏰", "blokpax": "🎯", "active": "📋", "sold": "💰"}.get(
        scrape_type.lower(), "🔄"
    )

    return _send_log(
        title=f"{type_emoji} Scrape Started",
        description=f"Starting **{scrape_type.title()}** scrape job",
        color=0x3B82F6,  # Blue
        fields=[
            {"name": "📦 Cards", "value": f"`{card_count:,}`", "inline": True},
            {"name": "📋 Type", "value": scrape_type.title(), "inline": True},
            {"name": "🕐 Time", "value": datetime.now(timezone.utc).strftime("%H:%M UTC"), "inline": True},
        ],
    )


def log_scrape_complete(
    cards_processed: int, new_listings: int, new_sales: int, duration_seconds: float, errors: int = 0
) -> bool:
    """Log when a scrape job completes."""
    if errors > 0:
        title = "⚠️ Scrape Complete (with errors)"
        color = 0xF59E0B  # Yellow
    else:
        title = "✅ Scrape Complete"
        color = 0x10B981  # Green

    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    return _send_log(
        title=title,
        description=f"Successfully processed **{cards_processed:,}** cards",
        color=color,
        fields=[
            {"name": "📦 Cards", "value": f"`{cards_processed:,}`", "inline": True},
            {"name": "📋 Listings", "value": f"`{new_listings:,}`", "inline": True},
            {"name": "💰 Sales", "value": f"`{new_sales:,}`", "inline": True},
            {"name": "⏱️ Duration", "value": f"`{duration_str}`", "inline": True},
            {"name": "❌ Errors", "value": f"`{errors}`", "inline": True},
        ],
    )


def log_scrape_error(card_name: str, error: str) -> bool:
    """Log a scrape error for a specific card."""
    return _send_log(
        title="🚨 Scrape Error",
        description=f"Error scraping **{card_name}**",
        color=0xEF4444,  # Red
        fields=[{"name": "❌ Error Details", "value": f"```{error[:900]}```", "inline": False}],
    )


def log_snapshot_update(cards_updated: int) -> bool:
    """Log when market snapshots are updated."""
    return _send_log(
        title="📸 Snapshots Updated",
        description=f"Updated market snapshots for **{cards_updated:,}** cards",
        color=0x8B5CF6,  # Purple
        fields=[
            {"name": "📦 Cards", "value": f"`{cards_updated:,}`", "inline": True},
            {"name": "🕐 Time", "value": datetime.now(timezone.utc).strftime("%H:%M UTC"), "inline": True},
        ],
    )


def log_info(title: str, message: str) -> bool:
    """Log a general info message."""
    return _send_log(
        title=f"ℹ️ {title}",
        description=message,
        color=0x6B7280,  # Gray
    )


def log_warning(title: str, message: str) -> bool:
    """Log a warning message."""
    return _send_log(
        title=f"⚠️ Warning: {title}",
        description=message,
        color=0xF59E0B,  # Yellow
    )


def log_error(title: str, message: str) -> bool:
    """Log an error message."""
    return _send_log(
        title=f"🚨 Error: {title}",
        description=message,
        color=0xEF4444,  # Red
    )


def log_new_sale(
    card_name: str,
    price: float,
    treatment: Optional[str] = None,
    url: Optional[str] = None,
    sold_date: Optional[str] = None,
    floor_price: Optional[float] = None,
) -> bool:
    """Log a new sale discovery to the new-sales channel."""
    description = f"**{card_name}** sold for **${price:.2f}**"
    if treatment and treatment != "Classic Paper":
        description += f" ({treatment})"

    # Add floor price comparison
    if floor_price and floor_price > 0:
        delta = price - floor_price
        delta_pct = (delta / floor_price) * 100
        if delta > 0:
            description += f"\n📈 **+${delta:.2f}** (+{delta_pct:.1f}%) above floor"
        elif delta < 0:
            description += f"\n📉 **-${abs(delta):.2f}** (-{abs(delta_pct):.1f}%) below floor"
        else:
            description += "\n➡️ At floor price"

    fields = []
    if floor_price and floor_price > 0:
        fields.append({"name": "Floor", "value": f"${floor_price:.2f}", "inline": True})
    if sold_date:
        fields.append({"name": "Sold", "value": sold_date, "inline": True})
    if url:
        fields.append({"name": "Link", "value": f"[View on eBay]({url})", "inline": True})

    # Color based on deal quality: green if below floor, yellow if above
    if floor_price and floor_price > 0:
        color = 0x10B981 if price <= floor_price else 0xF59E0B  # Green if deal, yellow if premium
    else:
        color = 0x10B981  # Default green

    return _send_log(
        title="New Sale Detected",
        description=description,
        color=color,
        fields=fields if fields else None,
        webhook_url=NEW_SALES_WEBHOOK_URL,
        username="Wonders Sales",
    )


def log_new_listing(
    card_name: str,
    price: float,
    treatment: Optional[str] = None,
    url: Optional[str] = None,
    is_auction: bool = False,
    floor_price: Optional[float] = None,
) -> bool:
    """Log a new active listing discovery to the new-listings channel."""
    listing_type = "Auction" if is_auction else "Buy It Now"
    description = f"**{card_name}** listed for **${price:.2f}** ({listing_type})"
    if treatment and treatment != "Classic Paper":
        description += f" - {treatment}"

    # Add floor price comparison
    if floor_price and floor_price > 0:
        delta = price - floor_price
        delta_pct = (delta / floor_price) * 100
        if delta < 0:
            description += f"\n🔥 **${abs(delta):.2f}** ({abs(delta_pct):.1f}%) BELOW floor!"
        elif delta > 0:
            description += f"\n📊 +${delta:.2f} (+{delta_pct:.1f}%) above floor"
        else:
            description += "\n➡️ At floor price"

    fields = []
    if floor_price and floor_price > 0:
        fields.append({"name": "Floor", "value": f"${floor_price:.2f}", "inline": True})
    if url:
        fields.append({"name": "Link", "value": f"[View on eBay]({url})", "inline": True})

    # Color: green if below floor (deal!), blue if at/above
    if floor_price and floor_price > 0 and price < floor_price:
        color = 0x10B981  # Green for deals below floor
    else:
        color = 0x3B82F6  # Blue default

    return _send_log(
        title="New Listing" if not (floor_price and price < floor_price) else "🎯 Deal Alert",
        description=description,
        color=color,
        fields=fields if fields else None,
        webhook_url=NEW_LISTINGS_WEBHOOK_URL,
        username="Wonders Listings",
    )


def log_market_insights(insights_text: str) -> bool:
    """
    Post market insights to the updates channel.
    This is for the 2x daily market summary with ASCII-formatted reports.
    """
    if not UPDATES_WEBHOOK_URL:
        print("DISCORD_UPDATES_WEBHOOK_URL not set, skipping market insights")
        return False

    try:
        # Post as regular message (not embed) to preserve code block formatting
        response = requests.post(
            UPDATES_WEBHOOK_URL,
            json={
                "username": "Wonders Market",
                "avatar_url": "https://wonders.codyc.xyz/android-chrome-192x192.png",
                "content": insights_text[:2000],  # Discord message limit
            },
            timeout=10,
        )
        return response.status_code in (200, 204)
    except Exception as e:
        print(f"Market insights Discord post failed: {e}")
        return False


def log_hot_deal(
    card_name: str,
    price: float,
    floor_price: float,
    discount_pct: float,
    deal_quality: str,
    treatment: Optional[str] = None,
    url: Optional[str] = None,
    volatility_cv: Optional[float] = None,
    threshold_pct: Optional[float] = None,
) -> bool:
    """
    Log a hot deal alert using smart deal detection.

    This uses volatility-based thresholds:
    - Stable cards (CV < 0.3): 15% below floor = deal
    - Moderate (CV 0.3-0.5): 25% below floor = deal
    - Volatile (CV > 0.5): 40% below floor = deal

    Args:
        card_name: Name of the card
        price: Listed/sold price
        floor_price: Current floor price
        discount_pct: Discount percentage (e.g., 25.0 for 25% off)
        deal_quality: "hot", "good", or "marginal"
        treatment: Card treatment (optional)
        url: Link to listing (optional)
        volatility_cv: Card's coefficient of variation (optional)
        threshold_pct: Deal threshold for this card (optional)
    """
    webhook_url = DEALS_WEBHOOK_URL or NEW_LISTINGS_WEBHOOK_URL
    if not webhook_url:
        return False

    # Emoji and color based on deal quality
    quality_config = {
        "hot": {"emoji": "🔥🔥🔥", "color": 0xEF4444, "label": "HOT DEAL"},  # Red
        "good": {"emoji": "🔥🔥", "color": 0xF59E0B, "label": "Good Deal"},  # Orange
        "marginal": {"emoji": "🔥", "color": 0x10B981, "label": "Deal"},  # Green
    }
    config = quality_config.get(deal_quality, quality_config["marginal"])

    # Build description
    description = f"**{card_name}**"
    if treatment and treatment != "Classic Paper":
        description += f" ({treatment})"
    description += f"\n\n💰 **${price:.2f}** — {discount_pct:.0f}% below floor!"

    # Add volatility context if available
    if volatility_cv is not None and threshold_pct is not None:
        stability = "stable" if volatility_cv < 0.3 else "moderate" if volatility_cv < 0.5 else "volatile"
        description += f"\n📊 Card is {stability} (threshold: {threshold_pct:.0f}%)"

    fields = [
        {"name": "Price", "value": f"${price:.2f}", "inline": True},
        {"name": "Floor", "value": f"${floor_price:.2f}", "inline": True},
        {"name": "Discount", "value": f"{discount_pct:.0f}%", "inline": True},
    ]

    if url:
        fields.append({"name": "Link", "value": f"[View Listing]({url})", "inline": False})

    return _send_log(
        title=f"{config['emoji']} {config['label']}!",
        description=description,
        color=config["color"],
        fields=fields,
        webhook_url=webhook_url,
        username="Wonders Deals",
    )


def check_and_log_deal(
    card_id: int,
    card_name: str,
    price: float,
    treatment: Optional[str] = None,
    url: Optional[str] = None,
    min_quality: str = "good",
) -> bool:
    """
    Check if a listing qualifies as a deal and log it if so.

    Uses the DealDetector with volatility-based thresholds.

    Args:
        card_id: Database ID of the card
        card_name: Name of the card (for display)
        price: Listed price
        treatment: Card treatment (optional)
        url: Link to listing (optional)
        min_quality: Minimum quality to log ("marginal", "good", "hot")

    Returns:
        True if a deal was detected and logged
    """
    try:
        from app.services.market_patterns import get_deal_detector

        detector = get_deal_detector()
        result = detector.check_deal(card_id, price, treatment)

        quality_order = {"not_a_deal": 0, "marginal": 1, "good": 2, "hot": 3}
        if quality_order.get(result.deal_quality, 0) >= quality_order.get(min_quality, 1):
            return log_hot_deal(
                card_name=card_name,
                price=result.price,
                floor_price=result.floor_price,
                discount_pct=result.discount_pct,
                deal_quality=result.deal_quality,
                treatment=treatment,
                url=url,
                volatility_cv=result.volatility_cv,
                threshold_pct=result.threshold_pct,
            )
        return False
    except Exception as e:
        print(f"Deal detection failed: {e}")
        return False
