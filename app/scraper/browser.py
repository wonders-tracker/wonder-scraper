# Use pydoll for undetected browser automation
from pydoll.browser.chromium.chrome import Chrome
from pydoll.browser.options import ChromiumOptions
from typing import Optional
import asyncio
import os
import random
import shutil
import tempfile


# Serialize browser operations - only 1 at a time for stability
_semaphore = asyncio.Semaphore(1)

# Remote browser server URL (set in Railway env)
BROWSER_SERVER_URL = os.getenv("BROWSER_WS_URL", "")


def find_chrome_binary() -> Optional[str]:
    """Find Chrome/Chromium binary on the system."""
    # Check env var first
    chrome_path = os.getenv("CHROME_PATH")
    if chrome_path and os.path.exists(chrome_path):
        return chrome_path

    # Common Chrome/Chromium paths
    common_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path

    # Try which command
    for cmd in ["chromium", "chromium-browser", "google-chrome"]:
        found = shutil.which(cmd)
        if found:
            return found

    return None


def get_user_data_dir():
    """Get unique profile directory for this process"""
    return os.path.join(tempfile.gettempdir(), f"pydoll_profile_{os.getpid()}")


class BrowserManager:
    _browser: Optional[Chrome] = None
    _lock = asyncio.Lock()
    _restart_count: int = 0
    _max_restarts: int = 3

    @classmethod
    async def get_browser(cls) -> Chrome:
        async with cls._lock:
            if not cls._browser:
                print("Starting pydoll browser...")

                options = ChromiumOptions()
                options.headless = True

                # Use system Chrome if available (for production containers)
                chrome_path = find_chrome_binary()
                if chrome_path:
                    print(f"Using Chrome: {chrome_path}")
                    options.binary_location = chrome_path

                # Anti-detection args
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")  # Required for headless in containers

                # Use unique profile per process
                profile_dir = get_user_data_dir()
                print(f"Using profile: {profile_dir}")
                options.add_argument(f"--user-data-dir={profile_dir}")

                cls._browser = Chrome(options=options)
                try:
                    await cls._browser.start()
                    print("Pydoll browser started successfully!")
                except Exception as start_err:
                    print(f"Browser start failed: {type(start_err).__name__}: {start_err}")
                    raise

            return cls._browser

    @classmethod
    async def close(cls):
        async with cls._lock:
            if cls._browser:
                try:
                    await cls._browser.stop()
                except Exception as e:
                    print(f"Error closing browser: {e}")
                cls._browser = None

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
    Uses pydoll for undetected browsing.
    """
    last_error = None

    async with _semaphore:  # Serialize browser operations
        for attempt in range(retries + 1):
            tab = None
            try:
                browser = await BrowserManager.get_browser()
                tab = await browser.new_tab()

                # Random delay before navigation (human-like)
                await asyncio.sleep(random.uniform(1, 3))

                # Navigate
                await tab.go_to(url)

                # Random wait for content to load (human-like)
                await asyncio.sleep(random.uniform(2, 4))

                # Get page content
                content = await tab.page_source

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
                if any(keyword in error_msg for keyword in ["browser", "closed", "crashed", "connection"]):
                    print("Detected browser issue. Restarting browser...")
                    await BrowserManager.restart()
                    await asyncio.sleep(2)
                else:
                    await asyncio.sleep(1)

                if attempt == retries:
                    print(f"Failed after {retries + 1} attempts: {last_error}")
                    raise last_error

            finally:
                if tab:
                    try:
                        await tab.close()
                    except Exception:
                        pass

    raise last_error
