# Changelog: original prototype → this rebuild

The uploaded zip contained `app.py` and a `Setup.md` but was missing
`templates/`, `static/`, and `requirements.txt` entirely, so it could not
run. Beyond restoring those, the following bugs and gaps were fixed.

## Bugs fixed

1. **Sessions invalidated on every restart** — `app.secret_key =
   secrets.token_hex(16)` regenerated a random key on every process start.
   In production (multiple workers, redeploys, restarts) this logs every
   user out constantly and, with multiple workers, each worker would have
   a *different* key, corrupting sessions unpredictably. Now `SECRET_KEY`
   is a required, stable environment variable in production
   (`config.py::ProductionConfig`), with a startup check that refuses to
   run using the insecure default.

2. **Debug mode hardcoded on** — `app.run(debug=True, port=8000)` ships
   Werkzeug's interactive debugger (arbitrary code execution via the
   debugger console) to production. Debug mode is now driven by
   `FLASK_CONFIG`/environment, off by default in production, and the app
   is served via `gunicorn` in all deployment paths, not `app.run()`.

3. **Gemini client crashes the whole app if the key is missing/invalid** —
   `genai.configure(api_key=os.getenv('GEMINI_API_KEY'))` ran
   unconditionally at import time with no error handling. Now
   initialization is wrapped; if it fails, the app still boots and serves
   auth pages, and only the AI-dependent endpoints return a clean `503`
   instead of a raw exception.

4. **Unvalidated emotion values could break stats** — `emotion_counts`
   dictionaries in `/get-stats` and `/analyze-mental-state` assume exactly
   the keys `happy/sad/angry/neutral`. If Gemini responded slightly off
   the expected format, whatever string ended up in `emotion` was stored
   as-is; it just silently failed to increment any bucket (no crash, but
   silently wrong stats). It's now validated/normalized against a closed
   set with a safe fallback to `"neutral"` before it's ever stored.

5. **No input size limit on `/analyze`** — arbitrarily long messages could
   be sent, inflating API cost per request and DB row size. Capped at
   2000 characters, enforced server-side (previously enforced nowhere).

6. **No real email validation on registration** — any non-empty string
   was accepted as an email. Added a basic format check.

7. **`login_required` always redirected, including for JSON/XHR requests**
   — API calls hitting an expired session got redirected to an HTML login
   page instead of a JSON 401, which the original `dashboard.js` (also
   missing from the zip) would not have handled. Now returns JSON 401 for
   API-style requests and only redirects for full-page navigation.

8. **Login didn't clear prior session state** — logging in as a different
   user without logging out first could leave stale session keys behind.
   `session.clear()` is now called before setting new session values.

9. **SQLite path assumed the current working directory** — `sqlite:///
   emotions.db` resolves relative to wherever the process happens to be
   started from, which breaks under process managers/containers that use
   a different working directory. Now resolved to an explicit
   `instance/` directory that's created if missing.

10. **SQLite URI broke on Windows** — building the URI with
    `os.path.join` produced backslashes (e.g. `D:\Projects\...`) baked
    into a `sqlite:///` URI, which SQLite can't parse, causing
    `sqlite3.OperationalError: unable to open database file` on every
    Windows machine. `config.py` now normalizes the path with
    `pathlib.Path(...).as_posix()` before building the URI, which is
    correct on both Windows and POSIX systems.

## Gaps filled (previously missing entirely)

- `templates/base.html`, `login.html`, `register.html`, `dashboard.html`
- `static/css/style.css`, `static/js/dashboard.js`
- `requirements.txt` / `requirements-dev.txt` with pinned versions
- `.env.example`
- `config.py` for environment-based configuration
- `/healthz` endpoint for container/load-balancer health checks
- `tests/test_app.py` — smoke tests covering registration, login,
  auth-required routes, and the health check (7 tests, all passing)
- `Dockerfile`, `docker-compose.yml`, `Procfile` for deployment
- `DEPLOYMENT.md`, `ARCHITECTURE.md` (this file's siblings)

## Notes carried over from the original `Setup.md`

- The original code referenced a nonexistent `gemini-3-flash-preview`
  model; the prior author had already corrected this to
  `gemini-1.5-flash`, which this rebuild keeps as the default (overridable
  via `GEMINI_MODEL` env var). Since Google's model lineup changes
  independently of this app, check
  https://ai.google.dev/gemini-api/docs/models for the current
  recommended flash-tier model name before deploying, and update
  `GEMINI_MODEL` accordingly if it's been superseded.
