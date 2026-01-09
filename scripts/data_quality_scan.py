#!/usr/bin/env python3
"""
Comprehensive data quality scan for wonder-scraper database.
Run with: python scripts/data_quality_scan.py
"""

import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.db import engine


def scan():
    """Run comprehensive data quality checks."""
    with engine.connect() as conn:
        print('=== DATA QUALITY SCAN ===\n')

        # 1. Price outliers
        result = conn.execute(text('''
            SELECT title, price, listing_type, platform, scraped_at
            FROM marketprice
            WHERE price > 10000 OR price < 0.01
            ORDER BY price DESC
            LIMIT 10
        '''))
        rows = result.fetchall()
        print(f'1. PRICE OUTLIERS (>$10K or <$0.01): {len(rows)} records')
        for row in rows[:5]:
            print(f'   [{row[3]}] ${row[1]:.2f} - {row[0][:45]}')

        # 2. Invalid dates (future or very old)
        result = conn.execute(text('''
            SELECT COUNT(*) FROM marketprice
            WHERE sold_date > NOW() + INTERVAL '1 day'
               OR sold_date < '2024-01-01'
        '''))
        print(f"\n2. INVALID DATES (future or pre-2024): {result.fetchone()[0]} records")

        # 3. Missing titles
        result = conn.execute(text('''
            SELECT COUNT(*) FROM marketprice WHERE title IS NULL OR title = ''
        '''))
        print(f'\n3. MISSING TITLES: {result.fetchone()[0]} records')

        # 4. Treatment consistency
        result = conn.execute(text('''
            SELECT treatment, COUNT(*) as cnt
            FROM marketprice
            WHERE treatment IS NOT NULL
            GROUP BY treatment
            ORDER BY cnt DESC
        '''))
        print('\n4. TREATMENT VALUES:')
        for row in result:
            print(f'   {row[0]}: {row[1]}')

        # 5. Cards without market data
        result = conn.execute(text('''
            SELECT c.name, c.id
            FROM card c
            LEFT JOIN marketprice mp ON c.id = mp.card_id
            WHERE mp.id IS NULL
        '''))
        rows = result.fetchall()
        print(f'\n5. CARDS WITHOUT MARKET DATA: {len(rows)}')
        for row in rows[:10]:
            print(f'   {row[0]} (id={row[1]})')

        # 6. Check listing_type consistency
        result = conn.execute(text('''
            SELECT listing_type, COUNT(*) as cnt
            FROM marketprice
            GROUP BY listing_type
        '''))
        print('\n6. LISTING TYPES:')
        for row in result:
            print(f'   {row[0]}: {row[1]}')

        # 7. Check for zero quantity records
        result = conn.execute(text('''
            SELECT COUNT(*) FROM marketprice WHERE quantity = 0
        '''))
        print(f"\n7. ZERO QUANTITY RECORDS: {result.fetchone()[0]}")

        # 8. Blokpax data quality
        result = conn.execute(text('''
            SELECT treatment, COUNT(*) as cnt
            FROM blokpaxsale
            WHERE treatment IS NOT NULL
            GROUP BY treatment
            ORDER BY cnt DESC
        '''))
        print('\n8. BLOKPAX SALE TREATMENTS:')
        for row in result:
            print(f'   {row[0]}: {row[1]}')

        # Check for NULL treatments in blokpax
        result = conn.execute(text('''
            SELECT COUNT(*) FROM blokpaxsale WHERE treatment IS NULL
        '''))
        null_count = result.fetchone()[0]
        if null_count > 0:
            print(f'   (NULL treatments: {null_count})')

        # 9. Check for duplicate blokpax sales
        result = conn.execute(text('''
            SELECT listing_id, COUNT(*) as cnt
            FROM blokpaxsale
            GROUP BY listing_id
            HAVING COUNT(*) > 1
        '''))
        dupes = result.fetchall()
        print(f'\n9. DUPLICATE BLOKPAX SALES: {len(dupes)}')

        # 10. Check variant vs treatment consistency
        result = conn.execute(text('''
            SELECT variant, treatment, COUNT(*) as cnt
            FROM marketprice
            WHERE variant IS NOT NULL AND treatment IS NOT NULL
            GROUP BY variant, treatment
            ORDER BY cnt DESC
            LIMIT 20
        '''))
        print('\n10. VARIANT vs TREATMENT (top combinations):')
        for row in result:
            print(f'    variant={row[0]}, treatment={row[1]}: {row[2]}')


if __name__ == "__main__":
    scan()
