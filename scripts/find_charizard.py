from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")
# Find elements containing 'Charizard' text
for elem in soup.find_all(string=lambda text: "Charizard" in text if text else False):
    parent = elem.parent
    if parent.name != "script" and parent.name != "style":
        print(f"Tag: {parent.name}, Class: {parent.get('class')}, Text: {elem.strip()[:50]}")
