"""
Discord webhook logger for scrape activity and system events.
"""
import os
import requests
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
load_dotenv()


# Webhook URLs for different channels
LOGS_WEBHOOK_URL = os.getenv("DISCORD_LOGS_WEBHOOK_URL")
UPDATES_WEBHOOK_URL = os.getenv("DISCORD_UPDATES_WEBHOOK_URL")
NEW_LISTINGS_WEBHOOK_URL = os.getenv("DISCORD_NEW_LISTINGS_WEBHOOK_URL")
NEW_SALES_WEBHOOK_URL = os.getenv("DISCORD_NEW_SALES_WEBHOOK_URL")


def _send_log(
    title: str,
    description: str,
    color: int,
    fields: list = None,
    webhook_url: str = None,
    username: str = "Wonders Logs"
) -> bool:
    """Send a log message to Discord webhook."""
    url = webhook_url or LOGS_WEBHOOK_URL
    if not url:
        return False

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "WondersTracker"}
    }

    if fields:
        embed["fields"] = fields

    try:
        response = requests.post(
            url,
            json={
                "username": username,
                "embeds": [embed]
            },
            timeout=5
        )
        return response.status_code in (200, 204)
    except Exception as e:
        print(f"Discord log failed: {e}")
        return False


def log_scrape_start(card_count: int, scrape_type: str = "full") -> bool:
    """Log when a scrape job starts."""
    return _send_log(
        title="Scrape Started",
        description=f"Starting **{scrape_type}** scrape job",
        color=0x3B82F6,  # Blue
        fields=[
            {"name": "Cards", "value": str(card_count), "inline": True},
            {"name": "Type", "value": scrape_type.title(), "inline": True},
            {"name": "Time", "value": datetime.utcnow().strftime("%H:%M UTC"), "inline": True}
        ]
    )


def log_scrape_complete(
    cards_processed: int,
    new_listings: int,
    new_sales: int,
    duration_seconds: float,
    errors: int = 0
) -> bool:
    """Log when a scrape job completes."""
    status = "with errors" if errors > 0 else "successfully"
    color = 0xF59E0B if errors > 0 else 0x10B981  # Yellow if errors, green otherwise

    minutes = int(duration_seconds // 60)
    seconds = int(duration_seconds % 60)
    duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

    return _send_log(
        title=f"Scrape Complete",
        description=f"Scrape finished {status}",
        color=color,
        fields=[
            {"name": "Cards Processed", "value": str(cards_processed), "inline": True},
            {"name": "New Listings", "value": str(new_listings), "inline": True},
            {"name": "New Sales", "value": str(new_sales), "inline": True},
            {"name": "Duration", "value": duration_str, "inline": True},
            {"name": "Errors", "value": str(errors), "inline": True}
        ]
    )


def log_scrape_error(card_name: str, error: str) -> bool:
    """Log a scrape error for a specific card."""
    return _send_log(
        title="Scrape Error",
        description=f"Error scraping **{card_name}**",
        color=0xEF4444,  # Red
        fields=[
            {"name": "Error", "value": error[:1000], "inline": False}
        ]
    )


def log_snapshot_update(cards_updated: int) -> bool:
    """Log when market snapshots are updated."""
    return _send_log(
        title="Snapshots Updated",
        description=f"Updated market snapshots for **{cards_updated}** cards",
        color=0x8B5CF6,  # Purple
        fields=[
            {"name": "Cards", "value": str(cards_updated), "inline": True},
            {"name": "Time", "value": datetime.utcnow().strftime("%H:%M UTC"), "inline": True}
        ]
    )


def log_info(title: str, message: str) -> bool:
    """Log a general info message."""
    return _send_log(
        title=title,
        description=message,
        color=0x6B7280  # Gray
    )


def log_warning(title: str, message: str) -> bool:
    """Log a warning message."""
    return _send_log(
        title=f"Warning: {title}",
        description=message,
        color=0xF59E0B  # Yellow
    )


def log_error(title: str, message: str) -> bool:
    """Log an error message."""
    return _send_log(
        title=f"Error: {title}",
        description=message,
        color=0xEF4444  # Red
    )


def log_new_sale(
    card_name: str,
    price: float,
    treatment: Optional[str] = None,
    url: Optional[str] = None,
    sold_date: Optional[str] = None,
    floor_price: Optional[float] = None
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
            description += f"\n➡️ At floor price"

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
        username="Wonders Sales"
    )


def log_new_listing(
    card_name: str,
    price: float,
    treatment: Optional[str] = None,
    url: Optional[str] = None,
    is_auction: bool = False,
    floor_price: Optional[float] = None
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
            description += f"\n➡️ At floor price"

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
        username="Wonders Listings"
    )
