import urllib.parse

EBAY_BASE_URL = "https://www.ebay.com/sch/i.html"
TCG_CATEGORY_ID = "183454"  # CCG Individual Cards

def build_ebay_url(card_name: str, set_name: str = None, sold_only: bool = True, page: int = 1) -> str:
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
        "_ipg": "240", # Max items per page to capture more history in one go
        "_pgn": str(page), # Page number for pagination
        "RT": "nc"    # Result type? often used in ebay urls
    }
    
    if sold_only:
        # LH_Sold=1 implies sold items. eBay typically shows last 90 days of sold items.
        # To get MORE history would require Terapeak or other paid APIs. 
        # Standard eBay search is limited to ~90 days for sold listings.
        params["LH_Sold"] = "1"
        params["LH_Complete"] = "1"
        
    query_string = urllib.parse.urlencode(params)
    return f"{EBAY_BASE_URL}?{query_string}"
