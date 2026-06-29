# Household Manager API

The server behind the household app: grocery inventory, bills, price history,
and a daily WhatsApp summary for Amma. The Flutter app and the daily message
both read from the same logic, so nothing drifts out of sync.

## What each file does

| File | Job |
|------|-----|
| `core.py` | The brain. Pure logic: to-buy, to-pay, report, date math, staples. No DB, no web. |
| `db.py` | All SQLite. Connect, create tables, every read and write. |
| `app.py` | The web layer. Thin FastAPI routes calling `db` and `core`. |
| `whatsapp.py` | Sends one message via Meta's WhatsApp Cloud API. |
| `send_daily.py` | The 9am run. Builds Amma's summary and sends it. Runs once, exits. |
| `config.py` | Loads `.env`, hands out settings and secrets. |

## Run the API locally

Windows:
```
powershell -ExecutionPolicy Bypass -File run.ps1
```
Linux / Mac / git-bash:
```
chmod +x run.sh && ./run.sh
```
It makes a venv, installs deps, generates an `APP_TOKEN` into `.env` on first
run, and starts the server. Open http://localhost:8000/docs to click every
endpoint (use the Authorize button, paste the token).

## Smoke test

```bash
TOKEN="paste-the-printed-token"
curl -X POST localhost:8000/items/seed-staples -H "X-API-Token: $TOKEN"
curl localhost:8000/to-buy -H "X-API-Token: $TOKEN"
curl -X POST localhost:8000/bills -H "X-API-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Car Insurance","amount":12000,"category":"Insurance","recurrence":"Yearly","due_date":"2026-07-05","reminder_days":7}'
curl localhost:8000/to-pay -H "X-API-Token: $TOKEN"
```

## WhatsApp setup (do this in parallel, it does not block the code)

The code is ready. You provide the account. Steps in Meta's tooling:

1. Create a Meta Business account, then a WhatsApp app in the developer console.
2. Add a dedicated sending phone number (not your personal number).
3. In WhatsApp Manager, submit one message template, category Utility:
   - Name: daily_household_summary
   - Language: English
   - Body: Good morning Amma. {{1}}
   - Sample for {{1}}: Buy: rice, atta. Pay: car insurance due in 3 days.
4. Get three values and put them in `.env`:
   - WHATSAPP_TOKEN (a permanent access token)
   - WHATSAPP_PHONE_NUMBER_ID
   - WHATSAPP_RECIPIENT (Amma's number, e.g. 9198XXXXXXXX)

Then test the message without waiting for 9am:
```
python send_daily.py --dry-run   # prints the message, sends nothing
python send_daily.py             # actually sends it
```

Note on templates: business-initiated messages must use the approved template,
so the daily push always sends daily_household_summary with the summary as its
one variable. That is by Meta's design, not a limitation of the code.

## Deploy (managed host, no server to babysit)

Push this repo to GitHub, then on Railway or Render:

1. Create a web service from the repo. Start command:
   uvicorn app:app --host 0.0.0.0 --port $PORT
2. Set the environment variables from `.env` in the host's dashboard
   (APP_TOKEN, the WHATSAPP_* values). Do not commit `.env`.
3. Add a scheduled job / cron that runs `python send_daily.py` daily.
   Use 0 9 * * * in Asia/Kolkata, or 30 3 * * * in UTC, which is 9am IST.

That cron is what makes the morning message reliable: it fires whether or not
anyone opened anything, and there is no long-running process to die quietly.

## Not built yet

- /scan (server-side Claude vision, so the API key leaves the phone for good)

It builds on this same structure and is the natural next addition.
