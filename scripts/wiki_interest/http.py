"""HTTP access to Wikimedia APIs with an on-disk cache.

Every GET is cached as JSON keyed by URL (ttl=None: forever). wiki.py asks for
pageviews in canonical ranges (closed history forever, recent tail 24 h), so
follow-up questions ("same thing, but for Czech too", "extend to 3 years")
reuse everything already downloaded and only fetch what is new.
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

# Wikimedia wants a User-Agent with contact info (URL or email): without it the quota is
# 10 requests/minute instead of 200, and a 15-language run takes minutes. The project URL is
# the contact; set WIKI_INTEREST_UA to identify your own deployment instead.
PROJECT_URL = "https://github.com/val10010/wiki-interest"
USER_AGENT = os.environ.get(
    "WIKI_INTEREST_UA",
    f"wiki-interest-skill/1.0 ({PROJECT_URL}; agent skill for pageview research) python-requests",
)

_session = requests.Session()
_session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


RATE_LIMIT_RETRIES = 8  # 429s tolerated per request; each waits Retry-After (the quota is per minute)


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

    last_err, errors, limited = None, 0, 0
    while True:
        try:
            r = _session.get(url, params=params, timeout=30)
        except requests.RequestException as e:  # network hiccup
            last_err, errors = e, errors + 1
            if errors >= retries:
                break
            time.sleep(1.5 * errors)
            continue
        if r.status_code == 404:
            path.write_text(json.dumps({"__not_found__": True}), encoding="utf-8")
            raise NotFound(url)
        if r.status_code == 429:
            # Per-minute quota exceeded: wait as the server says, then continue where we were.
            limited += 1
            if limited > RATE_LIMIT_RETRIES:
                raise RuntimeError(f"Wikimedia rate limit (HTTP 429) persists for {r.url}. Wait a minute and "
                                   "rerun the same command: finished downloads are cached.")
            time.sleep(_retry_after(r.headers.get("Retry-After"), limited))
            continue
        if r.status_code >= 500:
            last_err, errors = RuntimeError(f"HTTP {r.status_code} for {r.url}"), errors + 1
            if errors >= retries:
                break
            time.sleep(2 * errors)
            continue
        r.raise_for_status()
        data = r.json()
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    raise RuntimeError(f"Request failed after {retries} attempts: {last_err}")


def _retry_after(header: str | None, attempt: int) -> float:
    """Seconds to wait after a 429: the server's Retry-After, else exponential back-off from 5 s
    (Wikimedia asks for at least five seconds). Capped so a run never hangs for minutes per request."""
    try:
        return min(max(float(header), 1.0), 60.0)
    except (TypeError, ValueError):
        return min(5.0 * 2 ** (attempt - 1), 60.0)
