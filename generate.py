from pathlib import Path
import py_compile, textwrap

code = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RatedMaps – Barcelona News Generator

Creates a static Barcelona news page for GitHub Pages.

Features:
- Fetches recent English-language Barcelona news from the GDELT DOC 2.0 API
- Up to 24 articles from the last 48 hours
- Uses a local JSON cache as fallback
- Does NOT overwrite the current index.html when both API and cache fail
- Generates a Leaflet + OpenStreetMap map
- No visible GDELT branding on the generated page
- Generates SEO metadata and ItemList JSON-LD
"""

from __future__ import annotations

import datetime as dt
import html
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

SITE_URL = "https://seoschweiz.github.io/ratedmaps-news-test/"
BRAND_URL = "https://ratedmaps.com/"
CITY = "Barcelona"
COUNTRY = "Spain"

INDEX_FILE = Path("index.html")
DATA_DIR = Path("data")
CACHE_FILE = DATA_DIR / "barcelona-news.json"

MAX_ARTICLES = 24
LOOKBACK_HOURS = 48

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def gdelt_datetime(value: dt.datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S")


def fetch_json(url: str, retries: int = 4, timeout: int = 40) -> dict:
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "RatedMapsNews/1.0 (+https://ratedmaps.com/)",
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return json.loads(raw)

        except Exception as exc:
            last_error = exc
            print(f"Fetch attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                time.sleep(min(3 * attempt, 10))

    raise RuntimeError(f"Could not fetch news data: {last_error}")


def build_gdelt_url() -> str:
    end = utc_now()
    start = end - dt.timedelta(hours=LOOKBACK_HOURS)

    params = {
        "query": '"Barcelona" sourcelang:english',
        "mode": "ArtList",
        "maxrecords": str(MAX_ARTICLES),
        "format": "json",
        "sort": "HybridRel",
        "startdatetime": gdelt_datetime(start),
        "enddatetime": gdelt_datetime(end),
    }

    return GDELT_ENDPOINT + "?" + urllib.parse.urlencode(params)


def normalize_article(item: dict) -> dict | None:
    title = (item.get("title") or "").strip()
    url = (item.get("url") or "").strip()

    if not title or not url:
        return None

    image = (
        item.get("socialimage")
        or item.get("image")
        or ""
    )

    source_country = (
        item.get("sourcecountry")
        or item.get("sourceCountry")
        or ""
    )

    language = (
        item.get("language")
        or item.get("sourcelang")
        or "English"
    )

    seen_date = (
        item.get("seendate")
        or item.get("date")
        or ""
    )

    domain = (
        item.get("domain")
        or urllib.parse.urlparse(url).netloc.replace("www.", "")
    )

    return {
        "title": title,
        "url": url,
        "image": image,
        "domain": domain,
        "source_country": source_country,
        "language": language,
        "date": seen_date,
    }


def unique_articles(items: list[dict]) -> list[dict]:
    seen_urls = set()
    seen_titles = set()
    result = []

    for item in items:
        article = normalize_article(item)
        if not article:
            continue

        url_key = article["url"].lower()
        title_key = " ".join(article["title"].lower().split())

        if url_key in seen_urls or title_key in seen_titles:
            continue

        seen_urls.add(url_key)
        seen_titles.add(title_key)
        result.append(article)

        if len(result) >= MAX_ARTICLES:
            break

    return result


def fetch_articles() -> list[dict]:
    url = build_gdelt_url()
    print("Fetching recent Barcelona news...")
    payload = fetch_json(url)

    candidates = (
        payload.get("articles")
        or payload.get("items")
        or payload.get("results")
        or []
    )

    if not isinstance(candidates, list):
        candidates = []

    articles = unique_articles(candidates)

    if not articles:
        raise RuntimeError("News API returned no usable articles.")

    return articles


def save_cache(articles: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "city": CITY,
        "country": COUNTRY,
        "updated_at": utc_now().isoformat(),
        "articles": articles,
    }

    CACHE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_cache() -> list[dict]:
    if not CACHE_FILE.exists():
        return []

    try:
        payload = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        articles = payload.get("articles", [])

        if not isinstance(articles, list):
            return []

        return unique_articles(articles)

    except Exception as exc:
        print(f"Could not read cache: {exc}")
        return []


def display_date(raw: str) -> str:
    raw = (raw or "").strip()

    if not raw:
        return "Recent"

    formats = [
        "%Y%m%dT%H%M%SZ",
        "%Y%m%d%H%M%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(raw[:len(dt.datetime.now().strftime(fmt))], fmt)
            return parsed.strftime("%d %B %Y")
        except Exception:
            pass

    if len(raw) >= 8 and raw[:8].isdigit():
        try:
            parsed = dt.datetime.strptime(raw[:8], "%Y%m%d")
            return parsed.strftime("%d %B %Y")
        except Exception:
            pass

    return "Recent"


def article_card(article: dict) -> str:
    title = esc(article["title"])
    url = esc(article["url"])
    domain = esc(article.get("domain") or "News source")
    date = esc(display_date(article.get("date", "")))
    image = (article.get("image") or "").strip()

    if image:
        media = (
            f'<a class="thumb-link" href="{url}" target="_blank" '
            f'rel="noopener noreferrer nofollow">'
            f'<img class="thumb" src="{esc(image)}" alt="{title}" loading="lazy" '
            f'onerror="this.parentElement.style.display=\'none\'">'
            f'</a>'
        )
    else:
        media = ""

    return f"""
    <article class="news-card">
      {media}
      <div class="news-body">
        <div class="meta">{date} · {domain}</div>
        <h2><a href="{url}" target="_blank" rel="noopener noreferrer nofollow">{title}</a></h2>
        <p>Latest news, stories and updates from Barcelona, Spain.</p>
        <a class="read-more" href="{url}" target="_blank" rel="noopener noreferrer nofollow">Read original article ↗</a>
      </div>
    </article>
    """


def schema_json(articles: list[dict]) -> str:
    items = []

    for pos, article in enumerate(articles, 1):
        items.append(
            {
                "@type": "ListItem",
                "position": pos,
                "name": article["title"],
                "url": article["url"],
            }
        )

    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Barcelona News from RatedMaps.com",
        "description": "Latest news, stories and updates from Barcelona, Spain.",
        "numberOfItems": len(items),
        "itemListElement": items,
    }

    return json.dumps(schema, ensure_ascii=False)


def build_html(articles: list[dict]) -> str:
    updated = utc_now().strftime("%d %B %Y, %H:%M UTC")
    cards = "\n".join(article_card(a) for a in articles)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">

<title>Barcelona News from RatedMaps.com</title>
<meta name="description" content="Latest news, stories and updates from Barcelona, Spain. Discover current Barcelona headlines and original news sources on RatedMaps.">
<link rel="canonical" href="{esc(SITE_URL)}">

<meta property="og:type" content="website">
<meta property="og:title" content="Barcelona News from RatedMaps.com">
<meta property="og:description" content="Latest news, stories and updates from Barcelona, Spain.">
<meta property="og:url" content="{esc(SITE_URL)}">

<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="Barcelona News from RatedMaps.com">
<meta name="twitter:description" content="Latest news, stories and updates from Barcelona, Spain.">

<link rel="preconnect" href="https://unpkg.com">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">

<style>
:root {{
  --bg:#f5f7f8;
  --card:#ffffff;
  --text:#17191c;
  --muted:#6a7077;
  --line:#e2e6e9;
  --accent:#d71920;
  --dark:#101214;
}}

* {{ box-sizing:border-box; }}

body {{
  margin:0;
  font-family:Arial,Helvetica,sans-serif;
  background:var(--bg);
  color:var(--text);
  line-height:1.55;
}}

a {{ color:inherit; }}

.site-header {{
  background:var(--dark);
  color:#fff;
  border-bottom:3px solid var(--accent);
}}

.header-inner {{
  max-width:1180px;
  margin:0 auto;
  padding:18px 20px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:20px;
}}

.brand {{
  color:#fff;
  text-decoration:none;
  font-size:24px;
  font-weight:900;
  letter-spacing:.3px;
}}

.brand span {{ color:#ff3a40; }}

.home-link {{
  color:#fff;
  text-decoration:none;
  font-size:14px;
  border:1px solid #555;
  padding:7px 11px;
  border-radius:999px;
}}

.hero {{
  background:linear-gradient(135deg,#151719,#33383d);
  color:#fff;
  padding:56px 20px 48px;
}}

.hero-inner {{
  max-width:1180px;
  margin:0 auto;
}}

.hero h1 {{
  margin:0 0 14px;
  font-size:clamp(36px,6vw,66px);
  line-height:1.02;
}}

.hero p {{
  margin:0;
  max-width:760px;
  font-size:19px;
  color:#eceff1;
}}

.wrap {{
  max-width:1180px;
  margin:0 auto;
  padding:34px 20px 60px;
}}

.status {{
  margin:0 0 18px;
  color:var(--muted);
  font-size:13px;
}}

.map-box {{
  background:#fff;
  border:1px solid var(--line);
  border-radius:16px;
  padding:14px;
  margin:0 0 34px;
  box-shadow:0 4px 18px rgba(0,0,0,.05);
}}

.map-title {{
  margin:2px 4px 12px;
  font-size:22px;
}}

#map {{
  width:100%;
  height:420px;
  border-radius:12px;
  overflow:hidden;
}}

.section-title {{
  font-size:30px;
  margin:0 0 18px;
}}

.news-grid {{
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:20px;
}}

.news-card {{
  background:var(--card);
  border:1px solid var(--line);
  border-radius:16px;
  overflow:hidden;
  box-shadow:0 4px 16px rgba(0,0,0,.04);
}}

.thumb-link {{
  display:block;
  background:#e8ebed;
}}

.thumb {{
  width:100%;
  aspect-ratio:16/9;
  object-fit:cover;
  display:block;
}}

.news-body {{
  padding:17px;
}}

.meta {{
  color:var(--muted);
  font-size:12px;
  margin-bottom:8px;
}}

.news-card h2 {{
  font-size:19px;
  line-height:1.3;
  margin:0 0 10px;
}}

.news-card h2 a {{
  text-decoration:none;
}}

.news-card h2 a:hover {{
  text-decoration:underline;
}}

.news-card p {{
  margin:0 0 14px;
  color:#4b5157;
  font-size:14px;
}}

.read-more {{
  display:inline-block;
  color:var(--accent);
  text-decoration:none;
  font-weight:700;
  font-size:14px;
}}

footer {{
  background:#fff;
  border-top:1px solid var(--line);
  color:var(--muted);
}}

.footer-inner {{
  max-width:1180px;
  margin:0 auto;
  padding:28px 20px;
  font-size:13px;
}}

.footer-inner a {{
  color:inherit;
}}

@media (max-width:900px) {{
  .news-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
}}

@media (max-width:620px) {{
  .header-inner {{
    align-items:flex-start;
    flex-direction:column;
  }}

  .hero {{
    padding-top:40px;
    padding-bottom:38px;
  }}

  .news-grid {{
    grid-template-columns:1fr;
  }}

  #map {{
    height:340px;
  }}
}}
</style>

<script type="application/ld+json">
{schema_json(articles)}
</script>
</head>

<body>

<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="{esc(BRAND_URL)}">Rated<span>Maps</span>.com</a>
    <a class="home-link" href="{esc(BRAND_URL)}">Visit RatedMaps.com ↗</a>
  </div>
</header>

<section class="hero">
  <div class="hero-inner">
    <h1>Barcelona News from RatedMaps.com</h1>
    <p>Latest news, stories and updates from Barcelona, Spain.</p>
  </div>
</section>

<main class="wrap">

  <p class="status">Updated {esc(updated)} · {len(articles)} current stories</p>

  <section class="map-box" aria-label="Barcelona map">
    <h2 class="map-title">Barcelona News Map</h2>
    <div id="map"></div>
  </section>

  <h2 class="section-title">Latest Barcelona News</h2>

  <section class="news-grid">
    {cards}
  </section>

</main>

<footer>
  <div class="footer-inner">
    © {utc_now().year} RatedMaps.com · Barcelona, Spain · News links lead to the original publishers.
  </div>
</footer>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const map = L.map('map').setView([41.3874, 2.1686], 12);

L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);

L.marker([41.3874, 2.1686])
  .addTo(map)
  .bindPopup('<strong>Barcelona</strong><br>Latest news, stories and updates.')
  .openPopup();
</script>

</body>
</html>
"""


def main() -> None:
    articles = []

    try:
        articles = fetch_articles()
        save_cache(articles)
        print(f"Fetched and cached {len(articles)} articles.")

    except Exception as exc:
        print(f"Live fetch failed: {exc}")
        articles = load_cache()

        if articles:
            print(f"Using {len(articles)} cached articles.")
        else:
            print("No live data and no usable cache available.")
            print("Existing index.html will NOT be overwritten.")
            return

    html_output = build_html(articles)
    INDEX_FILE.write_text(html_output, encoding="utf-8")

    print(f"Done. Wrote {INDEX_FILE} with {len(articles)} articles.")


if __name__ == "__main__":
    main()
'''

path = Path("/mnt/data/generate.py")
path.write_text(code, encoding="utf-8")
py_compile.compile(str(path), doraise=True)
print("Created and syntax-checked:", path)
