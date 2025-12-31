import re
import urllib.parse

EBAY_BASE_URL = "https://www.ebay.com/sch/i.html"
TCG_CATEGORY_ID = "183454"  # CCG Individual Cards

# Patterns that indicate a bulk lot (random/mixed card sales)
# Note: Only match 2+ items to avoid false positives on "1x" or "X1" listings
BULK_LOT_PATTERNS = [
    r"(?i)\b([2-9]|\d{2,})\s*x\s*[-–]?\s*wonders",  # "2X Wonders...", "3x - Wonders..." (2+ items)
    r"(?i)^x([2-9]|\d{2,})\s",  # "X3 Playset..." (2+ items)
    r"(?i)\blot\s+of\s+(\d+)",  # "LOT OF 5 COMMONS"
    r"(?i)\brandom\s+\d+\s+cards?",  # "RANDOM 5 CARDS"
    r"(?i)\b\d+\s+random\s+",  # "10 RANDOM CARDS"
    r"(?i)\bmixed\s+lot",  # "MIXED LOT"
    r"(?i)\bassorted\s+cards?",  # "ASSORTED CARDS"
    r"(?i)\b(\d+)\s+card\s+lot\b",  # "5 CARD LOT"
    r"(?i)\bbulk\s+(?:sale|lot)",  # "BULK SALE"
    r"(?i)\bplayset\b",  # "PLAYSET" (typically 4 copies)
    r"(?i)\b([2-9]|\d{2,})\s*pcs?\b",  # "5 PCS", "10 PCS" (2+ items)
]

# Official product names that should NOT be flagged as bulk lots
# These are specific product names, not generic words
PRODUCT_EXCEPTIONS = [
    "play bundle",
    "blaster box",
    "collector booster box",
    "collector booster",
    "serialized advantage",
    "starter set",
    "starter deck",
    "booster box",
    "play pack",
    "collector pack",
    "silver pack",
]


def is_bulk_lot(title: str, product_type: str = "Single") -> bool:
    """
    Detects if a listing is a bulk lot (random assorted cards) vs legitimate product.

    Bulk lots are multi-card sales of random/mixed cards, NOT official sealed products.
    These corrupt FMP calculations by creating artificial floor prices.

    Examples:
        - "3X - Wonders of the First Mixed Lot $0.65" → True (bulk lot)
        - "LOT OF 5 COMMON CARDS" → True (bulk lot)
        - "2X Play Bundle" → False (selling 2 official bundles)
        - "Collector Booster Box" → False (sealed product)

    Args:
        title: Listing title to analyze
        product_type: Card product type (Single, Box, Pack, Bundle, Lot)

    Returns:
        True if bulk lot, False otherwise
    """
    title_lower = title.lower()

    # Check for official product names first (these are NOT bulk lots)
    for exception in PRODUCT_EXCEPTIONS:
        if exception in title_lower:
            return False

    # Special case: "case" must be followed by "of" to avoid false positives
    # e.g., "Case of 6 Boxes" is a product, but "showcase" is not
    if re.search(r"(?i)\bcase\s+of\s+\d+", title_lower):
        return False

    # Sealed products (Box, Pack, Bundle) are typically NOT bulk lots
    # unless they match a bulk pattern explicitly
    if product_type in ("Box", "Pack", "Bundle"):
        # Allow sealed products through by default
        # Only flag if explicit bulk lot pattern matches
        pass

    # Check for bulk lot patterns
    for pattern in BULK_LOT_PATTERNS:
        if re.search(pattern, title):
            return True

    return False


def build_ebay_url(card_name: str, set_name: str | None = None, sold_only: bool = True, page: int = 1) -> str:
    """
    Constructs an eBay search URL for a given card name.

    Args:
        card_name: The name of the card to search for.
        set_name: Optional set name to refine search (e.g. "Existence").
        sold_only: If True, returns only sold/completed listings (default True).
        page: Page number for pagination (default 1).

    Returns:
        A valid eBay search URL.
    """
    # Refine search query
    # If card name is short (<= 1 words), append "Wonders of the First" or set name to avoid generic matches
    query = card_name
    if len(card_name.split()) <= 2:
        query += " Wonders of the First"
    elif set_name:
        # Optional: Include set name for specificity if needed, but usually full card name + TCG name is best
        # query += f" {set_name}"
        pass

    # Ensure "Wonders of the First" is in query if not present, to target the TCG
    if "wonders" not in query.lower():
        query += " Wonders of the First"

    params = {
        "_nkw": query,
        "_sacat": TCG_CATEGORY_ID,
        "_ipg": "240",  # Max items per page to capture more history in one go
        "_pgn": str(page),  # Page number for pagination
        "RT": "nc",  # Result type? often used in ebay urls
    }

    if sold_only:
        # LH_Sold=1 implies sold items. eBay typically shows last 90 days of sold items.
        # To get MORE history would require Terapeak or other paid APIs.
        # Standard eBay search is limited to ~90 days for sold listings.
        params["LH_Sold"] = "1"
        params["LH_Complete"] = "1"

    query_string = urllib.parse.urlencode(params)
    return f"{EBAY_BASE_URL}?{query_string}"
