from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")
print(f"Title: {soup.title.string if soup.title else 'No Title'}")

# Print text of body to see if it says "Security Measure"
print(soup.get_text()[:500])
