"""
Seller data extraction and normalization utilities.

This module handles:
- Extracting seller info from eBay listing HTML
- Normalizing seller names (removing extra text, feedback info)
- Seller data validation
"""

import re
from typing import Optional, Tuple
from bs4 import BeautifulSoup


def normalize_seller_name(raw_seller: Optional[str]) -> Optional[str]:
    """
    Normalize a seller name by removing extraneous text.

    Handles cases like:
    - "rhomscards  100% positive (1K)Top Rated Plus..." -> "rhomscards"
    - "  username  " -> "username"
    - "" -> None

    Returns None if the name is empty or invalid.
    """
    if not raw_seller:
        return None

    # Strip whitespace
    name = raw_seller.strip()

    if not name:
        return None

    # If it contains feedback info, extract just the username
    # Pattern: "username  100% positive (1K)..."
    if "positive" in name.lower() or "feedback" in name.lower():
        # Username is the first word before any numbers or special chars
        match = re.match(r'^([a-zA-Z0-9_\-\.]+)', name)
        if match:
            name = match.group(1)

    # Remove common suffixes that shouldn't be part of username
    patterns_to_remove = [
        r'\s+\d+%.*$',           # "100% positive..."
        r'\s+\(\d+[K]?\).*$',    # "(1K)..."
        r'\s+Top\s+Rated.*$',    # "Top Rated Plus..."
        r'\s+Sellers\s+with.*$', # "Sellers with highest..."
        r'\s+Returns,.*$',       # "Returns, money back"
    ]

    for pattern in patterns_to_remove:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)

    name = name.strip()

    # Validate: eBay usernames can only contain letters, numbers, underscores, hyphens, periods
    # and are 6-64 characters (though we'll be lenient on length for edge cases)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
        # If there are invalid chars, try to extract just the valid part
        match = re.match(r'^([a-zA-Z0-9_\-\.]+)', name)
        if match:
            name = match.group(1)
        else:
            return None

    # Must be at least 1 char
    if len(name) < 1:
        return None

    # Reject tracking parameters that look like usernames
    if re.match(r'^[pmls]\d+\.[pmls]\d+\.', name):
        return None

    # Normalize to lowercase for consistency
    return name.lower()


def extract_seller_from_html(html: str) -> Tuple[Optional[str], Optional[int], Optional[float]]:
    """
    Extract seller info from eBay item page HTML.
    Returns: (seller_name, feedback_score, feedback_percent)

    Multiple extraction methods are tried in order of reliability.
    """
    seller_name = None
    feedback_score = None
    feedback_percent = None

    # Method 1 (BEST): Look for "username" in JSON data - most reliable for modern eBay pages
    # This is the primary source of seller info in eBay's React-based pages
    username_match = re.search(r'"username"\s*:\s*"([^"]+)"', html)
    if username_match:
        candidate = username_match.group(1).strip()
        # Validate it's not a placeholder or tracking param
        if candidate and candidate != '@@' and not re.match(r'^[pmls]\d+\.', candidate):
            seller_name = candidate

    # Method 2: Look for /usr/ link in href (older pages)
    if not seller_name:
        usr_matches = re.findall(r'/usr/([^/?"\s]+)', html)
        for candidate in usr_matches:
            if candidate and candidate != '@@' and not re.match(r'^[pmls]\d+\.', candidate):
                seller_name = candidate
                break

    # Method 3: Look for sid= with actual seller username (not tracking params)
    # Real seller sids look like: sid=seller_name (alphanumeric with underscores/dashes)
    # Tracking params look like: sid=p4429486.m3561.l161211
    if not seller_name:
        sid_matches = re.findall(r'[?&]sid=([a-zA-Z][a-zA-Z0-9_\-]+)', html)
        for candidate in sid_matches:
            # Skip tracking parameters (start with p/m/l/s followed by digits and dots)
            if not re.match(r'^[pmls]\d+\.', candidate):
                seller_name = candidate
                break

    # Method 4: Fallback - look in structured seller data
    if not seller_name:
        patterns = [
            r'"sellerName"\s*:\s*"([^"]+)"',
            r'"seller_name"\s*:\s*"([^"]+)"',
            r'"sellerId"\s*:\s*"([^"]+)"',  # numeric ID as last resort
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                candidate = match.group(1).strip()
                if candidate and not candidate.isdigit():  # Skip numeric IDs
                    seller_name = candidate
                    break

    # Normalize the seller name
    seller_name = normalize_seller_name(seller_name)

    # Extract feedback if we found seller
    if seller_name:
        # Look for feedback percentage
        feedback_match = re.search(r'([\d.]+)%\s*positive', html, re.IGNORECASE)
        if feedback_match:
            try:
                feedback_percent = float(feedback_match.group(1))
            except ValueError:
                pass

        # Look for feedback score
        score_match = re.search(r'\((\d[\d,]*)\)', html)
        if score_match:
            try:
                feedback_score = int(score_match.group(1).replace(',', ''))
            except ValueError:
                pass

    return seller_name, feedback_score, feedback_percent


def validate_seller_name(name: str) -> bool:
    """
    Validate that a seller name looks like a real eBay username.

    eBay username rules:
    - 6-64 characters
    - Only letters, numbers, underscores, hyphens, periods
    - Cannot start/end with period or hyphen (we'll be lenient here)
    """
    if not name:
        return False

    # Check pattern
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', name):
        return False

    # Check length (being lenient, allowing 1-100)
    if len(name) < 1 or len(name) > 100:
        return False

    # Reject tracking parameter patterns (e.g., p4429486.m3561.l161211)
    if re.match(r'^[pmls]\d+\.[pmls]\d+\.', name):
        return False

    return True


def is_tracking_parameter(name: str) -> bool:
    """
    Check if a string looks like an eBay tracking parameter rather than a username.

    These patterns appear in URLs and can accidentally get extracted:
    - p4429486.m3561.l161211 (page/module/listing tracking)
    - Similar patterns starting with p/m/l/s followed by numbers and dots
    """
    if not name:
        return False

    # Pattern: letter + digits + dot + letter + digits + dot...
    # e.g., p4429486.m3561.l161211
    return bool(re.match(r'^[pmls]\d+\.[pmls]\d+\.', name))
