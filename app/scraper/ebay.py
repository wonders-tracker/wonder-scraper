from bs4 import BeautifulSoup
from typing import List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from dateutil import parser
import re
import difflib
from sqlmodel import Session, select
from app.core.typing import col
from app.models.market import MarketPrice
from app.services.ai_extractor import get_ai_extractor
from app.db import engine
from app.scraper.blocklist import load_blocklist
from app.scraper.utils import is_bulk_lot

STOPWORDS = {
    "the",
    "of",
    "a",
    "an",
    "in",
    "on",
    "at",
    "for",
    "to",
    "with",
    "by",
    "and",
    "or",
    "wonders",
    "first",
    "existence",
}


def score_sealed_match(title: str, card_name: str, product_type: str) -> int:
    """
    Score how well a listing title matches a sealed product card.

    Higher score = better match. Used to determine which card a listing
    should be assigned to when it could match multiple sealed products.

    Scoring:
    - Exact card name in title: +100
    - Key phrase matches: +20-50 each
    - Product type alignment: +15
    - Specificity bonuses: +15-25
    - Generic card penalties: -10 to -30

    Returns: integer score (higher = better match)
    """
    if product_type == "Single":
        return 0  # Not applicable to singles

    title_lower = title.lower()
    card_lower = card_name.lower()
    score = 0

    # 1. Exact card name match (strongest signal)
    if card_lower in title_lower:
        score += 100

    # 2. Key phrase matching
    # Collector Booster Box specific
    if "collector booster box" in card_lower:
        if "collector" in title_lower and "booster" in title_lower and "box" in title_lower:
            score += 50
        if "collector booster box" in title_lower:
            score += 30
        # Penalty if it's actually a bundle/blaster
        if "bundle" in title_lower or "blaster" in title_lower:
            score -= 30

    # Play Booster Pack specific
    if "play booster pack" in card_lower:
        if "play" in title_lower and "pack" in title_lower:
            score += 40
        # Penalty for bundles when searching for packs
        if "bundle" in title_lower or "blaster box" in title_lower:
            score -= 30

    # Play Bundle / Blaster Box specific
    if "play booster bundle" in card_lower or "bundle" in card_lower:
        if "play bundle" in title_lower or "blaster box" in title_lower:
            score += 50
        if "bundle" in title_lower:
            score += 20
        # Penalty if it's a box (not bundle)
        if "collector booster box" in title_lower:
            score -= 20

    # Collector Booster Pack specific
    if "collector booster pack" in card_lower:
        if "collector" in title_lower and "pack" in title_lower:
            score += 40
        # Penalty for boxes when searching for packs
        if "box" in title_lower and "blaster" not in title_lower:
            score -= 30

    # 3. Product type alignment
    if product_type == "Box":
        if "box" in title_lower and "blaster" not in title_lower:
            score += 15
        if "case" in title_lower:
            score += 10
    elif product_type == "Pack":
        if "pack" in title_lower and "box" not in title_lower:
            score += 15
    elif product_type == "Bundle":
        if "bundle" in title_lower or "blaster" in title_lower:
            score += 15
    elif product_type == "Lot":
        if "lot" in title_lower or "bulk" in title_lower:
            score += 15

    # 4. Specificity bonuses
    # More specific cards get bonuses when listing matches
    if "collector" in card_lower and "collector" in title_lower:
        score += 15
    if "play" in card_lower and "play" in title_lower:
        score += 15
    if "serialized advantage" in card_lower and "serialized advantage" in title_lower:
        score += 25
    if "starter" in card_lower and "starter" in title_lower:
        score += 25

    # 5. Generic card penalties
    # Generic cards (like "Existence Booster Box") should lose to specific ones
    generic_names = [
        "existence booster box",
        "existence booster pack",
        "existence sealed pack",
        "wonders of the first booster",
        "booster box",
        "booster pack",
    ]
    for generic in generic_names:
        if generic in card_lower:
            # This card is generic - lower its score
            score -= 10
            break

    # 6. Keyword presence bonus (tie-breaker)
    # Give small bonus when card name keywords appear in title
    card_words = set(card_lower.split()) - {"of", "the", "a", "wonders", "first", "existence"}
    title_words = set(title_lower.split())
    matching_words = card_words & title_words
    score += len(matching_words) * 2

    return score


def _bulk_check_indexed(
    card_id: int,
    listings_data: List[dict],
    check_global: bool = True,
    card_name: str = "",
    product_type: str = "Single",
) -> set:
    """
    Bulk check if listings already exist in database (avoids N+1 query problem).

    For sealed products, uses smart matching to assign listings to the best-matching card.
    If a listing exists for a different card but the current card is a better match,
    it updates the existing record's card_id.

    Args:
        card_id: Card ID to check against
        listings_data: List of dicts with keys: external_id, title, price, sold_date
        check_global: If True, also check if external_id exists for ANY card
        card_name: Name of the card we're searching for (for smart matching)
        product_type: Type of product (Single, Box, Pack, Bundle, Lot)

    Returns:
        Set of indices of listings that are already indexed (should be skipped)
    """
    from app.models.card import Card
    from sqlalchemy import text

    if not listings_data:
        return set()

    indexed_indices = set()

    with Session(engine) as session:
        # Check by external_ids in bulk (most reliable)
        external_ids = [listing["external_id"] for listing in listings_data if listing.get("external_id")]

        if external_ids:
            if check_global:
                # Check if external_id exists for ANY card
                all_existing = session.execute(
                    select(MarketPrice.external_id, MarketPrice.card_id, MarketPrice.id).where(
                        col(MarketPrice.external_id).in_(external_ids)
                    )
                ).all()

                # Build maps for existing records
                existing_for_this_card = {ext_id for ext_id, cid, mid in all_existing if cid == card_id}
                existing_other_cards = {ext_id: (cid, mid) for ext_id, cid, mid in all_existing if cid != card_id}

                # For sealed products, use smart matching to determine best card assignment
                is_sealed = product_type in ("Box", "Pack", "Bundle", "Lot")

                for i, listing in enumerate(listings_data):
                    ext_id = listing.get("external_id")
                    if not ext_id:
                        continue

                    if ext_id in existing_for_this_card:
                        # Already indexed for this exact card - skip
                        indexed_indices.add(i)
                    elif ext_id in existing_other_cards:
                        # Exists for a different card
                        if is_sealed and card_name:
                            # Smart matching: compare scores to find best card
                            other_card_id, market_price_id = existing_other_cards[ext_id]
                            title = listing.get("title", "")

                            # Get the other card's details
                            other_card = session.execute(select(Card).where(Card.id == other_card_id)).scalars().first()

                            if other_card:
                                # Score current card vs the existing card
                                current_score = score_sealed_match(title, card_name, product_type)
                                other_score = score_sealed_match(title, other_card.name, other_card.product_type)

                                if current_score > other_score:
                                    # Current card is a better match - update the existing record
                                    session.execute(
                                        text("UPDATE marketprice SET card_id = :card_id WHERE id = :id"),
                                        {"card_id": card_id, "id": market_price_id},
                                    )
                                    session.commit()
                                    # Mark as indexed since we just updated it
                                    indexed_indices.add(i)
                                else:
                                    # Other card is equal or better match - skip
                                    indexed_indices.add(i)
                            else:
                                # Other card not found (shouldn't happen) - skip to avoid errors
                                indexed_indices.add(i)
                        else:
                            # Not sealed or no card_name - just skip to avoid duplicates
                            indexed_indices.add(i)
            else:
                # Original behavior: only check this card_id
                existing_ids = session.execute(
                    select(MarketPrice.external_id).where(
                        col(MarketPrice.external_id).in_(external_ids), MarketPrice.card_id == card_id
                    )
                ).all()
                existing_ids_set = set(existing_ids)

                # Mark indices with existing external_ids for THIS card
                for i, listing in enumerate(listings_data):
                    if listing.get("external_id") in existing_ids_set:
                        indexed_indices.add(i)

        # Check by composite key for listings without external_id or not found
        # Build OR conditions for composite keys
        from sqlalchemy import and_, or_

        composite_conditions = []
        composite_index_map = {}  # Maps condition index to listing index

        for i, listing in enumerate(listings_data):
            if i not in indexed_indices:  # Not already found by external_id
                condition = and_(
                    col(MarketPrice.card_id) == card_id,
                    col(MarketPrice.title) == listing["title"],
                    col(MarketPrice.price) == listing["price"],
                    col(MarketPrice.sold_date) == listing["sold_date"],
                )
                composite_conditions.append(condition)
                composite_index_map[len(composite_conditions) - 1] = i

        if composite_conditions:
            # Query with OR of all composite conditions
            existing_composites = session.execute(
                select(MarketPrice.title, MarketPrice.price, MarketPrice.sold_date)
                .where(or_(*composite_conditions))
                .distinct()
            ).all()

            # Mark indices that match composite keys
            for existing in existing_composites:
                for i, listing in enumerate(listings_data):
                    if (
                        i not in indexed_indices
                        and listing["title"] == existing[0]
                        and listing["price"] == existing[1]
                        and listing["sold_date"] == existing[2]
                    ):
                        indexed_indices.add(i)

    return indexed_indices


def parse_search_results(
    html_content: str,
    card_id: int = 0,
    card_name: str = "",
    target_rarity: str = "",
    return_all: bool = False,
    product_type: str = "Single",
) -> List[MarketPrice]:
    """
    Parses eBay HTML search results and extracts market prices (Sold listings).

    Args:
        return_all: If True, returns all valid listings (for stats).
                   If False, returns only new listings not in DB (for saving).
        product_type: Type of product (Single, Box, Pack, Lot) - affects treatment detection.
    """
    return _parse_generic_results(
        html_content,
        card_id,
        listing_type="sold",
        card_name=card_name,
        target_rarity=target_rarity,
        return_all=return_all,
        product_type=product_type,
    )


def parse_active_results(
    html_content: str, card_id: int = 0, card_name: str = "", target_rarity: str = "", product_type: str = "Single"
) -> List[MarketPrice]:
    """
    Parses eBay HTML search results for ACTIVE listings.

    Args:
        product_type: Type of product (Single, Box, Pack, Lot) - affects treatment detection.
    """
    return _parse_generic_results(
        html_content,
        card_id,
        listing_type="active",
        card_name=card_name,
        target_rarity=target_rarity,
        product_type=product_type,
    )


def _extract_item_details(item) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts item ID and URL from the listing element.
    """
    link_elem = item.select_one("a.s-item__link, a.s-card__link")
    if not link_elem:
        return None, None

    url = link_elem.get("href", "")
    # Extract ID from URL: .../itm/1234567890...
    # eBay URLs often look like: https://www.ebay.com/itm/1234567890?hash=...
    match = re.search(r"/itm/(\d+)", url)
    item_id = match.group(1) if match else None

    # Clean URL (remove query params)
    if url and "?" in url:
        url = url.split("?")[0]

    return item_id, url


def parse_total_results(html_content: str) -> int:
    """
    Parses the total number of results from the eBay search page header.
    """
    soup = BeautifulSoup(html_content, "lxml")
    result_count_elem = soup.select_one(".srp-controls__count-heading, .srp-controls__count-heading span.BOLD")
    if result_count_elem:
        text = result_count_elem.get_text(strip=True)
        # Handle "1,200+ results" format (with optional plus sign)
        match = re.search(r"([\d,]+)\+?\s*results", text)
        if match:
            return int(match.group(1).replace(",", ""))
    return 0


def _is_alt_art(title: str) -> bool:
    """Check if title indicates an Alt Art variant."""
    title_lower = title.lower()

    # Explicit alt art mentions
    if "alt art" in title_lower or "alternate art" in title_lower:
        return True

    # A1-A8 numbering pattern (e.g., "#A2-361/401", "A5-361/401")
    if re.search(r"[#\s]a[1-8]-\d+/\d+", title_lower):
        return True

    return False


def _detect_treatment(title: str, product_type: str = "Single") -> str | None:
    """
    Detects treatment based on title keywords.
    For singles: card treatments (Foil, Serialized, etc.) or None if unknown
    For boxes/packs/lots: simplified condition (Sealed, Open Box)

    Returns None for singles when treatment cannot be determined from title keywords.
    This distinguishes "unknown treatment" from "definitely Classic Paper".
    """
    title_lower = title.lower()

    # Handle sealed products (Box, Pack, Lot, Bundle)
    # Simplified to: Sealed, Open Box
    if product_type in ("Box", "Pack", "Lot", "Bundle"):
        # Check for sealed indicators first (unopened before opened check!)
        if any(
            kw in title_lower for kw in ["sealed", "factory sealed", "factory-sealed", "new", "unopened", "nib", "mint"]
        ):
            return "Sealed"
        # Check for opened/used indicators
        if "open box" in title_lower or "opened" in title_lower or "used" in title_lower:
            return "Open Box"
        # Default - assume sealed if no indicators (most eBay listings are sealed)
        return "Sealed"

    # Check for Alt Art first (will be appended to base treatment)
    is_alt_art = _is_alt_art(title)

    # Handle singles (cards)
    base_treatment = None

    # 1. Serialized / OCM (Highest Priority)
    if (
        "serialized" in title_lower
        or "/10" in title_lower
        or "/25" in title_lower
        or "/50" in title_lower
        or "/75" in title_lower
        or "/99" in title_lower
        or "ocm" in title_lower
    ):
        base_treatment = "OCM Serialized"

    # 2. Special Foils
    elif "stonefoil" in title_lower or "stone foil" in title_lower:
        base_treatment = "Stonefoil"
    elif "formless" in title_lower:
        base_treatment = "Formless Foil"

    # 3. Other Variants
    elif "prerelease" in title_lower:
        base_treatment = "Prerelease"
    elif "promo" in title_lower:
        base_treatment = "Promo"
    elif "proof" in title_lower or "sample" in title_lower:
        base_treatment = "Proof/Sample"
    elif "errata" in title_lower or "error" in title_lower:
        base_treatment = "Error/Errata"

    # 4. Classic Foil
    elif "foil" in title_lower or "holo" in title_lower or "refractor" in title_lower:
        base_treatment = "Classic Foil"

    # 5. Explicit Classic Paper detection (only when specifically mentioned)
    elif (
        "classic paper" in title_lower
        or "paper" in title_lower
        or "non-foil" in title_lower
        or "non foil" in title_lower
    ):
        base_treatment = "Classic Paper"

    # 6. Unknown treatment - return None instead of assuming Classic Paper
    # This allows downstream systems to distinguish "unknown" from "detected Classic Paper"
    else:
        base_treatment = None

    # Append Alt Art suffix if applicable (only if base treatment was detected)
    if is_alt_art and base_treatment:
        return f"{base_treatment} Alt Art"

    return base_treatment


def _detect_product_subtype(title: str, product_type: str = "Single") -> Optional[str]:
    """
    Detects the specific product subtype for sealed products.

    Subtypes:
    - Boxes: 'Collector Booster Box', 'Case'
    - Bundles: 'Play Bundle', 'Blaster Box', 'Serialized Advantage', 'Starter Set'
    - Packs: 'Collector Booster Pack', 'Play Booster Pack', 'Silver Pack'
    - Lots: 'Lot', 'Bulk'

    Returns None for singles or undetectable subtypes.
    """
    if product_type == "Single":
        return None

    title_lower = title.lower()

    # === BOXES ===
    if product_type == "Box":
        # Case (highest value - 6-box case)
        if "case" in title_lower:
            return "Case"
        # Collector Booster Box (12 packs)
        if "collector" in title_lower and "booster" in title_lower and "box" in title_lower:
            return "Collector Booster Box"
        if "collector booster box" in title_lower:
            return "Collector Booster Box"
        # Generic booster box
        if "booster" in title_lower and "box" in title_lower:
            return "Collector Booster Box"
        return "Box"

    # === BUNDLES ===
    if product_type == "Bundle":
        # Serialized Advantage (premium bundle - 4 packs + guaranteed serialized)
        if "serialized advantage" in title_lower:
            return "Serialized Advantage"
        # Starter Set / Starter Kit
        if "starter" in title_lower and ("set" in title_lower or "kit" in title_lower):
            return "Starter Set"
        # Play Bundle (6 packs)
        if "play bundle" in title_lower:
            return "Play Bundle"
        # Blaster Box (6 packs, same as Play Bundle)
        if "blaster" in title_lower and "box" in title_lower:
            return "Blaster Box"
        if "blaster box" in title_lower:
            return "Blaster Box"
        # Generic bundle
        if "bundle" in title_lower:
            return "Play Bundle"
        return "Bundle"

    # === PACKS ===
    if product_type == "Pack":
        # Silver Pack (special promo pack)
        if "silver" in title_lower and "pack" in title_lower:
            return "Silver Pack"
        # Collector Booster Pack
        if "collector" in title_lower and ("booster" in title_lower or "pack" in title_lower):
            return "Collector Booster Pack"
        if "collector booster" in title_lower:
            return "Collector Booster Pack"
        # Play Booster Pack
        if "play" in title_lower and ("booster" in title_lower or "pack" in title_lower):
            return "Play Booster Pack"
        if "play booster" in title_lower:
            return "Play Booster Pack"
        # Generic booster pack (default to collector since they're more common on eBay)
        if "booster" in title_lower:
            return "Collector Booster Pack"
        return "Pack"

    # === LOTS ===
    if product_type == "Lot":
        if "bulk" in title_lower:
            return "Bulk"
        return "Lot"

    return None


def _detect_grading(title: str) -> Optional[str]:
    """
    Detects grading company and grade from listing title.

    Grading Companies:
    - PSA (Professional Sports Authenticator) - scores 1-10
    - BGS (Beckett Grading Services) - scores 1-10, with .5 increments
    - TAG (Texas Authentication & Grading) - scores 1-10
    - CGC (Certified Guaranty Company) - scores 1-10, with .5 increments
    - SGC (Sportscard Guaranty Corporation) - scores 1-10

    Also detects:
    - TAG SLAB (common for WOTF prerelease cards)
    - Generic "GRADED" or "SLAB" mentions without specific service

    Returns: Grade string (e.g., "PSA 10", "BGS 9.5", "TAG SLAB", "GRADED") or None for raw cards.
    """
    import re

    title_upper = title.upper()

    # PSA grading patterns
    # "PSA 10", "PSA10", "PSA-10", "PSA GEM MINT 10"
    psa_patterns = [
        r"PSA\s*[-]?\s*(\d+(?:\.\d)?)",  # PSA 10, PSA-10, PSA10
        r"PSA\s+GEM\s*(?:MINT|MT)?\s*(\d+)",  # PSA GEM MINT 10
        r"PSA\s+MINT\s*(\d+)",  # PSA MINT 9
    ]
    for pattern in psa_patterns:
        match = re.search(pattern, title_upper)
        if match:
            grade = match.group(1)
            return f"PSA {grade}"

    # BGS (Beckett) grading patterns
    # "BGS 9.5", "BGS9.5", "BGS 10 BLACK LABEL", "BECKETT 9.5"
    bgs_patterns = [
        r"BGS\s*[-]?\s*(\d+(?:\.\d)?)",  # BGS 9.5, BGS-9.5
        r"BECKETT\s*[-]?\s*(\d+(?:\.\d)?)",  # BECKETT 9.5
        r"BGS\s+(\d+)\s*(?:BLACK\s*LABEL|PRISTINE)",  # BGS 10 BLACK LABEL
    ]
    for pattern in bgs_patterns:
        match = re.search(pattern, title_upper)
        if match:
            grade = match.group(1)
            return f"BGS {grade}"

    # TAG (Texas Authentication & Grading) patterns
    # "TAG 10", "TAG-10", "TAG PERFECT 10", "TAG SLAB"
    tag_patterns = [
        r"(?<!S)TAG\s*[-]?\s*(\d+(?:\.\d)?)",  # TAG 10 (exclude STAG)
        r"TAG\s+PERFECT\s*(\d+)",  # TAG PERFECT 10
    ]
    for pattern in tag_patterns:
        match = re.search(pattern, title_upper)
        if match:
            grade = match.group(1)
            return f"TAG {grade}"

    # TAG SLAB without grade (common for WOTF prerelease)
    if re.search(r"(?<!S)TAG\s+SLAB", title_upper) or re.search(r"(?<!S)TAG\s*[-]?\s*SLAB", title_upper):
        return "TAG SLAB"

    # CGC grading patterns
    # "CGC 9.8", "CGC-9.8"
    cgc_patterns = [
        r"CGC\s*[-]?\s*(\d+(?:\.\d)?)",  # CGC 9.8
    ]
    for pattern in cgc_patterns:
        match = re.search(pattern, title_upper)
        if match:
            grade = match.group(1)
            return f"CGC {grade}"

    # SGC grading patterns
    # "SGC 10", "SGC-10"
    sgc_patterns = [
        r"SGC\s*[-]?\s*(\d+(?:\.\d)?)",  # SGC 10
    ]
    for pattern in sgc_patterns:
        match = re.search(pattern, title_upper)
        if match:
            grade = match.group(1)
            return f"SGC {grade}"

    # Generic graded/slab mentions (without specific service or grade)
    # "GRADED", "SLAB", "SLABBED" - indicates professional grading but unclear which service
    if re.search(r"\bGRADED\b", title_upper):
        return "GRADED"
    if re.search(r"\bSLAB(?:BED)?\b", title_upper):
        return "GRADED"

    return None


def _detect_quantity(title: str, product_type: str = "Single") -> int:
    """
    Detects quantity from listing title for multi-unit listings.

    Examples:
    - "2 Wonders of the First Existence Play Bundle" -> 2
    - "3x Booster Pack" -> 3
    - "Lot of 5 packs" -> 5
    - "Bundle Box 6 Booster Packs" -> 1 (this is a single bundle containing 6 packs)
    - "2025 Wonders of the First" -> 1 (NOT 2025 - that's the year!)
    - "Carbon-X7 Synthforge" -> 1 (NOT 7 - that's the card name!)

    Returns 1 if no quantity detected.
    """
    title_lower = title.lower()

    # Helper to check if a number is likely a year (2020-2030)
    def is_likely_year(num: int) -> bool:
        return 2020 <= num <= 2030

    # Skip titles containing card names with X in them (Carbon-X7, X7v1, etc.)
    # These are card names, not quantities
    skip_patterns = [
        r"carbon-x\d",  # Carbon-X7 card name
        r"x\d+v\d",  # X7v1 variant naming
        r"experiment\s*x",  # Experiment X series
    ]
    for pattern in skip_patterns:
        if re.search(pattern, title_lower):
            return 1

    # For singles, quantity is usually 1 unless explicitly stated
    if product_type == "Single":
        # Look for explicit quantity patterns at start of title or after separator
        patterns = [
            r"^(\d+)\s*x\s+",  # "2x Card Name" at start
            r"^(\d+)\s+-\s+",  # "2 - Card Name" at start
            r"^x\s*(\d+)\s+",  # "X3 Card Name" at start
            r"(?:^|\s)(\d+)\s*x\s*(?:-|wonders|foil)",  # "3x -" or "2x Wonders"
            r"lot\s+of\s+(\d+)",  # "lot of 5"
            r"(\d+)\s*card\s*lot",  # "5 card lot"
            r"(\d+)\s*ct\b",  # "3ct"
            r"\sx\s*(\d+)\s*$",  # "x4" at end of title
        ]
        for pattern in patterns:
            match = re.search(pattern, title_lower)
            if match:
                qty = int(match.group(1))
                # Exclude years (2020-2030) and unreasonable quantities
                if 1 < qty <= 100 and not is_likely_year(qty):
                    return qty
        return 1

    # For sealed products (Box, Pack, Bundle), detect multi-unit sales
    # Important: "Bundle Box with 6 packs" is 1 bundle, not 6 packs

    # First check if this is describing contents (not quantity being sold)
    content_patterns = [
        r"(\d+)\s*booster\s*packs?\s*(inside|included|contains|per|each)",
        r"contains\s*(\d+)",
        r"includes\s*(\d+)",
        r"with\s*(\d+)\s*(booster|pack)",
    ]
    for pattern in content_patterns:
        if re.search(pattern, title_lower):
            # This describes contents, not sale quantity - return 1
            return 1

    # Now look for actual quantity being sold
    quantity_patterns = [
        r"^(\d+)\s*x\s*(wonders|existence|booster|play|collector|bundle|box|pack)",  # "2x Bundle" (requires x)
        r"^(\d{1,2})\s+(wonders|existence|booster|play|collector|bundle|box|pack)",  # "2 Wonders..." (max 2 digits to exclude years)
        r"(\d+)\s*(?:ct|count)\b",  # "5ct" or "5 count"
        r"lot\s+of\s+(\d+)",  # "lot of 3"
        r"set\s+of\s+(\d+)",  # "set of 2"
        r"x(\d+)\b",  # "x4" at end
    ]

    for pattern in quantity_patterns:
        match = re.search(pattern, title_lower)
        if match:
            qty = int(match.group(1))
            # Exclude years (2020-2030) and unreasonable quantities
            if 1 < qty <= 50 and not is_likely_year(qty):
                return qty

    return 1


def _detect_bundle_pack_count(title: str) -> int:
    """
    Detects how many packs are in a bundle/box from the title.

    Known WOTF bundle products:
    - Play Bundle / Blaster Box: 6 packs
    - Collector Booster Box: 12 packs
    - Serialized Advantage: 4 packs
    - Collector Box (30-pack): 30 packs

    Returns 0 if not a bundle (i.e., single pack listing).
    """
    title_lower = title.lower()

    # Known WOTF bundle products
    if "play bundle" in title_lower or "blaster box" in title_lower:
        return 6  # Play Bundle / Blaster Box = 6 packs
    if "serialized advantage" in title_lower:
        return 4  # Serialized Advantage = 4 packs
    if "collector booster" in title_lower and "box" in title_lower:
        return 12  # Collector Booster Box = 12 packs

    # Check for explicit pack counts in title (for 30-pack boxes etc.)
    if "collector" in title_lower and "30" in title_lower:
        return 30

    # Try to extract pack count from title patterns
    # Be careful not to match single pack listings like "pack + 12 bonus cards"
    patterns = [
        r"box\s*(?:of\s*)?(\d+)\s*(?:booster\s*)?packs?",  # "box of 6 packs"
        r"(\d+)\s*pack\s*box",  # "6 pack box"
    ]

    for pattern in patterns:
        match = re.search(pattern, title_lower)
        if match:
            count = int(match.group(1))
            if 2 <= count <= 36:  # Reasonable pack count for bundles
                return count

    # Don't match single packs with bonus cards
    # e.g., "COLLECTOR BOOSTER PACK Sealed +12 bonus" should return 0
    if "bonus" in title_lower or "+ " in title_lower:
        return 0

    return 0


def _is_valid_match(title: str, card_name: str, target_rarity: str = "") -> bool:
    """
    Validates if the listing title is a good match for the card name and rarity.
    Stricter matching logic to prevent "The Great Veridan" matching "The Great Usurper".
    Also filters out non-Wonders products (Harry Potter, Yu-Gi-Oh, Pokemon, etc.)
    """
    if not card_name:
        return True

    title_lower = title.lower()
    name_lower = card_name.lower()

    # FIRST: Check for positive WOTF identifiers
    # If present, we trust this is a WOTF listing and skip most blocklist checks
    wonders_identifiers = ["wonders of the first", "wotf", "existence tcg", "existence 1st edition"]
    has_wonders_identifier = any(ident in title_lower for ident in wonders_identifiers)

    # CRITICAL: For generic card names (Lot, Treasure Map, The Prisoner, etc.),
    # REQUIRE a WOTF identifier to avoid matching other TCGs
    generic_card_names = [
        "lot",
        "the prisoner",
        "treasure map",
        "catch",
        "the awakening",
        "eye of the maelstrom",
        "dragon's gold",
        "2-player starter",
    ]
    is_generic_name = any(generic in name_lower for generic in generic_card_names)
    if is_generic_name and not has_wonders_identifier:
        return False

    # CRITICAL: Reject non-Wonders TCG products that might match on keywords
    # e.g., "The Prisoner" should NOT match "Harry Potter Prisoner of Azkaban"
    # Blocklist loaded from blocklist.yaml (version: {version})
    #
    # Only apply blocklist if NO positive WOTF identifier is present
    # This prevents false positives like "Wonders of the First Dragon's Gold"
    # being blocked because "gold" matches some Pokemon/MTG term
    if not has_wonders_identifier:
        blocklist = load_blocklist()
        for keyword in blocklist:
            if keyword in title_lower:
                return False

    # Detect product types - use more lenient matching for sealed products
    product_type_keywords = ["box", "pack", "case", "lot", "bundle", "collection", "bulk", "sealed"]
    is_product = any(keyword in name_lower for keyword in product_type_keywords)

    # CRITICAL: Distinguish between individual packs vs bundles/boxes
    # When searching for "Booster Pack", reject listings that are clearly bundles
    is_searching_for_pack = "pack" in name_lower and "bundle" not in name_lower and "box" not in name_lower
    is_listing_bundle = any(
        kw in title_lower
        for kw in [
            "bundle",
            "blaster box",
            "play bundle",
            "collector box",
            "serialized advantage",
            "6 pack",
            "12 pack",
            "30 pack",
            # Multi-unit indicators
            "2x ",
            "3x ",
            "4x ",
            "5x ",
            "2 wonders",
            "3 wonders",
            "4 wonders",
            "5 wonders",
        ]
    )
    # Also check for quantity patterns at start of title
    if re.match(r"^\d+\s+(wonders|existence|play|collector|booster)", title_lower):
        is_listing_bundle = True

    if is_searching_for_pack and is_listing_bundle:
        return False  # Reject bundle listings when searching for individual packs

    # 1. Name Validation

    # Clean the title:
    # Remove "Wonders of the First" but KEEP key words like "existence"
    # Also normalize punctuation for better tokenization
    clean_title = title_lower.replace("wonders of the first", "").replace("-", " ").replace("–", " ")
    clean_name = name_lower.replace("wonders of the first", "").replace("-", " ").replace("–", " ")
    # Remove quotes, apostrophes, and commas (e.g., "Autumn, Essence Animated" should match "Autumn Essence Animated")
    for char in ["'", "'", '"', '"', '"', ",", ":", ";"]:
        clean_title = clean_title.replace(char, "")
        clean_name = clean_name.replace(char, "")

    # Special handling for "The First" card (single card, not sealed product)
    # This card requires VERY strict matching as it's easily confused with other cards
    if name_lower == "the first":
        # Must have specific indicators for "The First" card:
        # - Card number 001/401 (standard numbering)
        # - Or explicit mentions like "The First Land" or "The First Formless"
        # - NOT just any card from "Wonders of the First" set

        # Check for card number first (most reliable)
        if "001/401" in title_lower:
            return True

        # Check if "the first" appears as the actual card name (not just set name)
        # After removing "wonders of the first", check what remains
        if "the first land" in title_lower or "the first formless" in title_lower:
            return True

        # Check cleaned title - must have "first" as a distinct word, not part of another card name
        if clean_title.strip() and ("the first" in clean_title or clean_title.strip() == "first"):
            # Extra validation: shouldn't have other card names
            # Reject if it contains other character names like "voice of", "zeltona", etc
            reject_phrases = [
                "voice of",
                "zeltona",
                "cura",
                "captain",
                "king",
                "queen",
                "lord",
                "lady",
                "sir",
                "baron",
                "duke",
                "emperor",
                "empress",
            ]
            for phrase in reject_phrases:
                if phrase in title_lower:
                    return False

            # Skip if it has a card number that's not 001
            if any(f"{num:03d}/401" in title_lower for num in range(2, 402)):
                return False
            return True

        return False

    # Tokenize and remove stopwords
    card_tokens = [t for t in clean_name.split() if t not in STOPWORDS]
    title_tokens = [t for t in clean_title.split() if t not in STOPWORDS]

    card_tokens_set = set(card_tokens)
    title_tokens_set = set(title_tokens)

    if not card_tokens_set:
        # If card name is all stopwords (e.g. "The First" handled above, or unusual names)
        # Fallback to raw token match
        card_tokens_set = set(clean_name.split())
        title_tokens_set = set(clean_title.split())

    # Helper function for fuzzy token matching (handles typos like "Atherion" vs "Aetherion")
    def fuzzy_token_match(card_token: str, title_tokens_list: list) -> bool:
        """Check if card_token has a close match in title_tokens using fuzzy matching."""
        # IMPORTANT: Short words need HIGHER threshold to avoid false matches
        # e.g., "progo" vs "promo" = 0.80 - should NOT match!
        # Longer words can use lower threshold for typo tolerance
        if len(card_token) <= 5:
            threshold = 0.90  # Very strict for short words
        elif len(card_token) <= 7:
            threshold = 0.85  # Strict for medium words
        else:
            threshold = 0.80  # More lenient for long words (typo tolerance)

        for title_token in title_tokens_list:
            # Skip if lengths are too different (likely not a typo)
            if abs(len(card_token) - len(title_token)) > 2:
                continue
            # Use SequenceMatcher for fuzzy matching
            ratio = difflib.SequenceMatcher(None, card_token, title_token).ratio()
            if ratio >= threshold:
                return True
        return False

    # First try exact matching
    common_tokens = card_tokens_set.intersection(title_tokens_set)

    # If exact match is low, try fuzzy matching for remaining tokens
    # IMPORTANT: For SHORT single-token card names, DISABLE fuzzy matching
    # to prevent "Progo" (5 chars) matching "Promo"
    # But allow fuzzy for LONGER single-token names to catch typos
    # e.g., "Aetherion" (9 chars) should match "Atherion"
    unmatched_card_tokens = card_tokens_set - common_tokens
    fuzzy_matches = 0
    title_tokens_list = list(title_tokens_set)

    # Determine if we should use fuzzy matching
    use_fuzzy = True
    if len(card_tokens_set) == 1:
        # For single-token names, only allow fuzzy if the token is long enough
        single_token = list(card_tokens_set)[0]
        if len(single_token) <= 6:
            use_fuzzy = False  # Short names like "Progo" - no fuzzy matching

    if use_fuzzy:
        for card_token in unmatched_card_tokens:
            if len(card_token) >= 4 and fuzzy_token_match(card_token, title_tokens_list):
                fuzzy_matches += 1

    total_matches = len(common_tokens) + fuzzy_matches

    # If after stripping stopwords we have tokens, we require high match
    if len(card_tokens_set) > 0:
        match_ratio = total_matches / len(card_tokens_set)

        # For sealed products (boxes, packs, lots), be more lenient - require 60% match
        # For single cards with short names (1-2 tokens), require 100% match
        # For single cards with longer names (3+ tokens), allow 80% match for flexibility
        if is_product:
            required_ratio = 0.6
        elif len(card_tokens_set) <= 2:
            required_ratio = 1.0  # Short names need exact match to avoid false positives
        else:
            required_ratio = 0.8  # Longer names can have some flexibility

        if match_ratio < required_ratio:
            return False

    else:
        # Fallback for very short/stopword-heavy names
        if name_lower not in title_lower:
            return False

    # 2. Rarity Validation (if provided)
    if target_rarity:
        # Check if the rarity appears in the title
        # Common rarity keywords to check
        rarity_lower = target_rarity.lower()

        # Skip rarity validation for sealed products - they often don't list rarity
        if is_product:
            return True

        # For single cards, validate rarity if specified
        # Look for exact rarity name or common abbreviations
        rarity_keywords = {
            "common": ["common", "c"],
            "uncommon": ["uncommon", "uc", "u"],
            "rare": ["rare", "r"],
            "epic": ["epic", "e"],
            "legendary": ["legendary", "leg", "l"],
            "mythic": ["mythic", "myth", "m"],
            "secret": ["secret"],
            "promo": ["promo", "promotional"],
        }

        # Find which category our target rarity falls into
        rarity_found = False
        for category, keywords in rarity_keywords.items():
            if category in rarity_lower:
                # Check if any of the keywords appear in the title
                for keyword in keywords:
                    if keyword in title_lower:
                        rarity_found = True
                        break
                break

        # If we have a rarity specified but couldn't find it, that's suspicious
        # But we'll be lenient and allow it if the name match is strong
        # This prevents false negatives when sellers don't list rarity
        if not rarity_found and len(common_tokens) < len(card_tokens_set):
            return False

    return True


def _extract_bid_count(item) -> int:
    """
    Extracts the bid count from an item element.
    Supports both old .s-item format and new .s-card format.
    """
    # Try standard bid count selectors (old format)
    bid_elem = item.select_one(".s-item__bidCount, .s-item__bids, .s-item__details .s-item__bidCount")
    if bid_elem:
        text = bid_elem.get_text(strip=True)
        match = re.search(r"(\d+)\s*bids?", text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # New s-card format: bid count appears as "X bids" in span elements
    # Search all text for bid pattern
    item_text = item.get_text(strip=True)
    match = re.search(r"(\d+)\s*bids?", item_text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return 0


def _extract_listing_format(item, bid_count: int = 0) -> Optional[str]:
    """
    Extracts the listing format from an eBay item element.

    Returns:
        'auction' - Auction listing (has bids or shows auction indicators)
        'buy_it_now' - Fixed price Buy It Now listing
        'best_offer' - Buy It Now with Best Offer option
        None - Unknown format

    Detection logic:
    1. If bid_count > 0, it's definitely an auction
    2. Look for "Buy It Now" text/buttons
    3. Look for "or Best Offer" text
    4. Look for auction indicators (time left, place bid)
    """
    # Get all text content for searching
    item_text = item.get_text(strip=True).lower()

    # If there are bids, it's definitely an auction
    if bid_count > 0:
        return "auction"

    # Check for Buy It Now indicators
    buy_it_now_indicators = [
        ".s-item__buyItNowOption",
        ".s-item__dynamic.s-item__buyItNowOption",
        "[class*='buyItNow']",
        "[class*='buy-it-now']",
    ]
    for selector in buy_it_now_indicators:
        if item.select_one(selector):
            # Check if also has Best Offer
            if "best offer" in item_text or "or best offer" in item_text:
                return "best_offer"
            return "buy_it_now"

    # Check text content for Buy It Now
    if "buy it now" in item_text:
        if "or best offer" in item_text:
            return "best_offer"
        return "buy_it_now"

    # Check for auction indicators (both old .s-item and new .s-card formats)
    auction_indicators = [
        ".s-item__time-left",  # Old format: Time countdown
        ".s-item__time-end",
        ".s-item__bidCount",
        ".s-card__time-left",  # New format: Time left
        ".s-card__time",  # New format: Time container
        "[class*='timeLeft']",
        "[class*='time-left']",
    ]
    for selector in auction_indicators:
        if item.select_one(selector):
            return "auction"

    # Check text for auction indicators
    auction_text_patterns = [
        r"\d+\s*bids?",
        r"place bid",
        r"time left",
        r"\d+[hmd]\s*\d*[hmd]?\s*left",  # e.g., "2h 30m left", "1d left"
    ]
    for pattern in auction_text_patterns:
        if re.search(pattern, item_text, re.IGNORECASE):
            return "auction"

    # If we found price info but no format indicators, assume Buy It Now
    # (Most eBay listings without explicit auction indicators are BIN)
    price_elem = item.select_one(".s-item__price, .s-card__price")
    if price_elem:
        price_text = price_elem.get_text(strip=True).lower()
        # If price doesn't contain "bid" language, likely BIN
        if "bid" not in price_text:
            return "buy_it_now"

    return None


def _extract_seller_info(item) -> Tuple[Optional[str], Optional[int], Optional[float]]:
    """
    Extracts seller name and feedback info from an item element.
    Supports both old .s-item format and new .s-card format.
    Returns: (seller_name, feedback_score, feedback_percent)
    """
    seller_name = None
    feedback_score = None
    feedback_percent = None

    # ========== NEW s-card FORMAT (2024+) ==========
    # Format varies:
    #   <div class="su-card-container__attributes__secondary">
    #     <span>seller_name </span>
    #     <span>100% positive (3.8K)</span>
    #   </div>
    # OR combined in one span:
    #   <span>seller_name  100% positive (1K)</span>
    secondary_attrs = item.select_one(".su-card-container__attributes__secondary")
    if secondary_attrs:
        # eBay uses both span.su-styled-text AND plain span elements
        spans = secondary_attrs.select("span")
        for i, span in enumerate(spans):
            text = span.get_text(strip=True)

            # Look for feedback pattern: "100% positive (3.8K)" or "99.5% positive (1234)"
            feedback_match = re.search(r"([\d.]+)%\s*positive\s*\(([\d.]+)K?\)", text, re.IGNORECASE)
            if feedback_match:
                feedback_percent = float(feedback_match.group(1))
                score_str = feedback_match.group(2)
                if "K" in text.upper():
                    feedback_score = int(float(score_str) * 1000)
                else:
                    feedback_score = int(float(score_str))

                # CRITICAL: Check if seller name is BEFORE the feedback in same span
                # Format: "seller_name  100% positive (1K)"
                pre_feedback = text[: feedback_match.start()].strip()
                if pre_feedback and re.match(r"^[a-zA-Z0-9_\-\.]+$", pre_feedback):
                    seller_name = pre_feedback

            # Separate span that looks like a username (not customs/shipping info)
            elif text and not text.startswith(("Customs", "Located", "Free", "+$", "From")):
                potential_name = text.strip()
                if re.match(r"^[a-zA-Z0-9_\-\.]+$", potential_name):
                    seller_name = potential_name

        # If we found feedback but not seller name, check all spans for username
        if feedback_score and not seller_name:
            for span in spans:
                text = span.get_text(strip=True)
                if text and not re.search(r"[\d.]+%\s*positive", text, re.IGNORECASE):
                    potential_name = text.strip()
                    if re.match(r"^[a-zA-Z0-9_\-\.]+$", potential_name):
                        seller_name = potential_name
                        break

    # ========== OLD s-item FORMAT ==========
    if not seller_name:
        # Best approach: extract from seller link URL which has clean username
        seller_link = item.select_one("a[href*='/usr/']")
        if seller_link:
            href = seller_link.get("href", "")
            # URL format: https://www.ebay.com/usr/seller_name or /usr/seller_name
            match = re.search(r"/usr/([^/?]+)", href)
            if match:
                seller_name = match.group(1).strip()

    # Alternative: look for seller link text (but clean it up)
    if not seller_name:
        seller_link = item.select_one("a[class*='seller']")
        if seller_link:
            text = seller_link.get_text(strip=True)
            # Take just the first word/username before any spaces or special chars
            seller_name = text.split()[0] if text else None

    # Try to find seller info element (old format)
    if not seller_name:
        seller_elem = item.select_one(".s-item__seller-info, .s-item__seller-info-text")
        if seller_elem:
            text = seller_elem.get_text(strip=True)
            # Parse seller name - format varies:
            # "seller_name (1234) 99.5%"
            # "seller_name  100% positive (1.2K)..."

            # Try pattern: "seller_name (1234) 99.5%"
            match = re.search(r"^([a-zA-Z0-9_\-\.]+)\s*\((\d+)\)\s*([\d.]+)%?", text)
            if match:
                seller_name = match.group(1).strip()
                feedback_score = int(match.group(2))
                feedback_percent = float(match.group(3))
            else:
                # Try pattern: "seller_name  100% positive (1.2K)"
                match = re.search(r"^([a-zA-Z0-9_\-\.]+)\s+(\d+)%\s*positive\s*\(([\d.]+)K?\)", text, re.IGNORECASE)
                if match:
                    seller_name = match.group(1).strip()
                    feedback_percent = float(match.group(2))
                    score_str = match.group(3)
                    # Handle "1.2K" format
                    if "K" in text[text.find(match.group(3)) : text.find(match.group(3)) + 5].upper():
                        feedback_score = int(float(score_str) * 1000)
                    else:
                        feedback_score = int(float(score_str))
                else:
                    # Last resort: take first word that looks like a username
                    match = re.match(r"^([a-zA-Z0-9_\-\.]+)", text)
                    if match:
                        seller_name = match.group(1).strip()

    # Try to find feedback separately if not found (old format)
    if seller_name and not feedback_score:
        feedback_elem = item.select_one(".s-item__seller-info .s-item__feedback, [class*='feedback']")
        if feedback_elem:
            text = feedback_elem.get_text(strip=True)
            # Parse "(1234) 99.5%" or "100% positive (1.2K)" format
            match = re.search(r"\((\d+)\)\s*([\d.]+)%", text)
            if match:
                feedback_score = int(match.group(1))
                feedback_percent = float(match.group(2))
            else:
                match = re.search(r"([\d.]+)%\s*positive\s*\(([\d.]+)K?\)", text, re.IGNORECASE)
                if match:
                    feedback_percent = float(match.group(1))
                    score_str = match.group(2)
                    if "K" in text.upper():
                        feedback_score = int(float(score_str) * 1000)
                    else:
                        feedback_score = int(float(score_str))

    return seller_name, feedback_score, feedback_percent


def _extract_condition(item) -> Optional[str]:
    """
    Extracts item condition from listing.
    """
    # Standard condition element
    condition_elem = item.select_one(".s-item__subtitle, .SECONDARY_INFO, [class*='condition']")
    if condition_elem:
        text = condition_elem.get_text(strip=True)
        # Common conditions: "New", "Brand New", "Pre-Owned", "Used", "Like New", "For parts"
        conditions = ["Brand New", "New", "Like New", "Pre-Owned", "Used", "Open Box", "Refurbished", "For parts"]
        for condition in conditions:
            if condition.lower() in text.lower():
                return condition
        # Return the raw text if no known condition found (might still be useful)
        if len(text) < 50:  # Avoid long descriptions
            return text
    return None


def _extract_shipping_cost(item) -> Optional[float]:
    """
    Extracts shipping cost from listing.
    Returns: shipping cost in dollars (0.0 for free shipping, None if not found)
    """
    shipping_elem = item.select_one(
        ".s-item__shipping, .s-item__freeXDays, .s-item__logisticsCost, [class*='shipping']"
    )
    if shipping_elem:
        text = shipping_elem.get_text(strip=True).lower()

        # Free shipping
        if "free" in text:
            return 0.0

        # Parse shipping cost: "+$5.99 shipping" or "$5.99 shipping"
        match = re.search(r"\+?\$?([\d,.]+)\s*shipping", text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass

    return None


def _clean_title_text(title: str) -> str:
    """
    Removes junk text like 'Opens in a new window or tab' from the title.
    """
    junk_phrases = ["opens in a new window or tab", "opens in a new window", "opens in a new tab", "new listing"]
    title_lower = title.lower()
    for phrase in junk_phrases:
        if phrase in title_lower:
            # Case insensitive replace is tricky, do a regex replace
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            title = pattern.sub("", title)

    return title.strip()


def _parse_generic_results(
    html_content: str,
    card_id: int,
    listing_type: str,
    card_name: str = "",
    target_rarity: str = "",
    return_all: bool = False,
    product_type: str = "Single",
) -> List[MarketPrice]:
    soup = BeautifulSoup(html_content, "lxml")
    items = soup.select("li.s-item, li.s-card")

    # Phase 1a: Collect ALL valid listings (filter, validate)
    all_listings_data = []

    for item in items:
        item_classes = item.get("class") or []
        if "s-item__header" in item_classes or "s-card__header" in item_classes:
            continue

        title_elem = item.select_one(".s-item__title, .s-card__title")
        if not title_elem:
            continue
        raw_title = title_elem.get_text(strip=True)

        if "Shop on eBay" in raw_title:
            continue

        # Clean title BEFORE validation
        title = _clean_title_text(raw_title)

        if card_name and not _is_valid_match(title, card_name, target_rarity):
            continue

        # New eBay structure uses s-card__price with su-styled-text wrapper
        price_elem = item.select_one(".s-item__price, .s-card__price, [class*='s-card__price']")
        if not price_elem:
            continue

        price_str = price_elem.get_text(strip=True)
        price = _clean_price(price_str)
        if price is None:
            continue

        sold_date = None
        if listing_type == "sold":
            captions = item.select(".s-item__caption, .s-card__caption")
            for caption in captions:
                text = caption.get_text(strip=True)
                if "Sold" in text:
                    sold_date = _parse_date(text)
                    if sold_date:
                        break
            if not sold_date:
                tag = item.select_one(".s-item__title--tag")
                if tag:
                    text = tag.get_text(strip=True)
                    if "Sold" in text:
                        sold_date = _parse_date(text)
            if not sold_date:
                continue
        else:
            pass

        # Extract item ID
        item_id, url = _extract_item_details(item)

        # Extract additional metadata
        bid_count = _extract_bid_count(item)

        # Extract listing format (auction, buy_it_now, best_offer)
        listing_format = _extract_listing_format(item, bid_count)

        # Extract seller info
        seller_name, seller_feedback_score, seller_feedback_percent = _extract_seller_info(item)

        # Extract condition and shipping
        condition = _extract_condition(item)
        shipping_cost = _extract_shipping_cost(item)

        # Extract Image URL (both old and new eBay structure)
        image_elem = item.select_one(".s-item__image-img, .s-card__image img, img.s-card__image")
        image_url = None
        if image_elem:
            image_url = image_elem.get("src")
            if not image_url or "gif" in image_url or "base64" in image_url:
                image_url = image_elem.get("data-src")

        # Store all listing data for bulk dedup check
        all_listings_data.append(
            {
                "external_id": item_id,
                "title": title,
                "price": price,
                "sold_date": sold_date,
                "url": url,
                "bid_count": bid_count,
                "listing_format": listing_format,
                "image_url": image_url,
                "seller_name": seller_name,
                "seller_feedback_score": seller_feedback_score,
                "seller_feedback_percent": seller_feedback_percent,
                "condition": condition,
                "shipping_cost": shipping_cost,
            }
        )

    if not all_listings_data:
        return []

    # Phase 1b: Bulk DB dedup check (single query instead of N queries)
    # IMPORTANT: Skip dedup for active listings - we always want fresh data
    # Dedup only makes sense for sold listings (avoid re-saving same sale)
    if listing_type == "active":
        indexed_indices = set()  # No dedup for active listings
    else:
        indexed_indices = (
            _bulk_check_indexed(card_id, all_listings_data, card_name=card_name, product_type=product_type)
            if not return_all
            else set()
        )

    # Phase 1c: Filter out already-indexed listings (unless return_all=True for stats)
    listings_to_extract = []
    listing_metadata = []

    for i, listing_data in enumerate(all_listings_data):
        if return_all or i not in indexed_indices:
            # Include for AI extraction if: return_all=True OR not indexed yet
            listings_to_extract.append(
                {"title": listing_data["title"], "description": None, "price": listing_data["price"]}
            )
            listing_metadata.append(listing_data)

    if not listings_to_extract:
        return []

    # Phase 2: Batch AI extraction for all non-indexed listings
    ai_extractor = get_ai_extractor()
    extracted_batch = ai_extractor.extract_batch(listings_to_extract)

    # Phase 3: Create MarketPrice objects with extracted data
    results = []
    for metadata, extracted_data in zip(listing_metadata, extracted_batch):
        # For sealed products (Box, Pack, Lot, Bundle), always use rule-based detection
        # AI extractor doesn't understand sealed product treatments
        if product_type in ("Box", "Pack", "Lot", "Bundle"):
            treatment = _detect_treatment(metadata["title"], product_type)
            # Use rule-based quantity detection for sealed products
            quantity = _detect_quantity(metadata["title"], product_type)
            # Detect product subtype (Collector Booster Box, Play Bundle, etc.)
            product_subtype = _detect_product_subtype(metadata["title"], product_type)
        else:
            # For singles, use AI extraction with fallback to rule-based if low confidence
            treatment = extracted_data["treatment"]
            quantity = extracted_data["quantity"]
            product_subtype = None  # Singles don't have subtypes
            if extracted_data["confidence"] < 0.7:
                treatment = _detect_treatment(metadata["title"], product_type)
                # Also use rule-based quantity for low confidence
                rule_qty = _detect_quantity(metadata["title"], product_type)
                if rule_qty > 1:
                    quantity = rule_qty

        # Normalize price per unit for multi-quantity listings
        raw_price = metadata["price"]
        unit_price = raw_price / quantity if quantity > 1 else raw_price

        # For packs being sold as bundles, calculate per-pack price
        # e.g., "2 Play Bundle Boxes" at $59.99 = 2 bundles * 6 packs = 12 packs
        # Per-pack price = $59.99 / 12 = $4.99
        packs_per_bundle = _detect_bundle_pack_count(metadata["title"]) if product_type == "Pack" else 0
        if packs_per_bundle > 0:
            total_packs = quantity * packs_per_bundle
            unit_price = raw_price / total_packs
            # Update quantity to reflect total packs
            quantity = total_packs

        # Detect grading (PSA, TAG, BGS, CGC, SGC)
        grading = _detect_grading(metadata["title"]) if product_type == "Single" else None

        mp = MarketPrice(
            card_id=card_id,
            title=metadata["title"],
            price=round(unit_price, 2),  # Store normalized per-unit price
            quantity=quantity,
            product_subtype=product_subtype,
            sold_date=metadata["sold_date"],
            listing_type=listing_type,
            listing_format=metadata.get("listing_format"),  # auction, buy_it_now, best_offer
            treatment=treatment,
            bid_count=metadata["bid_count"],
            external_id=metadata["external_id"],
            url=metadata["url"],
            image_url=metadata["image_url"],
            platform="ebay",
            # Seller info
            seller_name=metadata.get("seller_name"),
            seller_feedback_score=metadata.get("seller_feedback_score"),
            seller_feedback_percent=metadata.get("seller_feedback_percent"),
            # Listing details
            condition=metadata.get("condition"),
            shipping_cost=metadata.get("shipping_cost"),
            grading=grading,
            # Bulk lot detection (for FMP exclusion)
            is_bulk_lot=is_bulk_lot(metadata["title"], product_type),
            scraped_at=datetime.now(timezone.utc),
        )

        results.append(mp)

    return results


def _clean_price(price_str: str) -> Optional[float]:
    try:
        match = re.search(r"[\d,]+\.\d{2}", price_str)
        if match:
            num_str = match.group(0).replace(",", "")
            return float(num_str)
        match = re.search(r"[\d,]+", price_str)
        if match:
            num_str = match.group(0).replace(",", "")
            return float(num_str)
        return None
    except (ValueError, AttributeError):
        return None


def _parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse eBay sold date strings, handling both absolute and relative dates.

    Examples:
    - "Sold Oct 4, 2025" -> datetime(2025, 10, 4)
    - "Sold 3 days ago" -> datetime.now(timezone.utc) - 3 days
    - "Sold Dec 1" -> datetime(current_year, 12, 1)
    """
    if not date_str:
        return None

    clean_str = date_str.lower().replace("sold", "").strip()

    # Handle relative dates like "3 days ago", "1 week ago"
    relative_match = re.search(r"(\d+)\s*(day|week|month|hour|minute)s?\s*ago", clean_str)
    if relative_match:
        quantity = int(relative_match.group(1))
        unit = relative_match.group(2)

        now = datetime.now(timezone.utc)
        if unit == "day":
            return now - timedelta(days=quantity)
        elif unit == "week":
            return now - timedelta(weeks=quantity)
        elif unit == "month":
            return now - timedelta(days=quantity * 30)
        elif unit == "hour":
            return now - timedelta(hours=quantity)
        elif unit == "minute":
            return now - timedelta(minutes=quantity)

    # Handle special relative terms
    if "just now" in clean_str or "just ended" in clean_str:
        return datetime.now(timezone.utc)
    if "yesterday" in clean_str:
        return datetime.now(timezone.utc) - timedelta(days=1)
    if "today" in clean_str:
        return datetime.now(timezone.utc)

    # Try standard date parsing for absolute dates like "Oct 4, 2025" or "Dec 1"
    try:
        # Use current year as default if year not specified
        now = datetime.now(timezone.utc)
        parsed = parser.parse(clean_str, default=datetime(now.year, 1, 1, tzinfo=timezone.utc))

        # Ensure parsed datetime is timezone-aware (parser.parse may return naive)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        # Sanity check: sold_date shouldn't be in future
        if parsed > now + timedelta(days=1):
            # If parsed date is in future, try previous year
            parsed = parser.parse(clean_str, default=datetime(now.year - 1, 1, 1, tzinfo=timezone.utc))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

        # Sanity check: shouldn't be too old (before 2023 for this TCG)
        if parsed.year < 2023:
            return None

        return parsed
    except (ValueError, parser.ParserError):
        return None
