from __future__ import annotations
import os, uuid, asyncio
from rq import Queue, Connection, Worker
from redis import Redis
from sqlalchemy.orm import Session
from .db import SessionLocal, init_db, Job, Result
from .scrapers.http import extract_contacts, fetch_http, normalize_url, allowed_by_robots
from .scrapers.playwright_fetch import fetch_rendered

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def _redis_from_url(url: str) -> Redis:
    return Redis.from_url(url)

def process_job(job_id: str, urls: list[str], render: bool, concurrency: int, timeout_ms: int) -> dict:
    init_db()
    session: Session = SessionLocal()
    job = session.get(Job, job_id)
    if not job:
        job = Job(id=job_id, status="running", params={"render": render, "concurrency": concurrency, "timeout_ms": timeout_ms})
        session.add(job)
        session.commit()
    else:
        job.status = "running"
        session.commit()

    results = asyncio.run(_scrape_batch(urls, render, concurrency, timeout_ms))
    for r in results:
        session.add(Result(
            job_id=job_id,
            url=r.get("url",""),
            org=r.get("org"),
            title=r.get("title"),
            emails=",".join(r.get("emails",[])),
            phones=",".join(r.get("phones",[])),
            socials=",".join(r.get("socials",[])),
            ok=1 if r.get("ok") else 0,
            error=r.get("error")
        ))
    from datetime import datetime
    job.status = "finished"
    job.finished_at = datetime.utcnow()
    session.commit()
    session.close()
    return {"ok": True, "count": len(results)}

async def _scrape_one(u: str, render: bool, timeout_ms: int) -> dict:
    url = normalize_url(u)
    try:
        if not allowed_by_robots(url):
            return {"url": url, "ok": False, "error": "blocked_by_robots"}
        html = await (fetch_rendered(url, timeout_ms) if render else fetch_http(url, timeout_ms))
        data = extract_contacts(html, url)
        data.update({"url": url, "ok": True})
        return data
    except Exception as e:
        return {"url": url, "ok": False, "error": str(e)[:300]}

async def _scrape_batch(urls: list[str], render: bool, concurrency: int, timeout_ms: int) -> list[dict]:
    import asyncio
    sem = asyncio.Semaphore(max(1, min(concurrency, 10)))
    out = []
    async def bound(u):
        async with sem:
            out.append(await _scrape_one(u, render, timeout_ms))
    await asyncio.gather(*(bound(u) for u in urls))
    return out

def run_worker():
    init_db()
    redis = _redis_from_url(REDIS_URL)
    with Connection(redis):
        w = Worker(["scrape"])
        w.work(with_scheduler=True)
