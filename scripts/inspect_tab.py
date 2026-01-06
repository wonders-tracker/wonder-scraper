from pydoll.browser import Chrome
import inspect


async def inspect_tab():
    browser = Chrome()
    # We won't start it, just check the return type of new_tab if possible or inspect the class
    # But we can't get the tab object without starting.
    # Let's inspect the class directly if we can find it.
    # from pydoll.browser.tab import Tab?
    pass


if __name__ == "__main__":
    # let's try to import Tab
    try:
        from pydoll.browser.tab import Tab

        print("Tab methods:")
        for name, member in inspect.getmembers(Tab):
            if not name.startswith("_"):
                print(name)
    except ImportError:
        print("Could not import Tab directly")
