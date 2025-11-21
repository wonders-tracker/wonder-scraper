from app.scraper.utils import build_ebay_url

def test_build_ebay_url():
    url = build_ebay_url("Black Lotus")
    print(f"URL: {url}")
    assert "Black+Lotus" in url
    assert "LH_Sold=1" in url
    assert "183454" in url
    
    url_active = build_ebay_url("Charizard", sold_only=False)
    print(f"Active URL: {url_active}")
    assert "Charizard" in url_active
    assert "LH_Sold=1" not in url_active

if __name__ == "__main__":
    test_build_ebay_url()
    print("Tests passed!")

