# Emotion Analyzer

A Flask web app that analyzes emotions in text messages using Google's Gemini
API, tracks history per user, and surfaces a mental-wellness summary with
suggested remedies. Rebuilt from an earlier prototype with authentication
bugs fixed, missing frontend restored, and a real deployment path.

> **Not a medical device.** This app gives lightweight, AI-generated
> reflections for personal journaling. It is not a substitute for professional
> mental health care. See [Crisis support](#crisis-support) below.

## Features

- Register / login / logout with hashed passwords (Werkzeug) and
  server-side sessions
- Emotion classification (happy / sad / angry / neutral) with explanation,
  powered by Gemini
- Emotion history per user, capped and paginated via `?limit=`
- Mental-state summary + actionable remedies generated from the last 10
  entries (requires ≥2 entries)
- Stats dashboard: total analyses, this-week count, per-emotion breakdown
- Health check endpoint for container/load-balancer probes

## Project structure

```
emotion-analyzer/
├── app.py                  # Flask app, routes, models
├── config.py                # Environment-based configuration
├── requirements.txt          # Runtime dependencies (pinned)
├── requirements-dev.txt      # + pytest for local development
├── .env.example               # Template for local secrets
├── .gitignore
├── Dockerfile                 # Production container image
├── docker-compose.yml         # Local/single-host deployment
├── Procfile                    # Heroku / Render style platforms
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   └── dashboard.html
├── static/
│   ├── css/style.css
│   └── js/dashboard.js
├── tests/
│   └── test_app.py
├── README.md                   # This file
├── DEPLOYMENT.md                # Step-by-step deployment guide
├── ARCHITECTURE.md              # System design, data model, request flow
└── CHANGELOG.md                 # What changed vs. the original prototype
```

## Quick start (local)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env
# edit .env: set GEMINI_API_KEY and SECRET_KEY

python app.py
```

Open `http://localhost:8000`. The SQLite database is created automatically
at `instance/emotions.db` on first run.

Get a Gemini API key at https://aistudio.google.com/app/apikey (the old
`makersuite.google.com` console has been folded into Google AI Studio).

## Running tests

```bash
pytest
```

## API endpoints

| Method | Path                    | Auth | Description                              |
|--------|-------------------------|------|--------------------------------------------|
| GET    | `/`                     | -    | Redirect to login or dashboard             |
| GET/POST | `/register`           | -    | Create an account                          |
| GET/POST | `/login`              | -    | Log in                                     |
| GET    | `/logout`               | ✔    | Clear session                              |
| GET    | `/dashboard`            | ✔    | Main UI                                    |
| POST   | `/analyze`              | ✔    | Classify emotion of a message              |
| GET    | `/get-history`          | ✔    | Emotion history (`?limit=1-100`)           |
| POST   | `/analyze-mental-state` | ✔    | Mental state + remedies from last 10 items |
| GET    | `/get-stats`            | ✔    | Aggregate stats for the user               |
| POST   | `/clear-history`        | ✔    | Delete all history for the user            |
| GET    | `/healthz`              | -    | Health check (`{"status": "ok", ...}`)     |

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for Docker, Render/Railway/Heroku, and
bare-metal instructions, plus a production checklist.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the data model, request flow, and
design decisions.

## What changed vs. the original prototype

See [CHANGELOG.md](CHANGELOG.md) for the full list of bugs fixed and
features added.

## Crisis support

This tool is not equipped to handle crises. If you or someone you know is in
immediate danger or considering self-harm, please contact local emergency
services or a crisis line in your country right away (for example, in the
US: call or text 988).

## License

Open source, for educational use.
