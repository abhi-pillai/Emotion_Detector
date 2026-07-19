# Architecture

## Overview

```
┌────────────┐     HTTPS      ┌───────────────────┐     HTTPS      ┌─────────────┐
│  Browser   │ ─────────────▶ │  Flask app         │ ─────────────▶ │  Gemini API │
│ (templates │ ◀───────────── │  (gunicorn workers) │ ◀───────────── │             │
│  + JS)     │   JSON/HTML    │                     │    JSON        └─────────────┘
└────────────┘                │  SQLAlchemy ORM     │
                               └──────────┬──────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │ SQLite / Postgres │
                                 └─────────────────┘
```

The app is a monolithic Flask service: server-rendered HTML shells
(`templates/`) with a small amount of vanilla JS (`static/js/dashboard.js`)
that talks to JSON API routes on the same origin. There's no separate
frontend build step or SPA framework — kept intentionally simple.

## Request flow: analyzing a message

1. User types a message and clicks "Analyze Emotion" in the dashboard.
2. `dashboard.js` POSTs `{ message }` to `/analyze` with the session
   cookie attached automatically by the browser.
3. `login_required` checks `session['user_id']`; if absent, returns 401
   (for JSON/API requests) instead of redirecting, so the frontend can
   show an inline error rather than silently following a redirect into
   HTML.
4. The route builds a fixed-format prompt and calls
   `model.generate_content(prompt)`.
5. `parse_emotion_response` extracts `Emotion:` / `Explanation:` lines. If
   Gemini doesn't follow the format, or returns an emotion outside
   `{happy, sad, angry, neutral}`, the parser falls back to `"neutral"`
   rather than storing a raw, unbounded string — this closes a bug in the
   original prototype where an off-format model response would either
   crash the stats aggregation (`emotion_counts[emotion]` assumes fixed
   keys) or silently store junk.
6. Result is saved to `EmotionHistory` and returned as JSON; the frontend
   re-fetches `/get-stats` and `/get-history` to refresh the UI.

## Data model

```
User
├─ id (PK)
├─ username (unique)
├─ email (unique)
├─ password_hash        # Werkzeug PBKDF2, never plaintext
├─ created_at
└─ emotions ─────────────┐
                          │  1-to-many, cascade delete
                          ▼
EmotionHistory
├─ id (PK)
├─ user_id (FK → User.id)
├─ message               # raw text analyzed, capped at 2000 chars
├─ emotion                # one of happy/sad/angry/neutral
├─ explanation
└─ timestamp
```

Deleting a user cascades to delete their `EmotionHistory` rows
(`cascade='all, delete-orphan'`), so there's no orphaned data if account
deletion is added later.

## Why these design choices

- **Session-based auth, not JWT**: the app is a first-party web UI, not a
  public API consumed by third parties, so server-side sessions are
  simpler and let us invalidate sessions (`session.clear()`) without a
  token blacklist.
- **Gemini client initialized once at import time, used everywhere**:
  avoids re-authenticating per request. If the key is missing/invalid,
  initialization is wrapped so the app still boots and serves auth/UI
  routes — only the AI-dependent routes return `503`. The original
  prototype would call `genai.configure(api_key=None)` unconditionally and
  only fail (with an unhandled exception) the first time someone tried to
  analyze a message.
- **`config.py` separated from `app.py`**: keeps `SECRET_KEY` /
  `SQLALCHEMY_DATABASE_URI` / debug flags out of the app logic and makes
  the "don't run with a default secret key in production" check
  enforceable in one place (`ProductionConfig`).
- **Emotion set is a closed enum, enforced server-side**: the stats/
  distribution endpoints assume exactly `{happy, sad, angry, neutral}` as
  dictionary keys. Validating and normalizing the model's output before
  storage prevents a mismatched key from silently disappearing from stats
  or, worse, raising a `KeyError` on `/get-stats`.
- **No client-side framework**: the UI is simple enough (one page with a
  form, a button, and a list) that a small vanilla JS file is easier to
  audit and deploy than a bundler/build pipeline.

## Known limitations / explicit non-goals

- No rate limiting on `/analyze` — add `Flask-Limiter` before exposing
  this publicly at scale (see DEPLOYMENT.md).
- No email verification or password reset flow.
- SQLite is fine for one instance; move to Postgres before scaling
  workers/replicas (see DEPLOYMENT.md).
- The AI's "mental state" output is a wellness reflection aid, not a
  clinical assessment, and the UI/README say so explicitly.
