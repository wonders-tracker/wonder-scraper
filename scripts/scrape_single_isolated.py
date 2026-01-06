"""
Scrape a single card in isolation - designed to be called repeatedly.
Each invocation starts fresh and exits cleanly.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.scrape_card import scrape_card
from app.scraper.browser import BrowserManager


async def main():
    if len(sys.argv) < 6:
        print("Usage: python scrape_single_isolated.py <card_name> <card_id> <search_term> <set_name> <product_type>")
        sys.exit(1)

    card_name = sys.argv[1]
    card_id = int(sys.argv[2])
    search_term = sys.argv[3]
    set_name = sys.argv[4]
    product_type = sys.argv[5]

    try:
        # Use keyword arguments to match the function signature correctly
        # signature: scrape_card(card_name, card_id=0, rarity_name="", search_term=None, set_name="", product_type="Single", max_pages=3)
        await scrape_card(
            card_name=card_name,
            card_id=card_id,
            search_term=search_term,
            set_name=set_name,
            product_type=product_type,
            rarity_name="",  # Default or could be passed if needed
        )
        print(f"✅ SUCCESS: {card_name}")
    except Exception as e:
        print(f"❌ ERROR: {card_name} - {e}")
        # Print stack trace for better debugging
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        await BrowserManager.close()


if __name__ == "__main__":
    asyncio.run(main())
