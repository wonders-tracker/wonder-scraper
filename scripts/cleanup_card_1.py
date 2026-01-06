from sqlmodel import Session, select
from app.db import engine
from app.models.market import MarketPrice, MarketSnapshot


def cleanup_card_1():
    with Session(engine) as session:
        print("Cleaning up data for Card ID 1 (The First)...")

        # Delete Snapshots
        snapshots = session.exec(select(MarketSnapshot).where(MarketSnapshot.card_id == 1)).all()
        for s in snapshots:
            session.delete(s)
        print(f"Deleted {len(snapshots)} snapshots.")

        # Delete Prices
        prices = session.exec(select(MarketPrice).where(MarketPrice.card_id == 1)).all()
        for p in prices:
            session.delete(p)
        print(f"Deleted {len(prices)} market prices.")

        session.commit()
        print("Cleanup complete.")


if __name__ == "__main__":
    cleanup_card_1()
