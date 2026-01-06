"""
Backfill NFT traits for MarketPrice records.

This script updates MarketPrice records where treatment='NFT' by:
1. For Blokpax: Looking up traits from BlokpaxAssetDB
2. For OpenSea: Fetching traits from OpenSea API

Usage:
    python scripts/backfill_nft_traits.py              # Dry run (preview changes)
    python scripts/backfill_nft_traits.py --execute    # Actually update records
    python scripts/backfill_nft_traits.py --limit 100  # Limit to 100 records
"""

import asyncio
import argparse
import re
import json
from typing import Optional, Dict, List

from sqlmodel import Session, select
from bs4 import BeautifulSoup
from app.db import engine
from app.models.market import MarketPrice
from app.models.blokpax import BlokpaxAssetDB, BlokpaxSale
from app.scraper.browser import get_page_content

# Map collection slugs to contract addresses
OPENSEA_CONTRACTS = {
    "wotf-character-proofs": "0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8",
    "wotf-existence-collector-boxes": "0x28a11da34a93712b1fde4ad15da217a3b14d9465",
}


def extract_treatment_from_traits(traits: List[Dict[str, str]]) -> Optional[str]:
    """
    Extract the most relevant single trait value for display.

    For WOTF Character Proofs: Use "Hierarchy" (Spell, Primary Form, Item, etc.)
    For Collector Boxes: Use "Box Art" (Dragon, First Form: Solfera, etc.)

    Traits are stored as: [{"trait_type": "Type", "value": "Foil"}, ...]
    Returns a simple string like "Spell" or "Dragon"
    """
    if not traits:
        return None

    # Build a dict for easy lookup
    trait_dict = {}
    for trait in traits:
        trait_type = (trait.get("trait_type") or "").lower()
        trait_value = trait.get("value") or ""
        if trait_type and trait_value:
            trait_dict[trait_type] = trait_value

    # Priority order for what to display
    # 1. Hierarchy (most useful for Character Proofs)
    if "hierarchy" in trait_dict:
        return trait_dict["hierarchy"]

    # 2. Box Art (for Collector Boxes)
    if "box art" in trait_dict:
        return trait_dict["box art"]

    # 3. Orbital Class
    if "orbital class" in trait_dict:
        return trait_dict["orbital class"]

    # 4. Universal Class
    if "universal class" in trait_dict:
        return trait_dict["universal class"]

    # 5. Type/Treatment/Variant
    for key in ["type", "treatment", "variant", "edition", "rarity"]:
        if key in trait_dict:
            return trait_dict[key]

    # 6. Fallback: first non-artist, non-legendary trait
    for trait in traits:
        trait_type = (trait.get("trait_type") or "").lower()
        trait_value = trait.get("value") or ""
        if trait_type not in ["artist", "legendary"] and trait_value.lower() not in ["yes", "no"]:
            return trait_value

    return None


async def fetch_opensea_nft_traits(
    contract_address: str, token_id: str, chain: str = "ethereum"
) -> Optional[List[Dict[str, str]]]:
    """
    Fetch NFT traits from OpenSea by scraping the NFT page.
    OpenSea embeds NFT data in URQL script tags.
    """
    url = f"https://opensea.io/assets/{chain}/{contract_address}/{token_id}"

    try:
        html = await get_page_content(url)
        soup = BeautifulSoup(html, "lxml")
        scripts = soup.find_all("script")

        for script in scripts:
            if not script.string:
                continue
            content = script.string

            # Look for URQL data with trait info
            if "traitType" not in content and "trait_type" not in content:
                continue

            # Extract JSON from push patterns
            matches = re.findall(r"\.push\((\{.*?\})\)", content, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    rehydrate = data.get("rehydrate", {})

                    for key, value in rehydrate.items():
                        item = value.get("data", {}).get("itemByIdentifier", {})
                        if not item:
                            continue

                        attributes = item.get("attributes", [])
                        if attributes:
                            # Convert OpenSea format to standard format
                            traits = []
                            for attr in attributes:
                                traits.append({"trait_type": attr.get("traitType", ""), "value": attr.get("value", "")})
                            return traits
                except json.JSONDecodeError:
                    continue

        return None
    except Exception as e:
        print(f"  [OpenSea] Error scraping traits: {e}")
        return None


def get_blokpax_traits(session: Session, asset_id: str) -> Optional[List[Dict[str, str]]]:
    """
    Look up traits from BlokpaxAssetDB for a given asset ID.
    """
    asset = session.exec(select(BlokpaxAssetDB).where(BlokpaxAssetDB.external_id == asset_id)).first()

    if asset and asset.traits:
        return asset.traits
    return None


def parse_opensea_url(url: str) -> Optional[Dict[str, str]]:
    """
    Parse OpenSea URL to extract chain, contract, and token_id.
    Format: https://opensea.io/item/{chain}/{contract_or_slug}/{token_id}
           or https://opensea.io/assets/{chain}/{contract_or_slug}/{token_id}
    """
    if not url or "opensea.io" not in url:
        return None

    import re

    match = re.search(r"opensea\.io/(?:item|assets)/([^/]+)/([^/]+)/(\d+)", url)
    if match:
        chain = match.group(1)
        contract_or_slug = match.group(2)
        token_id = match.group(3)

        # If it's a slug (not starting with 0x), look up the actual contract
        if not contract_or_slug.startswith("0x"):
            contract = OPENSEA_CONTRACTS.get(contract_or_slug)
            if not contract:
                print(f"  [OpenSea] Unknown collection slug: {contract_or_slug}")
                return None
        else:
            contract = contract_or_slug

        return {"chain": chain, "contract": contract, "token_id": token_id}
    return None


async def backfill_nft_traits(execute: bool = False, limit: int = None):
    """
    Main backfill function.
    """
    print("=" * 60)
    print("NFT TRAITS BACKFILL")
    print("=" * 60)
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN (use --execute to apply)'}")
    print()

    updated_count = 0
    skipped_count = 0
    error_count = 0

    with Session(engine) as session:
        # Find all MarketPrice records from OpenSea/Blokpax that need traits populated
        # Records where traits field is NULL
        query = select(MarketPrice).where(
            MarketPrice.platform.in_(["opensea", "blokpax"]), MarketPrice.traits.is_(None)
        )
        if limit:
            query = query.limit(limit)

        records = session.exec(query).all()
        print(f"Found {len(records)} NFT records to process")
        print()

        for i, record in enumerate(records):
            print(f"[{i+1}/{len(records)}] Processing MarketPrice ID {record.id}...")
            print(f"  Platform: {record.platform}")
            print(f"  Title: {record.title[:50]}..." if len(record.title) > 50 else f"  Title: {record.title}")
            print(f"  Current treatment: {record.treatment}")

            new_treatment = None
            traits = None

            # Try to get traits based on platform
            if record.platform == "blokpax":
                # For Blokpax, we need to find the asset by matching the sale
                # The external_id might be a tx hash or listing ID
                # Let's try to find via BlokpaxSale -> asset_id -> BlokpaxAssetDB

                blokpax_sale = session.exec(
                    select(BlokpaxSale).where(BlokpaxSale.listing_id == record.external_id)
                ).first()

                if blokpax_sale:
                    traits = get_blokpax_traits(session, blokpax_sale.asset_id)
                    if traits:
                        new_treatment = extract_treatment_from_traits(traits)
                        print(f"  Found Blokpax traits: {traits[:2]}...")
                else:
                    print(f"  No BlokpaxSale found for external_id: {record.external_id}")

            elif record.platform == "opensea":
                # For OpenSea, parse the URL to get contract/token_id
                parsed = parse_opensea_url(record.url)
                if parsed:
                    print(f"  Fetching OpenSea traits for {parsed['contract'][:10]}.../{parsed['token_id']}")
                    traits = await fetch_opensea_nft_traits(parsed["contract"], parsed["token_id"], parsed["chain"])
                    if traits:
                        new_treatment = extract_treatment_from_traits(traits)
                        print(f"  Found OpenSea traits: {traits[:2]}...")
                    await asyncio.sleep(0.5)  # Rate limiting
                else:
                    print(f"  Could not parse OpenSea URL: {record.url}")

            # Update if we found traits
            if traits:
                new_treatment = extract_treatment_from_traits(traits)
                print(f"  -> Treatment: {new_treatment}")
                print(f"  -> Traits: {len(traits)} attributes")
                if execute:
                    record.treatment = new_treatment or record.treatment
                    record.traits = traits  # Store ALL traits in the new JSON field
                    session.add(record)
                    session.commit()  # Commit after each record to avoid timeout
                    print("  [Saved]")
                updated_count += 1
            else:
                print("  -> No traits found, keeping as-is")
                skipped_count += 1

            print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total processed: {len(records)}")
    print(f"Updated: {updated_count}")
    print(f"Skipped (no traits): {skipped_count}")
    print(f"Errors: {error_count}")

    if not execute:
        print()
        print("This was a DRY RUN. Use --execute to apply changes.")


async def main():
    parser = argparse.ArgumentParser(description="Backfill NFT traits for MarketPrice records")
    parser.add_argument("--execute", action="store_true", help="Actually update records (default is dry run)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of records to process")
    args = parser.parse_args()

    await backfill_nft_traits(execute=args.execute, limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
