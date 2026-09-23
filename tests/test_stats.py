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
