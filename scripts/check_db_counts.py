from sqlmodel import Session, select, func
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot, MarketPrice

def check_data():
    with Session(engine) as session:
        card_count = session.exec(select(func.count(Card.id))).one()
        snapshot_count = session.exec(select(func.count(MarketSnapshot.id))).one()
        price_count = session.exec(select(func.count(MarketPrice.id))).one()
        
        print(f"Cards: {card_count}")
        print(f"MarketSnapshots: {snapshot_count}")
        print(f"MarketPrices: {price_count}")

if __name__ == "__main__":
    check_data()

