# Standard library imports
import sys
import asyncio

# Ensure the appropriate event loop policy on Windows for subprocess support
if sys.platform.startswith("win"):
    # ProactorEventLoop supports subprocesses on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Third‑party imports
from playwright.async_api import async_playwright

# Project imports
from logger import logger


async def scrape_website_playwright(url: str) -> str:
    """Scrape a webpage using Playwright and return its HTML content.

    Args:
        url: The URL to fetch.

    Returns:
        The page HTML content, or an empty string on failure.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            content = await page.content()
        except Exception as e:
            logger.error(f"Failed to load {url}: {e}")
            content = ""
        await browser.close()
        return content
