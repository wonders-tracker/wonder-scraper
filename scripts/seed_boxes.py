from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card, Rarity

def seed_products():
    with Session(engine) as session:
        # Ensure Rarity 'Sealed' exists
        sealed_rarity = session.exec(select(Rarity).where(Rarity.name == "Sealed")).first()
        if not sealed_rarity:
            sealed_rarity = Rarity(name="Sealed")
            session.add(sealed_rarity)
            session.commit()
            session.refresh(sealed_rarity)
            print("Created 'Sealed' rarity category.")
        
        products = [
            {
                "name": "Existence Collector Box",
                "set_name": "Existence",
                "product_type": "Box"
            },
            {
                "name": "Existence Booster Pack",
                "set_name": "Existence", 
                "product_type": "Pack"
            }
        ]
        
        for p in products:
            existing = session.exec(select(Card).where(Card.name == p["name"])).first()
            if not existing:
                card = Card(
                    name=p["name"],
                    set_name=p["set_name"],
                    product_type=p["product_type"],
                    rarity_id=sealed_rarity.id
                )
                session.add(card)
                print(f"Added product: {p['name']}")
            else:
                print(f"Product already exists: {p['name']}")
                if existing.product_type != p["product_type"]:
                    existing.product_type = p["product_type"]
                    session.add(existing)
                    print(f"Updated product type for: {p['name']}")
        
        session.commit()
        print("Seeding complete.")

if __name__ == "__main__":
    seed_products()

