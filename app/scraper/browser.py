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
import uuid

from app.core.config import settings


# Control concurrent browser tab operations
# Configured via BROWSER_SEMAPHORE_LIMIT (default 4 tabs for speed vs memory balance)
_semaphore = asyncio.Semaphore(settings.BROWSER_SEMAPHORE_LIMIT)

# Flag to track if we're in a container environment
IS_CONTAINER = os.path.exists("/.dockerenv") or os.getenv("RAILWAY_ENVIRONMENT") is not None

# Unique session ID for this process (avoids PID=1 collision in containers)
_SESSION_ID = uuid.uuid4().hex[:8]


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
            timeout=settings.BROWSER_CHROME_SEARCH_TIMEOUT,
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
    """Get unique profile directory for this process session."""
    # Use session ID instead of PID - in containers PID is often 1
    # which causes all instances to collide on the same profile
    return os.path.join(tempfile.gettempdir(), f"pydoll_profile_{_SESSION_ID}")


def kill_stale_chrome_processes():
    """Kill any stale Chrome processes that might be blocking resources."""
    try:
        # Find and kill any orphaned chrome processes
        # On macOS, use pkill with pattern matching for headless Chrome
        result = subprocess.run(
            ["pkill", "-9", "-f", "chrome.*--headless"],
            capture_output=True,
            timeout=settings.BROWSER_PKILL_TIMEOUT,
        )
        if result.returncode == 0:
            print("[Browser] Killed stale Chrome processes")
    except subprocess.TimeoutExpired:
        print(f"[Browser] WARNING: pkill timed out after {settings.BROWSER_PKILL_TIMEOUT}s")
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        # pkill might not exist or no processes to kill - that's fine
        pass


def force_kill_all_chrome():
    """Aggressively kill ALL Chrome/Chromium processes - nuclear option."""
    print("[Browser] FORCE KILLING all Chrome processes...")
    kill_commands = [
        ["pkill", "-9", "-f", "chrome"],
        ["pkill", "-9", "-f", "chromium"],
        ["killall", "-9", "chrome"],
        ["killall", "-9", "chromium"],
        ["killall", "-9", "Google Chrome"],
    ]
    for cmd in kill_commands:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass
    # Give OS time to clean up
    import time

    time.sleep(2)
    print("[Browser] Force kill complete")


def cleanup_stale_profiles():
    """Clean up old profile directories from previous sessions."""

    try:
        tmp_dir = tempfile.gettempdir()
        current_profile = f"pydoll_profile_{_SESSION_ID}"

        for item in os.listdir(tmp_dir):
            if item.startswith("pydoll_profile_") and item != current_profile:
                path = os.path.join(tmp_dir, item)
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                        print(f"[Browser] Cleaned up stale profile: {item}")
                except (OSError, PermissionError):
                    # Directory cleanup can fail due to permissions or locks - safe to ignore
                    pass
    except (OSError, PermissionError):
        # Listing temp dir can fail in restricted environments - safe to ignore
        pass


class BrowserManager:
    _browser: Optional[Chrome] = None
    _lock = asyncio.Lock()
    _restart_count: int = 0
    _max_restarts: int = settings.BROWSER_MAX_RESTARTS
    _startup_timeout: int = settings.BROWSER_STARTUP_TIMEOUT
    _page_count: int = 0
    _max_pages_before_restart: int = settings.BROWSER_MAX_PAGES_BEFORE_RESTART
    _restarting: bool = False  # Flag to coordinate concurrent restart requests
    _last_restart_time: float = 0  # Timestamp of last restart
    _consecutive_timeouts: int = 0  # Track consecutive timeout errors
    _max_consecutive_timeouts: int = 3  # Force hard restart after this many

    @classmethod
    async def get_browser(cls) -> Chrome:
        async with cls._lock:
            if not cls._browser:
                await cls._start_browser_internal()
            assert cls._browser is not None  # Guaranteed by _start_browser_internal
            return cls._browser

    @classmethod
    async def _close_internal(cls):
        """Internal close - assumes lock is already held."""
        if cls._browser:
            try:
                await asyncio.wait_for(cls._browser.stop(), timeout=10)
            except asyncio.TimeoutError:
                print("[Browser] Stop timed out, forcing cleanup")
            except Exception as e:
                print(f"[Browser] Error closing browser: {e}")
            cls._browser = None
            # Ensure Chrome processes are cleaned up
            kill_stale_chrome_processes()

    @classmethod
    async def close(cls):
        async with cls._lock:
            await cls._close_internal()

    @classmethod
    async def restart(cls):
        """
        Force restart of the browser instance.
        Coordinates concurrent restart requests to prevent race conditions.
        """
        import time

        async with cls._lock:
            # Check if another task just restarted (within last 2 seconds)
            # If so, just return the existing browser
            if cls._browser and (time.time() - cls._last_restart_time) < 2:
                print("[Browser] Skipping restart - browser was just restarted")
                return cls._browser

            # Check if we've hit the restart limit
            if cls._restart_count >= cls._max_restarts:
                print(f"[Browser] Restarted {cls._restart_count} times. Applying extended cooldown...")
                cls._restart_count = 0
                # Release lock during cooldown so other operations don't deadlock
                cls._restarting = True

        # Extended cooldown outside the lock
        if cls._restarting:
            await asyncio.sleep(settings.BROWSER_EXTENDED_COOLDOWN)

        async with cls._lock:
            cls._restarting = False
            cls._restart_count += 1
            cls._page_count = 0
            print(f"[Browser] Restarting browser (attempt {cls._restart_count}/{cls._max_restarts})...")

            # Close existing browser
            await cls._close_internal()

            # Brief delay before restart
            await asyncio.sleep(settings.BROWSER_RESTART_DELAY)

            # Start new browser (inline to keep lock held)
            try:
                await cls._start_browser_internal()
                cls._last_restart_time = time.time()
            except Exception as e:
                print(f"[Browser] Restart failed: {e}")
                raise

            return cls._browser

    @classmethod
    async def _start_browser_internal(cls):
        """Internal browser start - assumes lock is already held."""
        print("[Browser] Starting pydoll browser...")

        # Clean up stale resources before starting
        kill_stale_chrome_processes()
        cleanup_stale_profiles()

        options = ChromiumOptions()
        options.headless = True

        # Use system Chrome if available
        chrome_path = find_chrome_binary()
        if chrome_path:
            print(f"[Browser] Using Chrome: {chrome_path}")
            options.binary_location = chrome_path
        else:
            print("[Browser] ERROR: No Chrome binary found.")

        # Essential args for headless Chrome
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")

        if IS_CONTAINER:
            options.add_argument("--disable-setuid-sandbox")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-default-apps")
            options.add_argument("--disable-sync")
            options.add_argument("--disable-translate")
            options.add_argument("--metrics-recording-only")
            options.add_argument("--mute-audio")
            options.add_argument("--safebrowsing-disable-auto-update")
            options.add_argument("--renderer-process-limit=1")
            options.add_argument("--disable-features=TranslateUI")

        profile_dir = get_user_data_dir()
        print(f"[Browser] Using profile: {profile_dir}")
        options.add_argument(f"--user-data-dir={profile_dir}")

        cls._browser = Chrome(options=options)

        try:
            print(f"[Browser] Starting with {cls._startup_timeout}s timeout...")
            await asyncio.wait_for(cls._browser.start(), timeout=cls._startup_timeout)
            print("[Browser] Started successfully!")
        except asyncio.TimeoutError:
            print(f"[Browser] ERROR: Startup timed out after {cls._startup_timeout}s")
            cls._browser = None
            kill_stale_chrome_processes()
            raise Exception("Browser startup timed out")
        except Exception as e:
            print(f"[Browser] ERROR: Start failed: {type(e).__name__}: {e}")
            cls._browser = None
            kill_stale_chrome_processes()
            raise

    @classmethod
    async def increment_page_count(cls) -> bool:
        """
        Increment page count and restart browser if threshold reached.
        Returns True if browser was restarted.
        """
        cls._page_count += 1
        cls._consecutive_timeouts = 0  # Reset timeout counter on success
        if cls._page_count >= cls._max_pages_before_restart:
            print(f"[Browser] Preventive restart after {cls._page_count} pages to free memory")
            await cls.restart()
            return True
        return False

    @classmethod
    async def handle_timeout_error(cls):
        """
        Handle a timeout error - track consecutive timeouts and force restart if needed.
        Returns True if a hard restart was performed.
        """
        cls._consecutive_timeouts += 1
        print(f"[Browser] Timeout #{cls._consecutive_timeouts}/{cls._max_consecutive_timeouts}")

        if cls._consecutive_timeouts >= cls._max_consecutive_timeouts:
            print("[Browser] Too many consecutive timeouts - forcing hard restart!")
            cls._consecutive_timeouts = 0
            # Nuclear option - kill everything
            force_kill_all_chrome()
            # Clear browser reference
            async with cls._lock:
                cls._browser = None
                cls._restart_count = 0
            # Start fresh
            await cls.restart()
            return True
        return False


async def get_page_content(
    url: str,
    retries: int = settings.BROWSER_PAGE_RETRIES,
    extra_wait: float = 0,
) -> str:
    """
    Navigates to a URL and returns the HTML content.
    Uses pydoll for undetected browsing.

    Args:
        url: The URL to navigate to
        retries: Number of retry attempts
        extra_wait: Additional seconds to wait after content load (for JS-heavy sites)
    """
    last_error = None

    async with _semaphore:  # Serialize browser operations
        for attempt in range(retries + 1):
            tab = None
            try:
                browser = await BrowserManager.get_browser()
                tab = await browser.new_tab()

                # Random delay before navigation (human-like)
                await asyncio.sleep(
                    random.uniform(
                        settings.BROWSER_PRE_NAV_DELAY_MIN,
                        settings.BROWSER_PRE_NAV_DELAY_MAX,
                    )
                )

                # Navigate
                await tab.go_to(url)

                # Random wait for content to load (human-like)
                await asyncio.sleep(
                    random.uniform(
                        settings.BROWSER_CONTENT_LOAD_DELAY_MIN,
                        settings.BROWSER_CONTENT_LOAD_DELAY_MAX,
                    )
                )

                # Extra wait for JS-heavy sites like OpenSea
                if extra_wait > 0:
                    await asyncio.sleep(extra_wait)

                # Get page content
                content = await tab.page_source

                if not content or len(content) < settings.BROWSER_MIN_CONTENT_LENGTH:
                    raise Exception("Empty or invalid page content received")

                # Check for eBay blocking indicators (only for eBay URLs)
                # Only trigger if we DON'T have real listing content AND have blocking phrases
                if "ebay.com" in url.lower():
                    content_lower = content.lower()
                    has_listings = "s-item__link" in content or "srp-results" in content

                    if not has_listings:
                        # More specific blocking phrases (avoid false positives from JS/CSS)
                        blocking_phrases = [
                            "please verify yourself",
                            "robot or human",
                            "security measure",
                            "access to this page has been denied",
                            "unusual traffic from your computer",
                            "too many requests",
                            "complete the captcha",
                        ]
                        for phrase in blocking_phrases:
                            if phrase in content_lower:
                                raise Exception(f"eBay blocking detected: '{phrase}' found")

                # Track page count for preventive restart
                await BrowserManager.increment_page_count()

                return content

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                error_type = type(e).__name__
                print(f"Error in get_page_content (attempt {attempt + 1}/{retries + 1}):")
                print(f"  Type: {error_type}")
                print(f"  Message: {e}")

                # Determine if this is a browser-level error requiring restart
                browser_error_keywords = [
                    "browser",
                    "closed",
                    "crashed",
                    "connection",
                    "websocket",
                    "connect call failed",
                    "errno 61",
                    "invalidstate",
                    "target",
                    "timeout",
                ]
                is_browser_error = error_type in ("OSError", "ConnectionError", "WebSocketException") or any(
                    keyword in error_msg for keyword in browser_error_keywords
                )

                # Handle different error types with appropriate recovery
                is_timeout = "timeout" in error_msg or error_type == "TimeoutError"

                if "blocking detected" in error_msg:
                    # eBay blocking - restart browser and apply longer cooldown
                    print("[Browser] eBay blocking detected. Restarting browser with extended cooldown...")
                    await BrowserManager.restart()
                    await asyncio.sleep(
                        random.uniform(
                            settings.BROWSER_BLOCKING_COOLDOWN_MIN,
                            settings.BROWSER_BLOCKING_COOLDOWN_MAX,
                        )
                    )
                elif is_timeout:
                    # Timeout error - track consecutive timeouts for hard restart
                    hard_restarted = await BrowserManager.handle_timeout_error()
                    if not hard_restarted:
                        # Normal restart if we haven't hit threshold
                        await BrowserManager.restart()
                    await asyncio.sleep(settings.BROWSER_RESTART_DELAY)
                elif is_browser_error:
                    # Browser-level error - restart
                    print("[Browser] Detected browser issue. Restarting browser...")
                    await BrowserManager.restart()
                    await asyncio.sleep(settings.BROWSER_RESTART_DELAY)
                else:
                    await asyncio.sleep(1)

                if attempt == retries:
                    print(f"Failed after {retries + 1} attempts: {last_error}")
                    raise last_error

            finally:
                if tab:
                    try:
                        await tab.close()
                    except (asyncio.TimeoutError, RuntimeError, OSError):
                        # Tab close can fail if browser crashed or connection lost - safe to ignore
                        pass

    # Should never reach here (loop raises on final attempt), but handle edge case
    if last_error:
        raise last_error
    raise Exception(f"Failed to get page content for {url} after {retries + 1} attempts")
