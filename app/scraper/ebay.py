from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime
from dateutil import parser
import re
from app.models.market import MarketPrice

def parse_search_results(html_content: str, card_id: int = 0) -> List[MarketPrice]:
    """
    Parses eBay HTML search results and extracts market prices (Sold listings).
    """
    return _parse_generic_results(html_content, card_id, listing_type="sold")

def parse_active_results(html_content: str, card_id: int = 0) -> List[MarketPrice]:
    """
    Parses eBay HTML search results for ACTIVE listings.
    Looking for Price (Ask) and potentially bid count if auction.
    """
    return _parse_generic_results(html_content, card_id, listing_type="active")

def parse_total_results(html_content: str) -> int:
    """
    Parses the total number of results from the eBay search page header.
    E.g., "1,200 results" -> 1200
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
    
    # Check for OCM / Serialized
    if "serialized" in title_lower or "/10" in title_lower or "/25" in title_lower or "/50" in title_lower or "/75" in title_lower or "/99" in title_lower or "ocm" in title_lower:
        return "OCM Serialized"
        
    # Check for Stonefoil
    if "stonefoil" in title_lower or "stone foil" in title_lower:
        return "Stonefoil"
        
    # Check for Formless Foil
    if "formless" in title_lower:
        return "Formless Foil"
        
    # Check for Classic Foil (just "foil" usually implies classic if not specified otherwise)
    if "foil" in title_lower:
        return "Classic Foil"
        
    # Default
    return "Classic Paper"

def _parse_generic_results(html_content: str, card_id: int, listing_type: str) -> List[MarketPrice]:
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

        price_elem = item.select_one(".s-item__price, .s-card__price")
        if not price_elem:
            continue
        
        price_str = price_elem.get_text(strip=True)
        price = _clean_price(price_str)
        if price is None:
            continue
            
        sold_date = None
        if listing_type == "sold":
            # Logic to find date
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
                continue # Skip sold items without date
        else:
            # Active listing
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
