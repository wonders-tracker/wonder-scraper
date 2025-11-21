from pydoll.browser import Chrome
import inspect
import asyncio

async def check_async():
    browser = Chrome()
    print(f"Is start async? {inspect.iscoroutinefunction(browser.start)}")
    print(f"Is new_tab async? {inspect.iscoroutinefunction(browser.new_tab)}")

if __name__ == "__main__":
    asyncio.run(check_async())

