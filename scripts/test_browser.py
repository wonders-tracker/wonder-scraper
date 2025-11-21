import asyncio
from app.scraper.browser import get_page_content

async def test_browser():
    print("Testing Pydoll...")
    url = "https://example.com"
    try:
        content = await get_page_content(url)
        print(f"Successfully fetched {url}")
        print(f"Content length: {len(content)}")
        if "Example Domain" in content:
            print("Content validation passed!")
        else:
            print("Content validation failed.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_browser())

