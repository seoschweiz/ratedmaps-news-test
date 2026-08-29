#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import html
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CITY = "Barcelona"
COUNTRY = "Spain"

MAX_ARTICLES = 24
TIMESPAN = "48h"

CACHE_DIR = "data"
CACHE_FILE = os.path.join(CACHE_DIR, "barcelona-news.json")
OUTPUT_FILE = "index.html"

GDELT_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

REQUEST_TIMEOUT = 75
MAX_RETRIES = 3
RETRY_WAIT = 15

BARCELONA_LAT = 41.3874
BARCELONA_LON = 2.1686

USER_AGENT = (
    "Mozilla/5.0 (compatible; RatedMapsNewsTest/1.3; "
    "+https://seoschweiz.github.io/ratedmaps-news-test/)"
)

def fetch_url(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
    )

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"GDELT request attempt {attempt}/{MAX_RETRIES}")

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                content = response.read().decode("utf-8", errors="replace")
                print("GDELT connection successful.")
                return content
        except Exception as error:
            last_error = error
            print(f"Attempt {attempt} failed: {error}")

            if attempt < MAX_RETRIES:
                print(f"Waiting {RETRY_WAIT} seconds before retry...")
                time.sleep(RETRY_WAIT)

    raise RuntimeError(
        f"GDELT failed after {MAX_RETRIES} attempts: {last_error}"
    )

def gdelt_url():
    params = {
        "query": '"Barcelona" sourcelang:english',
        "mode": "artlist",
        "maxrecords": str(MAX_ARTICLES),
        "timespan": TIMESPAN,
        "sort": "datedesc",
        "format": "json",
    }

    return GDELT_ENDPOINT + "?" + urllib.parse.urlencode(params)

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return []

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            print(f"Cache contains {len(data)} articles.")
            return data
    except Exception as error:
        print("Could not read cache:", error)

    return []

def save_cache(articles):
    os.makedirs(CACHE_DIR, exist_ok=True)

    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(articles, file, ensure_ascii=False, indent=2)

    print(f"Saved {len(articles)} articles to cache.")

def clean_text(value):
    if not value:
        return ""
    return " ".join(str(value).split())

def safe(value):
    return html.escape(clean_text(value), quote=True)

def normalize_date(value):
    if not value:
        return ""

    value = str(value).strip()

    for fmt in (
        "%Y%m%dT%H%M%SZ",
        "%Y%m%d%H%M%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%d %B %Y · %H:%M UTC")
        except ValueError:
            pass

    return value

def domain_from_url(url):
    try:
        return urllib.parse.urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def usable_article(article):
    title = clean_text(article.get("title"))
    url = clean_text(article.get("url"))
    return bool(title and url.startswith(("http://", "https://")))

def prepare_articles(raw_articles):
    articles = []
    seen_urls = set()

    for item in raw_articles:
        if not usable_article(item):
            continue

        url = clean_text(item.get("url"))

        if url in seen_urls:
            continue

        seen_urls.add(url)

        articles.append({
            "title": clean_text(item.get("title")),
            "url": url,
            "image": clean_text(item.get("socialimage")),
            "date": clean_text(item.get("seendate")),
            "domain": clean_text(item.get("domain")) or domain_from_url(url),
            "language": clean_text(item.get("language")),
            "country": clean_text(item.get("sourcecountry")),
        })

    return articles[:MAX_ARTICLES]

def get_articles():
    url = gdelt_url()

    print()
    print("Fetching GDELT:")
    print(url)
    print()

    try:
        text = fetch_url(url)
        data = json.loads(text)
        articles = prepare_articles(data.get("articles", []))

        if articles:
            print(f"Received {len(articles)} articles from GDELT.")
            save_cache(articles)
            return articles

        print("GDELT returned no usable articles.")
    except Exception as error:
        print()
        print("GDELT request failed:")
        print(error)
        print()

    cached = load_cache()

    if cached:
        print(f"Using {len(cached)} cached articles.")
        return cached

    print("No cache available. Existing page will be kept.")
    return None

def article_card(article):
    title = safe(article.get("title"))
    url = safe(article.get("url"))
    domain = safe(article.get("domain"))
    language = safe(article.get("language"))
    country = safe(article.get("country"))
    date = safe(normalize_date(article.get("date")))
    image = safe(article.get("image"))

    meta = " · ".join([x for x in (domain, country, language) if x])

    if image:
        image_html = f"""
        <div class="news-image-wrap">
          <img
            class="news-image"
            src="{image}"
            alt="{title}"
            loading="lazy"
            referrerpolicy="no-referrer"
            onerror="this.parentElement.classList.add('image-error'); this.remove();"
          >
          <div class="image-fallback">Barcelona News</div>
        </div>
        """
    else:
        image_html = """
        <div class="news-image-wrap image-error">
          <div class="image-fallback">Barcelona News</div>
        </div>
        """

    return f"""
    <article class="news-card">
      {image_html}
      <div class="news-content">
        <div class="news-meta">{meta}</div>
        <h2>
          <a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>
        </h2>
        <div class="news-date">{date}</div>
        <p class="news-description">
          Latest English-language coverage mentioning Barcelona
          from international and local news sources monitored by GDELT.
        </p>
        <a class="read-more" href="{url}" target="_blank" rel="noopener noreferrer">
          Read original article →
        </a>
      </div>
    </article>
    """

def schema_data(articles):
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Latest Barcelona News",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": position,
                "url": article.get("url", ""),
                "name": article.get("title", ""),
            }
            for position, article in enumerate(articles[:20], start=1)
        ],
    }

def build_html(articles):
    generated = datetime.now(timezone.utc).strftime("%d %B %Y · %H:%M UTC")
    cards = "\n".join(article_card(article) for article in articles)
    schema = json.dumps(schema_data(articles), ensure_ascii=False).replace("</", "<\\/")
    article_count = len(articles)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>Barcelona News Map | Latest Barcelona News & Updates</title>

<meta
  name="description"
  content="Latest Barcelona news from local and international media on an interactive Barcelona map. Discover current stories and worldwide coverage mentioning Barcelona."
>

<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="theme-color" content="#d71920">

<link
  rel="stylesheet"
  href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIINfQ3ynqMS7c5R5QFZxkIajPPbM4B4N0g="
  crossorigin=""
>

<script type="application/ld+json">
{schema}
</script>

<style>
* {{ box-sizing: border-box; }}

body {{
  margin: 0;
  background: #f4f6f8;
  color: #17212b;
  font-family: Arial, Helvetica, sans-serif;
}}

a {{ color: inherit; }}

header {{
  background: #ffffff;
  border-bottom: 1px solid #e1e5e8;
}}

.header-inner {{
  max-width: 1180px;
  margin: auto;
  padding: 18px 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}}

.logo {{
  font-size: 25px;
  font-weight: 800;
  text-decoration: none;
}}

.logo span {{ color: #d71920; }}

.city-label {{
  font-size: 14px;
  color: #65717b;
}}

main {{
  max-width: 1180px;
  margin: auto;
  padding: 34px 20px 60px;
}}

.hero {{
  background: #ffffff;
  padding: 34px;
  border-radius: 18px;
  box-shadow: 0 2px 14px rgba(0,0,0,.055);
  margin-bottom: 24px;
}}

h1 {{
  font-size: clamp(32px,5vw,48px);
  line-height: 1.05;
  margin: 0 0 14px;
}}

.intro {{
  max-width: 780px;
  font-size: 18px;
  line-height: 1.65;
  color: #596571;
  margin: 0;
}}

.status {{
  margin-top: 20px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}

.badge {{
  display: inline-block;
  padding: 7px 11px;
  border-radius: 999px;
  background: #f1f3f5;
  font-size: 13px;
  color: #505b65;
}}

.badge-live {{
  background: #fff0f0;
  color: #b4141a;
  font-weight: 700;
}}

#news-map {{
  width: 100%;
  height: 420px;
  border-radius: 18px;
  overflow: hidden;
  margin-bottom: 38px;
  border: 1px solid #dfe5e8;
  box-shadow: 0 2px 14px rgba(0,0,0,.05);
  background: #dfe5e8;
}}

.map-caption {{
  font-size: 13px;
  color: #71808c;
  margin-top: -25px;
  margin-bottom: 35px;
}}

.section-head {{
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 20px;
}}

.section-head h2 {{
  margin: 0;
  font-size: 30px;
}}

.updated {{
  color: #71808c;
  font-size: 13px;
}}

.news-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit,minmax(290px,1fr));
  gap: 20px;
}}

.news-card {{
  background: #ffffff;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 13px rgba(0,0,0,.06);
  display: flex;
  flex-direction: column;
  min-width: 0;
}}

.news-image-wrap {{
  width: 100%;
  height: 160px;
  background: #e5eaed;
  overflow: hidden;
  position: relative;
}}

.news-image {{
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}}

.image-fallback {{
  position: absolute;
  inset: 0;
  display: none;
  align-items: center;
  justify-content: center;
  background: #e8edef;
  color: #7a858e;
  font-size: 15px;
  font-weight: 700;
}}

.image-error .image-fallback {{
  display: flex;
}}

.news-content {{
  padding: 19px;
  display: flex;
  flex-direction: column;
  flex: 1;
}}

.news-meta {{
  color: #d71920;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .03em;
  min-height: 15px;
}}

.news-card h2 {{
  font-size: 20px;
  line-height: 1.35;
  margin: 9px 0;
}}

.news-card h2 a {{
  text-decoration: none;
}}

.news-card h2 a:hover {{
  text-decoration: underline;
}}

.news-date {{
  color: #89939b;
  font-size: 12px;
  margin-bottom: 13px;
}}

.news-description {{
  color: #596571;
  font-size: 14px;
  line-height: 1.55;
  margin: 0 0 18px;
}}

.read-more {{
  display: inline-block;
  margin-top: auto;
  font-size: 14px;
  font-weight: 700;
  color: #d71920;
  text-decoration: none;
}}

.seo-text {{
  margin-top: 45px;
  background: white;
  padding: 30px;
  border-radius: 16px;
  line-height: 1.7;
  color: #56626c;
}}

.seo-text h2 {{
  color: #17212b;
  margin-top: 0;
}}

footer {{
  background: white;
  border-top: 1px solid #e1e5e8;
  color: #78838c;
  text-align: center;
  padding: 28px 20px;
  font-size: 13px;
}}

@media(max-width:650px) {{
  .header-inner {{ padding: 15px 18px; }}
  .logo {{ font-size: 21px; }}
  main {{ padding: 22px 14px 45px; }}
  .hero {{ padding: 25px 21px; }}
  .intro {{ font-size: 16px; }}
  #news-map {{ height: 320px; }}
  .section-head {{ display: block; }}
  .updated {{ margin-top: 8px; }}
  .news-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>

<body>

<header>
  <div class="header-inner">
    <a class="logo" href="./">Rated<span>Maps</span> News</a>
    <div class="city-label">Barcelona · Spain</div>
  </div>
</header>

<main>

<section class="hero">
  <h1>Barcelona News Map</h1>

  <p class="intro">
    Discover the latest English-language news mentioning
    Barcelona from local and international media.
  </p>

  <div class="status">
    <span class="badge badge-live">● LIVE</span>
    <span class="badge">{article_count} articles</span>
    <span class="badge">Last 48 hours</span>
  </div>
</section>

<div id="news-map" aria-label="Interactive Barcelona news map"></div>

<div class="map-caption">
  Interactive map powered by Leaflet and OpenStreetMap.
  Individual news locations will be added in the next step.
</div>

<section>
  <div class="section-head">
    <h2>Latest Barcelona News</h2>
    <div class="updated">Updated {generated}</div>
  </div>

  <div class="news-grid">
    {cards}
  </div>
</section>

<section class="seo-text">
  <h2>Latest news about Barcelona</h2>

  <p>
    Barcelona is continuously covered by newspapers,
    broadcasters and online media around the world.
    This page brings together recent English-language
    news references mentioning Barcelona.
  </p>

  <p>
    Coverage may include Barcelona politics, tourism,
    culture, business, transport, sport, events,
    restaurants, neighborhoods and other current
    developments. Every story links to the original publisher.
  </p>
</section>

</main>

<footer>
RatedMaps News · Barcelona
<br><br>
News discovery powered by GDELT.
Map powered by Leaflet and OpenStreetMap.
Original articles remain on their respective publishers' websites.
</footer>

<script
  src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
  crossorigin=""
></script>

<script>
const map = L.map(
  "news-map",
  {{
    scrollWheelZoom: false
  }}
).setView(
  [{BARCELONA_LAT}, {BARCELONA_LON}],
  12
);

L.tileLayer(
  "https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
  {{
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }}
).addTo(map);

const barcelonaMarker = L.marker(
  [{BARCELONA_LAT}, {BARCELONA_LON}]
).addTo(map);

barcelonaMarker.bindPopup(
  "<strong>Barcelona News</strong><br>{article_count} current articles"
);
</script>

</body>
</html>
"""

def main():
    print("=" * 60)
    print("RatedMaps Barcelona News Generator")
    print("=" * 60)

    articles = get_articles()

    if articles is None:
        print()
        print("No new data and no cache.")
        print("Existing index.html will NOT be overwritten.")
        print("Workflow completed safely.")
        return

    page = build_html(articles)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write(page)

    print()
    print(f"Generated: {OUTPUT_FILE}")
    print(f"Articles: {len(articles)}")
    print("Done.")

if __name__ == "__main__":
    main()
