"""
Email Service using Resend

Handles transactional emails:
- Welcome emails for new users
- Password reset emails
- API access requests/approvals

Marketing/digest emails:
- Daily market digest
- Weekly market report
- Price alerts
- Portfolio summary
"""

import resend
from typing import Optional, List, Dict, Any
from app.core.config import settings

# Initialize Resend
resend.api_key = settings.RESEND_API_KEY


def send_welcome_email(to_email: str, user_name: Optional[str] = None) -> bool:
    """
    Send welcome email to new users.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping welcome email - RESEND_API_KEY not configured")
        return False

    name = user_name or to_email.split("@")[0]

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": "Welcome to WondersTracker!",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">WONDERSTRACKER</h1>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #fafafa;">Welcome, {name}!</h2>

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

            <p style="color: #71717a; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0;">
                Questions? Reply to this email or join our Discord community for support.
            </p>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] Welcome email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send welcome email to {to_email}: {e}")
        return False


def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """
    Send password reset email with reset link.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping password reset email - RESEND_API_KEY not configured")
        return False

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": "Reset Your Password - WondersTracker",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">WONDERSTRACKER</h1>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #fafafa;">Reset Your Password</h2>

            <p style="color: #a1a1aa; line-height: 1.6; margin: 0 0 20px 0;">
                We received a request to reset your password. Click the button below to create a new password. This link will expire in 1 hour.
            </p>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="display: inline-block; background-color: #fafafa; color: #000; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px;">RESET PASSWORD</a>
            </div>

            <div style="background-color: #27272a; border-radius: 6px; padding: 15px 20px; margin: 25px 0;">
                <p style="margin: 0; color: #71717a; font-size: 13px; line-height: 1.6;">
                    If you didn't request this password reset, you can safely ignore this email. Your password will remain unchanged.
                </p>
            </div>

            <p style="color: #52525b; font-size: 12px; line-height: 1.6; margin: 20px 0 0 0;">
                If the button doesn't work, copy and paste this link into your browser:<br>
                <span style="color: #71717a; word-break: break-all;">{reset_url}</span>
            </p>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] Password reset email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send password reset email to {to_email}: {e}")
        return False


def send_api_access_request_email(
    requester_email: str,
    requester_name: str,
    use_case: str,
    company: Optional[str] = None
) -> bool:
    """
    Send API access request notification to admin.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping API access request email - RESEND_API_KEY not configured")
        return False

    admin_email = settings.ADMIN_EMAIL or settings.FROM_EMAIL

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [admin_email],
            "reply_to": requester_email,
            "subject": f"API Access Request - {requester_name}",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">WONDERSTRACKER</h1>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #fafafa;">New API Access Request</h2>

            <div style="background-color: #27272a; border-radius: 6px; padding: 20px; margin: 0 0 25px 0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; color: #71717a; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; width: 100px;">Name</td>
                        <td style="padding: 10px 0; color: #fafafa; font-size: 14px;">{requester_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; color: #71717a; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;">Email</td>
                        <td style="padding: 10px 0; color: #fafafa; font-size: 14px;"><a href="mailto:{requester_email}" style="color: #60a5fa;">{requester_email}</a></td>
                    </tr>
                    {"<tr><td style='padding: 10px 0; color: #71717a; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;'>Company</td><td style='padding: 10px 0; color: #fafafa; font-size: 14px;'>" + company + "</td></tr>" if company else ""}
                </table>
            </div>

            <h3 style="margin: 0 0 10px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #71717a;">Use Case</h3>
            <div style="background-color: #27272a; border-radius: 6px; padding: 20px; margin: 0 0 25px 0;">
                <p style="margin: 0; color: #a1a1aa; line-height: 1.6; white-space: pre-wrap;">{use_case}</p>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{settings.FRONTEND_URL}/admin" style="display: inline-block; background-color: #fafafa; color: #000; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px;">GO TO ADMIN PANEL</a>
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] API access request email sent for {requester_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send API access request email: {e}")
        return False


async def send_api_access_approved_email(to_email: str, user_name: str) -> bool:
    """
    Send email to user when their API access request is approved.
    Includes link to purchase API Access subscription.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping API access approved email - RESEND_API_KEY not configured")
        return False

    checkout_url = f"{settings.FRONTEND_URL}/upgrade?product=api"

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": "Your API Access Request Has Been Approved! - WondersTracker",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">WONDERSTRACKER</h1>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <div style="text-align: center; margin-bottom: 25px;">
                <span style="font-size: 48px;">🎉</span>
            </div>

            <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #fafafa; text-align: center;">API Access Approved!</h2>

            <p style="color: #a1a1aa; line-height: 1.6; margin: 0 0 20px 0;">
                Great news, {user_name}! Your API access request has been approved. You can now subscribe to our API Access plan to start building integrations with WondersTracker.
            </p>

            <div style="background-color: #27272a; border-radius: 6px; padding: 20px; margin: 25px 0;">
                <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #71717a;">API Access Includes:</h3>
                <ul style="margin: 0; padding: 0 0 0 20px; color: #a1a1aa; line-height: 1.8;">
                    <li>Full access to market data endpoints</li>
                    <li>Real-time price and sales data</li>
                    <li>Pay only for what you use ($0.001/request)</li>
                    <li>Build Discord bots, portfolio trackers, and more</li>
                    <li>Priority support</li>
                </ul>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{checkout_url}" style="display: inline-block; background: linear-gradient(to right, #f59e0b, #ea580c); color: #000; padding: 16px 40px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 6px;">GET API ACCESS</a>
            </div>

            <p style="color: #71717a; font-size: 13px; line-height: 1.6; margin: 30px 0 0 0; text-align: center;">
                Questions? Reply to this email or join our Discord community.
            </p>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] API access approved email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send API access approved email to {to_email}: {e}")
        return False


def send_api_key_approved_email(to_email: str, user_name: str, api_key: str) -> bool:
    """
    Send email to user when their API access is approved with their new key.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping API key approved email - RESEND_API_KEY not configured")
        return False

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": "Your API Access Has Been Approved - WondersTracker",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">WONDERSTRACKER</h1>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <h2 style="margin: 0 0 20px 0; font-size: 20px; color: #fafafa;">API Access Approved!</h2>

            <p style="color: #a1a1aa; line-height: 1.6; margin: 0 0 20px 0;">
                Hi {user_name}, your API access request has been approved. Here is your API key:
            </p>

            <div style="background-color: #27272a; border-radius: 6px; padding: 20px; margin: 0 0 25px 0; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;">
                <p style="margin: 0; color: #4ade80; font-size: 14px; word-break: break-all;">{api_key}</p>
            </div>

            <div style="background-color: #7f1d1d; border: 1px solid #991b1b; border-radius: 6px; padding: 15px 20px; margin: 25px 0;">
                <p style="margin: 0; color: #fca5a5; font-size: 13px; line-height: 1.6;">
                    <strong>Important:</strong> This is the only time your full API key will be shown. Store it securely - we cannot recover it if lost.
                </p>
            </div>

            <div style="background-color: #27272a; border-radius: 6px; padding: 20px; margin: 25px 0;">
                <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #71717a;">Rate Limits</h3>
                <ul style="margin: 0; padding: 0 0 0 20px; color: #a1a1aa; line-height: 1.8;">
                    <li>60 requests per minute</li>
                    <li>10,000 requests per day</li>
                </ul>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{settings.FRONTEND_URL}/api" style="display: inline-block; background-color: #fafafa; color: #000; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px;">VIEW API DOCS</a>
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] API key approved email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send API key approved email to {to_email}: {e}")
        return False


# ============== MARKETING / DIGEST EMAILS ==============

def send_daily_market_digest(
    to_email: str,
    user_name: str,
    market_data: Dict[str, Any]
) -> bool:
    """
    Send daily market digest email with key market stats.

    market_data should include:
    - total_sales: int
    - total_volume: float
    - top_gainers: List[Dict] with name, price, change_percent
    - top_losers: List[Dict] with name, price, change_percent
    - hot_deals: List[Dict] with name, price, floor_price
    - market_sentiment: str ('bullish', 'bearish', 'neutral')
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping daily digest - RESEND_API_KEY not configured")
        return False

    # Build gainers/losers rows
    gainers_html = ""
    for card in market_data.get("top_gainers", [])[:5]:
        change = card.get("change_percent", 0)
        gainers_html += f"""
        <tr>
            <td style="padding: 8px 0; color: #fafafa; font-size: 14px;">{card.get('name', 'Unknown')}</td>
            <td style="padding: 8px 0; color: #fafafa; font-size: 14px; text-align: right;">${card.get('price', 0):.2f}</td>
            <td style="padding: 8px 0; color: #4ade80; font-size: 14px; text-align: right;">+{change:.1f}%</td>
        </tr>
        """

    losers_html = ""
    for card in market_data.get("top_losers", [])[:5]:
        change = card.get("change_percent", 0)
        losers_html += f"""
        <tr>
            <td style="padding: 8px 0; color: #fafafa; font-size: 14px;">{card.get('name', 'Unknown')}</td>
            <td style="padding: 8px 0; color: #fafafa; font-size: 14px; text-align: right;">${card.get('price', 0):.2f}</td>
            <td style="padding: 8px 0; color: #f87171; font-size: 14px; text-align: right;">{change:.1f}%</td>
        </tr>
        """

    # Hot deals section
    deals_html = ""
    for deal in market_data.get("hot_deals", [])[:3]:
        discount = ((deal.get('floor_price', 0) - deal.get('price', 0)) / deal.get('floor_price', 1)) * 100 if deal.get('floor_price') else 0
        deals_html += f"""
        <div style="background-color: #1e3a1e; border: 1px solid #166534; border-radius: 4px; padding: 12px; margin-bottom: 8px;">
            <div style="color: #fafafa; font-size: 14px; font-weight: 500;">{deal.get('name', 'Unknown')}</div>
            <div style="color: #4ade80; font-size: 13px; margin-top: 4px;">
                ${deal.get('price', 0):.2f} <span style="color: #71717a;">(Floor: ${deal.get('floor_price', 0):.2f})</span>
                <span style="color: #4ade80; font-weight: bold;"> -{discount:.0f}%</span>
            </div>
        </div>
        """

    sentiment = market_data.get("market_sentiment", "neutral")
    sentiment_color = "#4ade80" if sentiment == "bullish" else "#f87171" if sentiment == "bearish" else "#fbbf24"
    sentiment_icon = "📈" if sentiment == "bullish" else "📉" if sentiment == "bearish" else "➡️"

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": f"Daily Market Digest - {market_data.get('total_sales', 0)} Sales Today",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">DAILY DIGEST</h1>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <p style="color: #a1a1aa; line-height: 1.6; margin: 0 0 25px 0;">
                Hey {user_name}, here's your daily market summary for Wonders of the First.
            </p>

            <!-- Market Overview -->
            <div style="display: flex; gap: 15px; margin-bottom: 30px;">
                <div style="flex: 1; background-color: #27272a; border-radius: 6px; padding: 20px; text-align: center;">
                    <div style="color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Sales</div>
                    <div style="color: #fafafa; font-size: 28px; font-weight: bold; margin-top: 8px;">{market_data.get('total_sales', 0)}</div>
                </div>
                <div style="flex: 1; background-color: #27272a; border-radius: 6px; padding: 20px; text-align: center;">
                    <div style="color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Volume</div>
                    <div style="color: #fafafa; font-size: 28px; font-weight: bold; margin-top: 8px;">${market_data.get('total_volume', 0):,.0f}</div>
                </div>
                <div style="flex: 1; background-color: #27272a; border-radius: 6px; padding: 20px; text-align: center;">
                    <div style="color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Sentiment</div>
                    <div style="color: {sentiment_color}; font-size: 20px; font-weight: bold; margin-top: 8px;">{sentiment_icon} {sentiment.upper()}</div>
                </div>
            </div>

            <!-- Top Gainers -->
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #4ade80;">📈 Top Gainers</h3>
            <div style="background-color: #27272a; border-radius: 6px; padding: 15px 20px; margin-bottom: 25px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="padding: 8px 0; color: #71717a; font-size: 11px; text-transform: uppercase; text-align: left;">Card</th>
                            <th style="padding: 8px 0; color: #71717a; font-size: 11px; text-transform: uppercase; text-align: right;">Price</th>
                            <th style="padding: 8px 0; color: #71717a; font-size: 11px; text-transform: uppercase; text-align: right;">Change</th>
                        </tr>
                    </thead>
                    <tbody>
                        {gainers_html if gainers_html else '<tr><td colspan="3" style="padding: 15px 0; color: #71717a; text-align: center;">No significant gainers today</td></tr>'}
                    </tbody>
                </table>
            </div>

            <!-- Top Losers -->
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #f87171;">📉 Top Losers</h3>
            <div style="background-color: #27272a; border-radius: 6px; padding: 15px 20px; margin-bottom: 25px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="padding: 8px 0; color: #71717a; font-size: 11px; text-transform: uppercase; text-align: left;">Card</th>
                            <th style="padding: 8px 0; color: #71717a; font-size: 11px; text-transform: uppercase; text-align: right;">Price</th>
                            <th style="padding: 8px 0; color: #71717a; font-size: 11px; text-transform: uppercase; text-align: right;">Change</th>
                        </tr>
                    </thead>
                    <tbody>
                        {losers_html if losers_html else '<tr><td colspan="3" style="padding: 15px 0; color: #71717a; text-align: center;">No significant losers today</td></tr>'}
                    </tbody>
                </table>
            </div>

            <!-- Hot Deals -->
            {f'''
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #fbbf24;">🔥 Hot Deals (Below Floor)</h3>
            <div style="margin-bottom: 25px;">
                {deals_html}
            </div>
            ''' if deals_html else ''}

            <div style="text-align: center; margin: 30px 0;">
                <a href="{settings.FRONTEND_URL}/market" style="display: inline-block; background-color: #fafafa; color: #000; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px;">VIEW FULL MARKET</a>
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0 0 10px 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
            <p style="margin: 0; color: #3f3f46; font-size: 11px;">
                <a href="{settings.FRONTEND_URL}/profile" style="color: #52525b;">Manage email preferences</a>
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] Daily digest sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send daily digest to {to_email}: {e}")
        return False


def send_weekly_market_report(
    to_email: str,
    user_name: str,
    report_data: Dict[str, Any]
) -> bool:
    """
    Send weekly market report email with comprehensive stats.

    report_data should include:
    - week_start: str (date)
    - week_end: str (date)
    - total_sales: int
    - total_volume: float
    - volume_change: float (% vs previous week)
    - avg_sale_price: float
    - daily_breakdown: List[Dict] with date, sales, volume
    - top_cards_by_volume: List[Dict] with name, sales, volume
    - price_movers: List[Dict] with name, old_price, new_price, change_percent
    - market_health: Dict with unique_buyers, unique_sellers, liquidity_score
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping weekly report - RESEND_API_KEY not configured")
        return False

    # Daily breakdown chart (ASCII bars in email)
    daily_html = ""
    max_sales = max([d.get('sales', 0) for d in report_data.get('daily_breakdown', [])] or [1])
    for day in report_data.get("daily_breakdown", []):
        bar_width = int((day.get('sales', 0) / max_sales) * 100)
        daily_html += f"""
        <div style="display: flex; align-items: center; margin-bottom: 8px;">
            <div style="width: 60px; color: #71717a; font-size: 12px;">{day.get('date', '')}</div>
            <div style="flex: 1; background-color: #27272a; height: 20px; border-radius: 3px; overflow: hidden;">
                <div style="width: {bar_width}%; background-color: #3b82f6; height: 100%;"></div>
            </div>
            <div style="width: 50px; text-align: right; color: #a1a1aa; font-size: 12px;">{day.get('sales', 0)}</div>
        </div>
        """

    # Top cards by volume
    top_cards_html = ""
    for i, card in enumerate(report_data.get("top_cards_by_volume", [])[:10], 1):
        top_cards_html += f"""
        <tr>
            <td style="padding: 10px 0; color: #71717a; font-size: 14px; border-bottom: 1px solid #27272a;">{i}</td>
            <td style="padding: 10px 0; color: #fafafa; font-size: 14px; border-bottom: 1px solid #27272a;">{card.get('name', 'Unknown')}</td>
            <td style="padding: 10px 0; color: #a1a1aa; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">{card.get('sales', 0)}</td>
            <td style="padding: 10px 0; color: #fafafa; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">${card.get('volume', 0):,.0f}</td>
        </tr>
        """

    # Price movers
    movers_html = ""
    for card in report_data.get("price_movers", [])[:5]:
        change = card.get("change_percent", 0)
        color = "#4ade80" if change > 0 else "#f87171"
        arrow = "↑" if change > 0 else "↓"
        movers_html += f"""
        <tr>
            <td style="padding: 10px 0; color: #fafafa; font-size: 14px; border-bottom: 1px solid #27272a;">{card.get('name', 'Unknown')}</td>
            <td style="padding: 10px 0; color: #71717a; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">${card.get('old_price', 0):.2f}</td>
            <td style="padding: 10px 0; color: #fafafa; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">${card.get('new_price', 0):.2f}</td>
            <td style="padding: 10px 0; color: {color}; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">{arrow} {abs(change):.1f}%</td>
        </tr>
        """

    volume_change = report_data.get("volume_change", 0)
    vol_color = "#4ade80" if volume_change > 0 else "#f87171" if volume_change < 0 else "#a1a1aa"
    vol_arrow = "↑" if volume_change > 0 else "↓" if volume_change < 0 else ""

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": f"Weekly Market Report - ${report_data.get('total_volume', 0):,.0f} Volume",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">WEEKLY REPORT</h1>
            <p style="margin: 10px 0 0 0; color: #71717a; font-size: 14px;">{report_data.get('week_start', '')} - {report_data.get('week_end', '')}</p>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <p style="color: #a1a1aa; line-height: 1.6; margin: 0 0 25px 0;">
                Hey {user_name}, here's your comprehensive weekly market analysis.
            </p>

            <!-- Key Metrics -->
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #71717a;">Key Metrics</h3>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 30px;">
                <div style="background-color: #27272a; border-radius: 6px; padding: 20px;">
                    <div style="color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Total Sales</div>
                    <div style="color: #fafafa; font-size: 24px; font-weight: bold; margin-top: 8px;">{report_data.get('total_sales', 0):,}</div>
                </div>
                <div style="background-color: #27272a; border-radius: 6px; padding: 20px;">
                    <div style="color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Total Volume</div>
                    <div style="color: #fafafa; font-size: 24px; font-weight: bold; margin-top: 8px;">${report_data.get('total_volume', 0):,.0f}</div>
                    <div style="color: {vol_color}; font-size: 13px; margin-top: 4px;">{vol_arrow} {abs(volume_change):.1f}% vs last week</div>
                </div>
                <div style="background-color: #27272a; border-radius: 6px; padding: 20px;">
                    <div style="color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Avg Sale Price</div>
                    <div style="color: #fafafa; font-size: 24px; font-weight: bold; margin-top: 8px;">${report_data.get('avg_sale_price', 0):.2f}</div>
                </div>
                <div style="background-color: #27272a; border-radius: 6px; padding: 20px;">
                    <div style="color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Unique Buyers</div>
                    <div style="color: #fafafa; font-size: 24px; font-weight: bold; margin-top: 8px;">{report_data.get('market_health', {}).get('unique_buyers', 0)}</div>
                </div>
            </div>

            <!-- Daily Breakdown -->
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #71717a;">Daily Sales</h3>
            <div style="background-color: #27272a; border-radius: 6px; padding: 20px; margin-bottom: 30px;">
                {daily_html if daily_html else '<p style="color: #71717a; text-align: center;">No data available</p>'}
            </div>

            <!-- Top Cards -->
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #71717a;">Top Cards by Volume</h3>
            <div style="background-color: #27272a; border-radius: 6px; padding: 15px 20px; margin-bottom: 30px; overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; min-width: 400px;">
                    <thead>
                        <tr>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: left; border-bottom: 1px solid #3f3f46;">#</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: left; border-bottom: 1px solid #3f3f46;">Card</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">Sales</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">Volume</th>
                        </tr>
                    </thead>
                    <tbody>
                        {top_cards_html if top_cards_html else '<tr><td colspan="4" style="padding: 20px 0; color: #71717a; text-align: center;">No data available</td></tr>'}
                    </tbody>
                </table>
            </div>

            <!-- Price Movers -->
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #71717a;">Biggest Price Movers</h3>
            <div style="background-color: #27272a; border-radius: 6px; padding: 15px 20px; margin-bottom: 30px; overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; min-width: 400px;">
                    <thead>
                        <tr>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: left; border-bottom: 1px solid #3f3f46;">Card</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">Was</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">Now</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">Change</th>
                        </tr>
                    </thead>
                    <tbody>
                        {movers_html if movers_html else '<tr><td colspan="4" style="padding: 20px 0; color: #71717a; text-align: center;">No significant price changes</td></tr>'}
                    </tbody>
                </table>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{settings.FRONTEND_URL}/market" style="display: inline-block; background-color: #fafafa; color: #000; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px;">VIEW FULL MARKET</a>
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0 0 10px 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
            <p style="margin: 0; color: #3f3f46; font-size: 11px;">
                <a href="{settings.FRONTEND_URL}/profile" style="color: #52525b;">Manage email preferences</a>
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] Weekly report sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send weekly report to {to_email}: {e}")
        return False


def send_price_alert(
    to_email: str,
    user_name: str,
    alert_data: Dict[str, Any]
) -> bool:
    """
    Send price alert email when a watched card hits target price.

    alert_data should include:
    - card_name: str
    - card_slug: str
    - alert_type: str ('above', 'below', 'any')
    - target_price: float
    - current_price: float
    - treatment: str
    - listing_url: str (optional)
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping price alert - RESEND_API_KEY not configured")
        return False

    alert_type = alert_data.get("alert_type", "any")
    if alert_type == "above":
        alert_message = f"has risen above your target of ${alert_data.get('target_price', 0):.2f}"
        alert_color = "#4ade80"
        alert_icon = "📈"
    elif alert_type == "below":
        alert_message = f"has dropped below your target of ${alert_data.get('target_price', 0):.2f}"
        alert_color = "#f87171"
        alert_icon = "📉"
    else:
        alert_message = f"has a new price"
        alert_color = "#fbbf24"
        alert_icon = "🔔"

    card_url = f"{settings.FRONTEND_URL}/cards/{alert_data.get('card_slug', '')}"

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": f"🔔 Price Alert: {alert_data.get('card_name', 'Card')} - ${alert_data.get('current_price', 0):.2f}",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="font-size: 48px; margin-bottom: 10px;">{alert_icon}</div>
            <h1 style="margin: 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">PRICE ALERT</h1>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <p style="color: #a1a1aa; line-height: 1.6; margin: 0 0 25px 0;">
                Hey {user_name}, a card on your watchlist {alert_message}!
            </p>

            <!-- Card Info -->
            <div style="background-color: #27272a; border-radius: 8px; padding: 25px; margin-bottom: 25px; text-align: center;">
                <h2 style="margin: 0 0 10px 0; font-size: 20px; color: #fafafa;">{alert_data.get('card_name', 'Unknown Card')}</h2>
                <div style="color: #71717a; font-size: 13px; margin-bottom: 20px;">{alert_data.get('treatment', 'Classic Paper')}</div>

                <div style="font-size: 48px; font-weight: bold; color: {alert_color}; margin: 20px 0;">
                    ${alert_data.get('current_price', 0):.2f}
                </div>

                <div style="color: #71717a; font-size: 14px;">
                    Target: ${alert_data.get('target_price', 0):.2f}
                </div>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{card_url}" style="display: inline-block; background-color: #fafafa; color: #000; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px; margin-right: 10px;">VIEW CARD</a>
                {f'<a href="{alert_data.get("listing_url", "")}" style="display: inline-block; background-color: transparent; color: #fafafa; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px; border: 1px solid #52525b;">VIEW LISTING</a>' if alert_data.get("listing_url") else ''}
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0 0 10px 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
            <p style="margin: 0; color: #3f3f46; font-size: 11px;">
                <a href="{settings.FRONTEND_URL}/profile" style="color: #52525b;">Manage price alerts</a>
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] Price alert sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send price alert to {to_email}: {e}")
        return False


def send_portfolio_summary(
    to_email: str,
    user_name: str,
    portfolio_data: Dict[str, Any]
) -> bool:
    """
    Send portfolio summary email with P&L and holdings.

    portfolio_data should include:
    - total_cards: int
    - total_cost_basis: float
    - total_market_value: float
    - total_profit_loss: float
    - total_profit_loss_percent: float
    - top_performers: List[Dict] with name, profit_loss, profit_loss_percent
    - worst_performers: List[Dict] with name, profit_loss, profit_loss_percent
    - recent_changes: List[Dict] with name, change_type, amount
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping portfolio summary - RESEND_API_KEY not configured")
        return False

    pnl = portfolio_data.get("total_profit_loss", 0)
    pnl_percent = portfolio_data.get("total_profit_loss_percent", 0)
    pnl_color = "#4ade80" if pnl >= 0 else "#f87171"
    pnl_icon = "📈" if pnl >= 0 else "📉"

    # Top performers
    top_html = ""
    for card in portfolio_data.get("top_performers", [])[:5]:
        card_pnl = card.get("profit_loss", 0)
        card_pnl_pct = card.get("profit_loss_percent", 0)
        top_html += f"""
        <tr>
            <td style="padding: 10px 0; color: #fafafa; font-size: 14px; border-bottom: 1px solid #27272a;">{card.get('name', 'Unknown')}</td>
            <td style="padding: 10px 0; color: #4ade80; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">+${card_pnl:.2f}</td>
            <td style="padding: 10px 0; color: #4ade80; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">+{card_pnl_pct:.1f}%</td>
        </tr>
        """

    # Worst performers
    worst_html = ""
    for card in portfolio_data.get("worst_performers", [])[:5]:
        card_pnl = card.get("profit_loss", 0)
        card_pnl_pct = card.get("profit_loss_percent", 0)
        worst_html += f"""
        <tr>
            <td style="padding: 10px 0; color: #fafafa; font-size: 14px; border-bottom: 1px solid #27272a;">{card.get('name', 'Unknown')}</td>
            <td style="padding: 10px 0; color: #f87171; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">${card_pnl:.2f}</td>
            <td style="padding: 10px 0; color: #f87171; font-size: 14px; text-align: right; border-bottom: 1px solid #27272a;">{card_pnl_pct:.1f}%</td>
        </tr>
        """

    try:
        resend.Emails.send({
            "from": settings.FROM_EMAIL,
            "to": [to_email],
            "subject": f"Portfolio Update: {'📈' if pnl >= 0 else '📉'} {'+' if pnl >= 0 else ''}${pnl:.2f} ({'+' if pnl_percent >= 0 else ''}{pnl_percent:.1f}%)",
            "html": f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #0a0a0a; color: #fafafa; margin: 0; padding: 40px 20px;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #18181b; border-radius: 8px; border: 1px solid #27272a; overflow: hidden;">
        <!-- Header -->
        <div style="background-color: #000; padding: 30px; text-align: center; border-bottom: 1px solid #27272a;">
            <div style="display: inline-block; width: 50px; height: 50px; background-color: #fff; line-height: 50px; font-size: 28px; font-weight: bold; color: #000;">W</div>
            <h1 style="margin: 15px 0 0 0; font-size: 24px; font-weight: bold; letter-spacing: 2px;">PORTFOLIO UPDATE</h1>
        </div>

        <!-- Content -->
        <div style="padding: 40px 30px;">
            <p style="color: #a1a1aa; line-height: 1.6; margin: 0 0 25px 0;">
                Hey {user_name}, here's your portfolio performance summary.
            </p>

            <!-- Portfolio Value -->
            <div style="background-color: #27272a; border-radius: 8px; padding: 30px; margin-bottom: 25px; text-align: center;">
                <div style="color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">Total Portfolio Value</div>
                <div style="font-size: 36px; font-weight: bold; color: #fafafa; margin: 15px 0;">
                    ${portfolio_data.get('total_market_value', 0):,.2f}
                </div>
                <div style="font-size: 20px; color: {pnl_color};">
                    {pnl_icon} {'+' if pnl >= 0 else ''}${pnl:,.2f} ({'+' if pnl_percent >= 0 else ''}{pnl_percent:.1f}%)
                </div>
                <div style="color: #71717a; font-size: 13px; margin-top: 15px;">
                    Cost Basis: ${portfolio_data.get('total_cost_basis', 0):,.2f} • {portfolio_data.get('total_cards', 0)} cards
                </div>
            </div>

            <!-- Top Performers -->
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #4ade80;">🏆 Top Performers</h3>
            <div style="background-color: #27272a; border-radius: 6px; padding: 15px 20px; margin-bottom: 25px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: left; border-bottom: 1px solid #3f3f46;">Card</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">P&L</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {top_html if top_html else '<tr><td colspan="3" style="padding: 20px 0; color: #71717a; text-align: center;">No data yet</td></tr>'}
                    </tbody>
                </table>
            </div>

            <!-- Worst Performers -->
            <h3 style="margin: 0 0 15px 0; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; color: #f87171;">📉 Needs Attention</h3>
            <div style="background-color: #27272a; border-radius: 6px; padding: 15px 20px; margin-bottom: 25px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: left; border-bottom: 1px solid #3f3f46;">Card</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">P&L</th>
                            <th style="padding: 10px 0; color: #52525b; font-size: 11px; text-transform: uppercase; text-align: right; border-bottom: 1px solid #3f3f46;">%</th>
                        </tr>
                    </thead>
                    <tbody>
                        {worst_html if worst_html else '<tr><td colspan="3" style="padding: 20px 0; color: #71717a; text-align: center;">No underperformers!</td></tr>'}
                    </tbody>
                </table>
            </div>

            <div style="text-align: center; margin: 30px 0;">
                <a href="{settings.FRONTEND_URL}/portfolio" style="display: inline-block; background-color: #fafafa; color: #000; padding: 14px 32px; text-decoration: none; font-weight: bold; font-size: 14px; letter-spacing: 1px; border-radius: 4px;">VIEW FULL PORTFOLIO</a>
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #000; padding: 20px 30px; text-align: center; border-top: 1px solid #27272a;">
            <p style="margin: 0 0 10px 0; color: #52525b; font-size: 12px;">
                WondersTracker - Market Intelligence for Wonders of the First
            </p>
            <p style="margin: 0; color: #3f3f46; font-size: 11px;">
                <a href="{settings.FRONTEND_URL}/profile" style="color: #52525b;">Manage email preferences</a>
            </p>
        </div>
    </div>
</body>
</html>
            """,
        })
        print(f"[Email] Portfolio summary sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send portfolio summary to {to_email}: {e}")
        return False
