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
import time
from typing import Optional, Dict, Any, Callable, cast
from functools import wraps
from app.core.config import settings

# Initialize Resend
resend.api_key = settings.RESEND_API_KEY


# =============================================================================
# REUSABLE EMAIL COMPONENTS - Mobile-First, Data Visualization
# =============================================================================


def _email_wrapper(content: str, title: str = "WONDERSTRACKER") -> str:
    """Wrap email content in table-based layout that works in all email clients."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: 'Courier New', Courier, monospace; background-color: #111; margin: 0; padding: 0;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #111;">
        <tr>
            <td align="center" style="padding: 32px 16px;">
                <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 520px; background-color: #1a1a1a; border: 1px solid #333;">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 24px 28px; border-bottom: 1px solid #333;">
                            <table cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="width: 36px; height: 36px; background-color: #fff; text-align: center; vertical-align: middle; font-size: 18px; font-weight: bold; color: #111;">W</td>
                                    <td style="padding-left: 14px; font-size: 11px; font-weight: bold; letter-spacing: 3px; color: #888; vertical-align: middle;">{title}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding: 28px;">
                            {content}
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 28px; border-top: 1px solid #333; background-color: #151515;">
                            <p style="margin: 0; font-size: 10px; letter-spacing: 1px; color: #666;">WONDERSTRACKER</p>
                            <p style="margin: 8px 0 0 0;">
                                <a href="{settings.FRONTEND_URL}/profile" style="color: #7dd3a8; font-size: 11px; text-decoration: none;">Manage preferences</a>
                                <span style="color: #444; margin: 0 8px;">|</span>
                                <a href="{settings.FRONTEND_URL}/unsubscribe" style="color: #666; font-size: 11px; text-decoration: none;">Unsubscribe</a>
                            </p>
                            <p style="margin: 12px 0 0 0; font-size: 9px; color: #444; line-height: 1.5;">
                                WondersTracker · Los Angeles, CA · You're receiving this because you signed up for market updates.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def _send_email(params: Dict[str, Any]) -> Any:
    """Wrapper for resend.Emails.send with proper typing."""
    return resend.Emails.send(cast(Any, params))


def with_retry(max_attempts: int = 3, base_delay: float = 1.0):
    """
    Decorator that retries a function with exponential backoff.
    For transient email delivery failures (network issues, rate limits).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2**attempt)  # Exponential backoff
                        print(f"[Email] Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                        time.sleep(delay)
            print(f"[Email] All {max_attempts} attempts failed: {last_exception}")
            return False

        return wrapper

    return decorator


@with_retry(max_attempts=3)
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
        _send_email(
            {
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
            }
        )
        print(f"[Email] Welcome email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send welcome email to {to_email}: {e}")
        return False


@with_retry(max_attempts=3)
def send_personal_welcome_email(to_email: str, user_name: Optional[str] = None) -> bool:
    """
    Send a personal welcome email from Cody Robertson 1 day after signup.
    More personal tone, inviting feedback and community engagement.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping personal welcome email - RESEND_API_KEY not configured")
        return False

    name = user_name or to_email.split("@")[0]

    try:
        _send_email(
            {
                "from": "Cody Robertson <cody@wonderstracker.com>",
                "reply_to": "cody@wonderstracker.com",
                "to": [to_email],
                "subject": f"Hey {name} - Quick note from the founder",
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
        <div style="background-color: #000; padding: 30px; border-bottom: 1px solid #27272a;">
            <div style="display: flex; align-items: center; gap: 15px;">
                <div style="width: 50px; height: 50px; background-color: #27272a; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 24px;">👋</div>
                <div>
                    <h1 style="margin: 0; font-size: 20px; font-weight: bold; color: #fafafa;">Hey {name}!</h1>
                    <p style="margin: 5px 0 0 0; color: #71717a; font-size: 14px;">A personal note from the founder</p>
                </div>
            </div>
        </div>

        <!-- Content -->
        <div style="padding: 35px 30px;">
            <p style="color: #e4e4e7; line-height: 1.8; margin: 0 0 20px 0; font-size: 15px;">
                I'm Cody, the creator of WondersTracker. I noticed you signed up yesterday and wanted to reach out personally.
            </p>

            <p style="color: #e4e4e7; line-height: 1.8; margin: 0 0 20px 0; font-size: 15px;">
                I built this platform because I'm a collector myself and was frustrated with how hard it was to track Wonders of the First prices. Now you can:
            </p>

            <div style="background-color: #27272a; border-radius: 6px; padding: 20px; margin: 25px 0; border-left: 3px solid #3b82f6;">
                <ul style="margin: 0; padding: 0 0 0 20px; color: #a1a1aa; line-height: 2;">
                    <li><strong style="color: #fafafa;">Track real-time prices</strong> - eBay & Blokpax data updated hourly</li>
                    <li><strong style="color: #fafafa;">Build your portfolio</strong> - Track what you own and your total value</li>
                    <li><strong style="color: #fafafa;">Analyze market trends</strong> - See price history, VWAP, and floor prices</li>
                    <li><strong style="color: #fafafa;">Set price alerts</strong> - Get notified when cards hit your target price</li>
                </ul>
            </div>

            <p style="color: #e4e4e7; line-height: 1.8; margin: 0 0 20px 0; font-size: 15px;">
                <strong>I'd love your feedback.</strong> What features would make this more useful for you? What's missing? What's confusing?
            </p>

            <p style="color: #e4e4e7; line-height: 1.8; margin: 0 0 25px 0; font-size: 15px;">
                Hit me up anytime:
            </p>

            <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 30px;">
                <a href="https://discord.com/users/degendraper" style="display: inline-flex; align-items: center; gap: 8px; background-color: #5865F2; color: #fff; padding: 12px 20px; text-decoration: none; font-weight: 600; font-size: 14px; border-radius: 6px;">
                    <span>💬</span> DM me: degendraper
                </a>
                <a href="https://discord.gg/wonderstracker" style="display: inline-flex; align-items: center; gap: 8px; background-color: #27272a; color: #fafafa; padding: 12px 20px; text-decoration: none; font-weight: 600; font-size: 14px; border-radius: 6px; border: 1px solid #3f3f46;">
                    <span>🎮</span> Join our Discord
                </a>
            </div>

            <p style="color: #a1a1aa; line-height: 1.8; margin: 0 0 10px 0; font-size: 15px;">
                Or just reply to this email - I read every single one.
            </p>

            <p style="color: #e4e4e7; line-height: 1.8; margin: 30px 0 0 0; font-size: 15px;">
                Happy collecting,<br>
                <strong style="color: #fafafa;">Cody Robertson</strong><br>
                <span style="color: #71717a; font-size: 13px;">Founder, WondersTracker</span>
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
            }
        )
        print(f"[Email] Personal welcome email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send personal welcome email to {to_email}: {e}")
        return False


@with_retry(max_attempts=3)
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
        _send_email(
            {
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
            }
        )
        print(f"[Email] Password reset email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send password reset email to {to_email}: {e}")
        return False


def send_api_access_request_email(
    requester_email: str, requester_name: str, use_case: str, company: Optional[str] = None
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
        _send_email(
            {
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
            }
        )
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
        _send_email(
            {
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
            }
        )
        print(f"[Email] API access approved email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send API access approved email to {to_email}: {e}")
        return False


@with_retry(max_attempts=3)
def send_api_key_approved_email(to_email: str, user_name: str, api_key: str) -> bool:
    """
    Send email to user when their API access is approved with their new key.
    Returns True if sent successfully, False otherwise.
    """
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping API key approved email - RESEND_API_KEY not configured")
        return False

    try:
        _send_email(
            {
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
            }
        )
        print(f"[Email] API key approved email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send API key approved email to {to_email}: {e}")
        return False


# ============== MARKETING / DIGEST EMAILS ==============


def send_daily_market_digest(to_email: str, user_name: str, market_data: Dict[str, Any]) -> bool:
    """Send daily market digest email. Table-based layout for email client compatibility."""
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping daily digest - RESEND_API_KEY not configured")
        return False

    total_sales = market_data.get("total_sales", 0)
    total_volume = market_data.get("total_volume", 0)
    sentiment = market_data.get("market_sentiment", "neutral")

    # Build gainers rows
    gainers = market_data.get("top_gainers", [])[:5]
    gainers_rows = ""
    for card in gainers:
        change = card.get("change_percent", 0)
        price = card.get("price", 0)
        gainers_rows += f"""<tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">{card.get("name", "Unknown")}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 70px;">${price:.2f}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 60px;">+{change:.1f}%</td>
        </tr>"""

    # Build losers rows
    losers = market_data.get("top_losers", [])[:5]
    losers_rows = ""
    for card in losers:
        change = card.get("change_percent", 0)
        price = card.get("price", 0)
        losers_rows += f"""<tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">{card.get("name", "Unknown")}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 70px;">${price:.2f}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #ef4444; font-size: 13px; font-weight: bold; text-align: right; width: 60px;">{change:.1f}%</td>
        </tr>"""

    # Build deals rows
    deals = market_data.get("hot_deals", [])[:3]
    deals_rows = ""
    for deal in deals:
        floor = deal.get("floor_price", 0)
        price = deal.get("price", 0)
        deals_rows += f"""<tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">{deal.get("name", "Unknown")}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 70px;">${price:.2f}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 80px;">floor ${floor:.2f}</td>
        </tr>"""

    content = f"""
        <!-- Hero Stats -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 20px; background: #222; border: 1px solid #333;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">VOLUME</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 28px; font-weight: bold;">${total_volume:,.0f}</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">SALES</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 28px; font-weight: bold;">{total_sales}</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">SENTIMENT</p>
                                <p style="margin: 8px 0 0 0; color: #7dd3a8; font-size: 14px; font-weight: bold;">{sentiment.upper()}</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Gainers -->
        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">TOP GAINERS</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            {gainers_rows if gainers_rows else '<tr><td style="color: #666; font-size: 12px; padding: 12px 0;">No significant gainers today</td></tr>'}
        </table>

        <!-- Losers -->
        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">TOP LOSERS</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            {losers_rows if losers_rows else '<tr><td style="color: #666; font-size: 12px; padding: 12px 0;">No significant losers today</td></tr>'}
        </table>

        <!-- Deals -->
        {f'''<p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">BELOW FLOOR</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            {deals_rows}
        </table>''' if deals_rows else ''}

        <!-- CTA -->
        <table cellpadding="0" cellspacing="0">
            <tr>
                <td style="background: #fff; padding: 12px 24px;">
                    <a href="{settings.FRONTEND_URL}/market" style="color: #111; font-size: 11px; font-weight: bold; letter-spacing: 2px; text-decoration: none;">VIEW MARKET →</a>
                </td>
            </tr>
        </table>
    """

    try:
        _send_email(
            {
                "from": settings.FROM_EMAIL,
                "to": [to_email],
                "subject": f"Daily Digest: {total_sales} sales · ${total_volume:,.0f}",
                "html": _email_wrapper(content, "DAILY DIGEST"),
            }
        )
        print(f"[Email] Daily digest sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send daily digest to {to_email}: {e}")
        return False


def send_weekly_market_report(to_email: str, user_name: str, report_data: Dict[str, Any]) -> bool:
    """Send weekly market report email. Table-based layout for email client compatibility."""
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping weekly report - RESEND_API_KEY not configured")
        return False

    total_sales = report_data.get("total_sales", 0)
    total_volume = report_data.get("total_volume", 0)
    volume_change = report_data.get("volume_change", 0)
    avg_price = report_data.get("avg_sale_price", 0)
    week_start = report_data.get("week_start", "")
    week_end = report_data.get("week_end", "")
    change_color = "#7dd3a8" if volume_change >= 0 else "#ef4444"
    change_sign = "+" if volume_change >= 0 else ""

    # Daily breakdown rows
    daily_data = report_data.get("daily_breakdown", [])
    max_vol = max([d.get("volume", 0) for d in daily_data]) if daily_data else 1
    daily_rows = ""
    for day in daily_data:
        vol = day.get("volume", 0)
        sales = day.get("sales", 0)
        date_str = day.get("date", "")[-5:] if len(day.get("date", "")) > 5 else day.get("date", "")
        bar_width = int((vol / max_vol) * 100) if max_vol > 0 else 0
        daily_rows += f"""<tr>
            <td style="padding: 8px 0; color: #888; font-size: 12px; width: 50px;">{date_str}</td>
            <td style="padding: 8px 12px;">
                <div style="background: #333; height: 6px; width: 100%;">
                    <div style="background: #7dd3a8; height: 6px; width: {bar_width}%;"></div>
                </div>
            </td>
            <td style="padding: 8px 0; color: #fff; font-size: 12px; text-align: right; width: 70px;">${vol:,.0f}</td>
            <td style="padding: 8px 0; color: #666; font-size: 11px; text-align: right; width: 50px;">{sales} sales</td>
        </tr>"""

    # Top sellers rows
    top_cards = report_data.get("top_cards_by_volume", [])[:5]
    max_card_vol = max([c.get("volume", 0) for c in top_cards]) if top_cards else 1
    seller_rows = ""
    for i, card in enumerate(top_cards, 1):
        vol = card.get("volume", 0)
        sales = card.get("sales", 0)
        bar_width = int((vol / max_card_vol) * 100) if max_card_vol > 0 else 0
        seller_rows += f"""<tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">{i}. {card.get("name", "Unknown")}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; width: 60px;">{sales} sales</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 70px;">${vol:,.0f}</td>
        </tr>"""

    content = f"""
        <!-- Period -->
        <p style="margin: 0 0 24px 0; color: #666; font-size: 12px;">{week_start} – {week_end}</p>

        <!-- Hero Stats -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 20px; background: #222; border: 1px solid #333;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">VOLUME</p>
                                <p style="margin: 8px 0 4px 0; color: #fff; font-size: 24px; font-weight: bold;">${total_volume:,.0f}</p>
                                <p style="margin: 0; color: {change_color}; font-size: 12px;">{change_sign}{volume_change:.1f}%</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">SALES</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 24px; font-weight: bold;">{total_sales}</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">AVG PRICE</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 24px; font-weight: bold;">${avg_price:.0f}</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Daily Breakdown -->
        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">DAILY BREAKDOWN</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            {daily_rows if daily_rows else '<tr><td style="color: #666; font-size: 12px; padding: 12px 0;">No activity this week</td></tr>'}
        </table>

        <!-- Top Sellers -->
        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">TOP SELLERS</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            {seller_rows if seller_rows else '<tr><td style="color: #666; font-size: 12px; padding: 12px 0;">No sales this week</td></tr>'}
        </table>

        <!-- CTA -->
        <table cellpadding="0" cellspacing="0">
            <tr>
                <td style="background: #fff; padding: 12px 24px;">
                    <a href="{settings.FRONTEND_URL}/market" style="color: #111; font-size: 11px; font-weight: bold; letter-spacing: 2px; text-decoration: none;">VIEW MARKET →</a>
                </td>
            </tr>
        </table>
    """

    try:
        _send_email(
            {
                "from": settings.FROM_EMAIL,
                "to": [to_email],
                "subject": f"Weekly Report: ${total_volume:,.0f} volume · {total_sales} sales",
                "html": _email_wrapper(content, "WEEKLY REPORT"),
            }
        )
        print(f"[Email] Weekly report sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send weekly report to {to_email}: {e}")
        return False


def send_price_alert(to_email: str, user_name: str, alert_data: Dict[str, Any]) -> bool:
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
        alert_message = "has a new price"
        alert_color = "#fbbf24"
        alert_icon = "🔔"

    card_url = f"{settings.FRONTEND_URL}/cards/{alert_data.get('card_slug', '')}"

    try:
        _send_email(
            {
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
            }
        )
        print(f"[Email] Price alert sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send price alert to {to_email}: {e}")
        return False


def send_portfolio_summary(to_email: str, user_name: str, portfolio_data: Dict[str, Any]) -> bool:
    """Send portfolio summary email. Table-based layout for email client compatibility."""
    if not settings.RESEND_API_KEY:
        print("[Email] Skipping portfolio summary - RESEND_API_KEY not configured")
        return False

    pnl = portfolio_data.get("total_profit_loss", 0)
    pnl_percent = portfolio_data.get("total_profit_loss_percent", 0)
    market_value = portfolio_data.get("total_market_value", 0)
    cost_basis = portfolio_data.get("total_cost_basis", 0)
    total_cards = portfolio_data.get("total_cards", 0)
    is_profit = pnl >= 0
    pnl_color = "#7dd3a8" if is_profit else "#ef4444"
    pnl_sign = "+" if is_profit else ""

    # Build top performers rows
    top_performers = portfolio_data.get("top_performers", [])[:5]
    top_rows = ""
    for card in top_performers:
        card_pnl = card.get("profit_loss", 0)
        card_pct = card.get("profit_loss_percent", 0)
        top_rows += f"""<tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">{card.get("name", "Unknown")}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #7dd3a8; font-size: 13px; font-weight: bold; text-align: right; width: 80px;">+${card_pnl:.2f}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 60px;">+{card_pct:.0f}%</td>
        </tr>"""

    # Build worst performers rows
    worst_performers = portfolio_data.get("worst_performers", [])[:5]
    worst_rows = ""
    for card in worst_performers:
        card_pnl = card.get("profit_loss", 0)
        card_pct = card.get("profit_loss_percent", 0)
        worst_rows += f"""<tr>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #fff; font-size: 13px;">{card.get("name", "Unknown")}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #ef4444; font-size: 13px; font-weight: bold; text-align: right; width: 80px;">-${abs(card_pnl):.2f}</td>
            <td style="padding: 10px 0; border-bottom: 1px solid #333; color: #888; font-size: 12px; text-align: right; width: 60px;">{card_pct:.0f}%</td>
        </tr>"""

    content = f"""
        <!-- Hero Stats -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="padding: 20px; background: #222; border: 1px solid #333;">
                    <table width="100%" cellpadding="0" cellspacing="0">
                        <tr>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">VALUE</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 24px; font-weight: bold;">${market_value:,.0f}</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px; border-right: 1px solid #444;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">P&L</p>
                                <p style="margin: 8px 0 4px 0; color: {pnl_color}; font-size: 24px; font-weight: bold;">{pnl_sign}${abs(pnl):,.0f}</p>
                                <p style="margin: 0; color: {pnl_color}; font-size: 12px;">{pnl_sign}{pnl_percent:.1f}%</p>
                            </td>
                            <td style="text-align: center; padding: 0 10px;">
                                <p style="margin: 0; color: #888; font-size: 10px; letter-spacing: 2px;">HOLDINGS</p>
                                <p style="margin: 8px 0 0 0; color: #fff; font-size: 24px; font-weight: bold;">{total_cards}</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Cost Basis -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            <tr>
                <td style="color: #888; font-size: 12px;">Cost Basis</td>
                <td style="color: #fff; font-size: 12px; text-align: right;">${cost_basis:,.2f}</td>
            </tr>
        </table>

        <!-- Top Performers -->
        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">TOP PERFORMERS</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            {top_rows if top_rows else '<tr><td style="color: #666; font-size: 12px; padding: 12px 0;">No data yet</td></tr>'}
        </table>

        <!-- Worst Performers -->
        <p style="margin: 0 0 12px 0; color: #888; font-size: 10px; letter-spacing: 2px; border-bottom: 1px solid #333; padding-bottom: 8px;">NEEDS ATTENTION</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
            {worst_rows if worst_rows else '<tr><td style="color: #666; font-size: 12px; padding: 12px 0;">All holdings performing well</td></tr>'}
        </table>

        <!-- CTA -->
        <table cellpadding="0" cellspacing="0">
            <tr>
                <td style="background: #fff; padding: 12px 24px;">
                    <a href="{settings.FRONTEND_URL}/portfolio" style="color: #111; font-size: 11px; font-weight: bold; letter-spacing: 2px; text-decoration: none;">VIEW PORTFOLIO →</a>
                </td>
            </tr>
        </table>
    """

    try:
        _send_email(
            {
                "from": settings.FROM_EMAIL,
                "to": [to_email],
                "subject": f"Portfolio: {pnl_sign}${abs(pnl):.2f} ({pnl_sign}{pnl_percent:.1f}%)",
                "html": _email_wrapper(content, "PORTFOLIO"),
            }
        )
        print(f"[Email] Portfolio summary sent to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send portfolio summary to {to_email}: {e}")
        return False
