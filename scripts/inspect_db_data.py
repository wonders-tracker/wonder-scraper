from sqlmodel import Session, select
from app.db import engine
from app.models.market import MarketPrice
from app.models.card import Card

def inspect_db():
    with Session(engine) as session:
        # Check "The First"
        card = session.exec(select(Card).where(Card.name == 'The First')).first()
        if card:
            print(f'Card: {card.name} (ID: {card.id})')
            prices = session.exec(select(MarketPrice).where(MarketPrice.card_id == card.id).limit(20)).all()
            for p in prices:
                print(f'- {p.title} (${p.price})')
        else:
            print("Card 'The First' not found")

        # Check "The Blazing Phoenix"
        card_bp = session.exec(select(Card).where(Card.name == 'The Blazing Phoenix')).first()
        if card_bp:
            print(f'\nCard: {card_bp.name} (ID: {card_bp.id})')
            prices = session.exec(select(MarketPrice).where(MarketPrice.card_id == card_bp.id).limit(20)).all()
            for p in prices:
                print(f'- {p.title} (${p.price})')
        else:
            print("\nCard 'The Blazing Phoenix' not found")

if __name__ == "__main__":
    inspect_db()

