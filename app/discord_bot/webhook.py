"""
Discord webhook for sending scheduled reports.
Simpler than running a full bot - just POST to the webhook URL.
"""

import os
import io
import requests
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from app.discord_bot.stats import calculate_market_stats, generate_csv_report, format_stats_embed
from app.discord_bot.storage import upload_csv


WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def send_webhook_message(
    content: str = None,
    embeds: list = None,
    username: str = "Wonders Market Bot",
    file_data: bytes = None,
    filename: str = None,
) -> bool:
    """
    Send a message via Discord webhook.

    Args:
        content: Text message content
        embeds: List of embed dicts
        username: Bot display name
        file_data: Optional file bytes to attach
        filename: Filename for attachment

    Returns:
        True if successful
    """
    if not WEBHOOK_URL:
        print("ERROR: DISCORD_WEBHOOK_URL not set")
        return False

    payload = {"username": username}

    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    try:
        if file_data and filename:
            # Send with file attachment
            files = {"file": (filename, io.BytesIO(file_data), "text/csv")}
            # payload_json is required when sending files with embeds
            response = requests.post(WEBHOOK_URL, data={"payload_json": __import__("json").dumps(payload)}, files=files)
        else:
            # Send JSON only
            response = requests.post(WEBHOOK_URL, json=payload)

        if response.status_code in (200, 204):
            return True
        else:
            print(f"Webhook failed: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"Webhook error: {e}")
        return False


def send_daily_report() -> bool:
    """Generate and send daily market report via webhook."""
    try:
        # Calculate stats
        stats = calculate_market_stats("daily")
        embed_data = format_stats_embed(stats)

        # Convert to Discord embed format
        embed = {
            "title": embed_data["title"],
            "description": embed_data["description"],
            "color": embed_data["color"],
            "timestamp": embed_data["timestamp"],
            "footer": embed_data["footer"],
            "fields": embed_data["fields"],
        }

        # Generate and store CSV in Postgres
        filename, csv_content = generate_csv_report("daily")
        try:
            report_id = upload_csv(filename, csv_content)
            print(f"CSV report stored: {report_id}")
        except Exception as e:
            print(f"Failed to store CSV: {e}")

        # Send embed (attach CSV as file for Discord users)
        success = send_webhook_message(embeds=[embed], file_data=csv_content, filename=filename)

        if success:
            print(f"Daily report sent at {datetime.now(timezone.utc)}")
        return success

    except Exception as e:
        print(f"Failed to send daily report: {e}")
        return False


def send_weekly_report() -> bool:
    """Generate and send weekly market report via webhook."""
    try:
        # Calculate stats
        stats = calculate_market_stats("weekly")
        embed_data = format_stats_embed(stats)

        # Convert to Discord embed format
        embed = {
            "title": embed_data["title"],
            "description": embed_data["description"],
            "color": embed_data["color"],
            "timestamp": embed_data["timestamp"],
            "footer": embed_data["footer"],
            "fields": embed_data["fields"],
        }

        # Generate and store CSV in Postgres
        filename, csv_content = generate_csv_report("weekly")
        try:
            report_id = upload_csv(filename, csv_content)
            print(f"CSV report stored: {report_id}")
        except Exception as e:
            print(f"Failed to store CSV: {e}")

        # Send embed (attach CSV as file for Discord users)
        success = send_webhook_message(embeds=[embed], file_data=csv_content, filename=filename)

        if success:
            print(f"Weekly report sent at {datetime.now(timezone.utc)}")
        return success

    except Exception as e:
        print(f"Failed to send weekly report: {e}")
        return False


def send_test_message() -> bool:
    """Send a test message to verify webhook is working."""
    return send_webhook_message(
        content="Wonders Market Bot is connected!",
        embeds=[
            {
                "title": "Test Message",
                "description": "If you see this, the webhook is working correctly.",
                "color": 0x10B981,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "test":
            send_test_message()
        elif cmd == "daily":
            send_daily_report()
        elif cmd == "weekly":
            send_weekly_report()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python -m app.discord_bot.webhook [test|daily|weekly]")
    else:
        # Default: send test
        send_test_message()
