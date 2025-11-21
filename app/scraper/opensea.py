"""
Scraper for OpenSea collections using Pydoll.
"""
import asyncio
from typing import Dict, Any, Optional
from app.scraper.browser import get_page_content
from bs4 import BeautifulSoup
import re
from app.services.crypto import get_eth_price

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
            "currency": "ETH" 
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
            if not text: continue
            
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
                    json_match = re.search(r'\.push\((\{.*?\})\)', script.string, re.DOTALL)
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
            "floor_price": stats["floor_price_eth"], # For DB logic that expects 'floor_price'
            "floor_price_usd": stats["floor_price_usd"],
            "total_volume": stats["total_volume_eth"], # Raw volume
            "total_volume_usd": stats["total_volume_usd"],
            "owners": stats["owners"],
            "listed_count": stats["listed_count"],
            "currency": stats["currency"]
        }
        
        print(f"Final Stats: {final_stats}")
        return final_stats
        
    except Exception as e:
        print(f"Error scraping OpenSea: {e}")
        return {}
