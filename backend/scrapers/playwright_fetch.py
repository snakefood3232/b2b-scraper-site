from __future__ import annotations
import os, random
from typing import Optional
from playwright.async_api import async_playwright

USER_AGENT = "NeonLeadScraper/1.0 (+https://example.com)"

def pick_proxy() -> Optional[str]:
    raw = os.getenv("PROXY_LIST", "").strip()
    if not raw:
        return None
    parts = [p.strip() for p in raw.replace("\n", ",").split(",") if p.strip()]
    return random.choice(parts) if parts else None

async def fetch_rendered(url: str, timeout_ms: int = 15000) -> str:
    proxy = pick_proxy()
    launch_args = {"headless": True}
    if proxy:
        launch_args["proxy"] = {"server": proxy}
    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_args)
        context = await browser.new_context(user_agent=USER_AGENT)
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()
        page.set_default_timeout(timeout_ms)
        await page.goto(url, wait_until="domcontentloaded")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight/3);")
        html = await page.content()
        await browser.close()
        return html
