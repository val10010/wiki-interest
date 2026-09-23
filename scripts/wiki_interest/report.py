"""One-page A4 PDF: agent's conclusion + table + charts + caveats + method.

Numbers, table, charts and the caveats block are generated from analysis.json;
only the conclusion text comes from the agent.
"""
from __future__ import annotations

import datetime as dt
import textwrap

from .charts import L, draw_panels, fmt_num, plt, series_label  # plt from charts: Agg backend already set


def save_pdf(analysis: dict, path: str, title: str, conclusion: str,
             caveats: list[str], ui: str = "uk"):
    t = L[ui]
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
    lines = []
    for para in conclusion.split("\n"):
        lines += textwrap.wrap(para, 105) or [""]
    lines = lines[:9]
    fig.text(0.06, y, "\n".join(lines), fontsize=8.6, va="top", linespacing=1.45)
    y -= 0.0165 * len(lines) + 0.015

    # Table
    series = analysis["series"][:10]
    rows = []
    for s in series:
        st = s["stats"]
        mark = " [proxy]" if s.get("proxy") else ""
        room = 29 - len(mark)  # truncate the title, never the marker
        title = (s["title"][:room - 1] + "…") if len(s["title"]) > room else s["title"]
        rows.append([series_label(s), title + mark,
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
    y -= h + 0.03

    # Charts
    ch = min(0.44, y - 0.2)
    gap = 0.045
    ph = (ch - gap) / 2
    ax_a = fig.add_axes([0.09, y - ph, 0.85, ph])
    ax_b = fig.add_axes([0.09, y - 2 * ph - gap, 0.85, ph])
    draw_panels(ax_a, ax_b, series, ui)
    y -= ch + 0.04

    # Caveats + method
    fig.text(0.06, y, t["caveats"], fontsize=9.5, weight="bold", va="top")
    y -= 0.018
    cl = []
    for c in caveats[:7]:
        w = textwrap.wrap(c, 118)
        cl += ["• " + w[0]] + ["  " + x for x in w[1:]]
    cl += [""] + textwrap.wrap(t["method"] + ": " + t["method_txt"], 125)
    fig.text(0.06, y, "\n".join(cl[:16]), fontsize=7, va="top", color="#374151", linespacing=1.4)
    fig.savefig(path)
    plt.close(fig)
