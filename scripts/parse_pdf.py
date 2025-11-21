import pdfplumber
import json
import re

PDF_PATH = "data/Base-Set-WoTF-Existence-Checklist-Google-Sheets.pdf"
OUTPUT_PATH = "data/seeds/cards.json"

def parse_pdf():
    cards = []
    
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"Processing {len(pdf.pages)} pages...")
        
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                continue
                
            table = tables[0]
            for row in table:
                # Basic validation: Row must have at least 3 columns
                if not row or len(row) < 3:
                    continue
                
                col0 = row[0] # Number + Set
                col1 = row[1] # Name
                col2 = row[2] # Rarity
                
                # Check if Col 0 matches pattern "001/401 Existence" or similar
                # or just contains a number.
                if not col0 or not isinstance(col0, str):
                    continue
                    
                # Regex to match "001/401 Existence" or just "001/401"
                # We look for the pattern digit/digit
                match = re.search(r'(\d+/\d+)\s*(.*)', col0)
                if match:
                    card_number = match.group(1)
                    set_suffix = match.group(2).strip() or "Existence"
                    
                    name = col1.strip() if col1 else "Unknown"
                    rarity = col2.strip() if col2 else "Unknown"
                    
                    # Skip if name matches column header "Base Set"
                    if name == "Base Set":
                        continue

                    card = {
                        "card_number": card_number,
                        "set_name": set_suffix,
                        "name": name,
                        "rarity": rarity
                    }
                    cards.append(card)
                    print(f"Found: {card_number} - {name} ({rarity})")

    print(f"\nExtracted {len(cards)} cards.")
    
    # Ensure directory exists
    import os
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(cards, f, indent=2)
    print(f"Saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    parse_pdf()

