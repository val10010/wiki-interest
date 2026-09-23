"""Calibrate stats.py on synthetic series whose truth is known.

For each scenario, thousands of 24-month series are generated (seasonality with a
random phase, autocorrelated AR(1) noise like real pageviews, optional one-off
spike) and passed through stats.analyze_series. The table shows how often the
tool says growing / flat / declining and how often reliability is "high".
It answers "how often does a flat topic get called growing?" and "how large must
growth be before we see it?". Also cross-checks Theil-Sen and Mann-Kendall
against scipy (needs `pip install scipy`; skipped otherwise).

  .venv/bin/python evals/calibrate_stats.py            # ~1 min
  .venv/bin/python evals/calibrate_stats.py --n 300    # quicker
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from wiki_interest import stats  # noqa: E402

MONTHS = [f"{2024 + (k + 8) // 12}-{(k + 8) % 12 + 1:02d}" for k in range(24)]
EDITION = [100_000_000] * 24  # constant edition traffic: share moves with views

SCENARIOS = [  # (name, annual growth, noise sigma, volume, spike multiplier)
    # Noise levels are measured: the robust s.d. of month-to-month log change of 15 real articles
    # ranged 0.10-0.47 with median 0.17 (large, calm articles ~0.12).
    ("flat, sigma 0.12", 0.00, 0.12, 5000, None),
    ("flat, sigma 0.17 (typical)", 0.00, 0.17, 5000, None),
    ("flat, sigma 0.25", 0.00, 0.25, 5000, None),
    ("flat + one spike x5, sigma 0.17", 0.00, 0.17, 5000, 5.0),
    ("+10%/yr, sigma 0.12", 0.10, 0.12, 5000, None),
    ("+20%/yr, sigma 0.12", 0.20, 0.12, 5000, None),
    ("+20%/yr, sigma 0.17", 0.20, 0.17, 5000, None),
    ("+50%/yr, sigma 0.17", 0.50, 0.17, 5000, None),
    ("-20%/yr, sigma 0.17", -0.20, 0.17, 5000, None),
    ("+50%/yr, 150 views/mo, sigma 0.25", 0.50, 0.25, 150, None),
]


def series(rng, growth, sigma, volume, spike, phi=0.5):
    k = np.arange(24)
    season = 1 + 0.15 * np.cos(2 * np.pi * (k - rng.integers(12)) / 12)
    e = np.zeros(24)
    for i in range(24):  # AR(1): month-to-month noise is correlated, as in real pageviews
        e[i] = phi * (e[i - 1] if i else 0) + rng.normal(0, sigma * np.sqrt(1 - phi ** 2))
    v = volume * (1 + growth) ** (k / 12) * season * np.exp(e)
    if spike:
        v[rng.integers(12, 24)] *= spike
    return np.maximum(v.round(), 0).astype(int).tolist()


def calibrate(n, seed):
    rng = np.random.default_rng(seed)
    print(f"| scenario (24 months, {n} series each) | growing | flat | declining | unclear | reliability high "
          "| growing AND high |")
    print("|---|---|---|---|---|---|---|")
    for name, growth, sigma, volume, spike in SCENARIOS:
        dirs, high, growing_high = Counter(), 0, 0
        for _ in range(n):
            st = stats.analyze_series(MONTHS, series(rng, growth, sigma, volume, spike), EDITION)
            dirs[st["direction"]] += 1
            high += st["reliability"] == "high"
            growing_high += st["reliability"] == "high" and st["direction"] == "growing"
        pct = lambda c: f"{100 * c / n:.0f}%"  # noqa: E731
        print(f"| {name} | {pct(dirs['growing'])} | {pct(dirs['flat'])} | {pct(dirs['declining'])} | "
              f"{pct(dirs['unclear'])} | {pct(high)} | {pct(growing_high)} |")


def crosscheck(seed):
    try:
        from scipy import stats as sp
    except ImportError:
        print("\nscipy not installed: Theil-Sen / Mann-Kendall cross-check skipped")
        return
    rng = np.random.default_rng(seed)
    d_slope, d_p = 0.0, 0.0
    for _ in range(500):
        y = np.log1p(series(rng, rng.uniform(-0.3, 0.3), 0.15, 3000, None))
        d_slope = max(d_slope, abs(stats.theil_sen(y) - sp.theilslopes(y)[0]))
        # Mann-Kendall = Kendall's tau between time and values; scipy has no continuity
        # correction, so small differences in p are expected.
        d_p = max(d_p, abs(stats.mann_kendall_p(y) - sp.kendalltau(np.arange(len(y)), y, method="asymptotic")[1]))
    print(f"\nvs scipy on 500 random series: max |Theil-Sen slope diff| = {d_slope:.1e}, "
          f"max |Mann-Kendall p diff| = {d_p:.3f} (continuity correction)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    calibrate(a.n, a.seed)
    crosscheck(a.seed)
