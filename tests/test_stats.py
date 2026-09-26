"""stats.py: growth, spikes vs seasonal peaks, trend significance, reliability score."""
import numpy as np

from wiki_interest import stats

MONTHS = [f"{2023 + k // 12}-{k % 12 + 1:02d}" for k in range(24)]
FLAT_WIKI = [10**8] * 24


def test_growth_detected_and_reliable():
    v = [int(5000 * 1.5 ** (k / 12)) for k in range(24)]
    s = stats.analyze_series(MONTHS, v, FLAT_WIKI)
    assert s["direction"] == "growing"
    assert 35 < s["growth_pct"] < 65
    assert s["reliability"] == "high"


def test_spike_removed_from_headline_growth():
    v = [5000] * 24
    v[20] = 60000
    s = stats.analyze_series(MONTHS, v, FLAT_WIKI)
    assert [x["month"] for x in s["spikes"]] == [MONTHS[20]]
    assert s["growth_raw_pct"] > 15          # a naive comparison would call it growth
    assert abs(s["growth_pct"]) < 1          # after spike removal: flat
    assert s["direction"] == "flat"


def test_recurring_peak_is_seasonal_not_anomaly():
    v = [5000] * 24
    v[8] = v[20] = 15000                      # September both years (school start)
    s = stats.analyze_series(MONTHS, v, FLAT_WIKI)
    assert s["spikes"] == []
    assert [p["month"] for p in s["seasonal_peaks"]] == [MONTHS[8], MONTHS[20]]
    assert abs(s["growth_pct"]) < 1           # same calendar months compared -> cancels


def test_low_volume_is_low_reliability():
    rng = np.random.default_rng(0)
    v = list((50 * rng.normal(1, 0.4, 24)).clip(0).astype(int))
    s = stats.analyze_series(MONTHS, v, FLAT_WIKI)
    assert s["reliability"] == "low"
    assert any("volume" in r for r in s["reasons"])


def test_volume_cap_is_explicit():
    v = [int(1000 * 1.5 ** (k / 12)) for k in range(24)]   # clean trend, but only ~1k views/month
    s = stats.analyze_series(MONTHS, v, FLAT_WIKI)
    assert s["score"] >= 8 and s["reliability"] == "medium"
    assert s["reliability_cap"] and any("capped" in r for r in s["reasons"])


def test_normalisation_disagreement_flagged():
    v = [int(5000 * 1.1 ** (k / 12)) for k in range(24)]          # +10%/yr
    total = [int(1e8 * 1.5 ** (k / 12)) for k in range(24)]        # whole wiki +50%/yr
    s = stats.analyze_series(MONTHS, v, total)
    assert s["growth_share_pct"] < 0
    assert any("whole-wiki" in r for r in s["reasons"])


def test_mann_kendall():
    assert stats.mann_kendall_p(np.arange(20.0)) < 0.001
    assert stats.mann_kendall_p(np.array([1.0, 2, 1, 2, 1, 2, 1, 2])) > 0.5


def test_direction_needs_significant_trend():
    # Calibration (METHODOLOGY): with p < 0.2 a flat topic was called "growing" in ~11 % of cases.
    assert stats.direction(15.0, 12.0, 0.03) == "growing"
    assert stats.direction(15.0, 12.0, 0.10) == "unclear"
    assert stats.direction(-15.0, -12.0, 0.03) == "declining"
    assert stats.direction(-15.0, -12.0, 0.10) == "unclear"
    assert stats.direction(5.0, 12.0, 0.01) == "flat"
    assert stats.direction(None, 0.0, 0.5) == "unclear"


# ------------------------------------------------------------------ review fixes (README, iteration 7)
def _renamed():
    """Flat ~20k/month article renamed in month 9: the new title had no views before (review repro, series A)."""
    rng = np.random.default_rng(1)
    v = (20000 * np.exp(rng.normal(0, .1, 24))).astype(int)
    v[:8] = 0
    return [int(x) for x in v]


def test_leading_gap_counts_zeros_and_redirect_trickle():
    assert stats.leading_gap([0, 0, 0] + [1000] * 10) == 3
    assert stats.leading_gap([3, 7, 40] + [1000] * 10) == 3        # < 5 % of the later median: a redirect's trickle
    assert stats.leading_gap([60] + [1000] * 10) == 0               # 6 %: a real (small) month
    assert stats.leading_gap([1000] * 12) == 0


def test_renamed_article_is_not_growth():
    s = stats.analyze_series(MONTHS, _renamed(), FLAT_WIKI)
    assert s["direction"] != "growing" and s["reliability"] != "high"
    assert s["data_start"] == MONTHS[8] and s["gap_months"] == 8
    assert any(MONTHS[8] in r and "renamed" in r for r in s["reasons"])
    assert len(s["_clean"]) == 24                                  # chart still gets the whole period


def test_short_remainder_after_a_gap_is_capped_at_low():
    v = [0] * 14 + [int(5000 * 1.5 ** (k / 12)) for k in range(10)]  # a clean trend, but only 10 real months
    s = stats.analyze_series(MONTHS, v, FLAT_WIKI)
    assert s["reliability"] == "low" and s["cap_kinds"] == ["gap"] and "since" in s["reliability_cap"]


def _outlier_on_seasonal_peak():
    """Review repro, series B: 11 of 12 months -5 %, September 1.8x a year ago and 6x now."""
    v = np.full(24, 10000.0)
    v[12:] *= .95
    v[8], v[20] = 18000, 60000
    return [int(x) for x in v]


def test_outlier_on_top_of_a_seasonal_peak_is_cut_to_the_seasonal_level():
    s = stats.analyze_series(MONTHS, _outlier_on_seasonal_peak(), FLAT_WIKI)
    assert abs(s["growth_pct"]) < 10
    excess = [x for x in s["spikes"] if x.get("seasonal_excess")]
    assert [x["month"] for x in excess] == [MONTHS[20]] and excess[0]["kept"] < 35000
    assert MONTHS[20] in [p["month"] for p in s["seasonal_peaks"]]   # the seasonal part is still a peak
