import asyncio
from app.scraper.browser import get_page_content
from app.scraper.utils import build_ebay_url


async def fetch_sample():
    card_name = "Charizard Base Set"
    url = build_ebay_url(card_name, sold_only=True)
    print(f"Fetching {url}...")

    content = await get_page_content(url)

    with open("data/ebay_sample.html", "w") as f:
        f.write(content)
    print("Saved to data/ebay_sample.html")


if __name__ == "__main__":
    asyncio.run(fetch_sample())
