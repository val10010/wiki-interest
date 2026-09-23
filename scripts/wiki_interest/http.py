"""HTTP access to Wikimedia APIs with an on-disk cache.

Every GET is cached as JSON keyed by URL. Historical data never changes, so
responses whose time range ended long ago are cached forever; responses that
touch the last ~70 days are refreshed after 24h. Follow-up questions
("same thing, but for Czech too", "extend to 3 years") therefore reuse
everything already downloaded and only fetch what is new.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import warnings
from pathlib import Path

# macOS system Python links LibreSSL; urllib3 v2 warns about it on every run.
# Harmless for HTTPS GETs, but it pollutes the agent's context, so silence it.
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

import requests  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[2]  # scripts/wiki_interest/http.py -> skill root
CACHE_DIR = Path(os.environ.get("WIKI_INTEREST_CACHE", SKILL_DIR / ".cache"))

# Wikimedia requires a descriptive User-Agent. Set WIKI_INTEREST_UA to add contact info.
USER_AGENT = os.environ.get(
    "WIKI_INTEREST_UA",
    "wiki-interest-skill/1.0 (agent skill for pageview research; python-requests)",
)

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


class NotFound(Exception):
    """API answered 404 (e.g. article has no views in the range)."""


def cache_key(url: str, params: dict | None) -> str:
    raw = url + "?" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def get_json(url: str, params: dict | None = None, ttl: float | None = None,
             retries: int = 3):
    """GET url and return parsed JSON. ttl=None means cache forever.

    404 responses are cached too (as {"__not_found__": true}) so repeated runs
    do not hammer the API for articles that do not exist.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{cache_key(url, params)}.json"
    if path.exists() and (ttl is None or time.time() - path.stat().st_mtime < ttl):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("__not_found__"):
            raise NotFound(url)
        return data

    if os.environ.get("WIKI_INTEREST_OFFLINE"):
        # Cache-only mode: record what would have been fetched and treat as missing.
        log = os.environ.get("WIKI_INTEREST_MISSING_LOG")
        if log:
            with open(log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": path.stem, "url": url, "params": params}, ensure_ascii=False) + "\n")
        raise NotFound(url)

    last_err = None
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, timeout=30)
        except requests.RequestException as e:  # network hiccup
            last_err = e
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 404:
            path.write_text(json.dumps({"__not_found__": True}), encoding="utf-8")
            raise NotFound(url)
        if r.status_code == 429 or r.status_code >= 500:
            last_err = RuntimeError(f"HTTP {r.status_code} for {r.url}")
            time.sleep(2 * (attempt + 1))
            continue
        r.raise_for_status()
        data = r.json()
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    raise RuntimeError(f"Request failed after {retries} attempts: {last_err}")
