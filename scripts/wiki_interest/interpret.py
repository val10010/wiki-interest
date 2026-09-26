"""Numbers -> text the agent quotes: warnings, verdicts, answer skeleton, table, caveats.

Weak models get direction words, number ranges and caveats wrong when they
phrase them themselves, so every sentence the user must see is generated here
(see README, iterations 2-4).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import paths, stats

TRENDS = ("growing", "declining")
MAX_OUTPUT_CHARS = 15000  # analyze/show stdout; agent shells cut at ~30k, leave room for the rest of the context
MAX_TOP = 10              # at most this many full verdicts once the output has to be cut (as many series as the PDF)
COMPACT_LIMIT = 400       # languages in the compact comparison line
FULL_FILE = "all_series.md"
CMD = "scripts/wi"  # how the agent invokes the skill, relative to the skill root


def launcher() -> str:
    """CMD when the agent works in the skill root, else the launcher's absolute path, so every command
    the output suggests works from where the agent actually is."""
    return CMD if paths.caller_cwd().resolve() == paths.SKILL_DIR else str(paths.SKILL_DIR / CMD)

GLOBAL_CAVEATS = {
    "uk": [
        "Перегляди Wikipedia — це сигнал цікавості, а не готовності платити; висновки — гіпотези для подальшої перевірки.",
        "Мовний розділ ≠ країна: багато людей читають англійську або іншу Wikipedia замість рідної мови.",
        "Враховано лише трафік agent=user; частина ботів усе одно може потрапляти в дані, тому сплески відфільтровано.",
        "Перегляди редиректів і схожих статей не враховано, якщо не вказано інше; тема = конкретна стаття.",
    ],
    "en": [
        "Wikipedia views measure curiosity, not willingness to pay; treat conclusions as hypotheses to validate.",
        "Language edition ≠ country: many people read English or another edition instead of their native one.",
        "Only agent=user traffic is used; some bots still slip through, so anomalous spikes are filtered out.",
        "Redirects and related articles are not counted unless stated; a topic = one specific article.",
    ],
}

VERDICT = {
    "uk": {"growing": "інтерес зростає", "declining": "інтерес знижується",
           "flat": "інтерес стабільний (зміна в межах ±10%)", "unclear": "дані не підтверджують тренд",
           "no data": "даних недостатньо",
           "level": {"high": "висока", "medium": "середня", "low": "низька"},
           "body": "{dir}. Зміна {g}, частка в трафіку розділу {rel}, тренд {t}/рік; {med} переглядів/міс; "
                   "надійність {level}{cap}.",
           "cap": {"volume": "малим обсягом", "gap": "неповним рядом"}, "cap_fmt": " (обмежено {k})", "and": " і ",
           "gap": " Дані лише з {m} (стаття {kind} тоді): статистику пораховано за {n} міс., "
                  "без порівняння з тими самими місяцями рік тому.",
           "kind": {"created": "створена", "renamed": "перейменована", None: "створена або перейменована"},
           "renamed": " Статтю перейменовано: до {m} враховано перегляди старої назви {old} (редиректу), ряд безперервний.",
           "renamed_many": " Статтю перейменовано: до {m} враховано перегляди старих назв {old} (редиректів), "
                           "ряд безперервний.",
           "views_dir": {"growing": "перегляди ростуть", "declining": "перегляди падають",
                         "flat": "перегляди майже не змінились (±10%)", "unclear": "перегляди без підтвердженого тренду"},
           "share_dir": {"growing": "відносний інтерес (частка в трафіку розділу) зростає",
                         "declining": "відносний інтерес (частка в трафіку розділу) знижується",
                         "flat": "відносний інтерес (частка в трафіку розділу) стабільний (±10%)",
                         "unclear": "відносний інтерес (частка в трафіку розділу) без підтвердженого тренду"},
           "with_edition": "{views} разом із трафіком усього розділу, а {share}", "but": "{views}, але {share}",
           "share_moved": " Перегляди майже не змінились, але частка теми в розділі змінилась на {rel}.",
           "share_flat": " Частка теми майже не змінилась: зміна переглядів — це зміна трафіку всього розділу.",
           "share_up": " Перегляди падають, але частка теми в розділі зростає.",
           "share_down": " Перегляди ростуть, але частка теми в розділі падає.",
           "seasonal": " Сезонні піки (залишено): {m}.", "spikes": " Аномальні сплески (виключено): {m}.",
           "excess": " (надлишок понад сезонний пік)",
           "proxy": " PROXY: стаття про «{label}», а не про саму тему — інше поняття."},
    "en": {"growing": "interest is growing", "declining": "interest is declining",
           "flat": "interest is flat (change within ±10%)", "unclear": "the data does not confirm a trend",
           "no data": "not enough data",
           "level": {"high": "high", "medium": "medium", "low": "low"},
           "body": "{dir}. Change {g}, share of edition traffic {rel}, trend {t}/yr; {med} views/month; "
                   "reliability {level}{cap}.",
           "cap": {"volume": "low volume", "gap": "an incomplete series"}, "cap_fmt": " (capped by {k})", "and": " and ",
           "gap": " Data only since {m} (article {kind} then): statistics cover {n} months, "
                  "without a same-months-last-year comparison.",
           "kind": {"created": "created", "renamed": "renamed", None: "created or renamed"},
           "renamed": " The article was renamed: before {m} views of the old title {old} (a redirect) are counted, "
                      "so the series is continuous.",
           "renamed_many": " The article was renamed: before {m} views of the old titles {old} (redirects) are "
                           "counted, so the series is continuous.",
           "views_dir": {"growing": "views are growing", "declining": "views are declining",
                         "flat": "views barely moved (±10%)", "unclear": "views show no confirmed trend"},
           "share_dir": {"growing": "relative interest (share of edition traffic) is growing",
                         "declining": "relative interest (share of edition traffic) is declining",
                         "flat": "relative interest (share of edition traffic) is stable (±10%)",
                         "unclear": "relative interest (share of edition traffic) shows no confirmed trend"},
           "with_edition": "{views} together with the whole edition's traffic, while {share}",
           "but": "{views}, but {share}",
           "share_moved": " Views barely moved, but the topic's share of the edition changed by {rel}.",
           "share_flat": " The topic's share barely moved: the change in views is edition-wide traffic.",
           "share_up": " Views fall, but the topic's share of the edition grows.",
           "share_down": " Views grow, but the topic's share of the edition falls.",
           "seasonal": " Seasonal peaks (kept): {m}.", "spikes": " Anomalous spikes (excluded): {m}.",
           "excess": " (excess above the seasonal peak)",
           "proxy": " PROXY: article about '{label}', not the topic itself — a different concept."},
}

SKELETON = {
    "uk": {"data": "**Дані:** Wikipedia, {start} – {end} ({n} міс.); тема: {topics}.",
           "by_lang": "**По мовах:**", "missing": "**Статті немає:** {langs} — тема там не розвинена (це теж сигнал).",
           "rank": "**Порівняння мов** (частка в трафіку розділу): {none}{share}. **Обсяг:** {volume}.",
           "same": " (≈ без змін)",
           "none_grow": "за часткою жодна мова не росте (усі зміни в межах ±10%): ",
           "slot": "**Висновок:** <ЗАПОВНИ: 1–3 речення лише з рядків вище — що це означає для рішення і що "
                   "перевірити далі. Без фактів і узагальнень, яких немає вище.>",
           "limits": "**Обмеження:** перегляди Wikipedia — сигнал цікавості, а не готовності платити; "
                     "мовний розділ ≠ країна.",
           "proxy": " Для {langs} виміряно інше поняття (proxy), тож порівняння з ними не пряме.",
           "low": " Низька надійність: {names} — лише як слабкий сигнал.",
           "proxy_for": " (proxy для «{what}»: стаття міряє ширше поняття, а не саме цей інтерес)",
           "proxy_for_limit": " «{topics}» — лише proxy для «{what}»: висновки про «{what}» непрямі.",
           "shown": "**Показано {n} з {total} серій** (найбільша зміна частки); усі вердикти й повна таблиця: {path}",
           "rank_compact": "**Порівняння мов** (усі {total}; зміна частки в трафіку розділу, ≈ = у межах ±10%; "
                           "у дужках — медіана переглядів/міс): {none}{items}.",
           "more": "… ще {n}",
           "chart": "**Графік:** {path}"},
    "en": {"data": "**Data:** Wikipedia, {start} – {end} ({n} months); topic: {topics}.",
           "by_lang": "**By language:**", "missing": "**No article:** {langs} — the topic is undeveloped there (itself a signal).",
           "rank": "**Languages compared** (share of edition traffic): {none}{share}. **Volume:** {volume}.",
           "same": " (≈ no change)",
           "none_grow": "no language grows by share (all changes within ±10%): ",
           "slot": "**Conclusion:** <FILL: 1–3 sentences using only the lines above — what it means for the "
                   "decision and what to check next. No facts or generalisations not stated above.>",
           "limits": "**Limits:** Wikipedia views measure curiosity, not willingness to pay; "
                     "language edition ≠ country.",
           "proxy": " For {langs} a different concept was measured (proxy), so comparing with them is not like-for-like.",
           "low": " Low reliability: {names} — a weak signal only.",
           "proxy_for": " (a proxy for '{what}': the article measures a broader concept, not this interest itself)",
           "proxy_for_limit": " '{topics}' is only a proxy for '{what}': conclusions about '{what}' are indirect.",
           "shown": "**Showing {n} of {total} series** (largest share change); all verdicts and the full table: {path}",
           "rank_compact": "**Languages compared** (all {total}; share of edition traffic change, ≈ = within ±10%; "
                           "median views/month in brackets): {none}{items}.",
           "more": "… {n} more",
           "chart": "**Chart:** {path}"},
}


def _pct_txt(x) -> str:
    return "—" if x is None else f"{x:+.1f}%"


def _p_txt(p) -> str:
    """Mann-Kendall p for the table: '0.0' read as an exact zero, so tiny values become '<0.001'."""
    if p is None:
        return "—"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def rank_key(s: dict) -> float:
    """Sort order of the table and the PDF: share change first (edition-wide traffic removed),
    raw change when no edition total was available. Series without a number go last."""
    st = s["stats"]
    x = st.get("growth_share_pct")
    if x is None:
        x = st.get("growth_pct")
    return -1e9 if x is None else x


def quoted(titles: list[str], ui: str = "uk") -> str:
    return ", ".join(f"«{t}»" if ui == "uk" else f"'{t}'" for t in titles)


def proxy_label(s: dict) -> str | None:
    if not s.get("proxy"):
        return None
    return ", ".join(p.get("label_en") or p.get("description") or p["title"] for p in s["proxy"])


# ---------------------------------------------------------------- warnings
def build_warnings(topics_out: list[dict], series: list[dict]) -> list[str]:
    """Actionable problems with the measurement itself, phrased as next commands.

    Weak models follow concrete commands far more reliably than general advice,
    so every warning says exactly what to run.
    """
    out = []
    for t in topics_out:
        for lang in t["missing_languages"]:
            out.append(f"'{t['topic']}': no {lang}.wikipedia article linked to this concept. "
                       f"Tell the user (itself a signal: topic undeveloped there). To still measure it, "
                       f"search in that language: `{CMD} resolve \"<topic in {lang}>\" --search-lang {lang}`, "
                       f"then rerun with `--article {lang}:<Title>` and say which article you used.")
    for s in series:
        for p in s.get("proxy") or []:
            if not p.get("exists", True):
                out.append(f"{s['lang']}:{p['title']} does not exist on {s['lang']}.wikipedia (0 views). "
                           f"Check the exact title with `{CMD} resolve \"{p['title']}\" --search-lang {s['lang']}`.")
        if s.get("proxy"):
            out.append(f"PROXY {s['lang']}: '{s['title']}' is about '{proxy_label(s)}', not '{s['topic']}'. "
                       "It measures a different concept, so comparing this language with the others compares "
                       "different things. Say this in the answer; the PDF report adds it automatically. "
                       "Look at seasonal_peaks: peaks that fit the proxy but not the topic (e.g. religious "
                       "holidays) confirm the mismatch.")
    for s in series:
        fix, st = s.get("rename_fix") or {}, s["stats"]
        if fix.get("closed"):
            added = quoted(fix.get("added") or [], "en")
            out.append(f"RENAMED {s['lang']}: '{s['title']}' had no views before {fix['views_start']} (renamed then). "
                       f"Views of its old title {added} were added automatically and close the gap (of its "
                       f"{fix['redirects']} redirect(s) only those with views before that month are added; the "
                       "verdict names them). No action needed.")
        elif st.get("data_start"):
            titles = s.get("titles") or [s["title"]]
            add = " ".join(f'--article "{s["lang"]}:{t}"' for t in titles)
            kind, created = fix.get("kind"), fix.get("page_created")
            tried = (f" (adding its redirect(s) {', '.join(repr(t) for t in fix['added'])} still leaves a step at "
                     f"{fix['views_start']})" if fix.get("added") else "")
            head = (f"SHORT SERIES {s['lang']}: '{s['title']}' has (almost) no views before {st['data_start']}: ")
            tail = (f"Statistics use only {st['data_start']} onwards ({st.get('months')} months) and reliability is "
                    f"capped; the verdict says so, quote it. ")
            old_title = (f"rerun the same command with {add} --article \"{s['lang']}:<old title>\" (titles of one "
                         f"language are summed)")
            if kind == "created":
                out.append(head + f"the article was created then (its page history starts in {created}), so there is "
                           f"no older title to add. " + tail +
                           f"Tell the user that {s['lang']} has data only since {st['data_start']}.")
            elif kind == "renamed":
                out.append(head + f"the article was renamed then (its page history starts in {created}), but no "
                           f"redirect fills the gap{tried}. " + tail +
                           f"If you know the old title, {old_title}; otherwise tell the user that {s['lang']} has "
                           f"data only since {st['data_start']}.")
            else:
                out.append(head + f"the article was created or renamed then, and its redirects do not fill the "
                           f"gap{tried}. " + tail + f"If the article had an older title, {old_title}; otherwise tell "
                           f"the user that {s['lang']} has data only since {st['data_start']}.")
    thin = [s for s in series if (s["stats"].get("median_monthly") or 0) < stats.VERY_LOW_VOLUME]
    if thin and len(thin) * 2 >= len(series):
        names = ", ".join(f"{s['topic']} · {s['lang']}" for s in thin)
        out.append(f"Low volume: {len(thin)} of {len(series)} series have median < "
                   f"{stats.VERY_LOW_VOLUME} views/month ({names}), so their percentages are noise. "
                   "If the article is a proxy for a broader interest, it is too narrow: rerun with the "
                   "broader general article on the subject or sum related ones with 'A+B' "
                   "(see `alternatives`). Otherwise report the small audience itself as the finding.")
    return out


# ---------------------------------------------------------------- verdicts + skeleton
def _cap_txt(st: dict, v: dict) -> str:
    if not st.get("reliability_cap"):
        return ""
    kinds = st.get("cap_kinds") or ["volume"]  # runs saved before cap kinds existed had only the volume cap
    return v["cap_fmt"].format(k=v["and"].join(v["cap"][k] for k in kinds))


def _direction_txt(st: dict, v: dict) -> tuple[str, bool]:
    """Opening words of a verdict. Raw views alone say "interest is falling" when the whole edition
    lost traffic; when the share of edition traffic disagrees, both are named instead. Returns
    (text, whether the share was already explained)."""
    d, ds = st.get("direction", "no data"), st.get("direction_share")
    g, rel = st.get("growth_pct"), st.get("growth_share_pct")
    if ds is None or ds == d or d == "no data":
        return v[d], False
    moved = g is not None and rel is not None and abs(g) < 10 <= abs(rel)
    if not (d in TRENDS or ds in TRENDS or moved):
        return v[d], False
    joint = v["with_edition"] if d in TRENDS and ds == "flat" else v["but"]
    return joint.format(views=v["views_dir"][d], share=v["share_dir"][ds]), True


def verdict(s: dict, ui: str) -> str:
    """One quotable sentence per series, so the model never has to phrase the
    direction, the numbers or the caveats itself (weak models get these wrong)."""
    v, st = VERDICT[ui], s["stats"]
    g, rel = st.get("growth_pct"), st.get("growth_share_pct")
    opening, share_told = _direction_txt(st, v)
    text = f"{s['lang']} · «{s['title']}»: " + v["body"].format(
        dir=opening, g=_pct_txt(g), rel=_pct_txt(rel),
        t=_pct_txt(st.get("trend_annual_pct")), med=st.get("median_monthly"),
        level=v["level"].get(st.get("reliability"), "—"), cap=_cap_txt(st, v))
    if g is not None and rel is not None and not share_told:
        if abs(g) >= 10 and abs(rel) < 10:
            text += v["share_flat"]
        elif abs(g) >= 10 and (g < 0) != (rel < 0):
            text += v["share_up"] if g < 0 else v["share_down"]
        elif abs(g) < 10 <= abs(rel):
            text += v["share_moved"].format(rel=_pct_txt(rel))
    fix = s.get("rename_fix") or {}
    if st.get("data_start"):
        text += v["gap"].format(m=st["data_start"], n=st.get("months"), kind=v["kind"][fix.get("kind")])
    elif fix.get("closed"):
        added = fix.get("added") or []
        text += v["renamed_many" if len(added) > 1 else "renamed"].format(m=fix["views_start"], old=quoted(added, ui))
    if st.get("seasonal_peaks"):
        text += v["seasonal"].format(m=", ".join(p["month"] for p in st["seasonal_peaks"]))
    if st.get("spikes"):
        text += v["spikes"].format(m=", ".join(p["month"] + (v["excess"] if p.get("seasonal_excess") else "")
                                               for p in st["spikes"]))
    if s.get("proxy"):
        text += v["proxy"].format(label=proxy_label(s))
    return text


def _names(items: list[str], ui: str, limit: int = 20) -> str:
    """Comma-separated list, cut after `limit` items so 300 languages do not flood the answer."""
    more = SKELETON[ui]["more"].format(n=len(items) - limit) if len(items) > limit else ""
    return ", ".join(items[:limit]) + (" " + more if more else "")


def _tag(s: dict) -> str:
    return s["lang"] + (f" ({s['topic']})" if s.get("multi_topic") else "")


def _volume_txt(x) -> str:
    x = x or 0
    return f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.1f}k" if x >= 1e4 else str(x)


def _none_grow(series: list[dict], k: dict) -> str:
    """Said in words when no share change reaches +10 %: "vi +2.4% (≈ no change) > tr +0.6%" was still read as
    "vi is the only growing audience" (Haiku, iterations 6 and 9); a mark alone does not stop that."""
    shares = [s["stats"].get("growth_share_pct") for s in series]
    shares = [x for x in shares if x is not None]
    return k["none_grow"] if shares and max(shares) < 10 else ""


def _compact_comparison(series: list[dict], k: dict, ui: str) -> str:
    """Every language in one line (share change rounded, volume short): the comparison stays complete
    when verdicts are shown only for the top series."""
    items = []
    for s in sorted(series, key=rank_key, reverse=True):
        x = s["stats"].get("growth_share_pct")
        if x is None:
            x = s["stats"].get("growth_pct")
        chg = "—" if x is None else ("≈" if abs(x) < 10 else "") + f"{x:+.0f}%"
        items.append(f"{_tag(s)} {chg} ({_volume_txt(s['stats'].get('median_monthly'))})")
    return k["rank_compact"].format(total=len(series), none=_none_grow(series, k), items=_names(items, ui, COMPACT_LIMIT))


def answer_skeleton(run_dir: Path, analysis: dict, shown: list[dict] | None = None) -> str:
    """The whole user-facing answer except one slot. Weak models reliably copy
    text but drop rules (limits line, seasonal peaks, proxy caveat), so every
    mandatory element is already written here; the model fills only the slot.
    `shown`: the series to write verdicts for when not all fit (see summary)."""
    ui = analysis.get("ui", "uk")
    k, series, p = SKELETON[ui], analysis["series"], analysis["period"]
    topics, what = ", ".join(t["topic"] for t in analysis["topics"]), analysis.get("proxy_for")
    data = k["data"].format(start=p["start"], end=p["end"], n=p["months"], topics=topics)
    if what:
        data = data[:-1] + k["proxy_for"].format(what=what) + "."
    lines = [data, k["by_lang"]] + [f"- {verdict(s, ui)}" for s in (series if shown is None else shown)]
    if shown is not None:
        lines.append(k["shown"].format(n=len(shown), total=len(series), path=run_dir / FULL_FILE))
    missing = sorted({l for t in analysis["topics"] for l in t["missing_languages"]})
    if missing:
        lines.append(k["missing"].format(langs=_names(missing, ui, 30)))
    if shown is not None:
        lines.append(_compact_comparison(series, k, ui))
    elif len(series) >= 2:
        def share(s):  # same ±10% band as the verdict's "share barely moved", so the two never disagree
            x = s["stats"]["growth_share_pct"]
            return _pct_txt(x) + (k["same"] if abs(x) < 10 else "")
        by_share = sorted((s for s in series if s["stats"].get("growth_share_pct") is not None),
                          key=lambda s: -s["stats"]["growth_share_pct"])
        by_vol = sorted(series, key=lambda s: -(s["stats"].get("median_monthly") or 0))
        lines.append(k["rank"].format(
            none=_none_grow(series, k),
            share=" > ".join(f"{_tag(s)} {share(s)}" for s in by_share) or "—",
            volume=" > ".join(f"{_tag(s)} {s['stats'].get('median_monthly')}" for s in by_vol)))
    lines.append(k["slot"])
    limits = k["limits"]
    if what:
        limits += k["proxy_for_limit"].format(topics=topics, what=what)
    proxies = [s["lang"] for s in series if s.get("proxy")]
    if proxies:
        limits += k["proxy"].format(langs=_names(proxies, ui))
    low = [s["lang"] for s in series if s["stats"].get("reliability") == "low"]
    if low:
        limits += k["low"].format(names=_names(low, ui))
    lines += [limits, k["chart"].format(path=run_dir / "chart.png")]
    return "\n".join(lines)


# ---------------------------------------------------------------- table + summary
def _reliability_cell(st: dict) -> str:
    cell = f"{st.get('reliability')} ({st.get('score')}/10"
    if st.get("reliability_cap"):
        cell += ", " + "+".join(st.get("cap_kinds") or ["volume"]) + " cap"
    return cell + ")"


def _months_up_txt(st: dict) -> str:
    return "—" if st.get("months_up_yoy") is None else f"{st['months_up_yoy']}/12"


def table_md(series: list[dict]) -> str:
    head = ("| series | article | median/mo | change % | rel. change % | trend/yr % | p | months up | reliability "
            "| direction | direction (share) |")
    rows = [head, "|" + "---|" * 11]
    for s in sorted(series, key=rank_key, reverse=True):
        st = s["stats"]
        title = s["title"] + (" [proxy]" if s.get("proxy") else "")
        rows.append(f"| {s['topic']} · {s['lang']} | {title} | {st.get('median_monthly')} | {st.get('growth_pct')} | "
                    f"{st.get('growth_share_pct')} | {st.get('trend_annual_pct')} | {_p_txt(st.get('trend_p_value'))} | "
                    f"{_months_up_txt(st)} | {_reliability_cell(st)} | {st.get('direction')} | {st.get('direction_share') or '—'} |")
    return "\n".join(rows)


def _summary(run_dir: Path, analysis: dict, top: int | None) -> dict:
    ui, series = analysis.get("ui", "uk"), analysis["series"]
    shown = None if top is None else sorted(series, key=rank_key, reverse=True)[:top]
    listed = series if shown is None else shown
    warnings = [w.replace(f"`{CMD} ", f"`{launcher()} ") for w in analysis.get("warnings", [])]
    if shown is not None:  # keep whole warnings while they fit a quarter of the budget, count the rest
        kept, used = [], 0
        for w in warnings:
            if used + len(w) > MAX_OUTPUT_CHARS // 4:
                kept.append(f"... {len(warnings) - len(kept)} more warnings in {run_dir / FULL_FILE}")
                break
            kept.append(w)
            used += len(w)
        warnings = kept
    out = {
        "run_dir": str(run_dir),
        "chart": str(run_dir / "chart.png"),
        "period": analysis["period"],
        "topics": analysis["topics"],
        "warnings": warnings,
        # Placement measured on Haiku 4.5: here it was copied in 2/5 answers, as the last
        # field (list of lines) in 0/5. Run-to-run noise is large; see README, iteration 4.
        "answer_skeleton": answer_skeleton(run_dir, analysis, shown),
        "verdicts": [verdict(s, ui) for s in listed],
        "table": table_md(listed),
        "details": {s["id"]: {k: s["stats"].get(k) for k in
                              ("growth_raw_pct", "project_growth_pct", "per_million_views_last12",
                               "spike_share_pct", "spikes", "seasonal_peaks", "reasons")}
                    for s in listed},
        "caveats": analysis["caveats"],
    }
    if shown is not None:
        out["shown"] = {"series_shown": len(shown), "series_total": len(series), "full": str(run_dir / FULL_FILE)}
    out["next"] = f"{launcher()} report {run_dir} --title '...' --conclusion '...'"
    return out


def summary(run_dir: Path, analysis: dict) -> dict:
    """What `analyze` / `show` print for the agent. Agent shells cut long output (Claude Code at ~30k
    characters), which would cut the skeleton before its slot; each series costs ~1k characters. So when
    everything does not fit MAX_OUTPUT_CHARS, verdicts, table and details are given for the top series by
    rank_key (as many as fit), with a compact comparison of all languages and the full file's path."""
    out = _summary(run_dir, analysis, None)
    top = min(len(analysis["series"]) - 1, MAX_TOP)
    while _size(out) > MAX_OUTPUT_CHARS and top >= 1:
        out = _summary(run_dir, analysis, top)
        top -= 1
    return out


def _size(obj) -> int:
    return len(json.dumps(obj, ensure_ascii=False, indent=1))  # as cli._print prints it


def full_text(run_dir: Path, analysis: dict) -> str:
    """FULL_FILE: everything summary() may leave out — every verdict, the full table, every warning."""
    ui = analysis.get("ui", "uk")
    return "\n\n".join([f"# {run_dir.name}", table_md(analysis["series"]),
                         "\n".join(f"- {verdict(s, ui)}" for s in analysis["series"]),
                         "\n".join(f"- {w}" for w in analysis.get("warnings", []))]) + "\n"


def report_caveats(analysis: dict, ui: str, extra: list[str] | None = None) -> list[str]:
    """Caveats for the PDF. Proxy and low-reliability notes are never left to the model."""
    caveats = (extra or []) + analysis["caveats"]
    for s in analysis["series"]:
        if s.get("proxy"):
            caveats.insert(0, (f"Proxy ({s['lang']}): «{s['title']}» — стаття про «{proxy_label(s)}», а не про саму "
                               "тему; порівняння з іншими мовами міряє різні поняття." if ui == "uk" else
                               f"Proxy ({s['lang']}): '{s['title']}' is about '{proxy_label(s)}', not the topic "
                               "itself; comparing it with other languages compares different concepts."))
    for s in analysis["series"]:
        ds, fix = s["stats"].get("data_start"), s.get("rename_fix") or {}
        kind = VERDICT[ui]["kind"][fix.get("kind")]
        if ds:
            caveats.insert(0, (f"Неповний ряд ({s['lang']}): «{s['title']}» не має переглядів до {ds} (стаття {kind}); "
                               f"статистику пораховано лише з {ds}." if ui == "uk" else
                               f"Incomplete series ({s['lang']}): '{s['title']}' has no views before {ds} (article "
                               f"{kind}); statistics use {ds} onwards only."))
        elif fix.get("closed"):
            old_t = quoted(fix.get("added") or [], ui)
            caveats.insert(0, (f"Перейменування ({s['lang']}): до {fix['views_start']} враховано перегляди старої назви "
                               f"{old_t} (редиректу)." if ui == "uk" else
                               f"Rename ({s['lang']}): before {fix['views_start']} views of the old title {old_t} "
                               "(a redirect) are counted."))
    low = [f"{s['topic']} · {s['lang']}" for s in analysis["series"] if s["stats"].get("reliability") == "low"]
    if low:
        caveats.insert(0, ("Низька надійність даних: " if ui == "uk" else "Low reliability: ") + ", ".join(low))
    what = analysis.get("proxy_for")
    if what:
        topics = ", ".join(t["topic"] for t in analysis["topics"])
        caveats.insert(0, (f"Proxy теми: інтерес до «{what}» виміряно через статтю «{topics}» — це ширше поняття, "
                           "тож висновки непрямі." if ui == "uk" else
                           f"Proxy topic: interest in '{what}' is measured via the article '{topics}', a broader "
                           "concept, so conclusions are indirect."))
    return caveats
