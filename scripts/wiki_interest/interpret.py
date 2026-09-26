"""Numbers -> text the agent quotes: warnings, verdicts, answer skeleton, table, caveats.

Weak models get direction words, number ranges and caveats wrong when they
phrase them themselves, so every sentence the user must see is generated here
(see README, iterations 2-4).
"""
from __future__ import annotations

from pathlib import Path

from . import stats

TRENDS = ("growing", "declining")
CMD = "scripts/wi"  # how the agent invokes the skill, relative to the skill root

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
           "gap": " Дані лише з {m} (стаття створена або перейменована тоді): статистику пораховано за {n} міс., "
                  "без порівняння з тими самими місяцями рік тому.",
           "renamed": " Статтю перейменовано: до {m} враховано перегляди старої назви (редиректу), ряд безперервний.",
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
           "gap": " Data only since {m} (article created or renamed then): statistics cover {n} months, "
                  "without a same-months-last-year comparison.",
           "renamed": " The article was renamed: before {m} views of the old title (a redirect) are counted, "
                      "so the series is continuous.",
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
           "rank": "**Порівняння мов** (частка в трафіку розділу): {share}. **Обсяг:** {volume}.",
           "same": " (≈ без змін)",
           "slot": "**Висновок:** <ЗАПОВНИ: 1–3 речення лише з рядків вище — що це означає для рішення і що "
                   "перевірити далі. Без фактів і узагальнень, яких немає вище.>",
           "limits": "**Обмеження:** перегляди Wikipedia — сигнал цікавості, а не готовності платити; "
                     "мовний розділ ≠ країна.",
           "proxy": " Для {langs} виміряно інше поняття (proxy), тож порівняння з ними не пряме.",
           "low": " Низька надійність: {names} — лише як слабкий сигнал.",
           "proxy_for": " (proxy для «{what}»: стаття міряє ширше поняття, а не саме цей інтерес)",
           "proxy_for_limit": " «{topics}» — лише proxy для «{what}»: висновки про «{what}» непрямі.",
           "chart": "**Графік:** {path}"},
    "en": {"data": "**Data:** Wikipedia, {start} – {end} ({n} months); topic: {topics}.",
           "by_lang": "**By language:**", "missing": "**No article:** {langs} — the topic is undeveloped there (itself a signal).",
           "rank": "**Languages compared** (share of edition traffic): {share}. **Volume:** {volume}.",
           "same": " (≈ no change)",
           "slot": "**Conclusion:** <FILL: 1–3 sentences using only the lines above — what it means for the "
                   "decision and what to check next. No facts or generalisations not stated above.>",
           "limits": "**Limits:** Wikipedia views measure curiosity, not willingness to pay; "
                     "language edition ≠ country.",
           "proxy": " For {langs} a different concept was measured (proxy), so comparing with them is not like-for-like.",
           "low": " Low reliability: {names} — a weak signal only.",
           "proxy_for": " (a proxy for '{what}': the article measures a broader concept, not this interest itself)",
           "proxy_for_limit": " '{topics}' is only a proxy for '{what}': conclusions about '{what}' are indirect.",
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
            out.append(f"RENAMED {s['lang']}: '{s['title']}' had no views before {fix['views_start']} (renamed then). "
                       f"Views of its {fix['redirects']} redirect(s), including the old title, were added "
                       "automatically and close the gap; the verdict says so. No action needed.")
        elif st.get("data_start"):
            titles = s.get("titles") or [s["title"]]
            add = " ".join(f'--article "{s["lang"]}:{t}"' for t in titles)
            out.append(f"SHORT SERIES {s['lang']}: '{s['title']}' has (almost) no views before {st['data_start']}: "
                       f"the article was created or renamed then, and its redirects do not fill the gap. Statistics "
                       f"use only {st['data_start']} onwards ({st.get('months')} months) and reliability is capped; "
                       f"the verdict says so, quote it. If the article had an older title, rerun the same command "
                       f'with {add} --article "{s["lang"]}:<old title>" (titles of one language are summed); '
                       f"otherwise tell the user that {s['lang']} has data only since {st['data_start']}.")
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
    if st.get("data_start"):
        text += v["gap"].format(m=st["data_start"], n=st.get("months"))
    elif (s.get("rename_fix") or {}).get("closed"):
        text += v["renamed"].format(m=s["rename_fix"]["views_start"])
    if st.get("seasonal_peaks"):
        text += v["seasonal"].format(m=", ".join(p["month"] for p in st["seasonal_peaks"]))
    if st.get("spikes"):
        text += v["spikes"].format(m=", ".join(p["month"] + (v["excess"] if p.get("seasonal_excess") else "")
                                               for p in st["spikes"]))
    if s.get("proxy"):
        text += v["proxy"].format(label=proxy_label(s))
    return text


def answer_skeleton(run_dir: Path, analysis: dict) -> str:
    """The whole user-facing answer except one slot. Weak models reliably copy
    text but drop rules (limits line, seasonal peaks, proxy caveat), so every
    mandatory element is already written here; the model fills only the slot."""
    ui = analysis.get("ui", "uk")
    k, series, p = SKELETON[ui], analysis["series"], analysis["period"]
    topics, what = ", ".join(t["topic"] for t in analysis["topics"]), analysis.get("proxy_for")
    data = k["data"].format(start=p["start"], end=p["end"], n=p["months"], topics=topics)
    if what:
        data = data[:-1] + k["proxy_for"].format(what=what) + "."
    lines = [data, k["by_lang"]] + [f"- {verdict(s, ui)}" for s in series]
    missing = sorted({l for t in analysis["topics"] for l in t["missing_languages"]})
    if missing:
        lines.append(k["missing"].format(langs=", ".join(missing)))
    if len(series) >= 2:
        def tag(s):
            return s["lang"] + (f" ({s['topic']})" if s.get("multi_topic") else "")

        def share(s):  # same ±10% band as the verdict's "share barely moved", so the two never disagree
            x = s["stats"]["growth_share_pct"]
            return _pct_txt(x) + (k["same"] if abs(x) < 10 else "")
        by_share = sorted((s for s in series if s["stats"].get("growth_share_pct") is not None),
                          key=lambda s: -s["stats"]["growth_share_pct"])
        by_vol = sorted(series, key=lambda s: -(s["stats"].get("median_monthly") or 0))
        lines.append(k["rank"].format(
            share=" > ".join(f"{tag(s)} {share(s)}" for s in by_share) or "—",
            volume=" > ".join(f"{tag(s)} {s['stats'].get('median_monthly')}" for s in by_vol)))
    lines.append(k["slot"])
    limits = k["limits"]
    if what:
        limits += k["proxy_for_limit"].format(topics=topics, what=what)
    proxies = [s["lang"] for s in series if s.get("proxy")]
    if proxies:
        limits += k["proxy"].format(langs=", ".join(proxies))
    low = [s["lang"] for s in series if s["stats"].get("reliability") == "low"]
    if low:
        limits += k["low"].format(names=", ".join(low))
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


def summary(run_dir: Path, analysis: dict) -> dict:
    """What `analyze` / `show` print for the agent."""
    return {
        "run_dir": str(run_dir),
        "chart": str(run_dir / "chart.png"),
        "period": analysis["period"],
        "topics": analysis["topics"],
        "warnings": analysis.get("warnings", []),
        # Placement measured on Haiku 4.5: here it was copied in 2/5 answers, as the last
        # field (list of lines) in 0/5. Run-to-run noise is large; see README, iteration 4.
        "answer_skeleton": answer_skeleton(run_dir, analysis),
        "verdicts": [verdict(s, analysis.get("ui", "uk")) for s in analysis["series"]],
        "table": table_md(analysis["series"]),
        "details": {s["id"]: {k: s["stats"].get(k) for k in
                              ("growth_raw_pct", "project_growth_pct", "per_million_views_last12",
                               "spike_share_pct", "spikes", "seasonal_peaks", "reasons")}
                    for s in analysis["series"]},
        "caveats": analysis["caveats"],
        "next": f"{CMD} report {run_dir} --title '...' --conclusion '...'",
    }


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
        if ds:
            caveats.insert(0, (f"Неповний ряд ({s['lang']}): «{s['title']}» не має переглядів до {ds} (стаття створена "
                               f"або перейменована); статистику пораховано лише з {ds}." if ui == "uk" else
                               f"Incomplete series ({s['lang']}): '{s['title']}' has no views before {ds} (article "
                               f"created or renamed); statistics use {ds} onwards only."))
        elif fix.get("closed"):
            caveats.insert(0, (f"Перейменування ({s['lang']}): до {fix['views_start']} враховано перегляди старої назви "
                               "(редиректу)." if ui == "uk" else
                               f"Rename ({s['lang']}): before {fix['views_start']} views of the old title (a redirect) "
                               "are counted."))
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
