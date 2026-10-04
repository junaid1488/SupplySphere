# UptimeRobot Setup (Free Tier)

Keeps the Render backend awake and alerts on 502s.

**Why:** Render free spins down after 15 idle minutes, so the first visitor gets a cold boot
(502 / 30-60 s delay). The GitHub `keep-awake.yml` cron is not reliable — GitHub's scheduler
fired it every 3-5 hours instead of every 10 minutes, so the instance slept anyway.
UptimeRobot pings every 5 minutes, which is inside Render's 15-minute window.

## 1. Account

1. Go to <https://uptimerobot.com/> → **Sign Up** (free, no credit card).
2. Confirm the email, sign in to the dashboard.

## 2. Add the monitors (Free plan: 50 monitors, 5-min interval)

Dashboard → **Add New Monitor**:

| # | Monitor Type | Friendly Name | URL | Interval |
|---|--------------|---------------|-----|----------|
| 1 | HTTP(s) | supplysphere-api-health | `https://supplysphere-api.onrender.com/api/health` | 300 s |
| 2 | HTTP(s) | supplysphere-frontend | `https://supplysphere.vercel.app/` | 300 s |
| 3 | HTTP(s) | supplysphere-api-via-vercel | `https://supplysphere.vercel.app/api/health` | 300 s |

Settings per monitor:
- **Monitoring Interval:** 5 minutes (free-tier minimum)
- **Alert Contacts:** add your email (Dashboard → Alert Contacts → Add) and tick it
- Leave "Root CA check"/"Post data" off for monitor 1

Monitor 3 matters most: it exercises the exact Vercel → Render rewrite the browser uses, so a
502 from either hop raises an alert.

## 3. Verify

- Wait one interval, then **Dashboard → 3 dots green**.
- Kill the ping path deliberately: open `https://supplysphere-api.onrender.com/api/health`
  in a browser — status must be `200`.

## 4. GitHub keep-awake workflow

`.github/workflows/keep-awake.yml` can stay as a second net, but UptimeRobot is the one that
actually holds the instance awake. If you remove it:

```powershell
git rm .github/workflows/keep-awake.yml
git commit -m "chore: rely on UptimeRobot instead of GitHub cron ping"
git push
```

## Expected result

- Backend stays warm → `/api/health` returns `"warm"` context and `rss_mb` without a cold boot.
- First page load no longer shows `502 Bad Gateway`.
- You get an email within 5 minutes of a real outage instead of finding out from a user.
