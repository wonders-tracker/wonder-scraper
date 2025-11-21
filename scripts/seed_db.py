import json
import os
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card, Rarity

SEEDS_PATH = "data/seeds/cards.json"

def seed_db():
    if not os.path.exists(SEEDS_PATH):
        print(f"Seeds file not found at {SEEDS_PATH}")
        return

    with open(SEEDS_PATH, 'r') as f:
        data = json.load(f)

    with Session(engine) as session:
        # 1. Ensure Rarities exist
        rarity_names = set(item['rarity'] for item in data)
        rarity_map = {} # name -> id
        
        for r_name in rarity_names:
            # Check if exists
            statement = select(Rarity).where(Rarity.name == r_name)
            existing = session.exec(statement).first()
            if not existing:
                print(f"Creating Rarity: {r_name}")
                new_rarity = Rarity(name=r_name)
                session.add(new_rarity)
                session.commit()
                session.refresh(new_rarity)
                rarity_map[r_name] = new_rarity.id
            else:
                rarity_map[r_name] = existing.id
        
        # 2. Insert Cards
        count = 0
        for item in data:
            # Check if card exists by name (assuming unique name per set)
            # Realistically, name+set should be unique.
            statement = select(Card).where(Card.name == item['name'])
            existing = session.exec(statement).first()
            
            if not existing:
                card = Card(
                    name=item['name'],
                    rarity_id=rarity_map[item['rarity']],
                    set_name=item['set_name']
                    # We could store card_number if we added it to the model
                )
                session.add(card)
                count += 1
        
        session.commit()
        print(f"Seeded {count} new cards.")

if __name__ == "__main__":
    seed_db()

