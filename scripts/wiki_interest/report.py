"""One-page A4 PDF: agent's conclusion + table + charts + caveats + method.

Numbers, table, charts and the caveats block are generated from analysis.json;
only the conclusion text comes from the agent. Everything that does not fit on
the page is reported back (never dropped silently): which series are shown,
whether the conclusion was cut, how many caveats were left out.
"""
from __future__ import annotations

import datetime as dt
import textwrap
import warnings

from . import interpret
from .charts import L, draw_panels, fmt_num, plt, renderable, series_label  # plt from charts: Agg backend set

MAX_SERIES = 10                 # table rows / chart lines that stay legible on one page
CONCLUSION_FITS = [             # (font size, wrap width, max lines): shrink before cutting
    (8.6, 105, 9), (7.8, 116, 11), (7.0, 130, 13)]
MAX_CONCLUSION_CHARS = CONCLUSION_FITS[-1][1] * CONCLUSION_FITS[-1][2]
FOOTER_LINES = 16               # caveats + method block at the bottom of the page

NOTE = {
    "uk": {"shown": "Показано {n} із {total} серій із найбільшою зміною частки (порядок як у таблиці); "
                    "усі серії є в analysis.json.",
           "title": "Назви статей ({langs}) не відтворює жоден доступний шрифт: показано англійську назву поняття."},
    "en": {"shown": "Showing the {n} of {total} series with the largest share change (table order); "
                    "all series are in analysis.json.",
           "title": "Article titles ({langs}) have no glyphs in any available font: the English concept label is shown."},
}


def _fit_conclusion(conclusion: str) -> tuple[list[str], float, bool]:
    """Wrap the agent's text; shrink the font up to twice, then cut with an ellipsis."""
    for size, width, max_lines in CONCLUSION_FITS:
        lines = []
        for para in conclusion.split("\n"):
            lines += textwrap.wrap(para, width) or [""]
        if len(lines) <= max_lines:
            return lines, size, False
    lines = lines[:max_lines]
    lines[-1] = lines[-1][:width - 1].rstrip() + "…"
    return lines, size, True


def _display_title(s: dict, analysis: dict) -> tuple[str, bool]:
    """Article title for the table, or the English label when no font can draw it."""
    if renderable(s["title"]):
        return s["title"], False
    labels = [r["label_en"] for t in analysis["topics"] if t["topic"] == s["topic"] for r in t.get("resolved", [])]
    if s.get("proxy"):
        labels = [interpret.proxy_label(s)]
    return " + ".join(l for l in labels if l) or s["lang"], True


def save_pdf(analysis: dict, path: str, title: str, conclusion: str,
             caveats: list[str], ui: str = "uk") -> dict:
    t, notes = L[ui], NOTE[ui]
    fig = plt.figure(figsize=(8.27, 11.69))  # A4
    y = 0.965
    fig.text(0.06, y, title, fontsize=15, weight="bold", va="top")
    y -= 0.03
    p = analysis["period"]
    fig.text(0.06, y, t["source"].format(start=p["start"], end=p["end"], today=dt.date.today()),
             fontsize=7.5, color="#6b7280", va="top")
    y -= 0.03

    # Conclusion (written by the agent; numbers must come from analysis.json)
    fig.text(0.06, y, t["conclusion"], fontsize=10.5, weight="bold", va="top")
    y -= 0.022
    lines, size, truncated = _fit_conclusion(conclusion)
    fig.text(0.06, y, "\n".join(lines), fontsize=size, va="top", linespacing=1.45)
    y -= 0.0165 * size / 8.6 * len(lines) + 0.015

    # Table: same order as the markdown table, so the PDF never drops the most interesting series
    all_series = sorted(analysis["series"], key=interpret.rank_key, reverse=True)
    series = all_series[:MAX_SERIES]
    rows, unrenderable = [], []
    for s in series:
        st = s["stats"]
        mark = " [proxy]" if s.get("proxy") else ""
        shown, substituted = _display_title(s, analysis)
        if substituted:
            unrenderable.append(s["lang"])
        room = 29 - len(mark)  # truncate the title, never the marker
        shown = (shown[:room - 1] + "…") if len(shown) > room else shown
        rows.append([series_label(s), shown + mark,
                     fmt_num(st.get("median_monthly"), False), fmt_num(st.get("growth_pct")),
                     fmt_num(st.get("growth_share_pct")), fmt_num(st.get("trend_annual_pct")),
                     t["rel_map"].get(st.get("reliability"), "—")])
    h = 0.021 * (len(rows) + 1)
    ax_t = fig.add_axes([0.06, y - h, 0.88, h])
    ax_t.axis("off")
    tbl = ax_t.table(cellText=rows, colLabels=[t["series"], t["article"], t["median"], t["growth"],
                                              t["rel"], t["trend"], t["rel_col"]],
                     loc="upper left", cellLoc="left", colLoc="left",
                     colWidths=[0.16, 0.27, 0.13, 0.1, 0.1, 0.11, 0.13])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.8)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#e5e7eb")
        cell.set_height(1 / (len(rows) + 1))
        if r == 0:
            cell.set_facecolor("#f3f4f6"); cell.set_text_props(weight="bold")
    y -= h + 0.012
    table_notes = []
    if len(all_series) > len(series):
        table_notes.append(notes["shown"].format(n=len(series), total=len(all_series)))
    if unrenderable:
        table_notes.append(notes["title"].format(langs=", ".join(unrenderable)))
    if table_notes:
        fig.text(0.06, y, "\n".join(table_notes), fontsize=6.8, color="#6b7280", va="top", linespacing=1.3)
        y -= 0.012 * len(table_notes)
    y -= 0.018

    # Charts
    ch = min(0.44, y - 0.2)
    gap = 0.045
    ph = (ch - gap) / 2
    ax_a = fig.add_axes([0.09, y - ph, 0.85, ph])
    ax_b = fig.add_axes([0.09, y - 2 * ph - gap, 0.85, ph])
    draw_panels(ax_a, ax_b, series, ui)
    y -= ch + 0.04

    # Caveats + method: the method always fits; caveats fill the remaining lines in priority
    # order (report_caveats puts proxy / low-reliability / user notes first).
    fig.text(0.06, y, t["caveats"], fontsize=9.5, weight="bold", va="top")
    y -= 0.018
    method = [""] + textwrap.wrap(t["method"] + ": " + t["method_txt"], 125)
    budget = FOOTER_LINES - len(method)
    cl, caveats_shown = [], 0
    for c in caveats:
        w = textwrap.wrap(c, 118)
        block = ["• " + w[0]] + ["  " + x for x in w[1:]]
        if len(cl) + len(block) > budget:
            break
        cl += block
        caveats_shown += 1
    fig.text(0.06, y, "\n".join(cl + method), fontsize=7, va="top", color="#374151", linespacing=1.4)
    with warnings.catch_warnings():
        # User-supplied title/conclusion may still contain glyphs no font has; never spam the agent's stderr.
        warnings.filterwarnings("ignore", message="Glyph .* missing")
        fig.savefig(path)
    plt.close(fig)
    return {"series_shown": len(series), "series_total": len(all_series),
            "conclusion_lines": len(lines), "conclusion_truncated": truncated,
            "caveats_shown": caveats_shown, "caveats_total": len(caveats),
            "titles_substituted": unrenderable}
