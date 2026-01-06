from pydoll.browser import Chrome
import asyncio


async def check_page_source():
    browser = Chrome()
    await browser.start()
    tab = await browser.new_tab()
    try:
        prop = tab.page_source
        print(f"Type of tab.page_source: {type(prop)}")
        if asyncio.iscoroutine(prop):
            print("It is a coroutine object (property).")
        elif asyncio.iscoroutinefunction(prop):
            print("It is a coroutine function.")
        else:
            print("It is something else.")
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(check_page_source())
