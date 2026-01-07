from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

cards = soup.find_all("li", class_="s-card")

if len(cards) > 1:
    card = cards[2]  # Try index 2
    print("--- Card 2 ---")

    title = card.select_one(".s-card__title")
    print(f"Title: {title.get_text(strip=True) if title else 'None'}")

    # Look for all text in the card to see where date/price is
    print("--- Text Content ---")
    text = card.get_text(separator="|", strip=True)
    print(text)
