"""Trend statistics and a transparent reliability score for one monthly series.

Everything here is deterministic and documented in references/METHODOLOGY.md,
so the agent reports numbers instead of eyeballing charts.
"""
from __future__ import annotations

import math

import numpy as np

SPIKE_Z = 3.5          # robust z-score threshold for anomalous months
SPIKE_RATIO = 1.8      # ... and at least this many times the local median
SEASONAL_RATIO = 1.5   # same month a year apart this elevated -> seasonal peak, not anomaly
LOW_VOLUME = 3000      # median monthly views below this -> "low volume"
VERY_LOW_VOLUME = 300


def _pct(new: float, old: float) -> float | None:
    if old <= 0:
        return None
    return round((new / old - 1) * 100, 1)


def theil_sen(y: np.ndarray) -> float:
    """Median of pairwise slopes (robust to outliers). Units: y per step."""
    n = len(y)
    i, j = np.triu_indices(n, 1)
    return float(np.median((y[j] - y[i]) / (j - i)))


def mann_kendall_p(y: np.ndarray) -> float:
    """Two-sided p-value of the Mann-Kendall monotonic trend test (normal approx.)."""
    n = len(y)
    if n < 4:
        return 1.0
    i, j = np.triu_indices(n, 1)
    s = float(np.sign(y[j] - y[i]).sum())
    _, counts = np.unique(y, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18
    if var <= 0:
        return 1.0
    z = (s - np.sign(s)) / math.sqrt(var)
    return float(math.erfc(abs(z) / math.sqrt(2)))


def detect_spikes(v: np.ndarray, window: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Return (mask of spike months, baseline = rolling median).

    A month is a spike if its log-residual vs. the centred rolling median is a
    robust outlier AND it is at least SPIKE_RATIO x the baseline. Typical
    causes: news, viral posts, Google Doodles, bot traffic mislabelled as user.
    """
    n = len(v)
    lv = np.log1p(v.astype(float))
    half = window // 2
    base = np.array([np.median(lv[max(0, k - half):min(n, k + half + 1)]) for k in range(n)])
    resid = lv - base
    mad = np.median(np.abs(resid - np.median(resid))) * 1.4826
    mad = max(mad, 0.05)
    z = resid / mad
    mask = (z > SPIKE_Z) & (np.expm1(lv) > SPIKE_RATIO * np.expm1(base))
    return mask, np.expm1(base)


def split_seasonal(v: np.ndarray, mask: np.ndarray, base: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split detected spikes into (anomalies, seasonal peaks).

    A spike whose calendar month is also elevated (>= SEASONAL_RATIO x its own
    baseline) one year earlier or later is a recurring seasonal peak (school
    start, New-year diets), not an anomaly. Seasonal peaks are kept in the data:
    the year-over-year comparison already cancels them.
    """
    n = len(v)
    elevated = v >= SEASONAL_RATIO * np.maximum(base, 1)
    seasonal = np.zeros(n, dtype=bool)
    for k in np.where(mask)[0]:
        seasonal[k] = any(0 <= j < n and elevated[j] for j in (k - 12, k + 12))
    return mask & ~seasonal, seasonal


def window_growth(v: np.ndarray) -> dict:
    """Recent vs previous period. With >=24 months: last 12 vs previous 12
    (same calendar months -> seasonality cancels). Otherwise halves."""
    n = len(v)
    if n >= 24:
        recent, prev = v[-12:], v[-24:-12]
        wins = int(np.sum(recent > prev))
        return {"method": "last 12 months vs previous 12", "growth_pct": _pct(recent.mean(), prev.mean()),
                "months_up_yoy": wins, "months_compared": 12, "seasonality_controlled": True}
    h = n // 2
    recent, prev = v[-h:], v[-2 * h:-h] if h else v
    return {"method": f"last {h} months vs previous {h}", "growth_pct": _pct(recent.mean(), prev.mean()) if h else None,
            "months_up_yoy": None, "months_compared": None, "seasonality_controlled": False}


def analyze_series(months: list[str], views: list[int], project_total: list[int] | None) -> dict:
    v = np.array(views, dtype=float)
    n = len(v)
    out: dict = {"months": n, "total_views": int(v.sum()),
                 "median_monthly": int(np.median(v)) if n else 0,
                 "last_month": int(v[-1]) if n else 0}
    if n < 6 or v.sum() == 0:
        out.update({"direction": "no data", "reliability": "low", "score": 0,
                    "reasons": ["fewer than 6 months of data or zero views"]})
        return out

    spikes, base = detect_spikes(v)
    spikes, seasonal = split_seasonal(v, spikes, base)
    clean = np.where(spikes, base, v)
    out["_clean"] = [int(x) for x in clean]
    out["spikes"] = [{"month": months[k], "views": int(v[k]), "x_baseline": round(v[k] / max(base[k], 1), 1)}
                     for k in np.where(spikes)[0]]
    out["seasonal_peaks"] = [{"month": months[k], "views": int(v[k]), "x_baseline": round(v[k] / max(base[k], 1), 1)}
                             for k in np.where(seasonal)[0]]
    out["spike_share_pct"] = round(float((v[spikes] - base[spikes]).sum() / v.sum() * 100), 1)

    raw = window_growth(v)
    cln = window_growth(clean)
    out["growth_raw_pct"] = raw["growth_pct"]
    out["growth_pct"] = cln["growth_pct"]           # headline number: spikes removed
    out["growth_method"] = cln["method"]
    out["months_up_yoy"] = cln["months_up_yoy"]
    out["seasonality_controlled"] = cln["seasonality_controlled"]

    ly = np.log1p(clean)
    slope = theil_sen(ly)
    out["trend_annual_pct"] = round((math.exp(slope * 12) - 1) * 100, 1)
    out["trend_p_value"] = round(mann_kendall_p(ly), 4)

    share = None
    if project_total is not None and min(project_total) > 0:
        t = np.array(project_total, dtype=float)
        share = clean / t * 1e6
        out["per_million_views_last12"] = round(float(share[-12:].mean()), 2)
        out["growth_share_pct"] = window_growth(share)["growth_pct"]
        out["project_growth_pct"] = window_growth(t)["growth_pct"]

    # ---------------------------------------------------------- reliability
    score, reasons = 0, []
    med = out["median_monthly"]
    if med >= LOW_VOLUME:
        score += 2
    elif med >= VERY_LOW_VOLUME:
        score += 1; reasons.append(f"low volume (median {med} views/month): small absolute changes look large")
    else:
        reasons.append(f"very low volume (median {med} views/month): percentages are unreliable")

    p = out["trend_p_value"]
    if p < 0.05:
        score += 2
    elif p < 0.2:
        score += 1; reasons.append(f"trend only weakly significant (Mann-Kendall p={p})")
    else:
        reasons.append(f"no statistically significant monotonic trend (p={p})")

    wins = out["months_up_yoy"]
    if wins is not None:
        if wins >= 9 or wins <= 3:
            score += 2
        elif wins >= 7 or wins <= 5:
            score += 1; reasons.append(f"mixed month-by-month picture ({wins}/12 months above last year)")
        else:
            reasons.append(f"inconsistent: {wins}/12 months above last year")
    else:
        reasons.append("under 24 months: seasonality not controlled")

    g_raw, g = out["growth_raw_pct"], out["growth_pct"]
    same_sign = g_raw is not None and g is not None and (g_raw >= 0) == (g >= 0)
    if out["spike_share_pct"] < 25 and same_sign:
        score += 2
    else:
        reasons.append(f"spikes drive {out['spike_share_pct']}% of views; raw growth {g_raw}% vs {g}% without spikes")

    if share is not None and out.get("growth_share_pct") is not None and g is not None:
        if (out["growth_share_pct"] >= 0) == (g >= 0):
            score += 1
        else:
            reasons.append(f"whole-wiki traffic moved {out['project_growth_pct']}%: "
                           f"relative interest ({out['growth_share_pct']}%) disagrees with raw views")
    if n >= 24:
        score += 1

    out["score"] = score
    level = "high" if score >= 8 else "medium" if score >= 5 else "low"
    # Hard caps: too few views means percentages are noise, whatever else says.
    cap = None
    if med < VERY_LOW_VOLUME and level != "low":
        level, cap = "low", f"capped at low: median {med} < {VERY_LOW_VOLUME} views/month"
    elif med < LOW_VOLUME and level == "high":
        level, cap = "medium", f"capped at medium: median {med} < {LOW_VOLUME} views/month"
    if cap:
        reasons.append(f"reliability {cap} (score alone would give more)")
    out["reliability"] = level
    out["reliability_cap"] = cap
    if g is None:
        direction = "unclear"
    elif g >= 10 and out["trend_annual_pct"] > 0 and p < 0.2:
        direction = "growing"
    elif g <= -10 and out["trend_annual_pct"] < 0 and p < 0.2:
        direction = "declining"
    elif abs(g) < 10:
        direction = "flat"
    else:
        direction = "unclear"
    out["direction"] = direction
    out["reasons"] = reasons
    return out
