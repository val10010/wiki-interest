"""Topic -> articles in many languages -> monthly pageview series."""
from __future__ import annotations

import datetime as dt
from urllib.parse import quote

from .http import NotFound, get_json

RECENT_TTL = 24 * 3600          # data that may still change
META_TTL = 30 * 24 * 3600       # search results / sitelinks
PV = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
PAGEVIEWS_START = dt.date(2015, 7, 1)  # Pageviews API has no data before July 2015
CLOSED_LAG_MONTHS = 3           # months at least this old never change at Wikimedia -> cached forever

# Largest Wikipedias by user pageviews (rough order). Used for --langs top:N.
TOP_LANGS = ["en", "ja", "de", "ru", "es", "fr", "it", "zh", "pt", "pl", "fa", "ar",
             "nl", "id", "tr", "uk", "ko", "vi", "sv", "cs", "he", "hu", "fi", "th",
             "ro", "no", "da", "el", "hi", "bn", "ca", "sr", "bg", "ms", "sk", "hr",
             "lt", "sl", "et", "lv"]

NON_WIKIPEDIA_SITES = {"commonswiki", "specieswiki", "metawiki", "mediawikiwiki",
                       "wikidatawiki", "sourceswiki", "incubatorwiki", "foundationwiki",
                       "outreachwiki", "wikimaniawiki", "wikifunctionswiki"}
SITE_TO_LANG = {"be_x_oldwiki": "be-tarask", "zh_yuewiki": "zh-yue",
                "zh_min_nanwiki": "zh-min-nan", "zh_classicalwiki": "zh-classical"}


# ---------------------------------------------------------------- months
def parse_month(s: str) -> dt.date:
    try:
        y, m = s.split("-")[:2]
        return dt.date(int(y), int(m), 1)
    except ValueError:
        raise ValueError(f"month must be YYYY-MM (e.g. 2024-01), got '{s}'") from None


def add_months(d: dt.date, n: int) -> dt.date:
    idx = d.year * 12 + d.month - 1 + n
    return dt.date(idx // 12, idx % 12 + 1, 1)


def last_full_month(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    return add_months(dt.date(today.year, today.month, 1), -1)


def month_range(start: dt.date, end: dt.date) -> list[str]:
    out, d = [], start
    while d <= end:
        out.append(d.strftime("%Y-%m"))
        d = add_months(d, 1)
    return out


def _range_params(start: dt.date, end: dt.date) -> tuple[str, str]:
    last_day = add_months(end, 1) - dt.timedelta(days=1)
    return start.strftime("%Y%m%d") + "00", last_day.strftime("%Y%m%d") + "00"


# ---------------------------------------------------------------- resolve
def search_topic(query: str, lang: str = "en", limit: int = 5) -> list[dict]:
    """Full-text search on {lang}.wikipedia; returns candidate articles with QIDs."""
    data = get_json(
        f"https://{lang}.wikipedia.org/w/api.php",
        {"action": "query", "generator": "search", "gsrsearch": query,
         "gsrlimit": limit, "gsrnamespace": 0, "prop": "pageprops|description",
         "ppprop": "wikibase_item|disambiguation", "format": "json",
         "formatversion": 2, "redirects": 1},
        ttl=META_TTL)
    pages = sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99))
    out = []
    for p in pages:
        pp = p.get("pageprops", {})
        out.append({"title": p["title"], "qid": pp.get("wikibase_item"),
                    "description": p.get("description", ""),
                    "disambiguation": "disambiguation" in pp})
    return out


def sitelinks(qid: str) -> tuple[dict[str, str], str]:
    """Return ({lang: title} for all Wikipedias having the item, english label)."""
    data = get_json("https://www.wikidata.org/w/api.php",
                    {"action": "wbgetentities", "ids": qid, "props": "sitelinks|labels",
                     "languages": "en", "format": "json"}, ttl=META_TTL)
    ent = data.get("entities", {}).get(qid, {})
    links = {}
    for site, v in ent.get("sitelinks", {}).items():
        if not site.endswith("wiki") or site in NON_WIKIPEDIA_SITES:
            continue
        lang = SITE_TO_LANG.get(site, site[:-4].replace("_", "-"))
        links[lang] = v["title"]
    label = ent.get("labels", {}).get("en", {}).get("value", qid)
    return links, label


def resolve(query: str | None, search_lang: str, qid: str | None = None) -> dict:
    """Pick the Wikidata item for a topic. Returns chosen item + alternatives."""
    candidates = []
    if not qid:
        candidates = search_topic(query, search_lang)
        usable = [c for c in candidates if c["qid"] and not c["disambiguation"]]
        if not usable:
            raise SystemExit(f"No article found for '{query}' on {search_lang}.wikipedia. "
                             "Try another wording, another --search-lang, or --topic Q<id> if you know the Wikidata item.")
        qid = usable[0]["qid"]
    links, label = sitelinks(qid)
    return {"qid": qid, "label_en": label, "sitelinks": links,
            "alternatives": [c for c in candidates if c["qid"] != qid][:4]}


def article_info(lang: str, title: str) -> dict:
    """Wikidata item + short description of one article (to tell whether a
    manually chosen article is the topic itself or a different concept)."""
    data = get_json(f"https://{lang}.wikipedia.org/w/api.php",
                    {"action": "query", "titles": title, "prop": "pageprops|description",
                     "ppprop": "wikibase_item", "redirects": 1, "format": "json",
                     "formatversion": 2}, ttl=META_TTL)
    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        return {"qid": None, "label_en": None, "description": None, "exists": False}
    p = pages[0]
    qid = p.get("pageprops", {}).get("wikibase_item")
    return {"qid": qid, "label_en": sitelinks(qid)[1] if qid else None,
            "description": p.get("description"), "exists": True}


def redirects(lang: str, title: str, cap: int = 30) -> list[str]:
    data = get_json(f"https://{lang}.wikipedia.org/w/api.php",
                    {"action": "query", "prop": "redirects", "titles": title,
                     "rdnamespace": 0, "rdlimit": cap, "format": "json",
                     "formatversion": 2}, ttl=META_TTL)
    pages = data.get("query", {}).get("pages", [])
    return [r["title"] for p in pages for r in p.get("redirects", [])][:cap]


# ---------------------------------------------------------------- pageviews
def _monthly(url_for, start: dt.date, end: dt.date) -> dict[str, int]:
    """Monthly counts {YYYY-MM: n} for [start, end], months without data = 0.

    The API is asked for two *canonical* ranges instead of the requested one: the closed
    history (2015-07 .. cutoff, cached forever) and the recent tail (cutoff+1 .. last full
    month, refreshed after 24 h). Any period is then a slice of cached data, so a follow-up
    such as "three years instead of two" or "since 2019" costs no requests at all; only a
    new language or article is downloaded. The cutoff moves once a month.
    """
    last = last_full_month()
    cutoff = add_months(last, -CLOSED_LAG_MONTHS)
    months = {m: 0 for m in month_range(start, end)}
    ranges = []
    if start <= cutoff:
        ranges.append((PAGEVIEWS_START, cutoff, None))
    if end > cutoff:
        ranges.append((add_months(cutoff, 1), last, RECENT_TTL))
    for a, b, ttl in ranges:
        try:
            data = get_json(url_for(*_range_params(a, b)), ttl=ttl)
        except NotFound:
            continue
        for it in data.get("items", []):
            m = f"{it['timestamp'][:4]}-{it['timestamp'][4:6]}"
            if m in months:
                months[m] = int(it["views"])
    return months


def article_views(lang: str, title: str, start: dt.date, end: dt.date,
                  agent: str = "user") -> dict[str, int]:
    """Monthly views of one article {YYYY-MM: n}. Months without data are 0."""
    t = quote(title.replace(" ", "_"), safe="")
    return _monthly(lambda a, b: f"{PV}/per-article/{lang}.wikipedia/all-access/{agent}/{t}/monthly/{a}/{b}",
                    start, end)


def project_views(lang: str, start: dt.date, end: dt.date, agent: str = "user") -> dict[str, int]:
    """Total monthly views of a whole Wikipedia edition (for normalisation)."""
    return _monthly(lambda a, b: f"{PV}/aggregate/{lang}.wikipedia/all-access/{agent}/monthly/{a}/{b}",
                    start, end)
