"""
Scraper for OpenSea collections using Pydoll and the OpenSea API.
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from app.scraper.browser import get_page_content
from bs4 import BeautifulSoup
import re
import os
from app.services.crypto import get_eth_price

# OpenSea API Configuration
OPENSEA_API_KEY = os.environ.get("OPENSEA_API_KEY", "")
OPENSEA_API_BASE = "https://api.opensea.io/api/v2"


@dataclass
class OpenSeaSale:
    """Represents a single OpenSea sale event."""

    token_id: str
    token_name: str
    price_eth: float
    price_usd: float
    seller: str
    buyer: str
    sold_at: datetime
    tx_hash: str
    image_url: Optional[str] = None
    traits: Optional[List[str]] = None  # NFT traits (e.g., ["Rare", "Fire", "Level 5"])


async def scrape_opensea_collection(collection_url: str) -> Dict[str, Any]:
    """
    Scrapes an OpenSea collection page for stats (Floor Price, Volume, etc).
    """
    print(f"Scraping OpenSea Collection: {collection_url}")

    # Fetch ETH price for conversion
    eth_price_usd = 0.0
    try:
        eth_price_usd = await get_eth_price()
        print(f"Current ETH Price: ${eth_price_usd:.2f}")
    except Exception as e:
        print(f"Failed to fetch ETH price: {e}")

    try:
        html = await get_page_content(collection_url)

        # Wait additional time for dynamic content (volume loads via JS)
        await asyncio.sleep(5)

        soup = BeautifulSoup(html, "lxml")

        stats = {
            "floor_price_eth": 0.0,
            "floor_price_usd": 0.0,
            "total_volume_eth": 0.0,
            "total_volume_usd": 0.0,
            "owners": 0,
            "listed_count": 0,
            "currency": "ETH",
        }

        # --- Strategy 1: Title Extraction (Fast & Reliable for Floor) ---
        # Title format: "Collection Name 0.099 ETH - Collection | OpenSea"
        title_text = soup.title.string if soup.title else ""
        if title_text:
            floor_match = re.search(r"([\d\.]+)\s*(ETH|WETH)\s*-\s*Collection", title_text, re.IGNORECASE)
            if floor_match:
                val = float(floor_match.group(1))
                stats["floor_price_eth"] = val
                stats["floor_price_usd"] = val * eth_price_usd
                stats["currency"] = floor_match.group(2)
                print(f"Strategy 1 (Title) found Floor: {val} {stats['currency']}")

        # --- Strategy 2: CSS Classes (Tailwind Utility Classes) ---
        # Look for 'span.font-mono' which usually holds the numbers
        mono_spans = soup.select("span.font-mono")
        for span in mono_spans:
            text = span.get_text(strip=True)
            if not text:
                continue

            clean_text = text.replace(",", "")
            try:
                val = float(clean_text)
            except ValueError:
                continue

            # Context check (Parent Div)
            container = span.find_parent("div")
            if container:
                container_text = container.get_text(" ", strip=True).lower()

                if "floor" in container_text and stats["floor_price_eth"] == 0.0:
                    stats["floor_price_eth"] = val
                    stats["floor_price_usd"] = val * eth_price_usd
                    print(f"Strategy 2 (CSS) found Floor: {val}")
                elif "total volume" in container_text and stats["total_volume_eth"] == 0.0:
                    stats["total_volume_eth"] = val
                    stats["total_volume_usd"] = val * eth_price_usd
                    print(f"Strategy 2 (CSS) found Volume: {val}")
                elif "owners" in container_text and stats["owners"] == 0:
                    stats["owners"] = int(val)
                    print(f"Strategy 2 (CSS) found Owners: {val}")
                elif ("items" in container_text or "listed" in container_text) and stats["listed_count"] == 0:
                    stats["listed_count"] = int(val)
                    print(f"Strategy 2 (CSS) found Listed: {val}")

        # --- Strategy 3: URQL/GraphQL JSON Data (for Volume, Owners) ---
        # OpenSea embeds collection stats in script tags via URQL GraphQL client
        import json

        scripts = soup.find_all("script")
        for script in scripts:
            if script.string and "urql_transport" in script.string and "collectionBySlug" in script.string:
                try:
                    # Extract JSON from: (window[Symbol.for("urql_transport")] ??= []).push({...})
                    json_match = re.search(r"\.push\((\{.*?\})\)", script.string, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(1))
                        # Navigate to collectionBySlug data
                        rehydrate = data.get("rehydrate", {})
                        for key, value in rehydrate.items():
                            collection_data = value.get("data", {}).get("collectionBySlug", {})
                            if collection_data:
                                # Extract stats object
                                collection_stats = collection_data.get("stats", {})
                                if collection_stats:
                                    # Extract ownerCount
                                    owner_count = collection_stats.get("ownerCount", 0)
                                    if owner_count and stats["owners"] == 0:
                                        stats["owners"] = int(owner_count)
                                        print(f"Strategy 3 (URQL JSON) found Owners: {owner_count}")

                                    # Extract volume.native.unit (total volume in ETH)
                                    volume_data = collection_stats.get("volume", {})
                                    if volume_data:
                                        native_volume = volume_data.get("native", {})
                                        volume_unit = native_volume.get("unit", 0)
                                        if volume_unit and stats["total_volume_eth"] == 0.0:
                                            stats["total_volume_eth"] = float(volume_unit)
                                            stats["total_volume_usd"] = float(volume_unit) * eth_price_usd
                                            print(f"Strategy 3 (URQL JSON) found Volume: {volume_unit} ETH")

                                if stats["total_volume_eth"] > 0 and stats["owners"] > 0:
                                    break
                except Exception as e:
                    print(f"Strategy 3 JSON parse error: {e}")
                    continue

        # --- Strategy 4: Text Label Fallback ---
        if stats["floor_price_eth"] == 0.0 or stats["total_volume_eth"] == 0.0:
            text_content = soup.get_text(" ", strip=True)

            if stats["floor_price_eth"] == 0.0:
                floor_match = re.search(r"Floor price\s*([\d\.]+)", text_content, re.IGNORECASE)
                if floor_match:
                    val = float(floor_match.group(1))
                    stats["floor_price_eth"] = val
                    stats["floor_price_usd"] = val * eth_price_usd
                    print(f"Strategy 4 (Text) found Floor: {val}")

            if stats["total_volume_eth"] == 0.0:
                vol_match = re.search(r"Total volume\s*([\d\.,]+)", text_content, re.IGNORECASE)
                if vol_match:
                    val = float(vol_match.group(1).replace(",", ""))
                    stats["total_volume_eth"] = val
                    stats["total_volume_usd"] = val * eth_price_usd
                    print(f"Strategy 4 (Text) found Volume: {val}")

        # Normalize keys for output compatibility if needed (though DB expects specific fields)
        # Mapping to flat structure for caller
        final_stats = {
            "floor_price": stats["floor_price_eth"],  # For DB logic that expects 'floor_price'
            "floor_price_usd": stats["floor_price_usd"],
            "total_volume": stats["total_volume_eth"],  # Raw volume
            "total_volume_usd": stats["total_volume_usd"],
            "owners": stats["owners"],
            "listed_count": stats["listed_count"],
            "currency": stats["currency"],
        }

        print(f"Final Stats: {final_stats}")
        return final_stats

    except Exception as e:
        print(f"Error scraping OpenSea: {e}")
        return {}


async def scrape_opensea_sales(collection_slug: str, limit: int = 50, event_type: str = "sale") -> List[OpenSeaSale]:
    """
    Scrape sales history from OpenSea using their public API.

    Args:
        collection_slug: The OpenSea collection slug (e.g., 'wotf-character-proofs')
        limit: Maximum number of sales to fetch (max 50 per request)
        event_type: Event type to filter ('sale' for completed sales)

    Returns:
        List of OpenSeaSale objects
    """
    print(f"[OpenSea] Fetching sales for collection: {collection_slug}")

    # Get ETH price for USD conversion
    eth_price_usd = 0.0
    try:
        eth_price_usd = await get_eth_price()
        print(f"[OpenSea] ETH Price: ${eth_price_usd:.2f}")
    except Exception as e:
        print(f"[OpenSea] Failed to fetch ETH price: {e}")
        eth_price_usd = 3500.0  # Fallback estimate

    sales: List[OpenSeaSale] = []

    # OpenSea API v2 endpoint for collection events
    url = f"{OPENSEA_API_BASE}/events/collection/{collection_slug}"

    headers = {"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; WonderScraper/1.0)"}

    # Add API key if available
    if OPENSEA_API_KEY:
        headers["X-API-KEY"] = OPENSEA_API_KEY

    params = {
        "event_type": event_type,
        "limit": min(limit, 50),  # API max is 50
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 401:
                    print("[OpenSea] API key required or invalid. Falling back to web scraping.")
                    return await _scrape_opensea_sales_web(collection_slug, eth_price_usd, limit)

                if response.status == 429:
                    print("[OpenSea] Rate limited. Try again later.")
                    return []

                if response.status != 200:
                    print(f"[OpenSea] API error: {response.status}")
                    # Try web scraping fallback
                    return await _scrape_opensea_sales_web(collection_slug, eth_price_usd, limit)

                data = await response.json()
                events = data.get("asset_events", [])

                print(f"[OpenSea] Found {len(events)} sale events")

                for event in events:
                    try:
                        # Extract payment info
                        payment = event.get("payment", {})
                        quantity_raw = payment.get("quantity", "0")
                        decimals = int(payment.get("decimals", 18))
                        price_eth = int(quantity_raw) / (10**decimals)
                        price_usd = price_eth * eth_price_usd

                        # Extract NFT info
                        nft = event.get("nft", {})
                        token_id = nft.get("identifier", "")
                        token_name = nft.get("name", f"#{token_id}")
                        image_url = nft.get("image_url")

                        # Extract traits from NFT metadata
                        # OpenSea events API may include traits in the 'nft' object
                        traits = []
                        nft_traits = nft.get("traits", [])
                        for trait in nft_traits:
                            trait_type = trait.get("trait_type", "")
                            trait_value = trait.get("value", "")
                            # Prioritize treatment-related traits
                            if trait_type and trait_type.lower() in [
                                "treatment",
                                "type",
                                "variant",
                                "edition",
                                "rarity",
                            ]:
                                traits.insert(0, f"{trait_value}")  # Put treatment traits first
                            elif trait_value:
                                traits.append(f"{trait_value}")

                        # If no traits from event, try to extract from token name
                        if not traits and token_name:
                            name_lower = token_name.lower()
                            if "foil" in name_lower:
                                traits.append("Foil")
                            elif "serial" in name_lower or "/50" in name_lower or "/100" in name_lower:
                                traits.append("Serialized")
                            elif "proof" in name_lower:
                                traits.append("Proof")

                        # Extract transaction info
                        tx = event.get("transaction", {})
                        tx_hash = tx.get("hash", "")

                        # Extract timestamp
                        event_timestamp = event.get("event_timestamp", "")
                        sold_at = (
                            datetime.fromisoformat(event_timestamp.replace("Z", "+00:00"))
                            if event_timestamp
                            else datetime.utcnow()
                        )

                        # Extract seller/buyer
                        seller = event.get("seller", "")
                        buyer = event.get("buyer", "")

                        sale = OpenSeaSale(
                            token_id=token_id,
                            token_name=token_name,
                            price_eth=price_eth,
                            price_usd=price_usd,
                            seller=seller,
                            buyer=buyer,
                            sold_at=sold_at,
                            tx_hash=tx_hash,
                            image_url=image_url,
                            traits=traits if traits else None,
                        )
                        sales.append(sale)

                    except Exception as e:
                        print(f"[OpenSea] Error parsing event: {e}")
                        continue

    except aiohttp.ClientError as e:
        print(f"[OpenSea] Network error: {e}")
        return await _scrape_opensea_sales_web(collection_slug, eth_price_usd, limit)
    except Exception as e:
        print(f"[OpenSea] Error fetching sales: {e}")
        return []

    print(f"[OpenSea] Parsed {len(sales)} sales")
    return sales


async def _scrape_opensea_sales_web(collection_slug: str, eth_price_usd: float, limit: int = 50) -> List[OpenSeaSale]:
    """
    Fallback: Scrape sales from OpenSea activity page by parsing embedded URQL JSON data.
    OpenSea embeds GraphQL response data in script tags that we can extract.
    """
    print(f"[OpenSea] Web scraping activity page for {collection_slug}")

    activity_url = f"https://opensea.io/collection/{collection_slug}/activity?eventTypes=SUCCESSFUL"

    sales: List[OpenSeaSale] = []

    try:
        html = await get_page_content(activity_url)
        await asyncio.sleep(3)  # Wait for JS to load

        soup = BeautifulSoup(html, "lxml")
        import json

        # Find script tags with embedded URQL/GraphQL data
        scripts = soup.find_all("script")

        for script in scripts:
            if not script.string:
                continue

            content = script.string

            # Look for collectionActivity data in URQL transport
            if "collectionActivity" not in content:
                continue

            # Extract JSON from: (window[Symbol.for("urql_transport")] ??= []).push({...})
            json_matches = re.findall(r"\.push\((\{.*?\})\)", content, re.DOTALL)

            for match in json_matches:
                try:
                    data = json.loads(match)
                    rehydrate = data.get("rehydrate", {})

                    for key, value in rehydrate.items():
                        activity = value.get("data", {}).get("collectionActivity", {})
                        if not activity:
                            continue

                        items = activity.get("items", [])
                        print(f"[OpenSea] Found {len(items)} activity items in embedded data")

                        for item in items[:limit]:
                            try:
                                # Only process sales
                                if item.get("__typename") != "Sale":
                                    continue

                                # Extract timestamp
                                event_time = item.get("eventTime", "")
                                try:
                                    sold_at = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                                except (ValueError, TypeError, AttributeError):
                                    sold_at = datetime.utcnow()

                                # Extract transaction hash
                                tx_hash = item.get("transactionHash", "")

                                # Extract NFT info
                                nft = item.get("item", {})
                                token_id = nft.get("tokenId", "")
                                token_name = nft.get("name", f"#{token_id}")
                                image_url = nft.get("imageUrl", "")

                                # Extract price (safely handle None/missing data)
                                price_data = item.get("price") or {}
                                token_price = price_data.get("token") or {}
                                price_eth = float(token_price.get("unit", 0) or 0)
                                price_usd = float(price_data.get("usd") or (price_eth * eth_price_usd))

                                # Extract seller/buyer if available
                                seller = item.get("seller", {})
                                buyer = item.get("buyer", {})
                                seller_addr = seller.get("address", "") if isinstance(seller, dict) else str(seller)
                                buyer_addr = buyer.get("address", "") if isinstance(buyer, dict) else str(buyer)

                                # Extract traits from NFT data if available
                                traits = []
                                nft_traits = nft.get("traits", [])
                                for trait in nft_traits:
                                    if isinstance(trait, dict):
                                        trait_type = trait.get("trait_type", "").lower()
                                        trait_value = trait.get("value", "")
                                        # Prioritize treatment-related traits
                                        if trait_type in ["treatment", "type", "variant", "edition", "rarity"]:
                                            traits.insert(0, str(trait_value))
                                        elif trait_value:
                                            traits.append(str(trait_value))
                                    elif trait:
                                        traits.append(str(trait))

                                # If no traits from data, try to extract from token name
                                if not traits and token_name:
                                    name_lower = token_name.lower()
                                    if "foil" in name_lower:
                                        traits.append("Foil")
                                    elif "serial" in name_lower or "/50" in name_lower or "/100" in name_lower:
                                        traits.append("Serialized")
                                    elif "proof" in name_lower:
                                        traits.append("Proof")

                                sale = OpenSeaSale(
                                    token_id=token_id,
                                    token_name=token_name,
                                    price_eth=price_eth,
                                    price_usd=price_usd,
                                    seller=seller_addr,
                                    buyer=buyer_addr,
                                    sold_at=sold_at,
                                    tx_hash=tx_hash,
                                    image_url=image_url,
                                    traits=traits if traits else None,
                                )
                                sales.append(sale)

                            except Exception as e:
                                print(f"[OpenSea] Error parsing sale item: {e}")
                                continue

                        # If we found sales, we're done
                        if sales:
                            break

                except json.JSONDecodeError:
                    continue

            # If we found sales, stop searching
            if sales:
                break

    except Exception as e:
        print(f"[OpenSea] Web scraping error: {e}")

    print(f"[OpenSea] Web scraping found {len(sales)} sales")
    return sales
