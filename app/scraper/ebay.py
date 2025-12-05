from bs4 import BeautifulSoup
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
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
            # Filter by card_id to allow same listing to exist under different cards
            existing_ids = session.exec(
                select(MarketPrice.external_id)
                .where(
                    MarketPrice.external_id.in_(external_ids),
                    MarketPrice.card_id == card_id
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

def parse_search_results(html_content: str, card_id: int = 0, card_name: str = "", target_rarity: str = "", return_all: bool = False, product_type: str = "Single") -> List[MarketPrice]:
    """
    Parses eBay HTML search results and extracts market prices (Sold listings).

    Args:
        return_all: If True, returns all valid listings (for stats).
                   If False, returns only new listings not in DB (for saving).
        product_type: Type of product (Single, Box, Pack, Lot) - affects treatment detection.
    """
    return _parse_generic_results(html_content, card_id, listing_type="sold",
                                 card_name=card_name, target_rarity=target_rarity,
                                 return_all=return_all, product_type=product_type)

def parse_active_results(html_content: str, card_id: int = 0, card_name: str = "", target_rarity: str = "", product_type: str = "Single") -> List[MarketPrice]:
    """
    Parses eBay HTML search results for ACTIVE listings.

    Args:
        product_type: Type of product (Single, Box, Pack, Lot) - affects treatment detection.
    """
    return _parse_generic_results(html_content, card_id, listing_type="active", card_name=card_name, target_rarity=target_rarity, product_type=product_type)

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
        match = re.search(r'([\d,]+)\+?\s*results', text)
        if match:
            return int(match.group(1).replace(',', ''))
    return 0

def _detect_treatment(title: str, product_type: str = "Single") -> str:
    """
    Detects treatment based on title keywords.
    For singles: card treatments (Foil, Serialized, etc.)
    For boxes/packs/lots: product condition (Sealed, New, etc.)
    """
    title_lower = title.lower()

    # Handle sealed products (Box, Pack, Lot, Bundle)
    if product_type in ("Box", "Pack", "Lot", "Bundle"):
        # Check for sealed/new indicators (higher priority)
        if "factory sealed" in title_lower or "factory-sealed" in title_lower:
            return "Factory Sealed"
        if "sealed" in title_lower:
            return "Sealed"
        if "new" in title_lower and ("brand new" in title_lower or "new sealed" in title_lower or "new in box" in title_lower or "nib" in title_lower):
            return "New"
        if "unopened" in title_lower:
            return "Unopened"
        if "open box" in title_lower or "opened" in title_lower:
            return "Open Box"
        if "used" in title_lower:
            return "Used"
        # Default for sealed products - assume sealed if no indicators
        return "Sealed"

    # Handle singles (cards)
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

    # 5. Default for singles
    return "Classic Paper"

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

    # CRITICAL: Reject non-Wonders TCG products that might match on keywords
    # e.g., "The Prisoner" should NOT match "Harry Potter Prisoner of Azkaban"
    non_wonders_keywords = [
        # Other TCGs (include accent variations)
        'harry potter', 'pokemon', 'pokémon', 'poke mon', 'yu-gi-oh', 'yugioh', 'yu gi oh',
        'magic the gathering', 'mtg ', ' mtg', 'flesh and blood', 'fab ', 'one piece',
        'dragon ball', 'digimon', 'cardfight', 'weiss schwarz', 'force of will', 'keyforge',
        'lorcana', 'metazoo', 'sorcery contested', 'star wars', 'lord of the rings',
        'universus', 'ufs ', 'naruto', 'my hero academia', 'union arena',
        'fire emblem', 'cipher',  # Fire Emblem Cipher TCG
        # One Piece TCG specific (often has "Awakening" set)
        'op05', 'op04', 'op03', 'op02', 'op01', 'op06', 'op07', 'op08',
        'awakening of the new era',  # One Piece set name - NOT the WOTF card
        'new era', 'kaido', 'luffy', 'zoro', 'sanji', 'nami', 'sakazuki', 'enel',
        'eustass', 'straw hat', 'romance dawn', 'paramount war',
        # Pokemon-specific set names and terms
        'shining fates', 'evolving skies', 'scarlet & violet', 'scarlet violet',
        'prismatic evolutions', 'prismatic', 'sword and shield', 'sword shield',
        'paldea', 'obsidian flames', 'paradox rift', 'temporal forces', 'twilight masquerade',
        'surging sparks', 'shrouded fable', 'stellar crown', 'crown zenith', 'vivid voltage',
        'celebrations', 'black star promo', 'swsh', 'psa 10', 'psa 9', 'psa 8',
        ' etb ', 'etb ', ' etb',  # Elite Trainer Box (Pokemon term)
        'elite trainer',  # Catches "Elite Trainer Box" variants
        # Yu-Gi-Oh specific
        'lckc', 'secret rare nm', 'melody of awakening',  # Yu-Gi-Oh card "The Melody of Awakening Dragon"
        # Game-specific terms that indicate non-Wonders
        'azkaban', 'hogwarts', 'pikachu', 'charizard', 'blue-eyes', 'dark magician',
        'planeswalker', 'earthbound', 'maze of millennia', 'duelist', 'konami',
        'eevee', 'mewtwo', 'bulbasaur', 'squirtle', 'jigglypuff', 'snorlax', 'gengar',
        # Sports cards
        'topps', 'panini', 'upper deck', 'bowman', 'prizm', 'donruss',
        'nba', 'nfl', 'mlb', 'nhl', 'fifa', 'ufc',
    ]

    for keyword in non_wonders_keywords:
        if keyword in title_lower:
            return False

    # Positive signal: title should ideally contain Wonders identifiers
    # (but don't require it - some listings are abbreviated)
    wonders_identifiers = ['wonders', 'existence', 'wotf', 'wonders of the first']
    has_wonders_identifier = any(ident in title_lower for ident in wonders_identifiers)

    # Detect product types - use more lenient matching for sealed products
    product_type_keywords = ['box', 'pack', 'case', 'lot', 'bundle', 'collection', 'bulk', 'sealed']
    is_product = any(keyword in name_lower for keyword in product_type_keywords)

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
            reject_phrases = ['voice of', 'zeltona', 'cura', 'captain', 'king', 'queen',
                            'lord', 'lady', 'sir', 'baron', 'duke', 'emperor', 'empress']
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
        # Use lower threshold for shorter words (e.g., "lich" vs "lieh")
        threshold = 0.75 if len(card_token) <= 5 else 0.85
        for title_token in title_tokens_list:
            # Use SequenceMatcher for fuzzy matching
            ratio = difflib.SequenceMatcher(None, card_token, title_token).ratio()
            if ratio >= threshold:
                return True
        return False

    # First try exact matching
    common_tokens = card_tokens_set.intersection(title_tokens_set)

    # If exact match is low, try fuzzy matching for remaining tokens
    unmatched_card_tokens = card_tokens_set - common_tokens
    fuzzy_matches = 0
    title_tokens_list = list(title_tokens_set)

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

def _extract_seller_info(item) -> Tuple[Optional[str], Optional[int], Optional[float]]:
    """
    Extracts seller name and feedback info from an item element.
    Returns: (seller_name, feedback_score, feedback_percent)
    """
    seller_name = None
    feedback_score = None
    feedback_percent = None

    # Try to find seller info element
    seller_elem = item.select_one(".s-item__seller-info, .s-item__seller-info-text, .s-item__itemAff498, [class*='seller']")
    if seller_elem:
        text = seller_elem.get_text(strip=True)
        # Parse seller name - usually format: "seller_name (1234) 99.5%"
        # Or sometimes: "Sold by seller_name"

        # Try pattern: "seller_name (1234) 99.5%"
        match = re.search(r'^([^\(]+)\s*\((\d+)\)\s*([\d.]+)%?', text)
        if match:
            seller_name = match.group(1).strip()
            feedback_score = int(match.group(2))
            feedback_percent = float(match.group(3))
        else:
            # Just extract seller name if feedback isn't there
            seller_name = text.replace("Sold by", "").strip()

    # Alternative: look for seller link
    if not seller_name:
        seller_link = item.select_one("a[href*='/usr/'], a[class*='seller']")
        if seller_link:
            seller_name = seller_link.get_text(strip=True)

    # Try to find feedback separately if not found
    if seller_name and not feedback_score:
        feedback_elem = item.select_one(".s-item__seller-info .s-item__feedback, [class*='feedback']")
        if feedback_elem:
            text = feedback_elem.get_text(strip=True)
            # Parse "(1234) 99.5%" format
            match = re.search(r'\((\d+)\)\s*([\d.]+)%', text)
            if match:
                feedback_score = int(match.group(1))
                feedback_percent = float(match.group(2))

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
    shipping_elem = item.select_one(".s-item__shipping, .s-item__freeXDays, .s-item__logisticsCost, [class*='shipping']")
    if shipping_elem:
        text = shipping_elem.get_text(strip=True).lower()

        # Free shipping
        if "free" in text:
            return 0.0

        # Parse shipping cost: "+$5.99 shipping" or "$5.99 shipping"
        match = re.search(r'\+?\$?([\d,.]+)\s*shipping', text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                pass

    return None

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

def _parse_generic_results(html_content: str, card_id: int, listing_type: str, card_name: str = "", target_rarity: str = "", return_all: bool = False, product_type: str = "Single") -> List[MarketPrice]:
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
        all_listings_data.append({
            "external_id": item_id,
            "title": title,
            "price": price,
            "sold_date": sold_date,
            "url": url,
            "bid_count": bid_count,
            "image_url": image_url,
            "seller_name": seller_name,
            "seller_feedback_score": seller_feedback_score,
            "seller_feedback_percent": seller_feedback_percent,
            "condition": condition,
            "shipping_cost": shipping_cost
        })

    if not all_listings_data:
        return []

    # Phase 1b: Bulk DB dedup check (single query instead of N queries)
    # IMPORTANT: Skip dedup for active listings - we always want fresh data
    # Dedup only makes sense for sold listings (avoid re-saving same sale)
    if listing_type == "active":
        indexed_indices = set()  # No dedup for active listings
    else:
        indexed_indices = _bulk_check_indexed(card_id, all_listings_data) if not return_all else set()

    # Phase 1c: Filter out already-indexed listings (unless return_all=True for stats)
    listings_to_extract = []
    listing_metadata = []

    for i, listing_data in enumerate(all_listings_data):
        if return_all or i not in indexed_indices:
            # Include for AI extraction if: return_all=True OR not indexed yet
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
        # For sealed products (Box, Pack, Lot, Bundle), always use rule-based detection
        # AI extractor doesn't understand sealed product treatments
        if product_type in ("Box", "Pack", "Lot", "Bundle"):
            treatment = _detect_treatment(metadata["title"], product_type)
        else:
            # For singles, use AI extraction with fallback to rule-based if low confidence
            treatment = extracted_data["treatment"]
            if extracted_data["confidence"] < 0.7:
                treatment = _detect_treatment(metadata["title"], product_type)

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
            # Seller info
            seller_name=metadata.get("seller_name"),
            seller_feedback_score=metadata.get("seller_feedback_score"),
            seller_feedback_percent=metadata.get("seller_feedback_percent"),
            # Listing details
            condition=metadata.get("condition"),
            shipping_cost=metadata.get("shipping_cost"),
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
    except (ValueError, AttributeError):
        return None

def _parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse eBay sold date strings, handling both absolute and relative dates.

    Examples:
    - "Sold Oct 4, 2025" -> datetime(2025, 10, 4)
    - "Sold 3 days ago" -> datetime.utcnow() - 3 days
    - "Sold Dec 1" -> datetime(current_year, 12, 1)
    """
    if not date_str:
        return None

    clean_str = date_str.lower().replace("sold", "").strip()

    # Handle relative dates like "3 days ago", "1 week ago"
    relative_match = re.search(r'(\d+)\s*(day|week|month|hour|minute)s?\s*ago', clean_str)
    if relative_match:
        quantity = int(relative_match.group(1))
        unit = relative_match.group(2)

        now = datetime.utcnow()
        if unit == 'day':
            return now - timedelta(days=quantity)
        elif unit == 'week':
            return now - timedelta(weeks=quantity)
        elif unit == 'month':
            return now - timedelta(days=quantity * 30)
        elif unit == 'hour':
            return now - timedelta(hours=quantity)
        elif unit == 'minute':
            return now - timedelta(minutes=quantity)

    # Handle special relative terms
    if 'just now' in clean_str or 'just ended' in clean_str:
        return datetime.utcnow()
    if 'yesterday' in clean_str:
        return datetime.utcnow() - timedelta(days=1)
    if 'today' in clean_str:
        return datetime.utcnow()

    # Try standard date parsing for absolute dates like "Oct 4, 2025" or "Dec 1"
    try:
        # Use current year as default if year not specified
        parsed = parser.parse(clean_str, default=datetime(datetime.utcnow().year, 1, 1))

        # Sanity check: sold_date shouldn't be in future
        if parsed > datetime.utcnow() + timedelta(days=1):
            # If parsed date is in future, try previous year
            parsed = parser.parse(clean_str, default=datetime(datetime.utcnow().year - 1, 1, 1))

        # Sanity check: shouldn't be too old (before 2023 for this TCG)
        if parsed.year < 2023:
            return None

        return parsed
    except (ValueError, parser.ParserError):
        return None
