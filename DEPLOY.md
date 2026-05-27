# DEPLOY.md — How to Deploy Breathe ESG
**Railway (backend) + Vercel (frontend) — free tier, no credit card needed**

This is the fastest path from local to a live URL. The whole process takes ~15 minutes.

---

## Prerequisites

- GitHub account (push this repo first)
- [Railway](https://railway.app) account (sign in with GitHub)
- [Vercel](https://vercel.com) account (sign in with GitHub)

**Push to GitHub first:**
```powershell
cd d:\Placement\Companies\breathe
git init
git add .
git commit -m "Initial commit — Breathe ESG prototype"
# Create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/breathe-esg.git
git push -u origin main
```

---

## Step 1 — Deploy the backend to Railway

### 1a. Create a new Railway project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Choose **Deploy from GitHub repo** → select `breathe-esg`
3. When asked for the root directory, set it to: **`backend`**
4. Railway will auto-detect the `Procfile` and `requirements.txt`

### 1b. Add a PostgreSQL database

Inside your Railway project:
1. Click **+ New** → **Database** → **PostgreSQL**
2. Railway automatically creates a `DATABASE_URL` variable and injects it into your service

But our app uses individual `POSTGRES_*` env vars, so go to your **backend service → Variables** and add:

```
POSTGRES_DB       = ${{Postgres.PGDATABASE}}
POSTGRES_USER     = ${{Postgres.PGUSER}}
POSTGRES_PASSWORD = ${{Postgres.PGPASSWORD}}
POSTGRES_HOST     = ${{Postgres.PGHOST}}
POSTGRES_PORT     = ${{Postgres.PGPORT}}
```

(Use Railway's reference syntax `${{ServiceName.VAR}}` to link them.)

### 1c. Set required environment variables

In the backend service → **Variables**, add:

```
DJANGO_SECRET_KEY   = <generate a random 50-char string>
DJANGO_DEBUG        = False
ALLOWED_HOSTS       = your-backend.up.railway.app
```

You can generate a secret key with:
```python
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 1d. Deploy

Click **Deploy**. Railway will:
1. Install `requirements.txt`
2. Run `python manage.py migrate` (from Procfile `release:` line)
3. Run `python manage.py seed_analyst` (creates analyst user)
4. Start gunicorn

Note your backend URL: `https://your-backend.up.railway.app`

### 1e. Test the backend

```
curl https://your-backend.up.railway.app/api/auth/token/ \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"analyst","password":"analyst123"}'
```

You should get back `{"access": "...", "refresh": "..."}`.

---

## Step 2 — Deploy the frontend to Vercel

### 2a. Import the project

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your `breathe-esg` GitHub repo
3. Set **Root Directory** to: `frontend`
4. Framework preset: **Vite** (auto-detected)

### 2b. Set environment variables

In Vercel project settings → **Environment Variables**, add:

```
VITE_API_BASE_URL = https://your-backend.up.railway.app
```

This tells the React app where to send API requests.

### 2c. Deploy

Click **Deploy**. Vercel builds with `npm run build` and serves the `dist/` folder.

Note your frontend URL: `https://breathe-esg.vercel.app`

---

## Step 3 — Connect frontend ↔ backend (CORS)

Go back to your Railway backend service → **Variables**, add:

```
FRONTEND_URL = https://breathe-esg.vercel.app
```

Then redeploy the backend (or it picks up the variable on the next deploy).

This adds your Vercel URL to Django's `CORS_ALLOWED_ORIGINS`.

---

## Step 4 — Verify the full stack

1. Open `https://breathe-esg.vercel.app`
2. Login with `analyst / analyst123`
3. Upload a sample CSV from `sample_data/`
4. Confirm rows appear in the dashboard

---

## Environment variable summary

### Backend (Railway)
| Variable | Value |
|----------|-------|
| `DJANGO_SECRET_KEY` | Random 50-char string |
| `DJANGO_DEBUG` | `False` |
| `ALLOWED_HOSTS` | `your-backend.up.railway.app` |
| `POSTGRES_DB` | `${{Postgres.PGDATABASE}}` |
| `POSTGRES_USER` | `${{Postgres.PGUSER}}` |
| `POSTGRES_PASSWORD` | `${{Postgres.PGPASSWORD}}` |
| `POSTGRES_HOST` | `${{Postgres.PGHOST}}` |
| `POSTGRES_PORT` | `${{Postgres.PGPORT}}` |
| `FRONTEND_URL` | `https://breathe-esg.vercel.app` |

### Frontend (Vercel)
| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://your-backend.up.railway.app` |

---

## Alternative: Deploy backend on Render

If you prefer Render (also free tier):

1. New **Web Service** → connect GitHub repo → root dir: `backend`
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn breathe.wsgi --workers 2 --bind 0.0.0.0:$PORT`
4. Add a **PostgreSQL** database from the Render dashboard
5. Set the same env vars as above
6. In **Deploy Hook** or shell: `python manage.py migrate && python manage.py seed_analyst`

The `render.toml` in `backend/` pre-configures these settings.

---

## Submission checklist

- [ ] GitHub repo URL (public or shared with saura@breatheesg.com etc.)
- [ ] Live backend URL: `https://your-backend.up.railway.app/api/`
- [ ] Live frontend URL: `https://breathe-esg.vercel.app`
- [ ] Login credentials: `analyst / analyst123`
- [ ] Confirm login works and all 3 CSV uploads succeed on the live URL before submitting
