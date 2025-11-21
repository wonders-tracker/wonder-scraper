import pdfplumber

PDF_PATH = "data/Base-Set-WoTF-Existence-Checklist-Google-Sheets.pdf"

def inspect_pdf():
    with pdfplumber.open(PDF_PATH) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()
        
        if not tables:
            print("No tables found on page 1.")
            return

        table = tables[0]
        print(f"Found table with {len(table)} rows.")
        
        # Print headers and first 5 data rows
        for i, row in enumerate(table[:10]):
            print(f"Row {i}: {row}")

if __name__ == "__main__":
    inspect_pdf()
