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


def test_table_sorts_by_share_change_even_when_it_is_exactly_zero(series_with):
    # `x or y` treated a 0.0 share change as missing and sorted that row by raw growth instead.
    zero = dict(series_with(growth_pct=50.0, growth_share_pct=0.0), lang="a")
    small = dict(series_with(growth_pct=-30.0, growth_share_pct=3.0), lang="b")
    rows = interpret.table_md([zero, small]).split("\n")[2:]
    assert rows[0].startswith("| t · b") and rows[1].startswith("| t · a")


def test_table_shows_tiny_p_values_as_a_bound(series_with):
    assert "<0.001" in interpret.table_md([series_with(trend_p_value=0.0)])
    assert "| 0.031 |" in interpret.table_md([series_with(trend_p_value=0.0312)])
