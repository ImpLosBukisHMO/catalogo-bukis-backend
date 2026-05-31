# Catalogo Bukis — Deployment Guide (Railway)

## Architecture

```
Railway Project
├── Service: backend   (Django 6 + DRF + Gunicorn)
├── Service: frontend  (React 19 + Vite, served via `serve -s`)
└── Plugin:  postgres  (Railway-managed PostgreSQL)
```

---

## Required Environment Variables

### Backend (Railway → backend service → Variables)

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Django secret key — generate fresh for prod | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DEBUG` | Must be `False` in production | `False` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `your-backend.up.railway.app` |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins (with scheme) | `https://your-backend.up.railway.app` |
| `DATABASE_URL` | Injected automatically by Railway PostgreSQL plugin | `postgresql://user:pass@host:5432/db` |
| `JWT_SECRET_KEY` | Secret for JWT signing | any strong random string |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed frontend origins | `https://your-frontend.up.railway.app` |

### Frontend (Railway → frontend service → Variables)

| Variable | Description | Example |
|---|---|---|
| `VITE_API_BASE_URL` | Backend base URL — no trailing slash | `https://your-backend.up.railway.app` |

> **Note:** Vite bakes env vars into the bundle at build time.  
> Set `VITE_API_BASE_URL` in Railway BEFORE the first deploy so the build picks it up.

---

## Deploying Backend on Railway

1. In Railway dashboard → **New Project** → **Deploy from GitHub repo** → select `catalogo-bukis-backend`
2. Railway will detect the `Procfile` automatically
3. Add the **PostgreSQL** plugin to the project → Railway injects `DATABASE_URL`
4. Set all environment variables listed above
5. Deploy — the `release` command in `Procfile` runs `migrate` and `collectstatic` automatically

**Procfile commands:**
```
web:     cd catalogo_backend && gunicorn catalogo_backend.wsgi --bind 0.0.0.0:$PORT --workers 2
release: cd catalogo_backend && python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

---

## Deploying Frontend on Railway

1. In Railway dashboard → **New Project** → **Deploy from GitHub repo** → select `catalogo-bukis-frontend`
2. Railway reads `catalogo-frontend/railway.toml` for build/start config
3. Set `VITE_API_BASE_URL` to the backend service URL
4. Deploy — Railway runs `npm ci && npm run build`, then `npm start` (serves `dist/` in SPA mode)

**SPA routing:** `serve -s dist` handles the HTML5 History API — all paths fall back to `index.html`.

---

## Connecting PostgreSQL

Railway injects `DATABASE_URL` automatically when the PostgreSQL plugin is attached to the same project as the backend service. No manual configuration needed — `dj-database-url` parses it on startup.

---

## Running Migrations

Migrations run automatically on every deploy via the `release` command in `Procfile`.

To run manually (e.g. after a schema change):
```
Railway dashboard → backend service → Shell → python manage.py migrate
```
Or via Railway CLI:
```bash
railway run --service backend -- python catalogo_backend/manage.py migrate
```

---

## Custom Domain Setup

1. Railway dashboard → service → **Settings** → **Domains** → Add custom domain
2. Add the CNAME record your DNS provider shows
3. Update backend env vars:
   - `ALLOWED_HOSTS`: add your custom domain (comma-separated)
   - `CSRF_TRUSTED_ORIGINS`: add `https://yourdomain.com`
   - `CORS_ALLOWED_ORIGINS`: add `https://yourfrontenddomain.com`
4. Redeploy backend after env var changes

---

## Media / Image Files

### Current setup

Django serves media files from `MEDIA_ROOT = BASE_DIR / "media"` only when `DEBUG=True`.  
In production (`DEBUG=False`) media files are **not served** — this is intentional Django behavior.

### The problem with Railway

Railway's filesystem is **ephemeral** — it resets on every deploy. Any images uploaded by users will be lost.

### Options

| Option | Pros | Cons |
|---|---|---|
| **Railway Volume** (persistent disk) | Simple, no external service | Not replicated, extra cost, not globally distributed |
| **AWS S3 / Cloudflare R2** (recommended) | Durable, CDN-ready, scalable | Requires `django-storages` integration + bucket setup |
| **Cloudinary** | Free tier, image transforms built-in | Vendor lock-in |

### Recommended: Cloudflare R2 (S3-compatible, free egress)

Install `django-storages[s3]` and configure:
```python
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_S3_ENDPOINT_URL = 'https://<account>.r2.cloudflarestorage.com'
AWS_ACCESS_KEY_ID = os.environ.get('R2_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('R2_BUCKET_NAME')
```

Until external storage is configured, do not rely on uploaded images surviving a redeploy.

---

## Backup Recommendations

| What | How | Frequency |
|---|---|---|
| PostgreSQL | Railway dashboard → plugin → Backups (automatic) | Daily (Railway handles it) |
| PostgreSQL manual | `pg_dump $DATABASE_URL > backup.sql` | Before every migration |
| Media files | Sync to S3/R2 | Continuous (use external storage) |

---

## Railway Readiness Checklist

### Backend
- [x] `gunicorn` in requirements.txt
- [x] `dj-database-url` in requirements.txt
- [x] `whitenoise` in requirements.txt
- [x] `SECRET_KEY` reads from env var
- [x] `DEBUG` reads from env var
- [x] `ALLOWED_HOSTS` reads from env var
- [x] `CSRF_TRUSTED_ORIGINS` reads from env var
- [x] `DATABASES` uses `dj_database_url.config()` (auto-switches SQLite ↔ Postgres)
- [x] `CORS_ALLOWED_ORIGINS` reads from env var; `CORS_ALLOW_ALL_ORIGINS` only true in dev
- [x] `whitenoise` middleware configured
- [x] `STATIC_ROOT` and `STATICFILES_STORAGE` set
- [x] `Procfile` with `web` and `release` commands
- [x] `.env.example` with all variables documented
- [x] `.gitignore` excludes `db.sqlite3`, `venv/`, `.env`, `staticfiles/`
- [x] GitHub Actions CI (runs tests + collectstatic against Postgres)
- [ ] **TODO:** Configure external storage for media files (R2/S3)
- [ ] **TODO:** Set all env vars in Railway dashboard before first deploy
- [ ] **TODO:** Generate a fresh `SECRET_KEY` for production

### Frontend
- [x] `src/services/auth.ts` uses `VITE_API_BASE_URL` env var (no hardcoded URL)
- [x] `src/api/index.ts` uses `VITE_API_BASE_URL` env var
- [x] `.env.example` documents required variables
- [x] `railway.toml` with Nixpacks build + `serve -s` for SPA routing
- [x] `package.json` has `start` script using `serve`
- [x] Bulma CDN duplicate removed from `index.html`
- [x] GitHub Actions CI (lint + build check)
- [ ] **TODO:** Set `VITE_API_BASE_URL` in Railway before first deploy (build-time variable)
- [ ] **TODO:** Run `npm install` locally to update `package-lock.json` after adding `serve`
