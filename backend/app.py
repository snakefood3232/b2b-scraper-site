from __future__ import annotations

import asyncio
import csv
import io
import os
import uuid
from typing import Any, Dict, List

import httpx
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from .db import Job, Result, SessionLocal, init_db
from .scrapers.http import (
    allowed_by_robots,
    extract_contacts,
    fetch_http,
    normalize_url,
)
from .scrapers.playwright_fetch import fetch_rendered
from .schemas import ExportRequest, JobCreate, ScrapeRequest, SearchRequest


# ------------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------------
app = FastAPI(title="NeonLead B2B Scraper", openapi_url="/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

REDIS_URL = os.getenv("REDIS_URL")
BING_KEY = os.getenv("BING_SEARCH_KEY")
BING_ENDPOINT = os.getenv(
    "BING_SEARCH_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search"
)
SERPAPI_KEY = os.getenv("SERPAPI_KEY")


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
async def scrape_batch(
    urls: List[str], render: bool, concurrency: int, timeout_ms: int
) -> List[Dict[str, Any]]:
    sem = asyncio.Semaphore(max(1, min(concurrency, 10)))
    out: List[Dict[str, Any]] = []

    async def run_one(u: str) -> None:
        url = normalize_url(u)
        try:
            if not allowed_by_robots(url):
                out.append({"url": url, "ok": False, "error": "blocked_by_robots"})
                return
            html = await (fetch_rendered(url, timeout_ms) if render else fetch_http(url, timeout_ms))
            data = extract_contacts(html, url)
            data.update({"url": url, "ok": True})
            out.append(data)
        except Exception as e:
            out.append({"url": url, "ok": False, "error": str(e)[:300]})

    async def bound(u: str) -> None:
        async with sem:
            await run_one(u)

    await asyncio.gather(*(bound(u) for u in urls))
    return out


# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.get("/api/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


@app.post("/api/scrape")
async def api_scrape(req: ScrapeRequest):
    if not req.urls:
        raise HTTPException(400, "urls required")
    results = await scrape_batch(req.urls, req.render, req.concurrency, req.timeout_ms)
    return {"results": results}


@app.post("/api/jobs")
def api_jobs(req: JobCreate):
    if not REDIS_URL:
        raise HTTPException(400, "Queue mode requires REDIS_URL")

    redis = Redis.from_url(REDIS_URL)
    q = Queue("scrape", connection=redis)

    job_id = str(uuid.uuid4())
    session: Session = SessionLocal()
    try:
        j = Job(id=job_id, status="queued", params=req.model_dump())
        session.add(j)
        session.commit()
    finally:
        session.close()

    q.enqueue(
        "backend.worker.process_job",
        job_id,
        req.urls,
        req.render,
        req.concurrency,
        req.timeout_ms,
        job_id=job_id,
    )
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def api_job_status(job_id: str):
    session: Session = SessionLocal()
    try:
        j = session.get(Job, job_id)
        if not j:
            raise HTTPException(404, "job not found")
        return {
            "id": j.id,
            "status": j.status,
            "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        }
    finally:
        session.close()


@app.get("/api/jobs/{job_id}/results")
def api_job_results(job_id: str):
    session: Session = SessionLocal()
    try:
        rows = session.query(Result).filter(Result.job_id == job_id).all()
        payload = []
        for r in rows:
            payload.append(
                {
                    "url": r.url,
                    "org": r.org,
                    "title": r.title,
                    "emails": r.emails.split(",") if r.emails else [],
                    "phones": r.phones.split(",") if r.phones else [],
                    "socials": r.socials.split(",") if r.socials else [],
                    "ok": bool(r.ok),
                    "error": r.error,
                }
            )
        return {"results": payload}
    finally:
        session.close()


# --- CSV Export (primary endpoint) --------------------------------------------
@app.post(
    "/api/export",
    response_class=Response,
    include_in_schema=True,
    responses={
        200: {
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
            "description": "CSV download",
        }
    },
)
def api_export(payload: ExportRequest = Body(...)) -> Response:
    """
    Accepts: {"rows":[{org,url,title,emails,phones,socials,ok,error}, ...]}
    Returns: CSV file (text/csv) with Content-Disposition attachment.
    """
    buf = io.StringIO()
    fieldnames = ["org", "url", "title", "emails", "phones", "socials", "ok", "error"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()

    rows = payload.rows or []
    for r in rows:
        writer.writerow(
            {
                "org": r.get("org") or "",
                "url": r.get("url") or "",
                "title": r.get("title") or "",
                "emails": ",".join(r.get("emails") or []),
                "phones": ",".join(r.get("phones") or []),
                "socials": ",".join(r.get("socials") or []),
                "ok": bool(r.get("ok", False)),
                "error": r.get("error") or "",
            }
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="leads.csv"'},
    )


# Alias that returns the same CSV but hidden from the docs
@app.post("/api/export.csv", response_class=Response, include_in_schema=False)
def api_export_csv(payload: ExportRequest = Body(...)) -> Response:
    return api_export(payload)


@app.post("/api/search")
async def api_search(req: SearchRequest):
    urls: List[str] = []

    if BING_KEY:
        params = {"q": req.query, "count": req.count}
        headers = {"Ocp-Apim-Subscription-Key": BING_KEY}
        async with httpx.AsyncClient() as client:
            r = await client.get(BING_ENDPOINT, params=params, headers=headers, timeout=15.0)
            r.raise_for_status()
            data = r.json()
            for item in (data.get("webPages", {}) or {}).get("value", []):
                u = item.get("url")
                if u:
                    urls.append(u)

    elif SERPAPI_KEY:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://serpapi.com/search.json",
                params={"engine": "google", "q": req.query, "api_key": SERPAPI_KEY},
                timeout=15.0,
            )
            r.raise_for_status()
            data = r.json()
            for item in data.get("organic_results", []):
                u = item.get("link")
                if u:
                    urls.append(u)
    else:
        raise HTTPException(400, "No search key configured; upload a CSV of URLs instead.")

    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
        if len(out) >= req.count:
            break

    return {"urls": out}
