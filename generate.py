#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""VideoVediVinci – Chicago generator.

Generates a static multilingual Chicago video portal from YouTube search results.
Environment variables:
  YOUTUBE_API_KEY
  GOOGLE_TRANSLATE_API_KEY
Output directory:
  dist/
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import shutil
import hashlib
import urllib.parse
import urllib.request
from pathlib import Path

DOMAIN = "https://videovedivinci.com"
CITY = "Chicago"
CITY_SLUG = "chicago"
COUNTRY = "United States"
OUT = Path("dist")
ARCHIVE_FILE = Path("archive.json")
SEO_LIBRARY_FILE = Path("seo_keywords_en.json")

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()
GOOGLE_TRANSLATE_API_KEY = os.environ.get("GOOGLE_TRANSLATE_API_KEY", "").strip()

VIDEOS_PER_CATEGORY = 5
SEARCH_DAYS_BACK = 30

LANGUAGES = {
    "en": {"name": "English", "target": "en", "dir": "ltr"},
    "de": {"name": "Deutsch", "target": "de", "dir": "ltr"},
    "fr": {"name": "Français", "target": "fr", "dir": "ltr"},
    "it": {"name": "Italiano", "target": "it", "dir": "ltr"},
    "es": {"name": "Español", "target": "es", "dir": "ltr"},
    "pt": {"name": "Português", "target": "pt", "dir": "ltr"},
    "ja": {"name": "日本語", "target": "ja", "dir": "ltr"},
    "ar": {"name": "العربية", "target": "ar", "dir": "rtl"},
}

CATEGORIES = [
    {"id": "CAT01", "slug": "news", "name": "News", "query": "Chicago news"},
    {"id": "CAT02", "slug": "restaurants-food", "name": "Restaurants & Food", "query": "Chicago restaurants food"},
    {"id": "CAT03", "slug": "bars-nightlife", "name": "Bars & Nightlife", "query": "Chicago bars nightlife"},
    {"id": "CAT04", "slug": "events", "name": "Events", "query": "Chicago events"},
    {"id": "CAT05", "slug": "museums", "name": "Museums", "query": "Chicago museums"},
    {"id": "CAT06", "slug": "art-street-art", "name": "Art & Street Art", "query": "Chicago art street art"},
    {"id": "CAT07", "slug": "sports", "name": "Sports", "query": "Chicago sports"},
    {"id": "CAT08", "slug": "travel-tourism", "name": "Travel & Tourism", "query": "Chicago travel tourism"},
    {"id": "CAT09", "slug": "hotels", "name": "Hotels", "query": "Chicago hotels"},
    {"id": "CAT10", "slug": "real-estate", "name": "Real Estate", "query": "Chicago real estate"},
    {"id": "CAT11", "slug": "shopping", "name": "Shopping", "query": "Chicago shopping"},
    {"id": "CAT12", "slug": "jobs-business", "name": "Jobs & Business", "query": "Chicago jobs business"},
    {"id": "CAT13", "slug": "music-concerts", "name": "Music & Concerts", "query": "Chicago music concerts"},
    {"id": "CAT14", "slug": "lifestyle", "name": "Lifestyle", "query": "Chicago lifestyle"},
    {"id": "CAT15", "slug": "things-to-do", "name": "Things to Do", "query": "Chicago things to do"},
    {"id": "CAT16", "slug": "transport-mobility", "name": "Transport & Mobility", "query": "Chicago transport mobility"},
    {"id": "CAT17", "slug": "nature-outdoors", "name": "Nature & Outdoors", "query": "Chicago nature outdoors"},
]

UI = {
    "en": {"latest":"Latest Chicago Videos","intro":"Discover recent videos about Chicago across news, food, nightlife, culture, sports, travel and more.","watch":"Watch video","back":"Back to category","published":"Published","source":"Source","categories":"Explore 17 Chicago categories","more":"More Chicago videos","archive":"Video Archive"},
    "de": {"latest":"Neueste Videos aus Chicago","intro":"Entdecke aktuelle Videos über Chicago zu News, Essen, Nachtleben, Kultur, Sport, Reisen und mehr.","watch":"Video ansehen","back":"Zurück zur Kategorie","published":"Veröffentlicht","source":"Quelle","categories":"17 Chicago-Kategorien entdecken","more":"Weitere Chicago-Videos","archive":"Video-Archiv"},
    "fr": {"latest":"Dernières vidéos de Chicago","intro":"Découvrez des vidéos récentes sur Chicago : actualités, gastronomie, vie nocturne, culture, sport, voyage et plus.","watch":"Voir la vidéo","back":"Retour à la catégorie","published":"Publié","source":"Source","categories":"Explorer 17 catégories de Chicago","more":"Plus de vidéos sur Chicago","archive":"Archives vidéo"},
    "it": {"latest":"Ultimi video di Chicago","intro":"Scopri video recenti su Chicago: notizie, cibo, vita notturna, cultura, sport, viaggi e altro.","watch":"Guarda il video","back":"Torna alla categoria","published":"Pubblicato","source":"Fonte","categories":"Esplora 17 categorie di Chicago","more":"Altri video su Chicago","archive":"Archivio video"},
    "es": {"latest":"Últimos vídeos de Chicago","intro":"Descubre vídeos recientes sobre Chicago: noticias, gastronomía, vida nocturna, cultura, deporte, viajes y más.","watch":"Ver vídeo","back":"Volver a la categoría","published":"Publicado","source":"Fuente","categories":"Explora 17 categorías de Chicago","more":"Más vídeos de Chicago","archive":"Archivo de vídeos"},
    "pt": {"latest":"Vídeos mais recentes de Chicago","intro":"Descubra vídeos recentes sobre Chicago: notícias, gastronomia, vida noturna, cultura, esportes, viagens e muito mais.","watch":"Ver vídeo","back":"Voltar à categoria","published":"Publicado","source":"Fonte","categories":"Explore 17 categorias de Chicago","more":"Mais vídeos de Chicago","archive":"Arquivo de vídeos"},
    "ja": {"latest":"シカゴの最新動画","intro":"ニュース、グルメ、ナイトライフ、文化、スポーツ、旅行など、シカゴに関する最新動画を紹介します。","watch":"動画を見る","back":"カテゴリーに戻る","published":"公開日","source":"出典","categories":"シカゴの17カテゴリーを見る","more":"シカゴのその他の動画","archive":"動画アーカイブ"},
    "ar": {"latest":"أحدث فيديوهات شيكاغو","intro":"اكتشف أحدث الفيديوهات عن شيكاغو في الأخبار والطعام والحياة الليلية والثقافة والرياضة والسفر والمزيد.","watch":"مشاهدة الفيديو","back":"العودة إلى الفئة","published":"تاريخ النشر","source":"المصدر","categories":"استكشف 17 فئة في شيكاغو","more":"المزيد من فيديوهات شيكاغو","archive":"أرشيف الفيديو"},
}

CATEGORY_TRANSLATIONS = {
    "de": ["News","Restaurants & Essen","Bars & Nachtleben","Events","Museen","Kunst & Street Art","Sport","Reisen & Tourismus","Hotels","Immobilien","Shopping","Jobs & Wirtschaft","Musik & Konzerte","Lifestyle","Aktivitäten","Verkehr & Mobilität","Natur & Outdoor"],
    "fr": ["Actualités","Restaurants & Gastronomie","Bars & Vie nocturne","Événements","Musées","Art & Street Art","Sports","Voyage & Tourisme","Hôtels","Immobilier","Shopping","Emploi & Business","Musique & Concerts","Lifestyle","Que faire","Transport & Mobilité","Nature & Plein air"],
    "it": ["Notizie","Ristoranti & Food","Bar & Vita notturna","Eventi","Musei","Arte & Street Art","Sport","Viaggi & Turismo","Hotel","Immobiliare","Shopping","Lavoro & Business","Musica & Concerti","Lifestyle","Cose da fare","Trasporti & Mobilità","Natura & Outdoor"],
    "es": ["Noticias","Restaurantes & Gastronomía","Bares & Vida nocturna","Eventos","Museos","Arte & Street Art","Deportes","Viajes & Turismo","Hoteles","Inmobiliaria","Compras","Empleo & Negocios","Música & Conciertos","Lifestyle","Qué hacer","Transporte & Movilidad","Naturaleza & Aire libre"],
    "pt": ["Notícias","Restaurantes & Gastronomia","Bares & Vida noturna","Eventos","Museus","Arte & Street Art","Esportes","Viagens & Turismo","Hotéis","Imóveis","Compras","Empregos & Negócios","Música & Concertos","Lifestyle","O que fazer","Transporte & Mobilidade","Natureza & Ar livre"],
    "ja": ["ニュース","レストラン・グルメ","バー・ナイトライフ","イベント","博物館","アート・ストリートアート","スポーツ","旅行・観光","ホテル","不動産","ショッピング","仕事・ビジネス","音楽・コンサート","ライフスタイル","観光・アクティビティ","交通・モビリティ","自然・アウトドア"],
    "ar": ["الأخبار","المطاعم والطعام","الحانات والحياة الليلية","الفعاليات","المتاحف","الفن وفن الشارع","الرياضة","السفر والسياحة","الفنادق","العقارات","التسوق","الوظائف والأعمال","الموسيقى والحفلات","أسلوب الحياة","أشياء للقيام بها","النقل والتنقل","الطبيعة والهواء الطلق"],
}


def esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")[:80] or "video"


def api_json(url: str, data: dict | None = None) -> dict:
    headers = {"User-Agent": "VideoVediVinci/1.0"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def youtube_search(query: str) -> list[dict]:
    if not YOUTUBE_API_KEY:
        raise RuntimeError("Missing YOUTUBE_API_KEY")
    published_after = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=SEARCH_DAYS_BACK)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    params = {
        "part": "snippet", "q": query, "type": "video", "order": "date",
        "maxResults": str(VIDEOS_PER_CATEGORY), "publishedAfter": published_after,
        "regionCode": "US", "relevanceLanguage": "en", "videoEmbeddable": "true",
        "key": YOUTUBE_API_KEY,
    }
    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
    payload = api_json(url)
    videos = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id:
            continue
        thumbs = snippet.get("thumbnails", {})
        thumbnail = thumbs.get("high", {}).get("url") or thumbs.get("medium", {}).get("url") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        videos.append({
            "id": video_id,
            "title": snippet.get("title", "").strip(),
            "description": snippet.get("description", "").strip(),
            "publishedAt": snippet.get("publishedAt", ""),
            "channelTitle": snippet.get("channelTitle", "").strip(),
            "thumbnail": thumbnail,
            "youtubeUrl": f"https://www.youtube.com/watch?v={video_id}",
        })
    return videos


def translate_batch(texts: list[str], target: str) -> list[str]:
    if target == "en" or not texts:
        return texts
    if not GOOGLE_TRANSLATE_API_KEY:
        print(f"WARNING: Missing GOOGLE_TRANSLATE_API_KEY; using English for {target}")
        return texts
    endpoint = "https://translation.googleapis.com/language/translate/v2?key=" + urllib.parse.quote(GOOGLE_TRANSLATE_API_KEY)
    results = []
    for start in range(0, len(texts), 50):
        chunk = texts[start:start + 50]
        try:
            data = api_json(endpoint, {"q": chunk, "target": target, "format": "text"})
            rows = data.get("data", {}).get("translations", [])
            if len(rows) != len(chunk):
                raise RuntimeError("Translation response mismatch")
            results.extend(row.get("translatedText", "") for row in rows)
        except Exception as exc:
            print(f"WARNING: translation failed for {target}: {exc}")
            results.extend(chunk)
    return results


def page_path(lang: str, relative: str = "") -> str:
    relative = relative.strip("/")
    if lang == "en":
        return f"/{relative}/" if relative else "/"
    return f"/{lang}/{relative}/" if relative else f"/{lang}/"


def city_path(lang: str) -> str:
    return page_path(lang, CITY_SLUG)


def category_path(lang: str, cat_slug: str) -> str:
    return page_path(lang, f"{CITY_SLUG}/{cat_slug}")


def video_path(lang: str, cat_slug: str, video: dict) -> str:
    return page_path(lang, f"{CITY_SLUG}/{cat_slug}/{slugify(video['title'])}-{video['id']}")


def absolute(path: str) -> str:
    return DOMAIN + path


def localized_category_name(lang: str, index: int) -> str:
    return CATEGORIES[index]["name"] if lang == "en" else CATEGORY_TRANSLATIONS[lang][index]


def hreflang_links(relative: str) -> str:
    links = [f'<link rel="alternate" hreflang="{lang}" href="{esc(absolute(page_path(lang, relative)))}">' for lang in LANGUAGES]
    links.append(f'<link rel="alternate" hreflang="x-default" href="{esc(absolute(page_path("en", relative)))}">')
    return "\n".join(links)


def css() -> str:
    return """
:root{--fg:#161616;--muted:#666;--line:#e7e7e7;--bg:#f7f7f7;--card:#fff;--accent:#d71920}*{box-sizing:border-box}body{margin:0;font-family:Arial,Helvetica,sans-serif;background:var(--bg);color:var(--fg);line-height:1.55}a{color:inherit}header{background:#111;color:#fff}.wrap{max-width:1180px;margin:0 auto;padding:0 20px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 0}.brand{font-weight:900;letter-spacing:.8px;text-decoration:none;font-size:22px}.brand span{color:#ff2b31}.hero{padding:54px 0 44px;background:linear-gradient(135deg,#111,#333);color:#fff}.hero h1{font-size:clamp(34px,6vw,68px);line-height:1;margin:0 0 16px}.hero p{max-width:780px;font-size:18px;color:#eee;margin:0}.langs{display:flex;gap:8px;flex-wrap:wrap}.langs a{font-size:12px;text-decoration:none;border:1px solid #555;border-radius:999px;padding:5px 9px}main{padding:36px 0 60px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.cat-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card,.cat{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;text-decoration:none;box-shadow:0 3px 12px rgba(0,0,0,.04)}.card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block;background:#ddd}.card-body{padding:16px}.card h3{font-size:19px;line-height:1.3;margin:0 0 8px}.meta{font-size:13px;color:var(--muted)}.desc{color:#444;font-size:14px}.cat{padding:18px}.cat b{display:block;margin-bottom:4px}.cat small{color:var(--muted)}.section-title{font-size:28px;margin:38px 0 18px}.video-wrap{max-width:960px}.embed{position:relative;padding-top:56.25%;background:#000;border-radius:14px;overflow:hidden}.embed iframe{position:absolute;inset:0;width:100%;height:100%;border:0}.prose{background:#fff;border:1px solid var(--line);border-radius:14px;padding:24px;margin-top:22px}.button{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;border-radius:9px;padding:11px 16px}footer{border-top:1px solid var(--line);background:#fff;padding:28px 0;color:#666;font-size:13px}@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}.cat-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:600px){.grid,.cat-grid{grid-template-columns:1fr}.top{align-items:flex-start;flex-direction:column}.hero{padding:38px 0}.wrap{padding:0 15px}}
"""


def header(lang: str) -> str:
    langs = "".join(f'<a href="{esc(city_path(code))}">{code.upper()}</a>' for code in LANGUAGES)
    return f'<header><div class="wrap top"><a class="brand" href="{esc(page_path(lang))}">VIDEO <span>VEDI</span> VINCI</a><nav class="langs">{langs}</nav></div></header>'


def footer() -> str:
    return f'<footer><div class="wrap">© {dt.datetime.now().year} VideoVediVinci · {esc(CITY)}, {esc(COUNTRY)} · Videos remain hosted by YouTube.</div></footer>'


def html_doc(lang: str, title: str, description: str, canonical: str, relative: str, body: str, schema=None) -> str:
    jsonld = f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>' if schema else ""
    return f'''<!doctype html><html lang="{lang}" dir="{LANGUAGES[lang]['dir']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><meta name="description" content="{esc(description[:160])}"><link rel="canonical" href="{esc(canonical)}">{hreflang_links(relative)}<meta property="og:type" content="website"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description[:200])}"><meta property="og:url" content="{esc(canonical)}"><meta name="twitter:card" content="summary_large_image"><style>{css()}</style>{jsonld}</head><body>{header(lang)}{body}{footer()}</body></html>'''


def write_url(path: str, content: str) -> None:
    clean = path.strip("/")
    target = OUT / clean / "index.html" if clean else OUT / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")



def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_archive() -> dict:
    if not ARCHIVE_FILE.exists():
        return {"version": 1, "city": CITY, "videos": {}}
    try:
        data = json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("archive root must be an object")
        data.setdefault("version", 1)
        data.setdefault("city", CITY)
        data.setdefault("videos", {})
        return data
    except Exception as exc:
        print(f"WARNING: archive could not be read: {exc}")
        return {"version": 1, "city": CITY, "videos": {}}


def save_archive(archive: dict) -> None:
    archive["updatedAt"] = utc_now()
    ARCHIVE_FILE.write_text(json.dumps(archive, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def merge_archive(category_videos: dict[str, list[dict]], archive: dict) -> None:
    now = utc_now()
    store = archive.setdefault("videos", {})
    current_ids = set()
    for cat_slug, videos in category_videos.items():
        for video in videos:
            vid = video["id"]
            current_ids.add(vid)
            row = store.get(vid)
            if row is None:
                row = dict(video)
                row.update({
                    "categories": [cat_slug],
                    "firstDiscoveredAt": now,
                    "lastSeenAt": now,
                    "archivedAt": None,
                    "lastCheckedAt": now,
                    "lastAvailableAt": now,
                    "availabilityStatus": "active",
                    "consecutiveFailures": 0,
                })
                store[vid] = row
            else:
                for key in ("title","description","publishedAt","channelTitle","thumbnail","youtubeUrl"):
                    if video.get(key):
                        row[key] = video[key]
                cats = set(row.get("categories", []))
                cats.add(cat_slug)
                row["categories"] = sorted(cats)
                row["lastSeenAt"] = now
                row["lastCheckedAt"] = now
                row["lastAvailableAt"] = now
                row["availabilityStatus"] = "active"
                row["consecutiveFailures"] = 0

    # A video becomes archived when it is no longer in the current top-five search results.
    for vid, row in store.items():
        if vid not in current_ids and not row.get("archivedAt"):
            row["archivedAt"] = now


def load_seo_library() -> dict:
    if not SEO_LIBRARY_FILE.exists():
        print(f"WARNING: {SEO_LIBRARY_FILE} not found; source titles will be used.")
        return {}
    try:
        return json.loads(SEO_LIBRARY_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"WARNING: SEO library could not be read: {exc}")
        return {}


def pick(items: list[str], seed: str, salt: str) -> str:
    if not items:
        return ""
    raw = hashlib.sha256(f"{seed}:{salt}".encode("utf-8")).digest()
    return items[int.from_bytes(raw[:4], "big") % len(items)]


def seo_for_video(video: dict, cat_slug: str, library: dict) -> dict:
    """Conservative English SEO metadata; original YouTube data remains untouched."""
    original = (video.get("title") or "").strip()
    cat = library.get("categories", {}).get(cat_slug, {})
    terms = cat.get("terms", [])
    keyword = pick(terms, video["id"], "keyword") or cat_slug.replace("-", " ")
    # Keep the real source title as the concrete topic. This prevents invented claims.
    if original:
        seo_title = f"{original} | {CITY}"
    else:
        seo_title = f"{keyword.title()} in {CITY} | VideoVediVinci"
    if len(seo_title) > 72:
        seo_title = f"{original[:52].rstrip()} | {CITY}" if original else seo_title[:72].rstrip()

    descriptions = library.get("_meta", {}).get("description_patterns", [])
    template = pick(descriptions, video["id"], "description")
    if template:
        seo_description = template.format(city=CITY, keyword=keyword, topic=original or keyword)
    else:
        seo_description = f"Watch this selected video about {original or keyword} in {CITY}, part of the VideoVediVinci archive."
    return {
        "originalTitle": original,
        "seoTitle": seo_title,
        "seoDescription": seo_description[:160].rstrip(),
        "keyword": keyword,
    }


def archived_by_category(archive: dict, cat_slug: str) -> list[dict]:
    rows = []
    for video in archive.get("videos", {}).values():
        if cat_slug in video.get("categories", []) and video.get("availabilityStatus", "active") == "active":
            rows.append(video)
    rows.sort(key=lambda v: (v.get("publishedAt",""), v.get("firstDiscoveredAt","")), reverse=True)
    return rows


def archive_path(lang: str, cat_slug: str = "") -> str:
    rel = f"{CITY_SLUG}/archive"
    if cat_slug:
        rel += f"/{cat_slug}"
    return page_path(lang, rel)


def generate_archive_page(lang: str, archive: dict, localized: dict) -> None:
    ui = UI[lang]
    sections = []
    for idx, cat in enumerate(CATEGORIES):
        videos = archived_by_category(archive, cat["slug"])
        if not videos:
            continue
        cards = []
        for v in videos:
            loc = localized.get(v["id"], {}).get(lang)
            if not loc:
                loc = {"title": v.get("title",""), "description": v.get("description","") or v.get("title","")}
            cards.append(video_card(lang, cat, v, loc))
        name = localized_category_name(lang, idx)
        sections.append(
            f'<h2 class="section-title"><a href="{esc(archive_path(lang, cat["slug"]))}">{esc(name)}</a> · {len(videos)}</h2>'
            f'<div class="grid">{"".join(cards[:12])}</div>'
        )
    body = f'<section class="hero"><div class="wrap"><h1>{esc(ui["archive"])} · {CITY}</h1><p>{esc(ui["intro"])}</p></div></section><main class="wrap">{"".join(sections)}</main>'
    rel = f"{CITY_SLUG}/archive"
    write_url(archive_path(lang), html_doc(lang, f'{ui["archive"]} – {CITY} | VideoVediVinci', ui["intro"], absolute(archive_path(lang)), rel, body))


def generate_archive_category_page(lang: str, idx: int, cat: dict, archive: dict, localized: dict) -> None:
    videos = archived_by_category(archive, cat["slug"])
    name = localized_category_name(lang, idx)
    cards = []
    for v in videos:
        loc = localized.get(v["id"], {}).get(lang)
        if not loc:
            loc = {"title": v.get("title",""), "description": v.get("description","") or v.get("title","")}
        cards.append(video_card(lang, cat, v, loc))
    description = f'{name} video archive for {CITY}.'
    body = f'<section class="hero"><div class="wrap"><h1>{esc(name)} · {esc(UI[lang]["archive"])}</h1><p>{esc(description)}</p></div></section><main class="wrap"><div class="grid">{"".join(cards)}</div></main>'
    rel = f'{CITY_SLUG}/archive/{cat["slug"]}'
    write_url(archive_path(lang, cat["slug"]), html_doc(lang, f'{name} – {CITY} {UI[lang]["archive"]} | VideoVediVinci', description, absolute(archive_path(lang, cat["slug"])), rel, body))


def prepare_localizations(category_videos: dict[str, list[dict]], archive: dict | None = None) -> dict:
    unique = {}
    for videos in category_videos.values():
        for video in videos:
            unique[video["id"]] = video
    if archive:
        for vid, video in archive.get("videos", {}).items():
            if video.get("availabilityStatus", "active") == "active":
                unique[vid] = video
    localized = {vid: {"en": {"title": v["title"], "description": v.get("description") or v["title"]}} for vid, v in unique.items()}
    ids = list(unique)
    titles = [unique[vid]["title"] for vid in ids]
    descriptions = [(unique[vid].get("description") or unique[vid]["title"])[:900] for vid in ids]
    for lang, cfg in LANGUAGES.items():
        if lang == "en":
            continue
        tt = translate_batch(titles, cfg["target"])
        td = translate_batch(descriptions, cfg["target"])
        for i, vid in enumerate(ids):
            localized[vid][lang] = {"title": tt[i], "description": td[i]}
    return localized

def video_card(lang: str, cat: dict, video: dict, local: dict) -> str:
    desc = (local["description"] or "")[:180]
    return f'<a class="card" href="{esc(video_path(lang, cat["slug"], video))}"><img src="{esc(video["thumbnail"])}" alt="{esc(local["title"])}" loading="lazy"><div class="card-body"><h3>{esc(local["title"])}</h3><div class="meta">{esc(video["publishedAt"][:10])} · {esc(video["channelTitle"])}</div><p class="desc">{esc(desc)}</p></div></a>'


def generate_home(lang: str) -> None:
    ui = UI[lang]
    body = f'<section class="hero"><div class="wrap"><h1>VideoVediVinci</h1><p>{esc(ui["intro"])}</p></div></section><main class="wrap"><h2 class="section-title">{esc(ui["latest"])}</h2><a class="button" href="{esc(city_path(lang))}">{CITY} →</a></main>'
    schema = {"@context":"https://schema.org","@type":"WebSite","name":"VideoVediVinci","url":absolute(page_path(lang)),"inLanguage":lang}
    write_url(page_path(lang), html_doc(lang, f"VideoVediVinci – {CITY} Video Discovery", ui["intro"], absolute(page_path(lang)), "", body, schema))


def generate_city_page(lang: str, category_videos: dict[str, list[dict]], localized: dict) -> None:
    ui = UI[lang]
    cats = []
    for i, cat in enumerate(CATEGORIES):
        count = len(category_videos.get(cat["slug"], []))
        cats.append(f'<a class="cat" href="{esc(category_path(lang, cat["slug"]))}"><b>{esc(localized_category_name(lang, i))}</b><small>{cat["id"]} · {count} videos</small></a>')
    seen, recent = set(), []
    for cat in CATEGORIES:
        for video in category_videos.get(cat["slug"], []):
            if video["id"] not in seen:
                seen.add(video["id"])
                recent.append((cat, video))
    recent.sort(key=lambda pair: pair[1].get("publishedAt", ""), reverse=True)
    cards = "".join(video_card(lang, cat, video, localized[video["id"]][lang]) for cat, video in recent[:12])
    body = f'<section class="hero"><div class="wrap"><h1>{esc(ui["latest"])}</h1><p>{esc(ui["intro"])}</p></div></section><main class="wrap"><h2 class="section-title">{esc(ui["categories"])}</h2><div class="cat-grid">{"".join(cats)}</div><p style="margin-top:24px"><a class="button" href="{esc(archive_path(lang))}">{esc(ui["archive"])} →</a></p><h2 class="section-title">{esc(ui["more"])}</h2><div class="grid">{cards}</div></main>'
    schema = {"@context":"https://schema.org","@type":"CollectionPage","name":ui["latest"],"description":ui["intro"],"url":absolute(city_path(lang)),"inLanguage":lang,"about":{"@type":"City","name":CITY}}
    write_url(city_path(lang), html_doc(lang, f'{ui["latest"]} | VideoVediVinci', ui["intro"], absolute(city_path(lang)), CITY_SLUG, body, schema))


def generate_category_page(lang: str, idx: int, cat: dict, videos: list[dict], localized: dict) -> None:
    name = localized_category_name(lang, idx)
    ui = UI[lang]
    description = f'{name}: {ui["intro"]}'
    cards = "".join(video_card(lang, cat, v, localized[v["id"]][lang]) for v in videos) or '<p>No recent videos found.</p>'
    body = f'<section class="hero"><div class="wrap"><h1>{esc(name)} · {CITY}</h1><p>{esc(description)}</p></div></section><main class="wrap"><div class="grid">{cards}</div></main>'
    items = [{"@type":"ListItem","position":pos,"url":absolute(video_path(lang, cat["slug"], v)),"name":localized[v["id"]][lang]["title"]} for pos, v in enumerate(videos, 1)]
    schema = {"@context":"https://schema.org","@type":"ItemList","name":f'{name} – {CITY} Videos',"numberOfItems":len(items),"itemListElement":items}
    rel = f'{CITY_SLUG}/{cat["slug"]}'
    write_url(category_path(lang, cat["slug"]), html_doc(lang, f'{name} – {CITY} Videos | VideoVediVinci', description, absolute(category_path(lang, cat["slug"])), rel, body, schema))


def generate_video_page(lang: str, idx: int, cat: dict, video: dict, local: dict) -> None:
    ui = UI[lang]
    name = localized_category_name(lang, idx)
    path = video_path(lang, cat["slug"], video)
    canonical = absolute(path)
    description = (local["description"] or f'{local["title"]} – {CITY}')[:450]
    embed = f'https://www.youtube.com/embed/{urllib.parse.quote(video["id"])}'
    body = f'<main class="wrap"><div class="video-wrap"><p><a href="{esc(category_path(lang, cat["slug"]))}">← {esc(ui["back"])}</a></p><h1>{esc(local["title"])}</h1><p class="meta">{esc(ui["published"])}: {esc(video["publishedAt"][:10])} · {esc(ui["source"])}: {esc(video["channelTitle"])}</p><div class="embed"><iframe src="{esc(embed)}" title="{esc(local["title"])}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen loading="lazy"></iframe></div><section class="prose"><h2>{esc(local["title"])}</h2><p>{esc(description)}</p><p><b>{esc(name)} · {CITY}</b></p><p><a class="button" href="{esc(video["youtubeUrl"])}" target="_blank" rel="noopener">{esc(ui["watch"])} ↗</a></p></section></div></main>'
    schema = {"@context":"https://schema.org","@type":"VideoObject","name":local["title"],"description":description,"thumbnailUrl":[video["thumbnail"]],"uploadDate":video["publishedAt"],"embedUrl":embed,"contentUrl":video["youtubeUrl"],"url":canonical,"inLanguage":lang,"publisher":{"@type":"Organization","name":video["channelTitle"] or "YouTube"},"about":[{"@type":"City","name":CITY},{"@type":"Thing","name":name}]}
    rel = f'{CITY_SLUG}/{cat["slug"]}/{slugify(video["title"])}-{video["id"]}'
    write_url(path, html_doc(lang, f'{local["title"]} | {CITY} Video', description, canonical, rel, body, schema))


def generate_sitemap(urls: list[str]) -> None:
    today = dt.date.today().isoformat()
    rows = "\n".join(f'<url><loc>{esc(url)}</loc><lastmod>{today}</lastmod></url>' for url in sorted(set(urls)))
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + '\n</urlset>\n', encoding="utf-8")


def main() -> None:
    # IMPORTANT: archive.json lives outside dist/ and therefore survives dist regeneration
    # when the workflow commits archive.json back to the private repository.
    archive = load_archive()
    seo_library = load_seo_library()

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    print("Fetching Chicago videos from YouTube...")
    category_videos = {}
    for cat in CATEGORIES:
        print(f'  {cat["id"]} {cat["name"]}: {cat["query"]}')
        try:
            category_videos[cat["slug"]] = youtube_search(cat["query"])
        except Exception as exc:
            print(f'ERROR fetching {cat["name"]}: {exc}')
            category_videos[cat["slug"]] = []

    merge_archive(category_videos, archive)
    for video in archive.get("videos", {}).values():
        first_cat = (video.get("categories") or ["news"])[0]
        video["seo"] = seo_for_video(video, first_cat, seo_library)
    save_archive(archive)
    print(f'Archive: {len(archive.get("videos", {}))} unique videos.')

    print("Preparing translations...")
    localized = prepare_localizations(category_videos, archive)
    urls = []

    for lang in LANGUAGES:
        generate_home(lang)
        urls.append(absolute(page_path(lang)))
        generate_city_page(lang, category_videos, localized)
        urls.append(absolute(city_path(lang)))

        generate_archive_page(lang, archive, localized)
        urls.append(absolute(archive_path(lang)))

        for idx, cat in enumerate(CATEGORIES):
            current = category_videos[cat["slug"]]
            generate_category_page(lang, idx, cat, current, localized)
            urls.append(absolute(category_path(lang, cat["slug"])))

            generate_archive_category_page(lang, idx, cat, archive, localized)
            urls.append(absolute(archive_path(lang, cat["slug"])))

            # Generate stable video pages for ALL active archived videos, not only current top five.
            for video in archived_by_category(archive, cat["slug"]):
                local = localized[video["id"]][lang]
                generate_video_page(lang, idx, cat, video, local)
                urls.append(absolute(video_path(lang, cat["slug"], video)))

    generate_sitemap(urls)
    (OUT / "robots.txt").write_text(f'User-agent: *\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n', encoding="utf-8")
    (OUT / "CNAME").write_text("videovedivinci.com\n", encoding="utf-8")
    print(f'Done. Generated {len(set(urls))} URLs in {OUT}/')


if __name__ == "__main__":
    main()
