with open("data/ebay_sample.html", "r") as f:
    html = f.read()

print(f"Total Length: {len(html)}")
print("\n--- HEAD ---")
print(html[:2000])
