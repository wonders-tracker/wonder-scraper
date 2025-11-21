from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from typing import Optional
import asyncio
import subprocess
import time

class BrowserManager:
    _browser: Optional[Chrome] = None
    _restart_count: int = 0
    _max_restarts: int = 3

    @classmethod
    async def get_browser(cls) -> Chrome:
        if not cls._browser:
            try:
                # Kill any lingering Chrome processes from previous crashes
                subprocess.run(
                    ["pkill", "-f", "chrome.*--remote-debugging-port"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                await asyncio.sleep(1)
            except Exception:
                pass
                
            opts = ChromiumOptions()
            opts.headless = True
            
            # CRITICAL: Increase Pydoll's internal start timeout (default is only 10s)
            opts.start_timeout = 60  # Give it a full minute to start
            
            # Stealth args
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-infobars")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--disable-software-rasterizer")
            opts.add_argument("--disable-extensions")
            
            # Mimic a real browser UA
            opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Try to find Chrome binary explicitly (macOS paths)
            import os
            chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    opts.binary_location = path
                    print(f"Using Chrome at: {path}")
                    break
            
            print("Starting new browser instance (this may take up to 60 seconds)...")
            cls._browser = Chrome(options=opts)
            
            # Pydoll will handle timeout internally now with start_timeout
            await cls._browser.start()
            await asyncio.sleep(2)  # Give it time to fully initialize
            print("Browser started successfully!")
        return cls._browser

    @classmethod
    async def close(cls):
        if cls._browser:
            try:
                await cls._browser.stop()
            except Exception as e:
                print(f"Error closing browser: {e}")
            cls._browser = None
            
            # Cleanup any lingering processes
            try:
                subprocess.run(
                    ["pkill", "-f", "chrome.*--remote-debugging-port"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

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
        await asyncio.sleep(3)  # Longer wait between restarts
        return await cls.get_browser()

async def get_page_content(url: str, retries: int = 3) -> str:
    """
    Navigates to a URL and returns the HTML content.
    Includes auto-retry and browser recovery logic.
    """
    last_error = None
    
    for attempt in range(retries + 1):
        try:
            browser = await BrowserManager.get_browser()
            
            # Test browser connection before creating tab
            try:
                # Simple connectivity test
                await asyncio.wait_for(browser.new_tab(), timeout=10)
            except asyncio.TimeoutError:
                raise Exception("Browser is not responding (timeout on new_tab)")
            
            tab = await browser.new_tab()
            
            try:
                await asyncio.sleep(0.5) 
                
                # Navigate with timeout
                await asyncio.wait_for(tab.go_to(url), timeout=15)
                
                # Wait for content to load
                await asyncio.sleep(2)
                
                content = await tab.page_source
                
                if not content or len(content) < 100:
                    raise Exception("Empty or invalid page content received")
                    
                return content
            finally:
                # Safely close tab
                try:
                    await asyncio.wait_for(tab.close(), timeout=5)
                except Exception:
                    pass
                    
        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            print(f"Error in get_page_content: {e}")
            
            # If it's a connection error, restart browser
            if any(keyword in error_msg for keyword in ["websocket", "connection", "target closed", "timeout", "not responding"]):
                print("Detected browser issue. Restarting browser...")
                await BrowserManager.restart()
                await asyncio.sleep(3)
            else:
                # For other errors, wait before retry
                await asyncio.sleep(2)
                
            # On last attempt, raise the error
            if attempt == retries:
                print(f"Failed after {retries + 1} attempts: {last_error}")
                raise last_error
    
    raise last_error
