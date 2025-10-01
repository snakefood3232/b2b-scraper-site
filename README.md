# B2B Data Scraper — Minimal, Compliant Lead Finder (FastAPI + Vanilla JS)

This is a production‑ready starter for a B2B data scraper website:
- **Search** companies by niche/service/location via Bing Web Search API or SerpAPI (bring your own key).
- **Upload** a CSV of seed websites if you don’t have API keys.
- **Scrape** each site (robots‑aware) to extract generic contact info (role emails only), phone numbers, and social links.
- **Export** results as CSV.

> **Compliance by default:** The scraper checks `robots.txt`, sets a descriptive `User-Agent`, and filters **generic role emails only** (e.g., `info@`, `sales@`, `contact@`, `hello@`, `support@`). It avoids obvious personal emails where possible. You are responsible for compliance with target sites’ Terms of Service and applicable laws (e.g., CAN‑SPAM, GDPR, CCPA, CASL).

---

## Quick Start

### 1) Create and activate a virtual environment
```bash
cd b2b-scraper-site
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Provide an optional search API key
Choose **one** (or both) of these in your shell before starting the server:

```bash
# Option A — Bing Web Search (recommended)
export BING_SEARCH_KEY="YOUR_BING_KEY"
export BING_SEARCH_ENDPOINT="https://api.bing.microsoft.com/v7.0/search"

# Option B — SerpAPI (Google Results proxy)
export SERPAPI_KEY="YOUR_SERPAPI_KEY"
```

> If you don’t set any keys, you can still upload your own CSV of seed domains in the UI.

### 3) Run the backend
```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

### 4) Open the frontend
Just open `web/index.html` in a browser while the backend runs at `http://localhost:8000`.

---

## CSV format for seed URLs (no API keys)
Upload a simple CSV with a `url` column:
```csv
url
https://example.com
https://another-site.com
```

---

## Architecture

- **backend/app.py** — FastAPI app exposing:
  - `POST /api/search` — finds candidate websites for a query (via Bing or SerpAPI if keys present).
  - `POST /api/scrape` — scrapes each URL, respecting robots, extracting role emails, phones, socials.
  - `POST /api/export` — converts records to CSV and returns as a downloadable file.
- **backend/scrapers/http.py** — HTTP helpers (robots, fetch, parse).
- **web/** — vanilla HTML/JS UI.

---

## Notes & Limits

- This starter deliberately **avoids** scraping search engines directly to respect their ToS; use official APIs.
- Headless rendering (JS‑heavy sites) isn’t enabled by default. For that, add Playwright and a headless browser to `requirements.txt` and extend `http.fetch`.
- Always verify you have permission to collect and use the data for your specific use case.

## Pro add-ons: Stealth, Proxies, Queue & Persistence

**Stealth & Proxies**
- Install once: `python -m playwright install chromium`
- Provide rotating proxies:
```
export PROXY_LIST="http://user:pass@ip1:port,http://user:pass@ip2:port"
```
Playwright renders with stealth; browser occasionally relaunches to rotate proxies. `requests` uses a random proxy per fetch.

**Redis Queue + Postgres**
- Env:
```
export REDIS_URL="redis://localhost:6379/0"
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/neonlead"
```
- Start API:
```
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```
- Start worker:
```
python -c "from backend.worker import run_worker; run_worker()"
```
- Optional dashboard:
```
pip install rq-dashboard
rq-dashboard  # http://127.0.0.1:9181
```
Use **Queue mode** in the UI to enqueue a job; results persist and can be fetched later via `/api/jobs/{id}` endpoints.

---
## Easiest way to run (Docker — no local installs)
1) Copy `.env.example` to `.env` and fill any keys you have (or leave defaults).
2) Run:
```bash
docker compose up --build
```
3) Open **http://localhost:8080** (frontend) — it proxies **/api** to the backend.

- API also exposed at **http://localhost:8000**.
- Postgres & Redis run inside the compose stack.
- Playwright (Chromium) already available in the API/worker image.

**Local (non-Docker) fallback:** If you prefer local, keep `web/script.js` API as `http://localhost:8000`, then run `uvicorn` and open `web/index.html` from disk.
