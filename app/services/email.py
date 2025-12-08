"""
Email Service using Resend

Handles transactional emails:
- Welcome emails for new users
- Password reset emails
- (Future) Price alerts, weekly digests
"""

import resend
from typing import Optional
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
