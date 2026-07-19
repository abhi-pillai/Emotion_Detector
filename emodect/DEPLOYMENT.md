# Deployment Guide

This app is a standard Flask + SQLAlchemy service, so it deploys anywhere
that runs a Python WSGI app. Three paths are documented below, from
simplest to most controlled: **PaaS (Render/Railway/Heroku)**, **Docker**,
and **bare-metal / VM with Gunicorn + Nginx**.

The app serves via `gunicorn` in all production paths — `python app.py`
(Flask's dev server) must never be used in production; it is
single-threaded, unstable under load, and disables itself when `DEBUG` is
off anyway.

---

## 0. Pre-deployment checklist

- [ ] Generate a real `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Set `FLASK_CONFIG=production` (this enforces `SECRET_KEY` is not the dev default and turns `SESSION_COOKIE_SECURE` on, so cookies only travel over HTTPS)
- [ ] Get a `GEMINI_API_KEY` from https://aistudio.google.com/app/apikey
- [ ] Decide on your database: SQLite is fine for a single small instance;
      use Postgres (`DATABASE_URL=postgresql://...`) if you'll run more
      than one worker/replica or need durability beyond a single disk
- [ ] Put the app behind HTTPS (the PaaS options below do this for you;
      for bare-metal, terminate TLS at Nginx or a load balancer)
- [ ] Confirm `.env` / secrets are never committed (`.gitignore` already
      excludes it)

---

## 1. Docker (recommended default)

```bash
# Build
docker build -t emotion-analyzer .

# Run
docker run -d \
  --name emotion-analyzer \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your_key \
  -e SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  -e FLASK_CONFIG=production \
  -v emotion_data:/app/instance \
  emotion-analyzer
```

Or with Docker Compose (reads `GEMINI_API_KEY` / `SECRET_KEY` from your shell
or a `.env` file in the project root):

```bash
docker compose up -d --build
```

The container:
- Runs as a non-root user
- Uses `gunicorn` with 2 workers / 4 threads (tune via the `CMD` in the
  `Dockerfile` for your traffic/CPU)
- Exposes `/healthz` for `HEALTHCHECK` / your orchestrator's liveness probe
- Persists SQLite under `/app/instance`, mounted as a named volume so data
  survives container recreation

To push to a registry and deploy on any container platform (Fly.io, AWS
ECS/App Runner, Google Cloud Run, Azure Container Apps, etc.), tag and push
the built image, then set the same environment variables in that platform's
config and mount a persistent volume (or switch to Postgres — most managed
container platforms don't offer writable persistent disks by default,
which matters for SQLite; Cloud Run and similar serverless platforms in
particular require Postgres since local disk doesn't persist between
instances).

---

## 2. PaaS (Render, Railway, Heroku-style)

These platforms build directly from your repo and use the included
`Procfile`:

```
web: gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 app:app
```

Steps (Render as the example; Railway/Heroku are nearly identical):

1. Push this repo to GitHub/GitLab.
2. Create a new **Web Service**, point it at the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: leave default (it will pick up the `Procfile`) or set the
   command above explicitly.
5. Add environment variables in the dashboard:
   - `GEMINI_API_KEY`
   - `SECRET_KEY`
   - `FLASK_CONFIG=production`
   - `DATABASE_URL` — attach a managed Postgres add-on and use its
     connection string; **do not rely on local disk for SQLite on these
     platforms**, since most PaaS filesystems are ephemeral and your data
     (and all user accounts) will be wiped on every redeploy or restart
6. Deploy. The platform provides HTTPS automatically.

If you do want SQLite on a PaaS, only do so on a tier that gives you a
persistent disk (e.g. Render's paid "Persistent Disk" add-on mounted at
`/app/instance`) — otherwise use Postgres.

### Switching to Postgres

1. Add `psycopg2-binary` to `requirements.txt`.
2. Set `DATABASE_URL=postgresql://user:pass@host:5432/dbname`.
3. No code changes needed — SQLAlchemy uses whatever `DATABASE_URL` you
   provide.

---

## 3. Bare-metal / VM (Gunicorn + Nginx + systemd)

```bash
# On the server
sudo apt update && sudo apt install -y python3-venv nginx
git clone <your-repo> /opt/emotion-analyzer
cd /opt/emotion-analyzer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values
```

**systemd unit** (`/etc/systemd/system/emotion-analyzer.service`):

```ini
[Unit]
Description=Emotion Analyzer
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/emotion-analyzer
EnvironmentFile=/opt/emotion-analyzer/.env
Environment=FLASK_CONFIG=production
ExecStart=/opt/emotion-analyzer/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 3 --threads 4 --timeout 60 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now emotion-analyzer
```

**Nginx reverse proxy** (`/etc/nginx/sites-available/emotion-analyzer`):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then add TLS with Certbot:

```bash
sudo ln -s /etc/nginx/sites-available/emotion-analyzer /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
```

---

## Scaling notes

- **Multiple workers/replicas + SQLite don't mix well** — SQLite handles
  concurrent writes poorly across separate processes/hosts. If you scale
  beyond one worker process on one machine, move to Postgres.
- **Sessions**: currently server-side signed cookies via Flask's default
  session interface, which requires a stable `SECRET_KEY` across
  restarts/replicas — set it as an env var (already required by
  `ProductionConfig`), never let it regenerate randomly.
- **Rate limiting**: the Gemini API has its own rate/quota limits; if you
  expect real traffic, add `Flask-Limiter` in front of `/analyze` and
  `/analyze-mental-state` to protect both your quota and your users'
  experience.
- **Observability**: `/healthz` is wired for basic liveness; for real
  production, pipe `app.logger` output to a log aggregator and consider
  adding request tracing.

## Rollback

Because the app is stateless aside from the database, rollback is just
redeploying the previous image/commit. Keep database migrations (if you
add any via Flask-Migrate/Alembic) backward compatible for at least one
release to make this safe.
