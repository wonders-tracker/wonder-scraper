# Use pydoll for undetected browser automation
from pydoll.browser.chromium.chrome import Chrome
from pydoll.browser.options import ChromiumOptions
from typing import Optional
import asyncio
import os
import random
import shutil
import tempfile
import subprocess


# Serialize browser operations - only 1 at a time for stability
_semaphore = asyncio.Semaphore(1)

# Flag to track if we're in a container environment
IS_CONTAINER = os.path.exists("/.dockerenv") or os.getenv("RAILWAY_ENVIRONMENT") is not None


def find_chrome_binary() -> Optional[str]:
    """Find Chrome/Chromium binary on the system with extensive search."""
    # Check env var first (set by nixpacks.toml)
    chrome_path = os.getenv("CHROME_PATH")
    if chrome_path and os.path.exists(chrome_path):
        print(f"[Browser] Found Chrome via CHROME_PATH env: {chrome_path}")
        return chrome_path

    # Nixpacks-specific paths (Railway uses nixpacks)
    nixpacks_paths = [
        "/nix/var/nix/profiles/default/bin/chromium",
        "/nix/store/*/bin/chromium",  # Will use glob below
        "/root/.nix-profile/bin/chromium",
    ]

    # Common Chrome/Chromium paths for various Linux distros
    # Priority order: Google Chrome first (from Dockerfile), then Chromium
    common_paths = [
        "/usr/bin/google-chrome-stable",  # Dockerfile installs here
        "/usr/bin/google-chrome",
        "/opt/google/chrome/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
    ]

    # Try nixpacks paths first (for Railway)
    for path in nixpacks_paths:
        if "*" in path:
            # Use glob for wildcard paths
            import glob

            matches = glob.glob(path)
            if matches:
                print(f"[Browser] Found Chrome via glob: {matches[0]}")
                return matches[0]
        elif os.path.exists(path):
            print(f"[Browser] Found Chrome at: {path}")
            return path

    # Try common paths
    for path in common_paths:
        if os.path.exists(path):
            print(f"[Browser] Found Chrome at: {path}")
            return path

    # Try which command
    for cmd in ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"]:
        found = shutil.which(cmd)
        if found:
            print(f"[Browser] Found Chrome via which: {found}")
            return found

    # Last resort: search in PATH and nix store
    try:
        result = subprocess.run(
            ["find", "/nix/store", "-name", "chromium", "-type", "f", "-executable"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip().split("\n")[0]
            print(f"[Browser] Found Chrome via find: {path}")
            return path
    except Exception as e:
        print(f"[Browser] find command failed: {e}")

    print("[Browser] WARNING: No Chrome binary found!")
    return None


def get_user_data_dir():
    """Get unique profile directory for this process"""
    return os.path.join(tempfile.gettempdir(), f"pydoll_profile_{os.getpid()}")


class BrowserManager:
    _browser: Optional[Chrome] = None
    _lock = asyncio.Lock()
    _restart_count: int = 0
    _max_restarts: int = 3
    _startup_timeout: int = 60  # seconds to wait for browser startup

    @classmethod
    async def get_browser(cls) -> Chrome:
        async with cls._lock:
            if not cls._browser:
                print("[Browser] Starting pydoll browser...")
                print(f"[Browser] Container environment: {IS_CONTAINER}")

                options = ChromiumOptions()
                options.headless = True

                # Use system Chrome if available (for production containers)
                chrome_path = find_chrome_binary()
                if chrome_path:
                    print(f"[Browser] Using Chrome: {chrome_path}")
                    options.binary_location = chrome_path
                else:
                    print("[Browser] ERROR: No Chrome binary found. Browser will likely fail.")

                # Essential args for headless Chrome in containers
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-software-rasterizer")

                # Anti-detection args
                options.add_argument("--disable-blink-features=AutomationControlled")

                # Memory optimization for containers
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-plugins")

                # Additional container-specific settings
                if IS_CONTAINER:
                    print("[Browser] Applying container-specific settings...")
                    options.add_argument("--disable-setuid-sandbox")
                    options.add_argument("--disable-background-networking")
                    options.add_argument("--disable-default-apps")
                    options.add_argument("--disable-sync")
                    options.add_argument("--disable-translate")
                    options.add_argument("--metrics-recording-only")
                    options.add_argument("--mute-audio")
                    # Note: --no-first-run is added automatically by pydoll
                    options.add_argument("--safebrowsing-disable-auto-update")
                    # Reduce process count
                    options.add_argument("--renderer-process-limit=1")
                    options.add_argument("--disable-features=TranslateUI")

                # Use unique profile per process
                profile_dir = get_user_data_dir()
                print(f"[Browser] Using profile: {profile_dir}")
                options.add_argument(f"--user-data-dir={profile_dir}")

                # Create browser instance
                cls._browser = Chrome(options=options)

                # Start with timeout
                try:
                    print(f"[Browser] Starting browser with {cls._startup_timeout}s timeout...")
                    await asyncio.wait_for(cls._browser.start(), timeout=cls._startup_timeout)
                    print("[Browser] Pydoll browser started successfully!")
                except asyncio.TimeoutError:
                    print(f"[Browser] ERROR: Browser startup timed out after {cls._startup_timeout}s")
                    cls._browser = None
                    raise Exception(f"Browser startup timed out after {cls._startup_timeout}s")
                except Exception as start_err:
                    print(f"[Browser] ERROR: Browser start failed: {type(start_err).__name__}: {start_err}")
                    cls._browser = None
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
        # Check if we've hit the restart limit BEFORE incrementing
        if cls._restart_count >= cls._max_restarts:
            print(f"Browser restarted {cls._restart_count} times. Applying extended cooldown...")
            await asyncio.sleep(10)
            cls._restart_count = 0

        cls._restart_count += 1
        print(f"Restarting browser instance (attempt {cls._restart_count}/{cls._max_restarts})...")
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

    # Should never reach here (loop raises on final attempt), but handle edge case
    if last_error:
        raise last_error
    raise Exception(f"Failed to get page content for {url} after {retries + 1} attempts")
