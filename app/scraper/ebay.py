from bs4 import BeautifulSoup
from typing import List, Optional, Tuple
from datetime import datetime
from dateutil import parser
import re
import difflib
from sqlmodel import Session, select
from app.models.market import MarketPrice
from app.services.ai_extractor import get_ai_extractor
from app.db import engine

STOPWORDS = {"the", "of", "a", "an", "in", "on", "at", "for", "to", "with", "by", "and", "or", "wonders", "first", "existence"}

def _bulk_check_indexed(
    card_id: int,
    listings_data: List[dict]
) -> set:
    """
    Bulk check if listings already exist in database (avoids N+1 query problem).

    Args:
        card_id: Card ID to check against
        listings_data: List of dicts with keys: external_id, title, price, sold_date

    Returns:
        Set of indices of listings that are already indexed
    """
    if not listings_data:
        return set()

    indexed_indices = set()

    with Session(engine) as session:
        # Check by external_ids in bulk (most reliable)
        external_ids = [
            listing["external_id"]
            for listing in listings_data
            if listing.get("external_id")
        ]

        if external_ids:
            existing_ids = session.exec(
                select(MarketPrice.external_id)
                .where(MarketPrice.external_id.in_(external_ids))
            ).all()
            existing_ids_set = set(existing_ids)

            # Mark indices with existing external_ids
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
                    MarketPrice.card_id == card_id,
                    MarketPrice.title == listing["title"],
                    MarketPrice.price == listing["price"],
                    MarketPrice.sold_date == listing["sold_date"]
                )
                composite_conditions.append(condition)
                composite_index_map[len(composite_conditions) - 1] = i

        if composite_conditions:
            # Query with OR of all composite conditions
            existing_composites = session.exec(
                select(
                    MarketPrice.title,
                    MarketPrice.price,
                    MarketPrice.sold_date
                )
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

def parse_search_results(html_content: str, card_id: int = 0, card_name: str = "", target_rarity: str = "") -> List[MarketPrice]:
    """
    Parses eBay HTML search results and extracts market prices (Sold listings).
    """
    return _parse_generic_results(html_content, card_id, listing_type="sold", card_name=card_name, target_rarity=target_rarity)

def parse_active_results(html_content: str, card_id: int = 0, card_name: str = "", target_rarity: str = "") -> List[MarketPrice]:
    """
    Parses eBay HTML search results for ACTIVE listings.
    """
    return _parse_generic_results(html_content, card_id, listing_type="active", card_name=card_name, target_rarity=target_rarity)

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
        match = re.search(r'([\d,]+)\s+results', text)
        if match:
            return int(match.group(1).replace(',', ''))
    return 0

def _detect_treatment(title: str) -> str:
    """
    Detects card treatment based on title keywords.
    """
    title_lower = title.lower()
    
    # 1. Serialized / OCM (Highest Priority)
    if "serialized" in title_lower or "/10" in title_lower or "/25" in title_lower or "/50" in title_lower or "/75" in title_lower or "/99" in title_lower or "ocm" in title_lower:
        return "OCM Serialized"
        
    # 2. Special Foils
    if "stonefoil" in title_lower or "stone foil" in title_lower:
        return "Stonefoil"
    if "formless" in title_lower:
        return "Formless Foil"
        
    # 3. Other Variants
    if "prerelease" in title_lower:
        return "Prerelease"
    if "promo" in title_lower:
        return "Promo"
    if "proof" in title_lower or "sample" in title_lower:
        return "Proof/Sample"
    if "errata" in title_lower or "error" in title_lower:
        return "Error/Errata"
        
    # 4. Classic Foil
    if "foil" in title_lower or "holo" in title_lower or "refractor" in title_lower:
        return "Classic Foil"
        
    # 5. Default
    return "Classic Paper"

def _is_valid_match(title: str, card_name: str, target_rarity: str = "") -> bool:
    """
    Validates if the listing title is a good match for the card name and rarity.
    Stricter matching logic to prevent "The Great Veridan" matching "The Great Usurper".
    """
    if not card_name:
        return True

    title_lower = title.lower()
    name_lower = card_name.lower()

    # Detect product types - use more lenient matching for sealed products
    product_type_keywords = ['box', 'pack', 'case', 'lot', 'bundle', 'collection', 'bulk', 'sealed']
    is_product = any(keyword in name_lower for keyword in product_type_keywords)

    # 1. Name Validation

    # Clean the title:
    # Remove "Wonders of the First" but KEEP key words like "existence"
    clean_title = title_lower.replace("wonders of the first", "")
    clean_name = name_lower.replace("wonders of the first", "")

    # Special handling for "The First" card (single card, not sealed product)
    if name_lower == "the first":
        if "the first" not in clean_title:
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

    common_tokens = card_tokens_set.intersection(title_tokens_set)

    # If after stripping stopwords we have tokens, we require high match
    if len(card_tokens_set) > 0:
        match_ratio = len(common_tokens) / len(card_tokens_set)

        # For sealed products (boxes, packs, lots), be more lenient - require 60% match
        # For single cards, require strict 100% match to prevent mismatches
        required_ratio = 0.6 if is_product else 1.0

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
            'common': ['common', 'c'],
            'uncommon': ['uncommon', 'uc', 'u'],
            'rare': ['rare', 'r'],
            'epic': ['epic', 'e'],
            'legendary': ['legendary', 'leg', 'l'],
            'mythic': ['mythic', 'myth', 'm'],
            'secret': ['secret'],
            'promo': ['promo', 'promotional'],
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
    """
    # Try standard bid count selector
    bid_elem = item.select_one(".s-item__bidCount, .s-item__bids, .s-item__details .s-item__bidCount")
    if bid_elem:
        text = bid_elem.get_text(strip=True)
        match = re.search(r'(\d+)\s*bids?', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
            
    return 0

def _clean_title_text(title: str) -> str:
    """
    Removes junk text like 'Opens in a new window or tab' from the title.
    """
    junk_phrases = [
        "opens in a new window or tab",
        "opens in a new window",
        "opens in a new tab",
        "new listing"
    ]
    title_lower = title.lower()
    for phrase in junk_phrases:
        if phrase in title_lower:
            # Case insensitive replace is tricky, do a regex replace
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            title = pattern.sub("", title)
            
    return title.strip()

def _parse_generic_results(html_content: str, card_id: int, listing_type: str, card_name: str = "", target_rarity: str = "") -> List[MarketPrice]:
    soup = BeautifulSoup(html_content, "lxml")
    items = soup.select("li.s-item, li.s-card")

    # Phase 1a: Collect ALL valid listings (filter, validate)
    all_listings_data = []

    for item in items:
        if "s-item__header" in item.get("class", []) or "s-card__header" in item.get("class", []):
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

        price_elem = item.select_one(".s-item__price, .s-card__price")
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

        # Extract Image URL
        image_elem = item.select_one(".s-item__image-img")
        image_url = None
        if image_elem:
            image_url = image_elem.get("src")
            if not image_url or "gif" in image_url or "base64" in image_url:
                image_url = image_elem.get("data-src")

        # Store all listing data for bulk dedup check
        all_listings_data.append({
            "external_id": item_id,
            "title": title,
            "price": price,
            "sold_date": sold_date,
            "url": url,
            "bid_count": bid_count,
            "image_url": image_url
        })

    if not all_listings_data:
        return []

    # Phase 1b: Bulk DB dedup check (single query instead of N queries)
    indexed_indices = _bulk_check_indexed(card_id, all_listings_data)

    # Phase 1c: Filter out already-indexed listings
    listings_to_extract = []
    listing_metadata = []

    for i, listing_data in enumerate(all_listings_data):
        if i not in indexed_indices:
            # Not indexed yet, include for AI extraction
            listings_to_extract.append({
                "title": listing_data["title"],
                "description": None,
                "price": listing_data["price"]
            })
            listing_metadata.append(listing_data)

    if not listings_to_extract:
        return []

    # Phase 2: Batch AI extraction for all non-indexed listings
    ai_extractor = get_ai_extractor()
    extracted_batch = ai_extractor.extract_batch(listings_to_extract)

    # Phase 3: Create MarketPrice objects with extracted data
    results = []
    for metadata, extracted_data in zip(listing_metadata, extracted_batch):
        # Fallback to rule-based treatment detection if AI extraction has low confidence
        treatment = extracted_data["treatment"]
        if extracted_data["confidence"] < 0.7:
            treatment = _detect_treatment(metadata["title"])

        mp = MarketPrice(
            card_id=card_id,
            title=metadata["title"],
            price=metadata["price"],
            quantity=extracted_data["quantity"],
            sold_date=metadata["sold_date"],
            listing_type=listing_type,
            treatment=treatment,
            bid_count=metadata["bid_count"],
            external_id=metadata["external_id"],
            url=metadata["url"],
            image_url=metadata["image_url"],
            platform="ebay",
            scraped_at=datetime.utcnow()
        )

        results.append(mp)

    return results

def _clean_price(price_str: str) -> Optional[float]:
    try:
        match = re.search(r'[\d,]+\.\d{2}', price_str)
        if match:
            num_str = match.group(0).replace(',', '')
            return float(num_str)
        match = re.search(r'[\d,]+', price_str)
        if match:
             num_str = match.group(0).replace(',', '')
             return float(num_str)
        return None
    except:
        return None

def _parse_date(date_str: str) -> Optional[datetime]:
    clean_str = date_str.lower().replace("sold", "").strip()
    try:
        return parser.parse(clean_str)
    except:
        return None
