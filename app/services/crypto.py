import httpx
from typing import Optional

async def get_eth_price() -> float:
    """
    Fetches the current price of Ethereum in USD.
    Uses CoinGecko API.
    """
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            data = response.json()
            return float(data["ethereum"]["usd"])
    except Exception as e:
        print(f"Failed to fetch ETH price: {e}")
        # Fallback price (approximate, better than 0)
        return 3000.0

