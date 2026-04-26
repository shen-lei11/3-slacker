# Trio Hub

Flask app for a team of three: tasks, focus tracker, backlog, achievements, and slacking jar.

## Local development

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux

python app.py
```

App runs at http://localhost:5000. SQLite file `trio_hub.db` is created next to `app.py` on first launch.

## Environment variables

See [.env.example](.env.example). Production requires:

- `FLASK_ENV=production` — disables debug, enables secure cookies.
- `SECRET_KEY` — long random string. App refuses to start in production without it.
- `DATA_DIR` — directory holding the SQLite file; on Render, point at the mounted disk.

Optional: `DATABASE_URL` (override DB entirely), `PORT` (Render sets this automatically).

## Deployment (Render)

This repo includes [render.yaml](render.yaml) as a Blueprint.

1. Push the branch to GitHub.
2. In the Render dashboard: **New → Blueprint** → pick this repo. Render reads `render.yaml`, creates the web service, attaches a 1 GB disk at `/var/data`, and generates `SECRET_KEY`.
3. First deploy auto-runs `pip install -r requirements.txt` then `gunicorn app:app`.
4. Health check: `GET /healthz` must return 200.

Manual provisioning (no Blueprint):

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --workers 1 --timeout 120 --access-logfile - --error-logfile -`
- Disk: mount at `/var/data`, size 1 GB.
- Env vars: `FLASK_ENV=production`, `SECRET_KEY=<random>`, `DATA_DIR=/var/data`.

### Generating a SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Smoke test after deploy

1. `curl https://<service>.onrender.com/healthz` → `{"status":"ok"}`.
2. Register two users, log in/out on each.
3. Create a task, a focus item, a backlog entry, an achievement, and a fine.
4. Trigger a redeploy (or **Manual Deploy → Clear build cache & deploy**) and confirm all records persist.

## Backups

SQLite lives at `$DATA_DIR/trio_hub.db`. Recommended: daily snapshot retained 7–14 days.

Pull a snapshot from Render's shell:

```bash
sqlite3 /var/data/trio_hub.db ".backup /var/data/backup-$(date +%F).db"
```

Download via Render's Files tab, or run `scp` from a one-off shell. For automation, schedule a Render Cron Job that uploads the backup file to S3/Backblaze.

## Restart / rollback

- **Restart:** Render dashboard → service → **Manual Deploy → Deploy latest commit**.
- **Rollback:** dashboard → **Events** → pick a prior successful deploy → **Rollback**.
- **DB rollback:** stop the service, copy a backup over `/var/data/trio_hub.db` from the shell, restart.

## Uptime monitoring

Point UptimeRobot / BetterStack at `https://<service>.onrender.com/healthz` with a 5-minute interval and an email/Slack alert channel. Verify by pausing the service once and confirming the alert fires.

## When to migrate off SQLite

Move to Render's managed Postgres if any of these appear:

- Concurrent-write errors (`database is locked`) in logs.
- More than ~10 active users or sustained writes.
- Need for point-in-time recovery beyond file snapshots.
