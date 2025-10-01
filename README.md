# B2B Data Scraper — Minimal, Compliant Lead Finder

FastAPI backend + tiny vanilla JS frontend.

## Render (quick)

1) Create Postgres → copy **Internal** URL → convert:
   `postgresql://...` → `postgresql+psycopg2://...`
2) Create **Web Service** (Docker):
   - Dockerfile Path: `Dockerfile.api`
   - Build Context: `.`
   - Port: `8000`
   - Env: `DATABASE_URL` = your value above
3) Create **Static Site**:
   - Build Command: *(empty)*
   - Publish Directory: `web`
4) Edit `web/script.js`:
   ```js
   const API = 'https://<your-api>.onrender.com';
   ```

## Optional Queue mode
- Create Redis → set `REDIS_URL` on API + a **Background Worker** (start command:
  `python -c "from backend.worker import run_worker; run_worker()"`)

## Local Docker
```bash
cp .env.example .env
docker compose up --build
# UI:  http://localhost:8080
# API: http://localhost:8000/docs
```
