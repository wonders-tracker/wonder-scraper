"""
Clean up Pokémon and other non-WoTF entries from the database.
"""
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card

def list_all_sealed_products():
    """List all boxes and packs to identify what needs cleanup."""
    with Session(engine) as session:
        # Get all boxes
        boxes = session.exec(select(Card).where(Card.product_type == 'Box')).all()
        print('=' * 80)
        print('BOXES')
        print('=' * 80)
        for card in boxes:
            print(f'{card.id:4d}: {card.name:50s} (Set: {card.set_name})')

        print('\n' + '=' * 80)
        print('PACKS')
        print('=' * 80)
        # Get all packs
        packs = session.exec(select(Card).where(Card.product_type == 'Pack')).all()
        for card in packs:
            print(f'{card.id:4d}: {card.name:50s} (Set: {card.set_name})')

        print('\n' + '=' * 80)
        print(f'Total Boxes: {len(boxes)}')
        print(f'Total Packs: {len(packs)}')
        print('=' * 80)

def cleanup_bad_entries():
    """Remove Pokémon and other non-WoTF entries."""
    # Keywords that indicate non-WoTF products
    bad_keywords = [
        'pokemon', 'pokémon', 'charizard', 'pikachu', 'mewtwo',
        'magic the gathering', 'mtg', 'yugioh', 'yu-gi-oh',
        'dragon ball', 'digimon', 'flesh and blood'
    ]

    with Session(engine) as session:
        # Get all sealed products (Box, Pack)
        sealed = session.exec(
            select(Card).where(Card.product_type.in_(['Box', 'Pack']))
        ).all()

        to_delete = []

        for card in sealed:
            card_name_lower = card.name.lower()
            set_name_lower = (card.set_name or '').lower()

            # Check if this is a bad entry
            is_bad = False
            for keyword in bad_keywords:
                if keyword in card_name_lower or keyword in set_name_lower:
                    is_bad = True
                    break

            # Also check if it's NOT a WoTF product
            # WoTF products should have "Wonders" or "Existence" in name or set
            is_wotf = (
                'wonders' in card_name_lower or
                'existence' in card_name_lower or
                'wonders' in set_name_lower or
                'existence' in set_name_lower
            )

            if is_bad or not is_wotf:
                to_delete.append(card)
                print(f'WILL DELETE: {card.id} - {card.name} (Set: {card.set_name})')

        if to_delete:
            print(f'\n{len(to_delete)} entries will be deleted.')
            confirm = input('Proceed with deletion? (yes/no): ')

            if confirm.lower() == 'yes':
                for card in to_delete:
                    session.delete(card)
                session.commit()
                print(f'✓ Deleted {len(to_delete)} bad entries.')
            else:
                print('Deletion cancelled.')
        else:
            print('No bad entries found!')

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'list':
        list_all_sealed_products()
    elif len(sys.argv) > 1 and sys.argv[1] == 'cleanup':
        cleanup_bad_entries()
    else:
        print('Usage:')
        print('  python cleanup_bad_entries.py list     - List all boxes and packs')
        print('  python cleanup_bad_entries.py cleanup  - Remove bad entries')
