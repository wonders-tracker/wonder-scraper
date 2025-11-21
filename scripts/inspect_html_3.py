from bs4 import BeautifulSoup

with open("data/ebay_sample.html", "r") as f:
    html = f.read()

# Use lxml for better parsing
soup = BeautifulSoup(html, "lxml")

# Just find all elements with class s-item
items = soup.find_all(class_="s-item")
print(f"Found {len(items)} items with class 's-item'.")

if len(items) > 0:
    item = items[1] # 0 might be header
    print(f"Item 1 Tag: {item.name}")
    print(f"Item 1 Classes: {item.get('class')}")
    
    title = item.select_one(".s-item__title")
    price = item.select_one(".s-item__price")
    # Date sold is often in .s-item__title--tag-block .POSITIVE for "Sold Dec 12, 2023"
    # Or .s-item__caption
    
    print(f"Title: {title.get_text(strip=True) if title else 'None'}")
    print(f"Price: {price.get_text(strip=True) if price else 'None'}")
    
    # Debug all text in item
    # print(item.get_text(strip=True)[:200])

