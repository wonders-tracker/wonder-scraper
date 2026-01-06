"""
Complete data refresh using subprocess isolation for reliability
"""

import sys
import os
import subprocess
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot


def scrape_card_isolated(card):
    """Scrape a card in a completely isolated subprocess"""
    search_term = f"{card.name} {card.set_name}"
    product_type = card.product_type if hasattr(card, "product_type") else "Single"

    # Call isolated script using the same python interpreter
    cmd = [
        sys.executable,
        "scripts/scrape_single_isolated.py",
        card.name,
        str(card.id),
        search_term,
        card.set_name,
        product_type,
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = "/Users/Cody/code_projects/wonder-scraper"

    try:
        result = subprocess.run(
            cmd,
            cwd="/Users/Cody/code_projects/wonder-scraper",
            env=env,
            capture_output=True,
            text=True,
            timeout=180,  # 3 minute timeout per card
        )

        if result.returncode == 0:
            print(f"✅ {card.name}")
            return True
        else:
            print(f"❌ {card.name}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏱️  {card.name}: Timeout (3min)")
        return False
    except Exception as e:
        print(f"❌ {card.name}: {e}")
        return False


def main():
    print("\n🚀 FULL DATA REFRESH (ROBUST MODE)")
    print("=" * 60)

    # Check current data
    with Session(engine) as session:
        snapshot_count_before = len(session.exec(select(MarketSnapshot)).all())
        cards = session.exec(select(Card)).all()

    print("📊 Starting State:")
    print(f"   - Cards to scrape: {len(cards)}")
    print(f"   - Existing snapshots: {snapshot_count_before}")
    print()

    success_count = 0
    fail_count = 0

    print("SCRAPING EBAY (Each card in isolated process)")
    print("=" * 60)

    for i, card in enumerate(cards, 1):
        print(f"[{i}/{len(cards)}] {card.name} ({card.product_type})... ", end="", flush=True)

        if scrape_card_isolated(card):
            success_count += 1
        else:
            fail_count += 1

        # Brief delay between cards
        time.sleep(2)

        # Status update every 10 cards
        if i % 10 == 0:
            print(f"\n📊 Progress: {i}/{len(cards)} | ✅ {success_count} | ❌ {fail_count}\n")

    # Final stats
    with Session(engine) as session:
        snapshot_count_after = len(session.exec(select(MarketSnapshot)).all())

    print("\n" + "=" * 60)
    print("✅ SCRAPING COMPLETE!")
    print("=" * 60)
    print(f"Success: {success_count}/{len(cards)}")
    print(f"Failed: {fail_count}/{len(cards)}")
    print(f"New snapshots: {snapshot_count_after - snapshot_count_before}")
    print(f"Total snapshots: {snapshot_count_after}")

    # ---------------------------------------------------------
    # OPENSEA SCRAPE
    # ---------------------------------------------------------
    print("\n" + "=" * 60)
    print("SCRAPING OPENSEA (Isolated Process)")
    print("=" * 60)

    opensea_cmd = [sys.executable, "scripts/scrape_opensea.py"]

    try:
        result = subprocess.run(
            opensea_cmd,
            cwd="/Users/Cody/code_projects/wonder-scraper",
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for OpenSea
        )

        if result.returncode == 0:
            print(result.stdout)
            print("✅ OpenSea Scrape Successful")
        else:
            print(result.stdout)
            print(result.stderr)
            print("❌ OpenSea Scrape Failed")
            fail_count += 1  # Tracking roughly

    except subprocess.TimeoutExpired:
        print("⏱️  OpenSea Scrape Timeout")
    except Exception as e:
        print(f"❌ OpenSea Execution Error: {e}")


if __name__ == "__main__":
    main()
