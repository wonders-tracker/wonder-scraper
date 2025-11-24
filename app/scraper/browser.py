from playwright.async_api import async_playwright, Browser, BrowserContext
from typing import Optional
import asyncio
import os


class BrowserManager:
    _playwright = None
    _browser: Optional[Browser] = None
    _context: Optional[BrowserContext] = None
    _restart_count: int = 0
    _max_restarts: int = 3

    @classmethod
    async def get_browser(cls) -> Browser:
        if not cls._browser:
            print("Starting Playwright browser...")

            cls._playwright = await async_playwright().start()

            # Launch args optimized for containers
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--single-process",
                "--no-zygote",
            ]

            cls._browser = await cls._playwright.chromium.launch(
                headless=True,
                args=launch_args,
            )

            # Create a context with stealth settings
            cls._context = await cls._browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
            )

            print("Playwright browser started successfully!")
        return cls._browser

    @classmethod
    async def get_context(cls) -> BrowserContext:
        if not cls._context:
            await cls.get_browser()
        return cls._context

    @classmethod
    async def close(cls):
        if cls._context:
            try:
                await cls._context.close()
            except Exception as e:
                print(f"Error closing context: {e}")
            cls._context = None

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
    Uses Playwright for reliable browser automation.
    """
    last_error = None

    for attempt in range(retries + 1):
        try:
            context = await BrowserManager.get_context()
            page = await context.new_page()

            try:
                # Navigate with timeout
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait for content to load
                await page.wait_for_timeout(2000)

                content = await page.content()

                if not content or len(content) < 100:
                    raise Exception("Empty or invalid page content received")

                return content

            finally:
                await page.close()

        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            print(f"Error in get_page_content (attempt {attempt + 1}/{retries + 1}):")
            print(f"  Type: {type(e).__name__}")
            print(f"  Message: {e}")

            # If it's a connection/timeout error, restart browser
            if any(keyword in error_msg for keyword in ["timeout", "connection", "target closed", "browser", "context"]):
                print("Detected browser issue. Restarting browser...")
                await BrowserManager.restart()
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(1)

            if attempt == retries:
                print(f"Failed after {retries + 1} attempts: {last_error}")
                raise last_error

    raise last_error
