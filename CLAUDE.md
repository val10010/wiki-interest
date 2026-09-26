# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An [Agent Skill](https://agentskills.io/specification) that analyses Wikipedia pageviews across language editions
(trends, reliability, chart, one-page PDF) to help B2C founders pick topics and languages. **The repo root is the
skill directory**: `SKILL.md` is the prompt the *using* agent gets, and its `name: wiki-interest` must match the
directory name. All own code and materials (tests, evals included) must stay inside this directory, and no
personal data (names, emails, local paths) may appear in committed files: the work is graded anonymously.

`README.md` is in Ukrainian (it is for graders); `SKILL.md`, code and comments are in English. User-facing
strings in `interpret.py` / `report.py` exist in both `uk` and `en` (`--ui`).

## Commands

```bash
scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs   # first run creates .venv (root, or XDG if read-only)
scripts/wi resolve "Astronomy" --langs uk                          # topic -> Wikidata item -> titles per language
scripts/wi report runs/<run> --conclusion "…"                      # PDF from an existing run
scripts/wi show runs/<run>   |   scripts/wi runs                   # reprint / list runs, no network
scripts/wi prune-cache [--days 62]                                 # delete stale cache files

.venv/bin/pip install -r requirements-dev.txt                      # pytest + openai (evals)
.venv/bin/python -m pytest                                         # all tests, offline (fake API)
.venv/bin/python -m pytest tests/test_cli.py::test_end_to_end      # single test
OPENROUTER_API_KEY=… .venv/bin/python evals/run_agent.py --case fasting_pl_cs   # cheap-model scenario (paid)
OPENROUTER_API_KEY=… .venv/bin/python evals/run_agent.py --repeat 5  # pass rate per check
.venv/bin/python evals/calibrate_stats.py                         # stats vs synthetic truth (needs scipy)
```

`scripts/wi` always `cd`s to the root and sets `PYTHONPATH=scripts`; it exports the caller's directory as
`WIKI_INTEREST_CALLER_CWD`, and `paths.py` resolves `@file` / `--out` against it; a `RUN_DIR` written as `runs/<name>`
is looked up in the configured runs dir first, any other relative one against the caller, then the root, then the runs
dir. Suggested commands (`next`, warnings) use `interpret.launcher()`: `scripts/wi` from the root, the absolute launcher
path elsewhere. Data dirs (`paths.data_dirs`, same rule in `scripts/wi` for the venv): the root
if writable, else `${XDG_DATA_HOME:-~/.local/share}/wiki-interest` (venv, runs) and
`${XDG_CACHE_HOME:-~/.cache}/wiki-interest` (cache). Env vars: `WIKI_INTEREST_HOME` (venv + runs + `.cache`),
`WIKI_INTEREST_RUNS`, `WIKI_INTEREST_CACHE`, `WIKI_INTEREST_OFFLINE=1` (cache only), `WIKI_INTEREST_UA` (User-Agent),
`WIKI_INTEREST_PYTHON` (interpreter for the venv), `WIKI_INTEREST_CALLER_CWD` (set by the launcher). Must run on
Python 3.9 (macOS system Python): keep `from __future__ import annotations`, no `match`.

## Architecture

Flow of `analyze`: `cli` parses args → `pipeline.build_analysis` resolves each topic via Wikipedia search →
Wikidata item → sitelinks (the *same concept* in every language), fetches monthly `agent=user` views per article
plus the whole edition's total, runs `stats.analyze_series` per series → `pipeline.save_run` writes
`runs/<name>/analysis.json` + `chart.png` + `all_series.md` → `interpret.summary` prints JSON for the agent.

- `analysis.json` is the contract between commands: `show` and `report` only read it, never the network.
  Run names include topics, sorted languages, period and the redirect flag, so a follow-up ("add Slovak") gets a
  new dir; re-running the same question deletes that run's now-stale `report.pdf`.
- `http.get_json` caches every response keyed by URL (atomic write; unparsable file = miss); 404s are cached too.
  `wiki._monthly` requests pageviews as two canonical ranges (history to a cutoff 3 months back, forever; the recent
  tail, 24 h) and slices the period from them, so a changed period is a cache hit.
  Keep the fake API deterministic per calendar month.
- `stats.py` holds all maths: `leading_gap` (new/renamed article: stats only from the first real month, gap cap),
  spike detection (robust z vs rolling median) with **seasonal peaks** (same month elevated a year apart) kept only
  up to 1.75× the paired peak (excess = `seasonal_excess` spike), 12-vs-12-month growth, share of edition traffic,
  Theil–Sen + Mann–Kendall on views and on share (`direction` / `direction_share`), and a 0–10 reliability score
  (six components; months-up points only when they agree with the sign of growth) with volume and gap caps.
  `pipeline` adds redirects automatically when `leading_gap` finds a gap (`rename_fix` on the series).
  Thresholds are documented in `references/METHODOLOGY.md`; keep the two in sync.
- `interpret.py` holds **every sentence the user may see** (the verdict opening names views and share when
  `direction_share` disagrees; `--proxy-for` goes into the data and limits lines and the PDF): `warnings` (each
  phrased as the next command to run), per-series `verdicts`, `answer_skeleton` (the whole answer with one
  `<ЗАПОВНИ…>`/`<FILL…>` slot), the table and PDF caveats. `interpret.CMD` is the launcher string used in those
  texts; keep it consistent with `SKILL.md`.
  `summary` keeps stdout ≤ `MAX_OUTPUT_CHARS` (15k): beyond it, full verdicts for the top series only plus a compact
  line for all languages; `save_run` writes everything to `all_series.md`.
- An `--article lang:Title` added to a topic is checked against Wikidata (`wiki.article_info`); a different item
  → `proxy` on the series → `[proxy]` in the table, a `PROXY` warning, and a caveat forced into the PDF.
- `report.py` renders the PDF; only the conclusion text comes from the agent, everything else from `analysis.json`.
  It never drops content silently: `save_pdf` returns what fitted (series shown of total, conclusion truncated,
  caveats shown) and `cli.cmd_report` turns that into `note` / `hint` for the agent. Fonts: `charts.font_families`
  adds installed system fonts as per-glyph fallbacks; `charts.renderable` decides when a title must be substituted.

## Design rule behind most of the code

The skill must work on a cheap model (Haiku 4.5 class). Four measured Haiku runs (README, iterations 1–4) showed:
whatever the tool *outputs* is followed reliably; rules written only as prose in `SKILL.md` are dropped about half
the time. So when the agent keeps getting something wrong, move it into generated output (`interpret.py`) or into
the PDF, not into more `SKILL.md` text. With one run per case, run-to-run noise exceeds small prompt/format
effects (iteration 4 was reverted for that reason); judge such changes over repeated `evals/run_agent.py` runs.
`answer_skeleton`'s position in the summary JSON is one of those measured choices; don't move it casually.

## Tests

`tests/fake_api.py` is a deterministic stand-in for every Wikimedia endpoint (pl grows, cs flat + spike, uk tiny,
en declines, sk unlinked in Wikidata, `Q777` = broader "fasting", ro renamed in 2024-05 with the old title as a
redirect, hu created in 2024-03; per-article values depend on the title, redirects come from `REDIRECTS`). Any new
API call in `wiki.py` needs a branch there, or tests fail with `unexpected url`.
Fixtures in `tests/conftest.py`: `fake` (patch API), `runs` (temp `RUNS_DIR`), `analyze(*argv)` (run the CLI,
return parsed JSON), `series_with(**stats)`. Most tests in `test_cli.py` are regressions for real failures found in review or in Haiku runs; README lists them.
`evals/cases.json` checks agent behaviour (commands run, required and forbidden answer patterns, files);
`run_agent.py` gives each case its own `WIKI_INTEREST_RUNS` (`files: runs/...` is checked there), cuts tool output at
30k like Claude Code, and anonymises transcripts before writing them. `tests/test_paths.py` runs the launcher from a
read-only copy of the skill. `evals/calibrate_stats.py` needs scipy; its table is copied into METHODOLOGY.
