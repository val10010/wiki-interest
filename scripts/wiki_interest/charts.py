"""PNG chart panels (matplotlib only). Shared by the run chart and the PDF report."""
from __future__ import annotations

import datetime as dt

import functools

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ft2font import FT2Font  # noqa: E402

# DejaVu Sans (bundled with matplotlib) covers Latin, Cyrillic, Greek, Arabic and Hebrew but not CJK,
# Thai or Indic scripts. Matplotlib falls back per glyph through this list, so article titles such as
# 英語 render wherever one of these system fonts exists (macOS, Windows, Linux with Noto/Droid).
FONT_FALLBACKS = ["Arial Unicode MS", "Hiragino Sans", "PingFang SC", "Apple SD Gothic Neo",       # macOS
                  "Noto Sans CJK JP", "Noto Sans CJK SC", "Noto Sans", "Droid Sans Fallback",      # Linux
                  "Microsoft YaHei", "Malgun Gothic", "MS Gothic", "Segoe UI"]                     # Windows


@functools.lru_cache(maxsize=None)
def font_families() -> tuple[str, ...]:
    installed = {f.name for f in fm.fontManager.ttflist}
    return ("DejaVu Sans",) + tuple(f for f in FONT_FALLBACKS if f in installed)


@functools.lru_cache(maxsize=None)
def _faces() -> tuple[FT2Font, ...]:
    return tuple(FT2Font(fm.findfont(fm.FontProperties(family=f), fallback_to_default=False))
                 for f in font_families())


def renderable(text: str) -> bool:
    """True if every character of `text` has a glyph in one of the fonts we can draw with."""
    return all(any(face.get_char_index(ord(ch)) for face in _faces()) for ch in text if not ch.isspace())


plt.rcParams.update({"font.family": list(font_families()), "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False})
PALETTE = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2",
           "#ca8a04", "#db2777", "#4b5563", "#65a30d"]

L = {
    "uk": {"abs": "Перегляди за місяць (лише люди, лог. шкала)",
           "idx_short": "Відносний інтерес (частка у переглядах вікі, без сплесків), індекс: перші 12 міс. = 100",
           "spike": "аномальний сплеск", "series": "Тема / мова", "article": "Стаття",
           "median": "Медіана/міс", "growth": "Зміна %", "rel": "Відн. %",
           "trend": "Тренд/рік", "rel_col": "Надійність", "conclusion": "Висновок",
           "caveats": "Припущення та обмеження", "method": "Метод",
           "source": "Джерело: Wikimedia Pageviews API (agent=user), {start} – {end}. Згенеровано {today}.",
           "rel_map": {"high": "висока", "medium": "середня", "low": "низька"},
           "method_txt": ("Зміна = середнє за останні 12 міс. проти попередніх 12 (ті самі календарні місяці, "
                          "сплески замінено ковзною медіаною). Відн. зміна = те саме для частки статті у всіх "
                          "переглядах мовного розділу. Тренд = нахил Тейла–Сена, значущість — тест Манна–Кендалла. "
                          "Надійність — бал 0–10 за обсягом, значущістю, стабільністю по місяцях, впливом сплесків "
                          "і узгодженістю з нормалізацією.")},
    "en": {"abs": "Monthly views (humans only, log scale)",
           "idx_short": "Relative interest (share of wiki views, spikes removed), index: first 12 months = 100",
           "spike": "anomalous spike", "series": "Topic / language", "article": "Article",
           "median": "Median/mo", "growth": "Change, %", "rel": "Rel. change, %",
           "trend": "Trend/yr, %", "rel_col": "Reliability", "conclusion": "Conclusion",
           "caveats": "Assumptions & limitations", "method": "Method",
           "source": "Source: Wikimedia Pageviews API (agent=user), {start} – {end}. Generated {today}.",
           "rel_map": {"high": "high", "medium": "medium", "low": "low"},
           "method_txt": ("Change = mean of last 12 months vs previous 12 (same calendar months, spikes replaced by "
                          "rolling median). Rel. change = same for the article's share of all views of that language "
                          "edition. Trend = Theil–Sen slope, significance = Mann–Kendall test. Reliability = 0–10 "
                          "score from volume, significance, month-by-month consistency, spike impact and agreement "
                          "with normalisation.")},
}


def _dates(months):
    return [dt.date(int(m[:4]), int(m[5:7]), 15) for m in months]


def series_label(s):
    return f"{s['topic']} · {s['lang']}" if s.get("multi_topic") else s["lang"]


def fmt_num(x, signed=True):
    if x is None:
        return "—"
    return f"{x:+.0f}" if signed else f"{x:,.0f}".replace(",", " ")


def draw_panels(ax_abs, ax_idx, series, ui):
    for k, s in enumerate(series):
        c = PALETTE[k % len(PALETTE)]
        d = _dates(s["months"])
        v = np.array(s["views"], float)
        ax_abs.plot(d, np.maximum(v, 1), color=c, lw=1.6, label=series_label(s))
        spike_months = {sp["month"] for sp in s["stats"].get("spikes", [])}
        sx = [d[i] for i, m in enumerate(s["months"]) if m in spike_months]
        sy = [max(v[i], 1) for i, m in enumerate(s["months"]) if m in spike_months]
        if sx:
            ax_abs.scatter(sx, sy, s=40, facecolors="none", edgecolors=c, lw=1.4, zorder=3)
        t = np.array(s.get("project_total") or [], float)
        vc = np.array(s.get("views_clean") or s["views"], float)
        if len(t) == len(v) and t.min() > 0:
            share = vc / t
            k0 = min(12, len(share))
            base = share[:k0].mean()
            if base > 0:
                ax_idx.plot(d, share / base * 100, color=c, lw=1.6, label=series_label(s))
    ax_abs.set_yscale("log")
    # Default log ticks show only powers of ten (often a single "10^3"); use 1-2-5 steps in plain numbers.
    ax_abs.yaxis.set_major_locator(mticker.LogLocator(base=10, subs=(1, 2, 5)))
    ax_abs.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: fmt_num(y, signed=False)))
    ax_abs.yaxis.set_minor_formatter(mticker.NullFormatter())
    ax_abs.set_title(L[ui]["abs"], loc="left", fontsize=9)
    ax_idx.set_title(L[ui]["idx_short"], loc="left", fontsize=9)
    ax_idx.axhline(100, color="#9ca3af", lw=0.8, ls="--")
    for ax in (ax_abs, ax_idx):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax.grid(axis="y", color="#e5e7eb", lw=0.6)
        ax.tick_params(axis="x", labelsize=7)
    ax_abs.legend(fontsize=7, frameon=False, ncol=2)


def save_chart(analysis: dict, path: str, ui: str = "uk"):
    fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6.4), constrained_layout=True)
    draw_panels(a, b, analysis["series"], ui)
    fig.savefig(path, dpi=130)
    plt.close(fig)
