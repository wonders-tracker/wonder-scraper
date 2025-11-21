from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card, Rarity

def seed_character_proofs():
    with Session(engine) as session:
        # Ensure 'Sealed' rarity exists (or use appropriate rarity)
        sealed_rarity = session.exec(select(Rarity).where(Rarity.name == "Sealed")).first()
        if not sealed_rarity:
            sealed_rarity = Rarity(name="Sealed")
            session.add(sealed_rarity)
            session.commit()
            session.refresh(sealed_rarity)
            print("Created 'Sealed' rarity category.")

        # Add Character Proofs
        char_proofs = session.exec(select(Card).where(Card.name == "Character Proofs")).first()
        if not char_proofs:
            char_proofs = Card(
                name="Character Proofs",
                set_name="Existence",
                rarity_id=sealed_rarity.id,
                product_type="Proof"
            )
            session.add(char_proofs)
            session.commit()
            session.refresh(char_proofs)
            print("Added product: Character Proofs")
        else:
            print("Character Proofs already exists.")

        print("Seeding complete.")

if __name__ == "__main__":
    seed_character_proofs()

