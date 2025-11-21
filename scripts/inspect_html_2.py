from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# Try to find the results list
results_ul = soup.select_one("ul.srp-results")

if results_ul:
    print("Found ul.srp-results")
    items = results_ul.select("li.s-item")
    print(f"Found {len(items)} items in srp-results.")
    
    if items:
        print("--- First Item ---")
        # print(items[0].prettify()[:1000])
        item = items[0]
        
        # Selectors
        title = item.select_one(".s-item__title")
        price = item.select_one(".s-item__price")
        date = item.select_one(".s-item__caption")
        
        print(f"Title: {title.get_text(strip=True) if title else 'None'}")
        print(f"Price: {price.get_text(strip=True) if price else 'None'}")
        print(f"Caption/Date: {date.get_text(strip=True) if date else 'None'}")
else:
    print("Did not find ul.srp-results")
    # Fallback: Look for any s-item
    items = soup.select(".s-item")
    print(f"Total .s-item count: {len(items)}")

