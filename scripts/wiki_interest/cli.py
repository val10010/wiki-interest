"""CLI: scripts/wi <command> ...

Commands
  resolve  QUERY            find the Wikidata item + article titles per language
  analyze  --topic ...      fetch pageviews, compute stats, draw chart -> run dir
  show     RUN_DIR          re-print the summary of an existing run (no network)
  report   RUN_DIR          render a one-page PDF from a run
  runs                      list previous runs (for follow-up questions)

Every command prints JSON; errors are {"error": ..., "hint": ...}, never a traceback.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import interpret, pipeline, report, wiki


def _print(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def cmd_resolve(args):
    r = pipeline.resolve_topic(args.query, args.search_lang)
    out = []
    for it in r["items"]:
        langs = pipeline.expand_langs(args.langs, it["sitelinks"]) if args.langs else None
        out.append({
            "qid": it["qid"], "label_en": it["label_en"],
            "languages_with_article": len(it["sitelinks"]),
            "titles": {l: it["sitelinks"].get(l) for l in langs} if langs else
                      {l: it["sitelinks"][l] for l in wiki.TOP_LANGS if l in it["sitelinks"]},
            "alternatives": it["alternatives"],
        })
    _print(out)


def cmd_analyze(args):
    start, end = pipeline.period(args.months, args.start, args.end)
    topics = args.topic or []
    analysis, langs = pipeline.build_analysis(
        topics, pipeline.parse_articles(args.article), args.langs, start, end,
        search_lang=args.search_lang, include_redirects=args.include_redirects, ui=args.ui,
        command=" ".join(sys.argv[1:]))
    name = args.name or pipeline.run_name(topics, langs, start, end, args.include_redirects)
    run_dir = Path(args.out) if args.out else pipeline.RUNS_DIR / name
    pipeline.save_run(analysis, run_dir)
    _print(interpret.summary(run_dir, analysis))


def cmd_show(args):
    run_dir = Path(args.run_dir)
    _print(interpret.summary(run_dir, pipeline.load_run(run_dir)))


def cmd_runs(args):
    _print(pipeline.list_runs())


def cmd_report(args):
    run_dir = Path(args.run_dir)
    analysis = pipeline.load_run(run_dir)
    ui = args.ui or analysis.get("ui", "uk")
    conclusion = args.conclusion
    if conclusion and conclusion.startswith("@"):
        conclusion = Path(conclusion[1:]).read_text(encoding="utf-8")
    if not conclusion:
        raise SystemExit("--conclusion is required: 3-6 sentences based on the numbers in the table.")
    out = Path(args.out) if args.out else run_dir / "report.pdf"
    title = args.title or ("Інтерес до теми у Wikipedia" if ui == "uk" else "Wikipedia interest report")
    fit = report.save_pdf(analysis, str(out), title, conclusion, interpret.report_caveats(analysis, ui, args.caveat), ui)
    result = {"pdf": str(out), **fit}
    if fit["conclusion_truncated"]:
        result["hint"] = (f"the conclusion did not fit on one page and was cut after {fit['conclusion_lines']} lines: "
                          f"shorten --conclusion to at most {report.MAX_CONCLUSION_CHARS} characters and rerun")
    if fit["series_total"] > fit["series_shown"]:
        result["note"] = (f"the PDF shows the {fit['series_shown']} of {fit['series_total']} series with the largest "
                          "share change (as in the table); all series stay in analysis.json")
    print(json.dumps(result, ensure_ascii=False))


class _Parser(argparse.ArgumentParser):
    """argparse prints usage errors to stderr and exits 2; the agent expects JSON on stdout like every
    other error. Sub-parsers inherit this class automatically."""

    def error(self, message):
        _fail(f"{self.prog}: {message}", f"see `{interpret.CMD} {self.prog.split(' ', 1)[-1]} -h` for the options")


def build_parser() -> argparse.ArgumentParser:
    ap = _Parser(prog="wi", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("resolve", help="find articles for a topic")
    r.add_argument("query")
    r.add_argument("--search-lang", default="en")
    r.add_argument("--langs", default=None, help="uk,pl | top:N | all")
    r.set_defaults(func=cmd_resolve)

    a = sub.add_parser("analyze", help="fetch + analyse + chart")
    a.add_argument("--topic", action="append", help="search text, Q-id, or 'A+B' to sum articles; repeatable")
    a.add_argument("--article", action="append", help="explicit lang:Title (bypasses search); repeatable")
    a.add_argument("--search-lang", default="en", help="language used to search the topic text")
    a.add_argument("--langs", default="en", help="uk,pl,cs | top:N | all")
    a.add_argument("--months", type=int, default=24)
    a.add_argument("--start", help="YYYY-MM (overrides --months)")
    a.add_argument("--end", help="YYYY-MM (default: last full month)")
    a.add_argument("--include-redirects", action="store_true")
    a.add_argument("--ui", default="uk", choices=["uk", "en"], help="language of chart/report labels")
    a.add_argument("--name", help="run name")
    a.add_argument("--out", help="run directory")
    a.set_defaults(func=cmd_analyze)

    s = sub.add_parser("show", help="print summary of an existing run")
    s.add_argument("run_dir")
    s.set_defaults(func=cmd_show)

    p = sub.add_parser("report", help="one-page PDF")
    p.add_argument("run_dir")
    p.add_argument("--title")
    p.add_argument("--conclusion", help="text or @file")
    p.add_argument("--caveat", action="append")
    p.add_argument("--ui", choices=["uk", "en"])
    p.add_argument("--out")
    p.set_defaults(func=cmd_report)

    l = sub.add_parser("runs", help="list previous runs (newest first)")
    l.set_defaults(func=cmd_runs)
    return ap


def _fail(error: str, hint: str):
    print(json.dumps({"error": error, "hint": hint}, ensure_ascii=False))
    sys.exit(1)


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except SystemExit as e:
        if isinstance(e.code, str):  # our own usage errors: JSON on stdout like every other error
            _fail(e.code, "fix the arguments as the error says")
        raise
    except Exception as e:  # clear one-line error for the agent instead of a traceback
        _fail(f"{type(e).__name__}: {e}", "check spelling of language codes / topic, network access, or retry")
