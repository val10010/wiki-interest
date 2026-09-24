"""report.py: nothing falls off the one-page PDF silently (audit before submission found three such cases)."""
from pathlib import Path

from wiki_interest import charts, report

MONTHS = [f"{2023 + (k + 8) // 12}-{(k + 8) % 12 + 1:02d}" for k in range(24)]


def _series(lang, share_change, title=None):
    return {"lang": lang, "topic": "t", "title": title or f"Title {lang}", "months": MONTHS,
            "views": [1000 + k for k in range(24)], "views_clean": [1000 + k for k in range(24)],
            "project_total": [10**8] * 24,
            "stats": {"direction": "flat", "growth_pct": 1.0, "growth_share_pct": share_change,
                      "trend_annual_pct": 0.0, "median_monthly": 1000, "reliability": "high", "spikes": []}}


def _analysis(series):
    return {"period": {"start": MONTHS[0], "end": MONTHS[-1], "months": 24}, "ui": "uk", "series": series,
            "topics": [{"topic": "t", "resolved": [{"qid": "Q1", "label_en": "Topic label"}], "missing_languages": []}]}


def test_pdf_keeps_the_top_series_by_share_change_and_says_so(tmp_path):
    # 15 languages in input order with the best two (fa, tr) last: the old code showed the first ten.
    langs = [f"l{i}" for i in range(13)] + ["fa", "tr"]
    series = [_series(l, -20.0 - i) for i, l in enumerate(langs[:13])] + [_series("fa", 4.0), _series("tr", 0.6)]
    fit = report.save_pdf(_analysis(series), str(tmp_path / "r.pdf"), "T", "C", [], "uk")
    assert (fit["series_shown"], fit["series_total"]) == (report.MAX_SERIES, 15)
    assert (tmp_path / "r.pdf").read_bytes()[:4] == b"%PDF"


def test_long_conclusion_shrinks_then_is_cut_with_a_flag(tmp_path):
    ok = "Речення з цифрами і висновком для засновника. " * 20          # ~940 chars: shrinks, not cut
    fit = report.save_pdf(_analysis([_series("pl", 1.0)]), str(tmp_path / "a.pdf"), "T", ok, [], "uk")
    assert not fit["conclusion_truncated"]
    too_long = ok * 4
    fit = report.save_pdf(_analysis([_series("pl", 1.0)]), str(tmp_path / "b.pdf"), "T", too_long, [], "uk")
    assert fit["conclusion_truncated"] and fit["conclusion_lines"] == report.CONCLUSION_FITS[-1][2]


def test_footer_always_keeps_the_method_and_counts_dropped_caveats(tmp_path):
    caveats = [f"Примітка {i}: " + "довгий текст " * 15 for i in range(12)]
    fit = report.save_pdf(_analysis([_series("pl", 1.0)]), str(tmp_path / "c.pdf"), "T", "C", caveats, "uk")
    assert 0 < fit["caveats_shown"] < fit["caveats_total"] == 12


def test_unrenderable_title_falls_back_to_english_label(tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "renderable", lambda text: text.isascii())   # a machine with DejaVu Sans only
    monkeypatch.setattr(report, "renderable", charts.renderable)
    fit = report.save_pdf(_analysis([_series("ja", 1.0, "英語"), _series("en", 0.0, "English")]),
                          str(tmp_path / "d.pdf"), "T", "C", [], "uk")
    assert fit["titles_substituted"] == ["ja"]


def test_font_fallback_list_starts_with_bundled_font():
    assert charts.font_families()[0] == "DejaVu Sans"
    assert charts.renderable("Język angielski · Английский · İngilizce")
