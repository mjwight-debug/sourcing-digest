"""
Scraper for Joe's New Balance Outlet.
Site is server-rendered (Salesforce Commerce Cloud), so a plain requests + BeautifulSoup
approach works without needing a headless browser.

Returns a list of dicts: {retailer, brand, model, price, originalPrice, discountPercent, url}
"""
import re
import requests
from bs4 import BeautifulSoup

RETAILER_NAME = "Joe's New Balance Outlet"

# Category pages to check. Add more as needed (e.g. women's, lifestyle, trail).
PAGES = [
    "https://www.joesnewbalanceoutlet.com/men/shoes/running/",
    "https://www.joesnewbalanceoutlet.com/men/deals/new-markdowns/",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Referer": "https://www.google.com/",
}

# Matches: "SAVE $85.00 | 52% off Price reduced to $79.99 from $164.99"
SAVE_PATTERN = re.compile(
    r"SAVE\s*\$[\d.,]+\s*\|\s*(\d+)%\s*off\s*Price reduced to\s*\$([\d.,]+)\s*from\s*\$([\d.,]+)",
    re.IGNORECASE
)
# Matches: "Extra 30% off ABZORB 2000", "Extra 40% off select footwear", etc.
SITEWIDE_PROMO_PATTERN = re.compile(r"Extra\s+\d+%\s+off\s+[A-Za-z0-9 ]+", re.IGNORECASE)
# Matches plain price with no discount shown, e.g. "$89.99"
PLAIN_PRICE_PATTERN = re.compile(r"\$([\d.,]+)")


_session = requests.Session()
_session.headers.update(HEADERS)


def fetch_page(url):
    try:
        resp = _session.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[joes_nb] Failed to fetch {url}: {e}")
        return None


def parse_listings(html, page_url):
    """
    Parses product tiles. Selectors below are a best-effort based on common
    Salesforce Commerce Cloud storefront markup (product-tile / pdp-link classes).
    If the site's markup differs, this may return zero results — check the
    debug output and we'll adjust the selectors together.
    """
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Try the common SFCC product tile container first.
    tiles = soup.select("div.product-tile, div[class*='product-tile']")

    if not tiles:
        print(f"[joes_nb] No product tiles found on {page_url} with primary selector — "
              f"site markup may have changed. Falling back to text-block scan.")
        return parse_listings_fallback(soup, page_url)

    for tile in tiles:
        name_el = tile.select_one("a.pdp-link, a[class*='pdp-link'], a[class*='name-link']")
        name = name_el.get_text(strip=True) if name_el else None
        link = name_el["href"] if name_el and name_el.has_attr("href") else None
        if link and link.startswith("/"):
            link = "https://www.joesnewbalanceoutlet.com" + link

        tile_text = tile.get_text(separator=" ", strip=True)
        match = SAVE_PATTERN.search(tile_text)

        if match:
            discount_pct, sale_price, orig_price = match.groups()
            results.append({
                "retailer": RETAILER_NAME,
                "brand": "New Balance",
                "model": name or "Unknown model",
                "price": float(sale_price.replace(",", "")),
                "originalPrice": float(orig_price.replace(",", "")),
                "discountPercent": float(discount_pct),
                "url": link or page_url,
            })
        else:
            # No explicit markdown shown — grab first plain price as a fallback signal.
            price_match = PLAIN_PRICE_PATTERN.search(tile_text)
            if name and price_match:
                results.append({
                    "retailer": RETAILER_NAME,
                    "brand": "New Balance",
                    "model": name,
                    "price": float(price_match.group(1).replace(",", "")),
                    "originalPrice": None,
                    "discountPercent": None,
                    "url": link or page_url,
                })

    return results


def parse_listings_fallback(soup, page_url):
    """
    Fallback: scan raw page text for the "ModelName ... SAVE $X | Y% off ..." pattern
    directly, without relying on tile container classes. Less precise (may miss the
    exact model name association) but still surfaces discount data if the primary
    selector breaks.
    """
    results = []
    full_text = soup.get_text(separator="\n", strip=True)
    lines = full_text.split("\n")
    for i, line in enumerate(lines):
        match = SAVE_PATTERN.search(line)
        if match:
            discount_pct, sale_price, orig_price = match.groups()
            name = None
            for j in range(i - 1, max(i - 5, -1), -1):
                candidate = lines[j].strip()
                if candidate and len(candidate) > 3 and "$" not in candidate:
                    name = candidate
                    break
            results.append({
                "retailer": RETAILER_NAME,
                "brand": "New Balance",
                "model": name or "Unknown model (check page manually)",
                "price": float(sale_price.replace(",", "")),
                "originalPrice": float(orig_price.replace(",", "")),
                "discountPercent": float(discount_pct),
                "url": page_url,
            })
    return results


def find_sitewide_promos(html):
    """Detects sitewide/stacking promo banners like 'Extra 40% off select footwear' —
    these stack on top of individual item markdowns, which matters for your actual
    out-the-door price."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    matches = SITEWIDE_PROMO_PATTERN.findall(text)
    seen = set()
    unique = []
    for m in matches:
        m_clean = m.strip()
        if m_clean not in seen:
            seen.add(m_clean)
            unique.append(m_clean)
    return unique


def scrape():
    all_results = []
    all_promos = set()
    for page_url in PAGES:
        html = fetch_page(page_url)
        if not html:
            continue
        listings = parse_listings(html, page_url)
        promos = find_sitewide_promos(html)
        all_promos.update(promos)
        print(f"[joes_nb] {page_url} -> {len(listings)} listings found, "
              f"{len(promos)} sitewide promos detected")
        all_results.extend(listings)

    if all_promos:
        promo_note = " | ".join(sorted(all_promos))
        for item in all_results:
            item["sitewidePromo"] = promo_note

    return all_results


if __name__ == "__main__":
    import json
    data = scrape()
    print(json.dumps(data, indent=2))
