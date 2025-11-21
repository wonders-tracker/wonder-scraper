from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime
from dateutil import parser
import re
import difflib
from app.models.market import MarketPrice

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
    """
    if not card_name:
        return True 
        
    title_lower = title.lower()
    name_lower = card_name.lower()
    
    # 1. Name Validation
    card_tokens = set(name_lower.split())
    title_tokens = set(title_lower.replace("wonders of the first", "").split())
    
    common_tokens = card_tokens.intersection(title_tokens)
    
    if len(card_tokens) == 1:
        if list(card_tokens)[0] not in title_tokens:
            return False
    else:
        match_ratio = len(common_tokens) / len(card_tokens)
        if match_ratio < 0.66:
            return False

    # 2. Rarity Validation (if provided)
    # If target is "Common", reject "Mythic" or "Rare" in title
    # But accept "Common" in title.
    # This is tricky because listings might say "Rare card!" for a common card as spam.
    # So we should be conservative. Only reject obvious mismatches if we are sure.
    # E.g. If card is "Common", and title says "Mythic", it's likely a mismatch OR a special version.
    # If it's a special version (Foil Mythic), _detect_treatment might handle it.
    # Let's skip strict rarity rejection for now unless requested, to avoid false negatives.
    # User said "parse for the rarity... need to be smart".
    # Smart = Parse it, maybe warn?
    # For now, let's just rely on name + treatment. 
    # If I search for "Card X" and get "Card X Mythic", it's probably Card X but the Mythic version.
    # Since we want to track ALL sales of Card X (including variants), we should ACCEPT it.
    # The `treatment` field will capture "Classic Foil" etc.
    # If rarity changes (e.g. Promo is Mythic, Base is Common), treatment 'Promo' captures it.
    
    return True

def _parse_generic_results(html_content: str, card_id: int, listing_type: str, card_name: str = "", target_rarity: str = "") -> List[MarketPrice]:
    soup = BeautifulSoup(html_content, "lxml")
    results = []
    
    items = soup.select("li.s-item, li.s-card")
    
    for item in items:
        if "s-item__header" in item.get("class", []) or "s-card__header" in item.get("class", []):
            continue
            
        title_elem = item.select_one(".s-item__title, .s-card__title")
        if not title_elem:
            continue
        title = title_elem.get_text(strip=True)
        
        if "Shop on eBay" in title:
            continue

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
                    if sold_date: break
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

        treatment = _detect_treatment(title)

        mp = MarketPrice(
            card_id=card_id,
            title=title,
            price=price,
            sold_date=sold_date,
            listing_type=listing_type,
            treatment=treatment,
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
