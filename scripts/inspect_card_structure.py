from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

cards = soup.find_all("li", class_="s-card")
print(f"Found {len(cards)} cards.")

if cards:
    card = cards[0]
    # print(card.prettify()[:1000])
    
    title = card.select_one(".s-card__title")
    print(f"Title: {title.get_text(strip=True) if title else 'None'}")
    
    # Try to find price. Look for class containing 'price' or 'su-styled-text' with '$'
    # Usually .s-card__price or similar
    price_elem = card.select_one(".s-card__price")
    if not price_elem:
        # Search for text with $
        price_elem = card.find(string=lambda t: t and "$" in t)
        
    print(f"Price: {price_elem.get_text(strip=True) if price_elem else 'None'}")
    
    # Date sold?
    # Usually "Sold  Nov 10, 2023"
    date_elem = card.find(string=lambda t: t and "Sold" in t)
    print(f"Date Text: {date_elem.strip() if date_elem else 'None'}")

