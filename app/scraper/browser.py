from playwright.async_api import async_playwright, Browser, BrowserContext
from typing import Optional
import asyncio
import os
import aiohttp


# Serialize browser operations - only 1 at a time for stability
_semaphore = asyncio.Semaphore(1)

# Remote browser server URL (set in Railway env)
# This should be the HTTP URL like http://playwright.railway.internal:3000
BROWSER_SERVER_URL = os.getenv("BROWSER_WS_URL", "")


class BrowserManager:
    _playwright = None
    _browser: Optional[Browser] = None
    _lock = asyncio.Lock()
    _restart_count: int = 0
    _max_restarts: int = 3

    @classmethod
    async def get_browser(cls) -> Browser:
        async with cls._lock:
            if not cls._browser or not cls._browser.is_connected():
                print("Starting Playwright browser...")

                if cls._playwright:
                    try:
                        await cls._playwright.stop()
                    except:
                        pass

                cls._playwright = await async_playwright().start()

                if BROWSER_SERVER_URL:
                    # Fetch the WebSocket endpoint from the browser server
                    http_url = BROWSER_SERVER_URL.replace("ws://", "http://").replace("wss://", "https://")
                    endpoint_url = f"{http_url}/ws-endpoint"
                    print(f"Fetching WebSocket endpoint from: {endpoint_url}")

                    async with aiohttp.ClientSession() as session:
                        async with session.get(endpoint_url) as resp:
                            data = await resp.json()
                            ws_path = data["wsPath"]
                            ws_port = data["wsPort"]

                    # Construct WebSocket URL with correct host (Railway internal)
                    # BROWSER_SERVER_URL is like ws://playwright.railway.internal:3000
                    base_host = BROWSER_SERVER_URL.split("://")[1].split(":")[0]
                    ws_endpoint = f"ws://{base_host}:{ws_port}{ws_path}"

                    print(f"Connecting to remote browser: {ws_endpoint}")
                    cls._browser = await cls._playwright.chromium.connect(ws_endpoint)
                else:
                    # Local browser launch (fallback for dev)
                    print("Launching local browser...")
                    launch_args = [
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--disable-extensions",
                        "--disable-background-networking",
                        "--disable-sync",
                        "--disable-translate",
                        "--no-first-run",
                        "--disable-default-apps",
                        "--mute-audio",
                        "--hide-scrollbars",
                    ]
                    cls._browser = await cls._playwright.chromium.launch(
                        headless=True,
                        args=launch_args,
                    )

                print("Playwright browser started successfully!")
            return cls._browser

    @classmethod
    async def new_context(cls) -> BrowserContext:
        """Create a new isolated context for each scrape"""
        browser = await cls.get_browser()
        return await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
        )

    @classmethod
    async def close(cls):
        async with cls._lock:
            if cls._browser:
                try:
                    await cls._browser.close()
                except Exception as e:
                    print(f"Error closing browser: {e}")
                cls._browser = None

            if cls._playwright:
                try:
                    await cls._playwright.stop()
                except Exception as e:
                    print(f"Error stopping playwright: {e}")
                cls._playwright = None

    @classmethod
    async def restart(cls):
        """Force restart of the browser instance"""
        cls._restart_count += 1

        if cls._restart_count > cls._max_restarts:
            print(f"Browser has been restarted {cls._restart_count} times. Applying extended cooldown...")
            await asyncio.sleep(10)
            cls._restart_count = 0

        print(f"Restarting browser instance (attempt {cls._restart_count})...")
        await cls.close()
        await asyncio.sleep(2)
        return await cls.get_browser()


async def get_page_content(url: str, retries: int = 3) -> str:
    """
    Navigates to a URL and returns the HTML content.
    Uses Playwright with isolated context per request for concurrency safety.
    Limited to 1 concurrent operation for stability.
    """
    last_error = None

    async with _semaphore:  # Serialize browser operations
        for attempt in range(retries + 1):
            context = None
            page = None
            try:
                # Create isolated context for this request
                context = await BrowserManager.new_context()
                page = await context.new_page()

                # Navigate with timeout
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait for content to load
                await page.wait_for_timeout(2000)

                content = await page.content()

                if not content or len(content) < 100:
                    raise Exception("Empty or invalid page content received")

                return content

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                print(f"Error in get_page_content (attempt {attempt + 1}/{retries + 1}):")
                print(f"  Type: {type(e).__name__}")
                print(f"  Message: {e}")

                # If it's a browser-level error, restart
                if any(keyword in error_msg for keyword in ["browser has been closed", "browser.newcontext", "target crashed", "connection closed"]):
                    print("Detected browser crash. Restarting browser...")
                    await BrowserManager.restart()
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(1)

                if attempt == retries:
                    print(f"Failed after {retries + 1} attempts: {last_error}")
                    raise last_error

            finally:
                # Always clean up context
                if page:
                    try:
                        await page.close()
                    except:
                        pass
                if context:
                    try:
                        await context.close()
                    except:
                        pass

    raise last_error
