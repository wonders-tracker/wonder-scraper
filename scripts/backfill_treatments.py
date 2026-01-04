from sqlmodel import Session, select
from sqlalchemy import func
from app.db import engine
from app.models.market import MarketPrice
from app.models.card import Card
from app.scraper.ebay import _detect_treatment

BATCH_SIZE = 1000  # Process in batches to avoid memory issues


def backfill_treatments():
    with Session(engine) as session:
        # Build card_id -> product_type lookup (small table, OK to load fully)
        cards = session.exec(select(Card)).all()
        card_product_types = {card.id: card.product_type for card in cards}

        # Get total count for progress reporting
        total_count = session.exec(select(func.count(MarketPrice.id))).one()
        print(f"Found {total_count} prices to check (processing in batches of {BATCH_SIZE}).")

        updated_count = 0
        offset = 0

        while True:
            # Fetch batch
            batch = session.exec(
                select(MarketPrice).offset(offset).limit(BATCH_SIZE)
            ).all()

            if not batch:
                break

            batch_updates = 0
            for price in batch:
                product_type = card_product_types.get(price.card_id, "Single")
                current_treatment = price.treatment
                detected_treatment = _detect_treatment(price.title, product_type)

                if current_treatment != detected_treatment:
                    price.treatment = detected_treatment
                    session.add(price)
                    batch_updates += 1

            # Commit after each batch to avoid long transactions
            if batch_updates > 0:
                session.commit()
                updated_count += batch_updates

            offset += BATCH_SIZE
            print(f"  Processed {min(offset, total_count)}/{total_count} ({updated_count} updated)")

        print(f"Successfully updated {updated_count} records with correct treatments.")

if __name__ == "__main__":
    backfill_treatments()

