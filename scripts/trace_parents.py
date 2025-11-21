from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

# Find one known title
target_text = "Charizard 004/102 Base Set Holo"
title_span = soup.find(string=lambda t: t and target_text in t).parent

print(f"Title Span: {title_span}")
print(f"Classes: {title_span.get('class')}")

# Walk up parents
current = title_span
for i in range(10):
    current = current.parent
    if not current: break
    print(f"Parent {i}: Tag={current.name}, Class={current.get('class')}, ID={current.get('id')}")
    if current.name == "li" or "s-item" in str(current.get("class")):
        print(">>> FOUND ITEM CONTAINER")
        break

