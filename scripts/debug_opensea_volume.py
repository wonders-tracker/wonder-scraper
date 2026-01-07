import asyncio
from app.scraper.browser import BrowserManager
from bs4 import BeautifulSoup


async def debug_volume():
    url = "https://opensea.io/collection/wotf-character-proofs"
    print(f"Fetching {url}...")

    browser = await BrowserManager.get_browser()
    page = await browser.new_tab()
    await page.go_to(url)

    # Wait longer for dynamic content
    print("Waiting 10 seconds for full page load...")
    await asyncio.sleep(10)

    html = await page.page_source

    with open("opensea_volume_debug.html", "w") as f:
        f.write(html)
    print("Saved HTML.")

    soup = BeautifulSoup(html, "lxml")

    # Search for "136" or "total volume" patterns
    print("\n--- Searching for volume patterns ---")

    # Try all span.font-mono elements
    mono_spans = soup.select("span.font-mono")
    print(f"Found {len(mono_spans)} span.font-mono elements")
    for i, span in enumerate(mono_spans[:20]):  # First 20
        text = span.get_text(strip=True)
        container = span.find_parent("div")
        context = container.get_text(" ", strip=True)[:100] if container else ""
        print(f"{i}: '{text}' | Context: {context}")

    # Search for text containing "volume"
    print("\n--- Searching for 'volume' text ---")
    volume_elements = soup.find_all(string=lambda t: "volume" in t.lower() if t else False)
    for elem in volume_elements[:10]:
        parent_text = elem.parent.get_text(strip=True)
        print(f"Found: {parent_text[:150]}")

    await browser.stop()


if __name__ == "__main__":
    asyncio.run(debug_volume())
