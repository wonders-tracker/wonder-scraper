"""
Simple HTTP-based scraper as fallback when browser automation fails.
Uses httpx with proper headers to mimic a real browser.
"""

import httpx
import asyncio
import random

# Rotate through multiple user agents
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


async def get_page_simple(url: str, retries: int = 3) -> str:
    """
    Fetches a page using simple HTTP requests with proper headers.
    More reliable than browser automation for basic scraping.
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    last_error = None

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
                # Add random delay to mimic human behavior
                await asyncio.sleep(random.uniform(0.5, 1.5))

                response = await client.get(url)
                response.raise_for_status()

                content = response.text

                if not content or len(content) < 100:
                    raise Exception("Empty or invalid page content")

                return content

        except Exception as e:
            last_error = e
            print(f"HTTP request attempt {attempt + 1} failed: {e}")

            if attempt < retries - 1:
                # Exponential backoff
                wait_time = (2**attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait_time)

    raise Exception(f"Failed to fetch {url} after {retries} attempts: {last_error}")
