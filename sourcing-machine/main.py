"""
Daily sourcing digest — orchestrator.

1. Runs each scraper module in scrapers/ to collect raw listings.
2. Filters to your watchlist of brands/models (cheap, fast pre-filter, no AI cost).
3. Sends the filtered shortlist to Claude for curation/ranking (small, capped cost).
4. Emails you a clean digest via Resend.

Run manually with: python main.py
Runs automatically via .github/workflows/daily-scan.yml on a schedule.
"""
import os
import json
import requests
from datetime import datetime, timezone

from scrapers import joes_nb
# As we add more sites, import and register them below in SCRAPERS.

SCRAPERS = [
    joes_nb,
    # dsw, scheels, jdsports, etc. get added here once built + tested
]

HISTORY_DIR = "history"

# --- Your watchlist: edit this list any time, no code changes needed elsewhere ---
WATCHLIST_KEYWORDS = [
    "ghost", "adrenaline",           # Brooks
    "clifton", "bondi",              # Hoka
    "vomero", "pegasus", "p-6000", "p6000", "moto 2k", "metcon",  # Nike
    "1080",                          # New Balance
    "gel nimbus", "nimbus", "gel cumulus", "cumulus",  # Asics
    "cloud",                         # On Running (their models are "Cloud X", "Cloudmonster" etc)
    # Saucony higher-end models — add specific ones you chase, e.g. "endorphin", "triumph"
    "endorphin", "triumph", "guide",
    # Keen / Merrell — add specific models once you know which ones you actually chase
]

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
EMAIL_TO = os.environ.get("EMAIL_TO")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "digest@resend.dev")  # Resend's free sandbox sender


def collect_all_listings():
    all_listings = []
    for scraper_module in SCRAPERS:
        try:
            listings = scraper_module.scrape()
            all_listings.extend(listings)
        except Exception as e:
            print(f"[main] Scraper {scraper_module.__name__} failed: {e}")
    return all_listings


def filter_by_watchlist(listings):
    filtered = []
    for item in listings:
        model_text = (item.get("model") or "").lower()
        if any(kw in model_text for kw in WATCHLIST_KEYWORDS):
            filtered.append(item)
    return filtered


def curate_with_claude(listings):
    """Send the pre-filtered shortlist to Claude for ranking/curation.
    This is the ONLY step that costs money — and it's one call on a small
    list (not per-page, not per-site), so cost stays low and predictable."""
    if not listings:
        return "No watchlist matches found today across the sites checked."

    if not ANTHROPIC_API_KEY:
        print("[main] No ANTHROPIC_API_KEY set — skipping AI curation, returning raw list.")
        return json.dumps(listings, indent=2)

    prompt = f"""Here is a raw list of shoe deals scraped today from outlet/clearance sites, already
pre-filtered to models I care about. Some items include a "sitewidePromo" field — that's an
additional stacking discount active site-wide right now (e.g. "extra 40% off select footwear")
that applies ON TOP OF the listed sale price at checkout. Factor that into how good a deal actually
is — a modest markdown plus a big stacking promo can be a better real deal than a deep markdown with
no stacking promo.

{json.dumps(listings, indent=2)}

I resell shoes on Amazon FBA/FBM. I'm not looking for a strict rule (like "X% off") — I want your
judgment on which of these are actually worth me looking at closer, considering: how in-demand the
model/colorway typically is for resale, whether the discount looks genuinely deep vs a mediocre
"sale" markup, any active stacking promo noted above, and anything about size/color availability
implied in the listing. It's fine to say few or none are worth it if that's true today.

Write a short, plain-text morning digest (not JSON) — a ranked list of the best few, each with a
one-line reason, followed by a one-line note on anything you're skipping and why. Keep it skimmable,
I'll click through myself to investigate anything that catches my eye."""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks) if text_blocks else "Claude returned no text — check raw listings below."
    except Exception as e:
        print(f"[main] Claude curation call failed: {e}")
        return f"AI curation failed ({e}) — raw filtered listings:\n\n{json.dumps(listings, indent=2)}"


def send_email(digest_text, raw_count, filtered_count):
    if not RESEND_API_KEY or not EMAIL_TO:
        print("[main] RESEND_API_KEY or EMAIL_TO not set — printing digest instead of emailing.")
        print(digest_text)
        return

    html_body = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto;">
      <h2 style="margin-bottom:4px;">Sourcing Digest</h2>
      <p style="color:#888; font-size:12px; margin-top:0;">
        Scanned {raw_count} listings across sites, {filtered_count} matched your watchlist.
      </p>
      <pre style="white-space: pre-wrap; font-family: -apple-system, sans-serif; font-size: 14px; line-height: 1.5;">{digest_text}</pre>
    </div>
    """

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": EMAIL_FROM,
                "to": [EMAIL_TO],
                "subject": "Your morning sourcing digest",
                "html": html_body,
            },
            timeout=30,
        )
        resp.raise_for_status()
        print("[main] Email sent successfully.")
    except Exception as e:
        print(f"[main] Email send failed: {e}")
        print(digest_text)


def log_history(raw_listings, filtered_listings):
    """Saves today's scan to history/ so we can start spotting seasonal patterns
    (e.g. 'this site tends to drop deep in March') once enough days accumulate.
    This only works if the workflow also commits the history/ folder back to the
    repo — see the README note on enabling that."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filepath = os.path.join(HISTORY_DIR, f"{today}.json")
    with open(filepath, "w") as f:
        json.dump({
            "date": today,
            "raw_count": len(raw_listings),
            "filtered_count": len(filtered_listings),
            "filtered_listings": filtered_listings,
        }, f, indent=2)
    print(f"[main] Logged today's scan to {filepath}")


def main():
    print("[main] Collecting listings...")
    raw = collect_all_listings()
    print(f"[main] {len(raw)} total raw listings collected.")

    filtered = filter_by_watchlist(raw)
    print(f"[main] {len(filtered)} listings matched your watchlist.")

    log_history(raw, filtered)

    digest = curate_with_claude(filtered)
    send_email(digest, len(raw), len(filtered))


if __name__ == "__main__":
    main()
