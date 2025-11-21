from bs4 import BeautifulSoup
from collections import Counter

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")
classes = Counter()

for tag in soup.find_all(True):
    cls = tag.get("class")
    if cls:
        for c in cls:
            classes[c] += 1

print("Top 20 classes:")
for c, count in classes.most_common(20):
    print(f"{c}: {count}")

