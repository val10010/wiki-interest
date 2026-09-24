"""Deterministic stand-in for Wikimedia APIs, used by tests (no network).

Synthetic series per language (monthly, with seasonality):
  pl: steady growth ~ +40%/yr          -> expect growing / high reliability
  cs: flat + one viral spike           -> expect flat, spike detected
  uk: tiny volume, noisy               -> expect low reliability
  en: slow decline                     -> expect declining
  sk: flat, NOT linked in Wikidata     -> reachable only via --article sk:Title
"""
import math
import re
from urllib.parse import unquote

import numpy as np

LABELS = {"Q777": "fasting"}
SITELINKS = {"plwiki": "Post przerywany", "cswiki": "Přerušovaný půst",
             "ukwiki": "Інтервальне голодування", "enwiki": "Intermittent fasting"}


def _months(a: str, b: str):
    y, m = int(a[:4]), int(a[4:6])
    y2, m2 = int(b[:4]), int(b[4:6])
    out = []
    while (y, m) <= (y2, m2):
        out.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


ORIGIN = (2023, 9)          # k = 0 here; tests analyse 2023-09 .. 2025-08
SPIKE_MONTH = (2025, 4)     # cs viral spike (5th month from the end of that window)
SEEDS = {"pl": 1, "cs": 2, "uk": 3, "en": 4, "sk": 5}


def _value(lang: str, y: int, m: int) -> int:
    """Views for one calendar month: a function of the date, not of the fetched range,
    so the same month has the same value whichever range the client asks for."""
    k = (y - ORIGIN[0]) * 12 + (m - ORIGIN[1])
    rng = np.random.default_rng([SEEDS[lang], y, m])
    season = 1 + 0.15 * math.cos(2 * math.pi * (m - 1) / 12)  # January peak (New-year diets)
    if lang == "pl":
        v = 8000 * (1.4 ** (k / 12)) * season * rng.normal(1, 0.04)
    elif lang == "cs":
        v = 5000 * season * rng.normal(1, 0.05)
        if (y, m) == SPIKE_MONTH:
            v *= 6  # viral spike
    elif lang == "sk":
        v = 2000 * season * rng.normal(1, 0.05)
    elif lang == "uk":
        v = 60 * season * rng.normal(1, 0.35)
    else:
        v = 90000 * (0.85 ** (k / 12)) * season * rng.normal(1, 0.03)
    return max(int(v), 0)


def _series(lang: str, months):
    return [_value(lang, y, m) for y, m in months]


def fake_get_json(url, params=None, ttl=None, retries=3):
    params = params or {}
    if url.endswith("/w/api.php") and params.get("generator") == "search":
        q = params["gsrsearch"]
        return {"query": {"pages": [
            {"index": 2, "title": q + " (film)", "pageprops": {"wikibase_item": "Q999"}, "description": "film"},
            {"index": 1, "title": q, "pageprops": {"wikibase_item": "Q1"}, "description": "diet"},
        ]}}
    if "wikidata" in url:
        qid = params["ids"]
        return {"entities": {qid: {
            "sitelinks": {k: {"title": v} for k, v in SITELINKS.items()} | {"commonswiki": {"title": "x"}},
            "labels": {"en": {"value": LABELS.get(qid, "Intermittent fasting")}}}}}
    if url.endswith("/w/api.php") and "titles" in params and "pageprops" in params.get("prop", ""):
        title = params["titles"]
        if title == "Nonexistent":
            return {"query": {"pages": [{"title": title, "missing": True}]}}
        qid = "Q1" if title in SITELINKS.values() else "Q777"   # anything unlinked = broader "fasting"
        return {"query": {"pages": [{"title": title, "pageprops": {"wikibase_item": qid},
                                     "description": "religious practice" if qid == "Q777" else "diet"}]}}
    if url.endswith("/w/api.php") and params.get("prop") == "redirects":
        return {"query": {"pages": [{"redirects": []}]}}
    m = re.search(r"per-article/(\w+)\.wikipedia/.+?/(.+)/monthly/(\d{10})/(\d{10})", url)
    if m:
        lang, _, a, b = m.groups()
        ms = _months(a, b)
        return {"items": [{"timestamp": f"{y}{mo:02d}0100", "views": v}
                          for (y, mo), v in zip(ms, _series(lang, ms))]}
    m = re.search(r"aggregate/(\w+)\.wikipedia/.+?/monthly/(\d{10})/(\d{10})", url)
    if m:
        ms = _months(m.group(2), m.group(3))
        return {"items": [{"timestamp": f"{y}{mo:02d}0100", "views": 100_000_000} for y, mo in ms]}
    raise AssertionError(f"unexpected url {unquote(url)} {params}")
