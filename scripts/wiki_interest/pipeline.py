"""Topic -> articles per language -> monthly series + stats -> analysis.json.

No argparse and no printing here: the CLI parses arguments, this module does
the data work, interpret.py turns the result into text.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from . import charts, interpret, stats, wiki
from .http import SKILL_DIR

RUNS_DIR = SKILL_DIR / "runs"
PAGEVIEWS_START = dt.date(2015, 7, 1)  # Pageviews API has no data before July 2015


# ---------------------------------------------------------------- arguments -> plan
def period(months: int, start: str | None = None, end: str | None = None) -> tuple[dt.date, dt.date]:
    """Resolve the analysis window; never includes the current, incomplete month."""
    last = wiki.last_full_month()
    e = min(wiki.parse_month(end), last) if end else last
    s = wiki.parse_month(start) if start else wiki.add_months(e, -(months - 1))
    return max(s, PAGEVIEWS_START), e


def expand_langs(spec: str, available: dict[str, str]) -> list[str]:
    """'uk,pl' | 'top:N' (largest editions having the article) | 'all'."""
    spec = spec.strip()
    if spec == "all":
        return sorted(available, key=lambda l: wiki.TOP_LANGS.index(l) if l in wiki.TOP_LANGS else 999)
    m = re.fullmatch(r"top:(\d+)", spec)
    if m:
        return [l for l in wiki.TOP_LANGS if l in available][: int(m.group(1))]
    return [l.strip() for l in spec.split(",") if l.strip()]


def resolve_topic(topic: str, search_lang: str) -> dict:
    """A topic is 'query', 'Q123', or several joined by '+' (views are summed)."""
    parts = [p.strip() for p in topic.split("+") if p.strip()]
    items = [wiki.resolve(None, search_lang, qid=p) if re.fullmatch(r"Q\d+", p) else wiki.resolve(p, search_lang)
             for p in parts]
    return {"topic": topic, "items": items}


def parse_articles(specs: list[str] | None) -> dict[str, list[str]]:
    """['pl:Post', 'sk:Pôst'] -> {'pl': ['Post'], 'sk': ['Pôst']}"""
    manual: dict[str, list[str]] = {}
    for a in specs or []:
        lang, _, title = a.partition(":")
        manual.setdefault(lang.strip(), []).append(title.strip())
    return manual


def slug(s: str) -> str:
    s = re.sub(r"[^\w]+", "-", s.lower(), flags=re.UNICODE).strip("-")
    return s[:40] or "run"


def run_name(topics: list[str], langs: list[str], start: dt.date, end: dt.date,
             redirects: bool = False) -> str:
    """Deterministic run name: same question -> same dir; any change -> new dir.

    Languages and the redirect flag are part of the name, so a follow-up such as
    "add Slovak" creates a new run instead of overwriting the previous one.
    """
    lang_part = "-".join(sorted(set(langs)))
    if len(lang_part) > 24:
        digest = hashlib.sha1(lang_part.encode()).hexdigest()[:6]
        lang_part = f"{len(set(langs))}langs-{digest}"
    name = f"{slug('_'.join(topics) or 'manual')}_{lang_part}_{start:%Y%m}-{end:%Y%m}"
    return name + ("_redirects" if redirects else "")


# ---------------------------------------------------------------- data
def _series_views(lang: str, titles: list[str], start, end, months, include_redirects: bool) -> tuple[list[int], int]:
    all_titles = list(titles)
    if include_redirects:
        for t in titles:
            all_titles += wiki.redirects(lang, t)
    total = [0] * len(months)
    for t in all_titles:
        v = wiki.article_views(lang, t, start, end)
        total = [a + b for a, b in zip(total, (v[m] for m in months))]
    return total, len(all_titles) - len(titles)


def build_analysis(topics: list[str], articles: dict[str, list[str]], langs_spec: str,
                   start: dt.date, end: dt.date, *, search_lang: str = "en",
                   include_redirects: bool = False, ui: str = "uk", command: str = "") -> tuple[dict, list[str]]:
    """Fetch everything and compute per-series stats. Returns (analysis, requested languages)."""
    if not topics and not articles:
        raise SystemExit("Give at least one --topic or --article lang:Title")
    months = wiki.month_range(start, end)
    project_cache: dict[str, list[int]] = {}
    series, topics_out = [], []

    resolved = [resolve_topic(t, search_lang) for t in topics]
    if len(resolved) == 1 and articles:
        # One topic + --article: the explicit articles fill in / override languages
        # of that same topic (e.g. a local article not linked in Wikidata).
        resolved[0]["manual"] = articles
    elif articles:
        resolved.append({"topic": "manual", "items": [], "manual": articles})
    multi = len(resolved) > 1
    requested_langs: list[str] = []

    for r in resolved:
        union: dict[str, list[str]] = {}
        for it in r["items"]:
            for l, t in it["sitelinks"].items():
                union.setdefault(l, []).append(t)
        extra = r.get("manual") or {}
        union.update(extra)
        langs = expand_langs(langs_spec, union) if r["items"] else []
        langs += [l for l in extra if l not in langs]
        requested_langs += langs
        topics_out.append({"topic": r["topic"],
                           "resolved": [{"qid": it["qid"], "label_en": it["label_en"]} for it in r["items"]],
                           "alternatives": [a for it in r["items"] for a in it["alternatives"]][:4],
                           "missing_languages": [l for l in langs if l not in union]})
        topic_qids = {it["qid"] for it in r["items"]}
        for lang in langs:
            titles = union.get(lang)
            if not titles:
                continue
            proxy = None
            if lang in extra and topic_qids:
                # A hand-picked article is a proxy unless Wikidata says it is the topic itself.
                infos = [{"title": t, **wiki.article_info(lang, t)} for t in extra[lang]]
                if any(i["qid"] not in topic_qids for i in infos):
                    proxy = infos
            total, n_redirects = _series_views(lang, titles, start, end, months, include_redirects)
            if lang not in project_cache:
                pv = wiki.project_views(lang, start, end)
                project_cache[lang] = [pv[m] for m in months]
            st = stats.analyze_series(months, total, project_cache[lang])
            clean = st.pop("_clean", total)
            lead = next((i for i, x in enumerate(total) if x > 0), len(total))
            if 0 < lead < len(total):
                st["reasons"].append(f"no views before {months[lead]} (article created or renamed then)")
            series.append({"id": f"{slug(r['topic'])}|{lang}", "topic": r["topic"], "lang": lang,
                           "title": " + ".join(titles), "proxy": proxy, "redirects_included": n_redirects,
                           "multi_topic": multi, "months": months, "views": total, "views_clean": clean,
                           "project_total": project_cache[lang], "stats": st})

    if not series:
        raise SystemExit("No articles found for the requested languages. See missing_languages via `resolve`.")

    analysis = {"created": dt.datetime.now().isoformat(timespec="seconds"), "command": command,
                "period": {"start": months[0], "end": months[-1], "months": len(months)},
                "ui": ui, "topics": topics_out, "series": series,
                "warnings": interpret.build_warnings(topics_out, series),
                "caveats": list(interpret.GLOBAL_CAVEATS[ui])}
    return analysis, requested_langs


# ---------------------------------------------------------------- persistence
def save_run(analysis: dict, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    stale = run_dir / "report.pdf"
    if stale.exists():
        stale.unlink()  # derived from the previous analysis.json, which is being replaced
    (run_dir / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=1), encoding="utf-8")
    charts.save_chart(analysis, str(run_dir / "chart.png"), analysis["ui"])


def load_run(run_dir: Path) -> dict:
    return json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))


def list_runs(limit: int = 20) -> list[dict]:
    rows = []
    for f in sorted(RUNS_DIR.glob("*/analysis.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        a = json.loads(f.read_text(encoding="utf-8"))
        rows.append({"run_dir": str(f.parent), "created": a["created"], "period": a["period"],
                     "series": [f"{s['topic']}|{s['lang']}" for s in a["series"]],
                     "has_report": (f.parent / "report.pdf").exists()})
    return rows
