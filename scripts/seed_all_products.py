"""
Comprehensive Product Seeder for Wonders of the First
Seeds all non-single products: Boxes, Packs, Cases, Lots, Proofs
"""
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card, Rarity

def seed_all_products():
    """
    Seeds comprehensive list of Wonders of the First sealed products.
    Based on typical TCG product structure and WoTF specifics.
    """
    with Session(engine) as session:
        # Ensure 'Sealed' rarity exists
        sealed_rarity = session.exec(select(Rarity).where(Rarity.name == "Sealed")).first()
        if not sealed_rarity:
            sealed_rarity = Rarity(name="Sealed")
            session.add(sealed_rarity)
            session.commit()
            session.refresh(sealed_rarity)
            print("✓ Created 'Sealed' rarity category.")
        
        products = [
            # === BOXES ===
            {
                "name": "Existence Booster Box",
                "set_name": "Existence",
                "product_type": "Box"
            },
            {
                "name": "Existence Collector Box",
                "set_name": "Existence",
                "product_type": "Box"
            },
            {
                "name": "Existence Elite Trainer Box",
                "set_name": "Existence",
                "product_type": "Box"
            },
            {
                "name": "Wonders of the First Booster Box",
                "set_name": "Existence",
                "product_type": "Box"
            },
            {
                "name": "Wonders of the First Starter Box",
                "set_name": "Existence",
                "product_type": "Box"
            },
            
            # === PACKS ===
            {
                "name": "Existence Booster Pack",
                "set_name": "Existence",
                "product_type": "Pack"
            },
            {
                "name": "Existence Sealed Pack",
                "set_name": "Existence",
                "product_type": "Pack"
            },
            {
                "name": "Wonders of the First Booster Pack",
                "set_name": "Existence",
                "product_type": "Pack"
            },
            {
                "name": "Wonders of the First Starter Pack",
                "set_name": "Existence",
                "product_type": "Pack"
            },
            
            # === CASES ===
            {
                "name": "Existence Booster Box Case",
                "set_name": "Existence",
                "product_type": "Box"  # Cases are treated as boxes for scraping
            },
            {
                "name": "Existence Case",
                "set_name": "Existence",
                "product_type": "Box"
            },
            
            # === LOTS / BUNDLES ===
            {
                "name": "Wonders of the First Card Lot",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            {
                "name": "Existence Card Lot",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            {
                "name": "Wonders of the First Bundle",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            {
                "name": "Wonders of the First Collection",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            {
                "name": "Wonders of the First Bulk Lot",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            {
                "name": "Existence Mixed Lot",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            {
                "name": "Wonders of the First Complete Set",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            
            # === PROOFS / SAMPLES ===
            {
                "name": "Character Proofs",
                "set_name": "Existence",
                "product_type": "Proof"
            },
            {
                "name": "Wonders of the First Proof Card",
                "set_name": "Existence",
                "product_type": "Proof"
            },
            {
                "name": "Wonders of the First Sample Card",
                "set_name": "Existence",
                "product_type": "Proof"
            },
            {
                "name": "Existence Prototype Card",
                "set_name": "Existence",
                "product_type": "Proof"
            },
            
            # === GRADED LOTS ===
            {
                "name": "Wonders of the First Graded Lot",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            {
                "name": "Wonders of the First PSA Lot",
                "set_name": "Existence",
                "product_type": "Lot"
            },
            {
                "name": "Wonders of the First CGC Lot",
                "set_name": "Existence",
                "product_type": "Lot"
            },
        ]
        
        added_count = 0
        updated_count = 0
        
        for p in products:
            existing = session.exec(
                select(Card).where(Card.name == p["name"])
            ).first()
            
            if not existing:
                card = Card(
                    name=p["name"],
                    set_name=p["set_name"],
                    product_type=p["product_type"],
                    rarity_id=sealed_rarity.id
                )
                session.add(card)
                added_count += 1
                print(f"✓ Added: {p['name']} ({p['product_type']})")
            else:
                # Update product_type if it's different
                if existing.product_type != p["product_type"]:
                    existing.product_type = p["product_type"]
                    session.add(existing)
                    updated_count += 1
                    print(f"✓ Updated: {p['name']} → {p['product_type']}")
                else:
                    print(f"  Skipped: {p['name']} (already exists)")
        
        session.commit()
        
        print("\n" + "="*60)
        print(f"Seeding Complete!")
        print(f"  Added: {added_count} products")
        print(f"  Updated: {updated_count} products")
        print("="*60)

if __name__ == "__main__":
    seed_all_products()

