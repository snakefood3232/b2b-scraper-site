from __future__ import annotations
import re, os, random, asyncio, httpx, tldextract
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional
from urllib import robotparser

USER_AGENT = "NeonLeadScraper/1.0 (+https://example.com)"
ROLE_PREFIXES = {"info","hello","contact","support","sales","team","office","enquiries","enquiry","admin"}

def pick_proxy() -> Optional[str]:
    raw = os.getenv("PROXY_LIST", "").strip()
    if not raw:
        return None
    parts = [p.strip() for p in re.split(r"[\n,]+", raw) if p.strip()]
    return random.choice(parts) if parts else None

def allowed_by_robots(target_url: str, timeout: float = 5.0) -> bool:
    try:
        parsed = urlparse(target_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(USER_AGENT, target_url)
    except Exception:
        return True

def normalize_url(u: str) -> str:
    u = u.strip()
    if not u:
        return u
    if not re.match(r"^https?://", u):
        u = "http://" + u
    return u

def extract_contacts(html: str, base_url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string or "").strip() if soup.title else ""
    text = soup.get_text(" ", strip=True)
    phones = set(re.findall(r"(?:\+?\d[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}", text))
    emails = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))

    filtered = set()
    for e in emails:
        local = e.split("@",1)[0].lower()
        if any(local.startswith(p) for p in ROLE_PREFIXES):
            filtered.add(e)

    socials = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        for dom in ["facebook.com","twitter.com","x.com","linkedin.com","instagram.com","tiktok.com","youtube.com"]:
            if dom in href:
                socials.add(href)

    ex = tldextract.extract(base_url)
    org = ex.domain.capitalize() if ex.domain else None

    return {
        "org": org,
        "title": title[:200],
        "emails": sorted(filtered),
        "phones": sorted(phones),
        "socials": sorted(socials),
    }

async def fetch_http(url: str, timeout_ms: int = 12000) -> str:
    proxy = pick_proxy()
    headers = {"User-Agent": USER_AGENT}
    timeout = httpx.Timeout(timeout_ms / 1000.0)
    async with httpx.AsyncClient(proxies=proxy, headers=headers, follow_redirects=True, timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text
