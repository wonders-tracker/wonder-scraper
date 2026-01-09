#!/usr/bin/env python3
"""
Email Preview Tool

Preview email templates in your browser before sending.

Usage:
    python scripts/preview_email.py                    # List available templates
    python scripts/preview_email.py product-update    # Preview product update
    python scripts/preview_email.py daily-digest      # Preview daily digest
    python scripts/preview_email.py weekly-report     # Preview weekly report
    python scripts/preview_email.py portfolio         # Preview portfolio summary
    python scripts/preview_email.py welcome           # Preview welcome email
"""

import sys
import os
import webbrowser
import tempfile
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.email import _email_wrapper
from app.core.config import settings


def get_product_update_html() -> str:
    """Generate detailed product update email HTML."""
    # Use local file paths for preview, production URL for actual sends
    import os
    local_path = os.path.abspath("frontend/public/emails/jan-2025")
    img_base = f"file://{local_path}"

    sections = [
        {
            "title": "Fair Market Price Algorithm",
            "description": "Our new pricing engine uses statistical methods to give you accurate, outlier-resistant prices you can trust.",
            "bullets": [
                "MAD-trimmed mean: Analyzes 8 recent sales and removes outliers",
                "Dynamic multipliers calculated from real sales data",
                "Liquidity adjustment factors in supply/demand",
            ],
            "image": f"{img_base}/card-prices.png",
        },
        {
            "title": "Confidence Scores",
            "description": "Every price now has a confidence indicator. Green means stable and reliable. Yellow means some volatility. Red means prices are moving fast—proceed with caution.",
            "bullets": [
                "Based on listing count, price spread, recency, and volatility",
                "See the colored dot next to any price on the site",
                "Hover to see the exact confidence percentage",
            ],
        },
        {
            "title": "Order Book Analysis",
            "description": "We now analyze active listings—not just past sales—to find the true floor price in real-time.",
            "bullets": [
                "Scans all active listings across eBay, Blokpax, OpenSea",
                "Filters outlier listings (damaged cards, price manipulation)",
                "Falls back to sales data when listings are sparse",
            ],
            "image": f"{img_base}/dashboard.png",
        },
        {
            "title": "OpenSea Integration",
            "description": "NFT sales from OpenSea are now included. Get the complete picture of Wonders market activity across all platforms.",
            "bullets": [
                "Track Wonders NFT sales and floor prices",
                "NFT traits displayed on listings",
            ],
        },
        {
            "title": "Reliability & Speed",
            "description": "Under the hood, we've added circuit breakers, auto-recovery, and smarter retry logic. Translation: fewer data gaps, more uptime.",
            "bullets": [
                "Circuit breakers prevent cascade failures",
                "Auto-recovery from browser crashes",
                "Discord alerts for system health monitoring",
            ],
        },
    ]

    # Build section rows
    section_html = ""
    for i, section in enumerate(sections):
        title = section.get("title", "")
        description = section.get("description", "")
        bullets = section.get("bullets", [])
        image = section.get("image")
        num = i + 1

        bullet_items = "".join(
            f'<tr><td style="color: #7dd3a8; padding-right: 8px; vertical-align: top;">→</td>'
            f'<td style="color: #888; font-size: 12px; line-height: 1.5; padding-bottom: 6px;">{b}</td></tr>'
            for b in bullets
        )
        bullet_html = (
            f'<table cellpadding="0" cellspacing="0" style="margin-top: 12px;">{bullet_items}</table>'
            if bullets
            else ""
        )

        image_html = ""
        if image:
            image_html = f'''
                <table cellpadding="0" cellspacing="0" style="margin-top: 16px;" width="100%">
                    <tr>
                        <td style="background: #222; border: 1px solid #333; padding: 4px;">
                            <img src="{image}" alt="{title}" style="max-width: 100%; height: auto; display: block; border-radius: 4px;" />
                        </td>
                    </tr>
                </table>
            '''

        section_html += f"""
        <tr>
            <td style="padding: 24px 0; border-bottom: 1px solid #333;">
                <table cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                        <td style="width: 32px; height: 32px; background: #333; text-align: center; vertical-align: middle; font-size: 14px; font-weight: bold; color: #7dd3a8;">{num}</td>
                        <td style="padding-left: 14px; vertical-align: middle;">
                            <p style="margin: 0; color: #fff; font-size: 16px; font-weight: bold;">{title}</p>
                        </td>
                    </tr>
                </table>
                <p style="margin: 14px 0 0 0; color: #888; font-size: 13px; line-height: 1.6;">{description}</p>
                {bullet_html}
                {image_html}
            </td>
        </tr>
        """

    content = f"""
        <table cellpadding="0" cellspacing="0" style="margin-bottom: 20px;">
            <tr>
                <td style="background: #7dd3a8; padding: 6px 12px; font-size: 10px; letter-spacing: 2px; color: #111; font-weight: bold;">
                    JANUARY 2025
                </td>
            </tr>
        </table>

        <h1 style="margin: 0 0 16px 0; color: #fff; font-size: 26px; font-weight: bold; line-height: 1.3;">
            Smarter Pricing & Confidence Scores
        </h1>

        <p style="margin: 0 0 32px 0; color: #888; font-size: 14px; line-height: 1.7;">
            Big update. We've rebuilt how prices are calculated so you always know what a card is worth—and how confident you can be in that price. Here's everything that's new.
        </p>

        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 32px;">
            {section_html}
        </table>

        <table cellpadding="0" cellspacing="0" style="margin-bottom: 24px;">
            <tr>
                <td style="background: #7dd3a8; padding: 14px 28px;">
                    <a href="{settings.FRONTEND_URL}/changelog" style="color: #111; font-size: 11px; font-weight: bold; letter-spacing: 2px; text-decoration: none;">SEE FULL CHANGELOG →</a>
                </td>
            </tr>
        </table>

        <p style="margin: 0; color: #666; font-size: 12px; line-height: 1.6;">
            Thanks for being part of WondersTracker.<br><br>
            — Cody
        </p>
    """
    return _email_wrapper(content, "PRODUCT UPDATE")


def get_daily_digest_html() -> str:
    """Generate daily digest email HTML."""
    content = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 20px; background: #222; border: 1px solid #333;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">VOLUME</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 28px; font-weight: bold;">$2,450</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">SALES</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 28px; font-weight: bold;">18</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">SENTIMENT</p>
                                <p style="margin: 8px 0 0 0; color: #7dd3a8; font-size: 14px; font-weight: bold;">BULLISH</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">TOP GAINERS</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">Dragonmaster Cai</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 70px;">$125.00</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 60px;">+18.5%</td>
            </tr>
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">Phoenix Rising</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 70px;">$85.50</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 60px;">+12.3%</td>
            </tr>
        </table>

        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">TOP LOSERS</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">Storm Caller</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 70px;">$42.00</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #ef4444; font-size: 13px; font-weight: bold; text-align: right; width: 60px;">-8.5%</td>
            </tr>
        </table>

        <table cellpadding="0" cellspacing="0">
            <tr>
                <td style="background: #fff; padding: 12px 24px;">
                    <a href="{settings.FRONTEND_URL}/market" style="color: #111; font-size: 11px; font-weight: bold; letter-spacing: 2px; text-decoration: none;">VIEW MARKET →</a>
                </td>
            </tr>
        </table>
    """
    return _email_wrapper(content, "DAILY DIGEST")


def get_weekly_report_html() -> str:
    """Generate weekly report email HTML."""
    daily_rows = ""
    days = [
        ("01/01", 420, 4),
        ("01/02", 850, 7),
        ("01/03", 320, 3),
        ("01/04", 1200, 9),
        ("01/05", 680, 5),
        ("01/06", 550, 4),
        ("01/07", 780, 6),
    ]
    max_vol = max(d[1] for d in days)
    for date, vol, sales in days:
        bar_width = int((vol / max_vol) * 100)
        daily_rows += f"""<tr>
            <td style="padding: 8px 0; color: #888; font-size: 12px; width: 50px;">{date}</td>
            <td style="padding: 8px 12px;">
                <div style="background: #333; height: 6px; width: 100%;">
                    <div style="background: #7dd3a8; height: 6px; width: {bar_width}%;"></div>
                </div>
            </td>
            <td style="padding: 8px 0; color: #fff; font-size: 12px; text-align: right; width: 70px;">${vol:,}</td>
            <td style="padding: 8px 0; color: #666; font-size: 11px; text-align: right; width: 50px;">{sales} sales</td>
        </tr>"""

    content = f"""
        <p style="margin: 0 0 24px 0; color: #666; font-size: 12px;">Dec 30 – Jan 6</p>

        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 20px; background: #222; border: 1px solid #333;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">VOLUME</p>
                                <p style="margin: 8px 0 4px 0; color: #fff; font-size: 24px; font-weight: bold;">$4,800</p>
                                <p style="margin: 0; color: #7dd3a8; font-size: 12px;">+12.5%</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">SALES</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 24px; font-weight: bold;">38</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">AVG PRICE</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 24px; font-weight: bold;">$126</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">DAILY BREAKDOWN</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            {daily_rows}
        </table>

        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">TOP SELLERS</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">1. Dragonmaster Cai</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; width: 60px;">8 sales</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 70px;">$1,250</td>
            </tr>
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">2. Phoenix Rising</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; width: 60px;">6 sales</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 70px;">$890</td>
            </tr>
        </table>

        <table cellpadding="0" cellspacing="0">
            <tr>
                <td style="background: #fff; padding: 12px 24px;">
                    <a href="{settings.FRONTEND_URL}/market" style="color: #111; font-size: 11px; font-weight: bold; letter-spacing: 2px; text-decoration: none;">VIEW MARKET →</a>
                </td>
            </tr>
        </table>
    """
    return _email_wrapper(content, "WEEKLY REPORT")


def get_portfolio_html() -> str:
    """Generate portfolio summary email HTML."""
    content = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 20px; background: #222; border: 1px solid #333;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">VALUE</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 24px; font-weight: bold;">$1,625</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">P&L</p>
                                <p style="margin: 8px 0 4px 0; color: #7dd3a8; font-size: 24px; font-weight: bold;">+$125</p>
                                <p style="margin: 0; color: #7dd3a8; font-size: 12px;">+8.3%</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">HOLDINGS</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 24px; font-weight: bold;">12</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="color: #888; font-size: 12px;">Cost Basis</td>
                <td style="color: #fff; font-size: 12px; text-align: right;">$1,500.00</td>
            </tr>
        </table>

        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">TOP PERFORMERS</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">Dragonmaster Cai</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 80px;">+$45.00</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 60px;">+15%</td>
            </tr>
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">Phoenix Rising</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 80px;">+$32.50</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 60px;">+12%</td>
            </tr>
        </table>

        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">NEEDS ATTENTION</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">Storm Caller</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #ef4444; font-size: 13px; font-weight: bold; text-align: right; width: 80px;">-$15.00</td>
                <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 60px;">-8%</td>
            </tr>
        </table>

        <table cellpadding="0" cellspacing="0">
            <tr>
                <td style="background: #fff; padding: 12px 24px;">
                    <a href="{settings.FRONTEND_URL}/portfolio" style="color: #111; font-size: 11px; font-weight: bold; letter-spacing: 2px; text-decoration: none;">VIEW PORTFOLIO →</a>
                </td>
            </tr>
        </table>
    """
    return _email_wrapper(content, "PORTFOLIO")


def get_welcome_html() -> str:
    """Generate welcome email HTML."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">WONDERSTRACKER</h1>
        </div>

        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #fafafa;">Welcome, Cody!</h2>

            <p style="color: #a1a1aa; line-height: 1.6; margin: 0 0 20px 0;">
                Your account has been created successfully. You now have access to the most comprehensive market tracker for Wonders of the First trading cards.
            </p>

            <div style="background-color: #27272a; border-radius: 6px; padding: 20px; margin: 25px 0;">
                <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #71717a;">What you can do:</h3>
                <ul style="margin: 0; padding: 0 0 0 20px; color: #a1a1aa; line-height: 1.8;">
                    <li>Track real-time market prices and trends</li>
                    <li>Build and monitor your portfolio value</li>
                    <li>Analyze floor prices across all treatments</li>
                    <li>View detailed price history and VWAP</li>
                </ul>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{settings.FRONTEND_URL}" style="display: inline-block; background-color: #fafafa; color: #000; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px;">GO TO DASHBOARD</a>
            </div>
        </div>

        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
        </div>
    </div>
</body>
</html>"""


TEMPLATES = {
    "product-update": ("Product Update", get_product_update_html),
    "daily-digest": ("Daily Digest", get_daily_digest_html),
    "weekly-report": ("Weekly Report", get_weekly_report_html),
    "portfolio": ("Portfolio Summary", get_portfolio_html),
    "welcome": ("Welcome Email", get_welcome_html),
}


def preview_email(template_name: str):
    """Open email template in browser."""
    if template_name not in TEMPLATES:
        print(f"Unknown template: {template_name}")
        print("\nAvailable templates:")
        for name, (title, _) in TEMPLATES.items():
            print(f"  {name:20} - {title}")
        return

    title, generator = TEMPLATES[template_name]
    html = generator()

    # Save to temp file and open
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
        f.write(html)
        filepath = f.name

    print(f"Opening {title} preview...")
    webbrowser.open(f"file://{filepath}")
    print(f"Saved to: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Preview email templates in browser")
    parser.add_argument("template", nargs="?", help="Template name to preview")
    parser.add_argument("--list", "-l", action="store_true", help="List available templates")
    args = parser.parse_args()

    if args.list or not args.template:
        print("Available email templates:\n")
        for name, (title, _) in TEMPLATES.items():
            print(f"  {name:20} - {title}")
        print("\nUsage: python scripts/preview_email.py <template-name>")
        return

    preview_email(args.template)


if __name__ == "__main__":
    main()
