# Your Sourcing Digest — Setup Guide

This is a v1 pilot: it currently checks **one site (Joe's New Balance Outlet)**. Once we confirm
it's finding real listings correctly, we add your other sites one at a time.

Every step below is one-time setup. No coding required, just following along.

---

## 1. Create a free GitHub account (skip if you have one)

Go to github.com and sign up. Free tier is all you need.

## 2. Create a new repository

- Click the **+** in the top right → **New repository**
- Name it something like `sourcing-digest`
- Set it to **Private** (so your setup isn't public)
- Click **Create repository**

## 3. Upload these files

On the new repo's page, click **"uploading an existing file"** and drag in this entire folder
(keep the folder structure — `scrapers/`, `.github/workflows/`, `main.py`, `requirements.txt`).

## 4. Get an Anthropic API key (for the AI curation step)

- Go to **console.anthropic.com** and sign in (or create an account)
- Go to **Settings → Billing** and add a small amount of prepaid credit (e.g. $5)
- **Important — set a spending limit:** in Billing settings, set a monthly spend cap so this can
  never exceed what you're comfortable with. This is separate from your claude.ai subscription.
- Go to **Settings → API Keys** → create a new key → copy it (you won't see it again)

## 5. Get a free Resend account (for sending you the email)

- Go to **resend.com** and sign up (free tier: 100 emails/day, more than enough for once-a-day)
- Go to **API Keys** → create a key → copy it
- (Optional, more setup: verify your own domain to send "from" your own address. Skipping this is
  fine — the default sandbox sender works for getting started.)

## 6. Add your secrets to GitHub

In your repo: **Settings → Secrets and variables → Actions → New repository secret**. Add these
three, one at a time:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | the key from step 4 |
| `RESEND_API_KEY` | the key from step 5 |
| `EMAIL_TO` | the email address you want the digest sent to |

## 7. Test it manually before waiting for the schedule

- Go to the **Actions** tab in your repo
- Click **"Daily Sourcing Scan"** on the left
- Click **"Run workflow"** → **Run workflow** (green button)
- Wait ~30-60 seconds, then click into the run to see the log output
- Check your email

## 8. If something looks wrong

Copy the error text from the Actions log and send it back to me — I'll fix the actual cause. The
most likely early issue is the scraper's selectors not matching the site's current markup (sites
change their HTML sometimes) — that's a quick fix once I see what it's actually returning, not a
sign anything is fundamentally broken.

---

## What happens automatically

Once secrets are set, this runs on its own every day at the scheduled time (edit the `cron` line
in `.github/workflows/daily-scan.yml` if you want a different time — the current one is roughly
early morning US time, in UTC).

## Editing your watchlist

Open `main.py` and edit the `WATCHLIST_KEYWORDS` list near the top — add or remove model
keywords any time, no other changes needed. Commit the change on GitHub and the next scheduled
run picks it up automatically.

## Adding more sites later

Each site gets its own file in `scrapers/`, following the same pattern as `joes_nb.py`. Send me
the next site once this one's confirmed working and I'll build it the same way — testing against
the real page structure first so it's not a guess.

## Building your historical sale-pattern record

Every run saves that day's filtered listings into a `history/` folder in your repo, and the
workflow commits it back automatically. This is the start of building your own record of when
sites actually run their deepest sales — worth nothing after a week, genuinely useful after a
few months. If you already know roughly when certain sites have run big sales in past years
(e.g. "Nordstrom Rack Friends & Family is usually March and October"), tell me and I'll add
those as calendar hints so the digest can flag "this is historically about when X tends to drop."
