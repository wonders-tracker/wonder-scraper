from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")
cards = soup.find_all(class_="s-card__link")
print(f"Found {len(cards)} s-card__link.")

if cards:
    print("First card link text:", cards[0].get_text(strip=True))
    print("First card link parent classes:", cards[0].parent.get("class"))

