from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

# Find text "Sold  Aug 28"
target = soup.find(string=lambda t: t and "Sold" in t and "Aug 28" in t)
if target:
    print(f"Sold Date Parent: {target.parent.name}, Classes: {target.parent.get('class')}")
    print(f"Grandparent: {target.parent.parent.name}, Classes: {target.parent.parent.get('class')}")

# Find price "$399.99"
target_price = soup.find(string=lambda t: t and "$399.99" in t)
if target_price:
    print(f"Price Parent: {target_price.parent.name}, Classes: {target_price.parent.get('class')}")
    print(f"Grandparent: {target_price.parent.parent.name}, Classes: {target_price.parent.parent.get('class')}")
