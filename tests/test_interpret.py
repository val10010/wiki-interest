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
