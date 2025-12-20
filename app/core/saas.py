"""
SaaS Mode Detection

Central module for detecting whether the application is running in SaaS or OSS mode.
This provides a single source of truth for all SaaS-related feature checks.

Usage:
    from app.core.saas import SAAS_ENABLED, is_saas_enabled

    if SAAS_ENABLED:
        # SaaS-specific code
        pass
"""

import logging

logger = logging.getLogger(__name__)


def _detect_saas_mode() -> bool:
    """
    Detect if the SaaS module is available.

    Returns True if the saas/ submodule is present and importable.
    """
    try:
        import saas  # noqa: F401 - intentional import to check availability

        return True
    except ImportError:
        return False


# Single source of truth for SaaS mode
SAAS_ENABLED = _detect_saas_mode()


def is_saas_enabled() -> bool:
    """Check if SaaS features are enabled."""
    return SAAS_ENABLED


def get_mode_info() -> dict:
    """
    Get detailed information about the current mode.

    Returns a dict suitable for health check endpoints.
    """
    features: dict[str, bool] = {
        "billing": False,
        "metering": False,
        "webhooks": False,
    }
    info: dict[str, object] = {
        "mode": "saas" if SAAS_ENABLED else "oss",
        "saas_enabled": SAAS_ENABLED,
        "features": features,
    }

    if SAAS_ENABLED:
        # Check individual feature availability
        try:
            from app.api.billing import BILLING_AVAILABLE

            features["billing"] = BILLING_AVAILABLE
        except ImportError:
            pass

        try:
            from app.middleware.metering import METERING_AVAILABLE

            features["metering"] = METERING_AVAILABLE
        except ImportError:
            pass

        try:
            from app.api.webhooks import WEBHOOKS_AVAILABLE

            features["webhooks"] = WEBHOOKS_AVAILABLE
        except ImportError:
            pass

    return info


# Log mode on module import
if SAAS_ENABLED:
    logger.debug("SaaS mode: ENABLED")
else:
    logger.debug("SaaS mode: DISABLED (OSS)")


__all__ = ["SAAS_ENABLED", "is_saas_enabled", "get_mode_info"]
