import urllib.parse

EBAY_BASE_URL = "https://www.ebay.com/sch/i.html"
TCG_CATEGORY_ID = "183454"  # CCG Individual Cards

def build_ebay_url(card_name: str, sold_only: bool = True) -> str:
    """
    Constructs an eBay search URL for a given card name.
    
    Args:
        card_name: The name of the card to search for.
        sold_only: If True, returns only sold/completed listings (default True).
        
    Returns:
        A valid eBay search URL.
    """
    params = {
        "_nkw": card_name,
        "_sacat": TCG_CATEGORY_ID,
        "_ipg": "60", # Items per page
        "RT": "nc"    # Result type? often used in ebay urls
    }
    
    if sold_only:
        params["LH_Sold"] = "1"
        params["LH_Complete"] = "1"
        
    query_string = urllib.parse.urlencode(params)
    return f"{EBAY_BASE_URL}?{query_string}"

