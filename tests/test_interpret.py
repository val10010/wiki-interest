"""interpret.py: the sentences the agent quotes must never contradict the numbers."""
from pathlib import Path

from wiki_interest import interpret


def test_verdict_never_says_growing_unless_direction_is_growing(series_with):
    flat_but_share_up = series_with(direction="flat", growth_pct=-2.4, growth_share_pct=10.6)
    for ui in ("uk", "en"):
        v = interpret.verdict(flat_but_share_up, ui)
        assert ("зростає" not in v.split(".")[0]) and ("growing" not in v)
    assert "інтерес зростає" in interpret.verdict(series_with(direction="growing", growth_pct=40.0), "uk")


def test_verdict_explains_edition_wide_decline(series_with):
    s = series_with(direction="declining", growth_pct=-23.1, growth_share_pct=2.4)
    assert "трафіку всього розділу" in interpret.verdict(s, "uk")


def test_verdict_quotes_exact_numbers(series_with):
    s = series_with(direction="declining", growth_pct=-51.2, growth_share_pct=-36.0, trend_annual_pct=-29.0,
                    median_monthly=441, reliability="medium", reliability_cap="capped",
                    seasonal_peaks=[{"month": "2024-03"}, {"month": "2025-03"}])
    v = interpret.verdict(s, "uk")
    for part in ("-51.2%", "-36.0%", "-29.0%/рік", "441", "середня (обмежено малим обсягом)", "2024-03, 2025-03"):
        assert part in v


def test_table_shows_volume_cap(series_with):
    s = series_with(reliability="medium", reliability_cap="capped at medium", score=9)
    assert "medium (9/10, volume cap)" in interpret.table_md([s])


def test_skeleton_single_language_has_no_comparison(series_with):
    analysis = {"ui": "uk", "period": {"start": "2024-01", "end": "2025-12", "months": 24},
                "topics": [{"topic": "t", "missing_languages": []}], "series": [series_with()]}
    sk = interpret.answer_skeleton(Path("runs/x"), analysis)
    assert "**Порівняння мов**" not in sk and sk.count("<ЗАПОВНИ") == 1


def test_comparison_line_marks_share_changes_within_noise(series_with):
    # Haiku read "vi +2.4% > tr +0.6% > ..." as "vi is the only growing audience", although the
    # verdicts of both say the share barely moved. The ranking must not contradict the verdicts.
    langs = {"vi": 2.4, "tr": 0.6, "id": -20.1}
    series = [dict(series_with(growth_pct=-20.0, growth_share_pct=g), lang=l) for l, g in langs.items()]
    analysis = {"ui": "uk", "period": {"start": "2024-01", "end": "2025-12", "months": 24},
                "topics": [{"topic": "t", "missing_languages": []}], "series": series}
    line = next(l for l in interpret.answer_skeleton(Path("runs/x"), analysis).split("\n") if "Порівняння" in l)
    assert "vi +2.4% (≈ без змін) > tr +0.6% (≈ без змін) > id -20.1%" in line
    analysis["ui"] = "en"
    assert "vi +2.4% (≈ no change)" in interpret.answer_skeleton(Path("runs/x"), analysis)


def test_comparison_line_says_no_language_grows_when_all_are_within_noise(series_with):
    # Iterations 6 and 9: "vi +2.4% (≈ без змін) > tr +0.6% ..." was still read as "vi is the only growing audience"
    # in 3 of 8 Haiku answers. The line must say it in words, not only with a mark.
    def line(langs, ui="uk"):
        series = [dict(series_with(growth_pct=-20.0, growth_share_pct=g), lang=l) for l, g in langs.items()]
        analysis = {"ui": ui, "period": {"start": "2024-01", "end": "2025-12", "months": 24},
                    "topics": [{"topic": "t", "missing_languages": []}], "series": series}
        return next(l for l in interpret.answer_skeleton(Path("runs/x"), analysis).split("\n") if "**Обсяг" in l or "**Volume" in l)
    flat = line({"vi": 2.4, "tr": 0.6, "pl": -9.8})
    assert "за часткою жодна мова не росте" in flat and "vi +2.4% (≈ без змін)" in flat
    assert "no language grows by share" in line({"vi": 2.4, "tr": 0.6}, "en")
    assert "жодна мова не росте" not in line({"vi": 12.4, "tr": 0.6})            # one really grows
    falling = line({"vi": -2.4, "tr": -20.1})
    assert "жодна мова не росте" in falling                                        # nothing grows here either


def test_unconfirmed_share_change_is_named_in_verdict_and_comparison(series_with):
    # Iteration 10: pl «Post» had +10.6 % share with direction (share) = unclear (p = 0.55); the answer called it
    # "a small growth". The number must carry its own caveat wherever the model reads it.
    pl = dict(series_with(direction="flat", growth_pct=-2.4, growth_share_pct=10.6, direction_share="unclear",
                          trend_share_p_value=0.551), lang="pl")
    v = interpret.verdict(pl, "uk")
    assert "Частка +10.6% — не підтверджений ріст" in v and "p=0.551" in v
    assert "not a confirmed growth" in interpret.verdict(pl, "en")
    cs = dict(series_with(direction="declining", growth_pct=-52.7, growth_share_pct=-45.6, direction_share="declining"), lang="cs")
    analysis = {"ui": "uk", "period": {"start": "2024-01", "end": "2025-12", "months": 24},
                "topics": [{"topic": "t", "missing_languages": []}], "series": [pl, cs]}
    line = next(l for l in interpret.answer_skeleton(Path("runs/x"), analysis).split("\n") if "**Обсяг" in l)
    assert "підтвердженого росту за часткою немає" in line and "pl +10.6% (не підтверджено)" in line
    assert "жодна мова не росте" not in line                       # +10.6 % is not "within ±10 %"
    pl["stats"]["direction_share"] = "growing"                      # a confirmed one: no caveats
    line = next(l for l in interpret.answer_skeleton(Path("runs/x"), analysis).split("\n") if "**Обсяг" in l)
    assert "не підтверджено" not in line and "росту за часткою немає" not in line
    assert "не підтверджений ріст" not in interpret.verdict(pl, "uk")
    down = dict(series_with(direction="flat", growth_pct=3.0, growth_share_pct=-14.0, direction_share="unclear",
                            trend_share_p_value=0.3), lang="tr")
    assert "Частка -14.0% — не підтверджене падіння" in interpret.verdict(down, "uk")


def test_compact_comparison_says_no_language_grows_too():
    series = _many_series(15)
    for s in series:
        s["stats"]["growth_share_pct"] = 3.0
    analysis = {"ui": "uk", "proxy_for": None, "period": {"start": "2024-01", "end": "2025-12", "months": 24},
                "topics": [{"topic": "t", "resolved": [], "alternatives": [], "missing_languages": []}],
                "series": series, "warnings": [], "caveats": []}
    assert "жодна мова не росте" in interpret.answer_skeleton(Path("runs/x"), analysis, shown=series[:3])


def test_table_sorts_by_share_change_even_when_it_is_exactly_zero(series_with):
    # `x or y` treated a 0.0 share change as missing and sorted that row by raw growth instead.
    zero = dict(series_with(growth_pct=50.0, growth_share_pct=0.0), lang="a")
    small = dict(series_with(growth_pct=-30.0, growth_share_pct=3.0), lang="b")
    rows = interpret.table_md([zero, small]).split("\n")[2:]
    assert rows[0].startswith("| t · b") and rows[1].startswith("| t · a")


def test_table_shows_tiny_p_values_as_a_bound(series_with):
    assert "<0.001" in interpret.table_md([series_with(trend_p_value=0.0)])
    assert "| 0.031 |" in interpret.table_md([series_with(trend_p_value=0.0312)])


def test_short_series_is_named_in_verdict_and_warning(series_with):
    s = dict(series_with(direction="flat", data_start="2024-05", gap_months=8, months=16, reliability="medium",
                         reliability_cap="capped at medium: …", cap_kinds=["gap"]), titles=["T"], id="t|pl")
    assert "лише з 2024-05" in interpret.verdict(s, "uk")
    assert "only since 2024-05" in interpret.verdict(s, "en")
    w = " ".join(interpret.build_warnings([{"topic": "t", "missing_languages": []}], [s]))
    assert "2024-05" in w and '--article "pl:T" --article "pl:<old title>"' in w
    assert "(обмежено неповним рядом)" in interpret.verdict(s, "uk")                       # cap reason is not "low volume"


def test_verdict_marks_excess_above_a_seasonal_peak(series_with):
    s = series_with(spikes=[{"month": "2025-09", "seasonal_excess": True}], seasonal_peaks=[{"month": "2025-09"}])
    assert "2025-09 (надлишок понад сезонний пік)" in interpret.verdict(s, "uk")


def test_verdict_does_not_call_edition_wide_decline_a_loss_of_interest(series_with):
    # evals/transcripts/haiku-4.5_2026-09-24/english_learning_report.md, vi: "інтерес знижується … надійність
    # висока" at -23.1 % views but +2.4 % share of the edition.
    vi = dict(series_with(direction="declining", growth_pct=-23.1, growth_share_pct=2.4, direction_share="flat",
                          trend_annual_pct=-28.5, median_monthly=14568), lang="vi", title="Tiếng Anh")
    uk = interpret.verdict(vi, "uk")
    first = uk.split(": ", 1)[1]
    assert not first.startswith("інтерес знижується")
    assert first.startswith("перегляди падають разом із трафіком усього розділу")
    assert "відносний інтерес (частка в трафіку розділу) стабільний" in first.split(".")[0]
    assert "views are declining together with the whole edition" in interpret.verdict(vi, "en")


def test_verdict_reports_share_change_when_views_are_flat(series_with):
    s = series_with(direction="flat", growth_pct=-3.0, growth_share_pct=18.0, direction_share="growing")
    first = interpret.verdict(s, "uk").split(": ", 1)[1].split(".")[0]
    assert first.startswith("перегляди майже не змінились") and "частка в трафіку розділу) зростає" in first
    s = series_with(direction="flat", growth_pct=-3.0, growth_share_pct=12.0, direction_share="unclear")
    assert "без підтвердженого тренду" in interpret.verdict(s, "uk").split(".")[0]


def test_table_has_both_directions(series_with):
    t = interpret.table_md([series_with(direction="declining", direction_share="flat")])
    assert "| direction | direction (share) |" in t.split("\n")[0] and "| declining | flat |" in t


# ------------------------------------------------------------------ output size (README, iteration 7)
def _many_series(n):
    """n realistic series: stats computed from random data; a third tiny, some new articles."""
    import numpy as np
    from wiki_interest import stats
    months = [f"{2024 + k // 12}-{k % 12 + 1:02d}" for k in range(24)]
    rng = np.random.default_rng(0)
    out = []
    for i in range(n):
        vol = [80, 2000, 40000][i % 3]
        v = (vol * (1 + rng.uniform(-.4, .6)) ** (np.arange(24) / 12) * np.exp(rng.normal(0, .2, 24))).astype(int)
        if i % 7 == 0:
            v[:9] = 0
        st = stats.analyze_series(months, [int(x) for x in v], [10**8] * 24)
        st.pop("_clean")
        lang = f"x{i:03d}"
        out.append({"id": f"english-language|{lang}", "topic": "English language", "lang": lang, "titles": ["Anglų kalba"],
                    "title": "Anglų kalba", "proxy": None, "rename_fix": None, "months": months, "stats": st})
    return out


def test_summary_for_300_languages_fits_the_agent_output_limit():
    import json
    series = _many_series(300)
    topics = [{"topic": "English language", "resolved": [], "alternatives": [],
               "missing_languages": [f"m{i}" for i in range(40)]}]
    analysis = {"ui": "uk", "proxy_for": None, "period": {"start": "2024-01", "end": "2025-12", "months": 24},
                "topics": topics, "series": series, "warnings": interpret.build_warnings(topics, series),
                "caveats": list(interpret.GLOBAL_CAVEATS["uk"])}
    run_dir = Path("/home/someone/.local/share/wiki-interest/runs/english-language_300langs-abcdef_202401-202512")
    out = interpret.summary(run_dir, analysis)
    text = json.dumps(out, ensure_ascii=False, indent=1)
    assert len(text) <= interpret.MAX_OUTPUT_CHARS
    sk = out["answer_skeleton"]
    assert sk.count("<ЗАПОВНИ") == 1 and "**Обмеження:**" in sk and "готовності платити" in sk
    n = out["shown"]["series_shown"]
    assert 3 <= n < 300 and out["shown"]["series_total"] == 300 and len(out["verdicts"]) == n
    assert f"Показано {n} з 300" in sk and str(run_dir / interpret.FULL_FILE) in sk
    comparison = next(l for l in sk.split("\n") if l.startswith("**Порівняння мов**"))
    assert all(s["lang"] in comparison for s in series)                    # compact, but every language


def test_small_summary_is_unchanged(series_with):
    s = dict(series_with(), id="t|pl")
    analysis = {"ui": "uk", "period": {"start": "2024-01", "end": "2025-12", "months": 24},
                "topics": [{"topic": "t", "missing_languages": []}], "series": [s], "caveats": []}
    out = interpret.summary(Path("runs/x"), analysis)
    assert "shown" not in out and len(out["verdicts"]) == 1
