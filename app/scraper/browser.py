from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions
from typing import Optional
import asyncio

class BrowserManager:
    _browser: Optional[Chrome] = None

    @classmethod
    async def get_browser(cls) -> Chrome:
        if not cls._browser:
            opts = ChromiumOptions()
            opts.headless = True # Explicitly enable headless mode
            # Stealth args
            opts.add_argument("--disable-blink-features=AutomationControlled")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-infobars")
            opts.add_argument("--disable-dev-shm-usage")
            # Mimic a real browser UA
            opts.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            cls._browser = Chrome(options=opts)
            await cls._browser.start()
        return cls._browser

    @classmethod
    async def close(cls):
        if cls._browser:
            await cls._browser.stop()
            cls._browser = None

async def get_page_content(url: str) -> str:
    """
    Navigates to a URL and returns the HTML content.
    """
    browser = await BrowserManager.get_browser()
    tab = await browser.new_tab()
    
    try:
        # Optional: Add random delay before navigation
        await asyncio.sleep(0.5) 
        
        await tab.go_to(url)
        
        # Wait for content to likely load (basic wait)
        await asyncio.sleep(2)
        
        content = await tab.page_source
        return content
    except Exception as e:
        print(f"Error in get_page_content: {e}")
        raise
    finally:
        await tab.close()
