from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketPrice
from app.scraper.ebay import _is_valid_match


def cleanup_bad_matches():
    print("Starting data cleanup for mismatched listings...")
    with Session(engine) as session:
        # 1. Get all cards to map ID -> Name
        cards = session.exec(select(Card)).all()
        card_map = {c.id: c.name for c in cards}
        print(f"Loaded {len(card_map)} cards.")

        # 2. Iterate through Market Prices (this might be slow for huge DBs, but fine for now)
        # For better performance, we could query in batches.
        prices = session.exec(select(MarketPrice)).all()
        print(f"Checking {len(prices)} market prices for validity...")

        deleted_count = 0

        for price in prices:
            card_name = card_map.get(price.card_id)
            if not card_name:
                continue  # Orphaned price?

            # Run validation with NEW logic
            # Note: _is_valid_match expects clean title, but our DB title might have "opens in new window" etc.
            # However, our NEW _is_valid_match handles cleaning internally too if we updated ebay.py correctly.
            # Actually, _is_valid_match in ebay.py does NOT call _clean_title_text internally,
            # but _clean_title_text was called BEFORE saving.
            # But old data might still have junk.

            # Let's assume title in DB is what matched BEFORE.
            # We apply the NEW strict validation.

            # Since _is_valid_match splits and checks tokens, junk at end usually doesn't hurt match ratio
            # (it adds tokens to title, making ratio LOWER, which is stricter).
            # So if it passed before, it might fail now due to stopwords or ratio.

            if not _is_valid_match(price.title, card_name):
                print(f"Deleting Mismatch: Card '{card_name}' vs Title '{price.title}'")
                session.delete(price)
                deleted_count += 1

        session.commit()
        print(f"Cleanup Complete. Deleted {deleted_count} mismatched listings.")


if __name__ == "__main__":
    cleanup_bad_matches()
