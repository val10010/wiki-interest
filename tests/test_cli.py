"""End-to-end through the CLI on the fake API: what the agent actually sees.

Most tests are regressions for problems found in review and in Haiku 4.5 runs (README).
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from wiki_interest import cli, interpret, report, wiki

FIT = {"series_shown": 1, "series_total": 1, "conclusion_truncated": False}  # what a mocked save_pdf returns


def test_end_to_end(fake, capsys):
    run = fake / "run"
    cli.main(["analyze", "--topic", "Intermittent fasting", "--langs", "pl,cs,uk,en,de",
              "--end", "2025-08", "--out", str(run)])
    out = json.loads(capsys.readouterr().out)
    assert out["topics"][0]["resolved"][0]["qid"] == "Q1"            # skipped the "(film)" hit
    assert out["topics"][0]["missing_languages"] == ["de"]           # no German article
    a = json.loads((run / "analysis.json").read_text())
    by = {s["lang"]: s["stats"] for s in a["series"]}
    assert by["pl"]["direction"] == "growing" and by["pl"]["reliability"] == "high"
    assert by["cs"]["direction"] == "flat" and by["cs"]["spikes"]
    assert by["uk"]["reliability"] == "low"
    assert by["en"]["direction"] == "declining"
    assert (run / "chart.png").stat().st_size > 10_000

    cli.main(["report", str(run), "--title", "Тест", "--conclusion", "Польська аудиторія зростає."])
    pdf = json.loads(capsys.readouterr().out)["pdf"]
    assert Path(pdf).read_bytes()[:4] == b"%PDF"


def test_report_requires_conclusion(fake, capsys):
    run = fake / "run"
    cli.main(["analyze", "--article", "pl:Post przerywany", "--end", "2025-08", "--out", str(run)])
    capsys.readouterr()
    with pytest.raises(SystemExit):
        cli.main(["report", str(run)])


def test_usage_errors_are_json_for_the_agent(runs, capsys, monkeypatch):
    with pytest.raises(SystemExit) as e:
        cli.main(["analyze", "--langs", "pl"])                     # neither --topic nor --article
    assert e.value.code == 1
    assert "--topic" in json.loads(capsys.readouterr().out)["error"]

    monkeypatch.setattr(wiki, "search_topic", lambda q, lang: [])  # nothing found
    with pytest.raises(SystemExit):
        cli.main(["resolve", "zzz"])
    err = json.loads(capsys.readouterr().out)["error"]
    assert "No article found" in err and "--topic Q" in err        # an option that exists


# ------------------------------------------------------------------ follow-ups
def test_followup_does_not_overwrite_previous_run(analyze, capsys):
    first = analyze("--langs", "pl,cs")
    cli.main(["report", first["run_dir"], "--conclusion", "x"])
    capsys.readouterr()
    second = analyze("--langs", "pl,cs,uk")                        # "add Ukrainian"
    assert second["run_dir"] != first["run_dir"]
    assert (Path(first["run_dir"]) / "report.pdf").exists()        # earlier result intact
    again = analyze("--langs", "pl,cs")                             # same question -> same dir
    assert again["run_dir"] == first["run_dir"]
    assert not (Path(first["run_dir"]) / "report.pdf").exists()    # stale PDF removed


SKILL = Path(__file__).resolve().parents[1]


def test_next_hint_uses_launcher(analyze, monkeypatch):
    monkeypatch.setenv("WIKI_INTEREST_CALLER_CWD", str(SKILL))
    assert analyze("--langs", "pl")["next"].startswith("scripts/wi report ")


def test_next_hint_is_absolute_outside_the_skill_root(analyze, monkeypatch, tmp_path):
    # `scripts/wi` works only from the skill root; an agent elsewhere gets a command that works where it is.
    monkeypatch.setenv("WIKI_INTEREST_CALLER_CWD", str(tmp_path))
    out = analyze("--langs", "uk,de")
    assert out["next"].startswith(f"{SKILL / 'scripts' / 'wi'} report ")
    assert f"`{SKILL / 'scripts' / 'wi'} resolve" in " ".join(out["warnings"])


# ------------------------------------------------------------------ warnings + proxies
def test_warnings_for_missing_language_and_thin_proxy(analyze):
    w = " ".join(analyze("--langs", "uk,de")["warnings"])       # uk: ~60 views/month, de: no article
    assert "scripts/wi resolve" in w and "--search-lang de" in w and "--article de:" in w
    assert "Low volume" in w and "too narrow" in w


def test_article_fills_missing_language_of_same_topic(analyze):
    out = analyze("--langs", "pl,sk", "--article", "sk:Prerušovaný pôst")
    assert out["topics"][0]["missing_languages"] == []
    assert len(out["topics"]) == 1                                  # not a separate "manual" topic
    a = json.loads((Path(out["run_dir"]) / "analysis.json").read_text())
    assert {s["lang"]: s["topic"] for s in a["series"]} == {"pl": "Intermittent fasting",
                                                            "sk": "Intermittent fasting"}


def test_handpicked_article_of_other_concept_is_marked_proxy(analyze):
    out = analyze("--langs", "pl,sk", "--article", "sk:Pôst")
    assert "Pôst [proxy]" in out["table"]
    assert any(w.startswith("PROXY sk") and "fasting" in w for w in out["warnings"])
    assert any("PROXY" in v and "fasting" in v for v in out["verdicts"] if v.startswith("sk"))
    a = json.loads((Path(out["run_dir"]) / "analysis.json").read_text())
    assert a["series"][-1]["proxy"][0]["qid"] == "Q777"


def test_report_always_carries_proxy_caveat(analyze, monkeypatch):
    out = analyze("--langs", "pl,sk", "--article", "sk:Pôst")
    seen = {}
    monkeypatch.setattr(report, "save_pdf", lambda a, path, title, concl, caveats, ui: seen.update(c=caveats) or FIT)
    cli.main(["report", out["run_dir"], "--conclusion", "x"])
    assert seen["c"][0].startswith("Proxy (sk)") and "fasting" in seen["c"][0]


def test_handpicked_article_of_same_concept_is_not_proxy(analyze):
    out = analyze("--langs", "pl", "--article", "pl:Post przerywany")
    assert "[proxy]" not in out["table"]
    assert not any(w.startswith("PROXY") for w in out["warnings"])


def test_nonexistent_article_is_reported(analyze):
    out = analyze("--langs", "pl,sk", "--article", "sk:Nonexistent")
    assert any("does not exist" in w for w in out["warnings"])


# ------------------------------------------------------------------ answer skeleton
def test_skeleton_contains_every_mandatory_element(analyze):
    out = analyze("--langs", "pl,cs,uk,de")                  # de: no article; uk: low reliability
    sk = out["answer_skeleton"]
    for v in out["verdicts"]:
        assert v in sk                                       # verdicts verbatim, incl. seasonal/spike notes
    assert "готовності платити" in sk                        # the limits line the model kept dropping
    assert "**Статті немає:** de" in sk
    assert "Низька надійність: uk" in sk
    assert "**Порівняння мов**" in sk and "**Обсяг:**" in sk
    assert sk.count("<ЗАПОВНИ") == 1                         # exactly one slot for the model
    assert sk.rstrip().endswith("chart.png")


def test_skeleton_flags_proxy_languages(analyze):
    assert "Для sk виміряно інше поняття (proxy)" in analyze("--langs", "pl,sk", "--article", "sk:Pôst")["answer_skeleton"]


def test_skeleton_english_ui(analyze):
    sk = analyze("--langs", "pl,cs", "--ui", "en")["answer_skeleton"]
    assert "willingness to pay" in sk and "<FILL" in sk


def test_argparse_errors_are_json_too(capsys, monkeypatch):
    monkeypatch.setenv("WIKI_INTEREST_CALLER_CWD", str(SKILL))
    with pytest.raises(SystemExit) as e:
        cli.main(["analyze", "--topic", "X", "--months", "abc"])
    assert e.value.code == 1
    out = json.loads(capsys.readouterr().out)
    assert "--months" in out["error"] and "scripts/wi analyze -h" in out["hint"]


def test_report_output_tells_what_did_not_fit(analyze, capsys):
    run = analyze("--langs", "pl")
    cli.main(["report", run["run_dir"], "--conclusion", "Коротко. " * 300])
    out = json.loads(capsys.readouterr().out)
    assert out["conclusion_truncated"] and "shorten --conclusion" in out["hint"]
    assert out["series_shown"] == out["series_total"] == 1 and "note" not in out


# ------------------------------------------------------------------ renamed / new articles (README, iteration 7)
def test_renamed_article_gap_is_closed_by_its_redirect(analyze):
    # ro: 'Post intermitent' was renamed from 'Post alimentar intermitent' in 2024-05; the old title is a redirect.
    out = analyze("--langs", "pl,ro")
    a = json.loads((Path(out["run_dir"]) / "analysis.json").read_text())
    ro = next(s for s in a["series"] if s["lang"] == "ro")
    assert ro["rename_fix"] == {"views_start": "2024-05", "redirects": 1, "added": ["Post alimentar intermitent"],
                                "closed": True, "kind": "renamed", "page_created": "2012-01"}
    assert "data_start" not in ro["stats"] and ro["stats"]["direction"] == "flat"
    assert any(w.startswith("RENAMED ro") and "'Post alimentar intermitent'" in w for w in out["warnings"])
    assert any("перейменовано" in v and "«Post alimentar intermitent»" in v for v in out["verdicts"] if v.startswith("ro"))


def test_new_article_is_analysed_from_its_first_month_only(analyze, monkeypatch):
    # hu: the article exists only since 2024-03 and has no redirects -> the gap stays.
    out = analyze("--langs", "pl,hu")
    a = json.loads((Path(out["run_dir"]) / "analysis.json").read_text())
    hu = next(s for s in a["series"] if s["lang"] == "hu")
    assert hu["stats"]["data_start"] == "2024-03" and hu["stats"]["direction"] != "growing"
    assert hu["stats"]["reliability"] != "high" and hu["rename_fix"]["closed"] is False
    assert any(w.startswith("SHORT SERIES hu") for w in out["warnings"])
    assert any("лише з 2024-03" in v for v in out["verdicts"] if v.startswith("hu"))
    seen = {}
    monkeypatch.setattr(report, "save_pdf", lambda a, path, title, concl, caveats, ui: seen.update(c=caveats) or FIT)
    cli.main(["report", out["run_dir"], "--conclusion", "x"])
    assert any(c.startswith("Неповний ряд (hu)") for c in seen["c"])


# ------------------------------------------------------------------ --proxy-for (README, iteration 7)
def test_proxy_for_is_named_in_data_line_limits_and_pdf(analyze, monkeypatch):
    # Transcript english_learning_report: "learning English" measured via "English language" without saying so.
    out = analyze("--langs", "pl,cs", "--proxy-for", "вивчення англійської")
    a = json.loads((Path(out["run_dir"]) / "analysis.json").read_text())
    assert a["proxy_for"] == "вивчення англійської"
    lines = out["answer_skeleton"].split("\n")
    assert "proxy для «вивчення англійської»" in lines[0]
    assert "лише proxy для «вивчення англійської»" in next(l for l in lines if l.startswith("**Обмеження:**"))
    seen = {}
    monkeypatch.setattr(report, "save_pdf", lambda a, path, title, concl, caveats, ui: seen.update(c=caveats) or FIT)
    cli.main(["report", out["run_dir"], "--conclusion", "x"])
    assert seen["c"][0].startswith("Proxy теми") and "вивчення англійської" in seen["c"][0]


def test_proxy_for_english_ui(analyze):
    sk = analyze("--langs", "pl", "--proxy-for", "learning English", "--ui", "en")["answer_skeleton"]
    assert "proxy for 'learning English'" in sk.split("\n")[0]


# ------------------------------------------------------------------ paths relative to the caller (README, iteration 7)
def test_launcher_resolves_paths_from_the_callers_directory(fake, capsys, tmp_path):
    cli.main(["analyze", "--article", "pl:Post przerywany", "--end", "2025-08", "--out", str(tmp_path / "run")])
    capsys.readouterr()
    work = tmp_path / "work"
    work.mkdir()
    (work / "conclusion.txt").write_text("Висновок із файлу.", encoding="utf-8")
    p = subprocess.run([str(SKILL / "scripts" / "wi"), "report", "../run", "--conclusion", "@conclusion.txt",
                        "--out", "r.pdf"], cwd=work, capture_output=True, text=True, timeout=600,
                       env={**os.environ, "WIKI_INTEREST_OFFLINE": "1"})
    out = json.loads(p.stdout)
    assert Path(out["pdf"]).resolve() == (work / "r.pdf").resolve() and (work / "r.pdf").read_bytes()[:4] == b"%PDF"


def test_missing_file_gets_its_own_error_with_the_full_path(analyze, capsys, monkeypatch, tmp_path):
    run = analyze("--langs", "pl")["run_dir"]
    monkeypatch.setenv("WIKI_INTEREST_CALLER_CWD", str(tmp_path))
    with pytest.raises(SystemExit):
        cli.main(["report", run, "--conclusion", "@missing.txt"])
    err = json.loads(capsys.readouterr().out)
    assert str(tmp_path / "missing.txt") in err["error"] and "check spelling" not in err["hint"]
    assert str(tmp_path) in err["hint"]
    with pytest.raises(SystemExit):
        cli.main(["show", "runs/no-such-run"])
    err = json.loads(capsys.readouterr().out)
    assert "no-such-run" in err["error"] and "runs" in err["hint"]


def test_run_dir_is_found_from_the_caller_then_from_the_skill_root(analyze, capsys, monkeypatch, tmp_path):
    run = Path(analyze("--langs", "pl")["run_dir"])
    monkeypatch.setenv("WIKI_INTEREST_CALLER_CWD", str(run.parent.parent))
    cli.main(["show", f"{run.parent.name}/{run.name}"])                  # relative to the caller
    assert json.loads(capsys.readouterr().out)["run_dir"] == str(run)
    monkeypatch.setenv("WIKI_INTEREST_CALLER_CWD", str(tmp_path))
    cli.main(["show", f"runs/{run.name}"])                               # runs/... still works from anywhere
    assert json.loads(capsys.readouterr().out)["run_dir"] == str(run)


def test_runs_prefix_is_looked_up_in_the_configured_runs_dir_first(analyze, capsys, monkeypatch, tmp_path):
    # evals/run_agent.py gives each case its own WIKI_INTEREST_RUNS. `report runs/<name>` looked in the caller's
    # directory and the skill root first, so a stale runs/<name> there won and got the PDF: the isolation was gone.
    from wiki_interest import paths
    run = Path(analyze("--langs", "pl")["run_dir"])                      # lives in the configured runs dir
    root, cwd = tmp_path / "skill", tmp_path / "cwd"
    for stale in (root / "runs" / run.name, cwd / "runs" / run.name):
        stale.mkdir(parents=True)
        (stale / "analysis.json").write_text((run / "analysis.json").read_text())
    monkeypatch.setattr(paths, "SKILL_DIR", root)
    monkeypatch.setenv("WIKI_INTEREST_CALLER_CWD", str(cwd))
    cli.main(["show", f"runs/{run.name}"])
    assert json.loads(capsys.readouterr().out)["run_dir"] == str(run)
    cli.main(["report", f"runs/{run.name}", "--conclusion", "x"])
    assert Path(json.loads(capsys.readouterr().out)["pdf"]) == run / "report.pdf"
    (cwd / "runs" / "only-here").mkdir()
    (cwd / "runs" / "only-here" / "analysis.json").write_text("{}")
    assert paths.find_run("runs/only-here", run.parent) == cwd / "runs" / "only-here"   # fallback still works
    assert paths.find_run(f"other/{run.name}", run.parent) == run                        # by name, as before


# ------------------------------------------------------------------ rename fix, second review (README, iteration 8)
def test_only_redirects_with_views_before_the_gap_are_added(analyze, monkeypatch):
    # it: renamed in 2024-05; besides the old title the article has two synonym redirects with ~1.5 % of its views
    # over the whole period. Summing all 30 redirects shifted the level against the other languages.
    from fake_api import _value
    out = analyze("--langs", "pl,it")
    a = json.loads((Path(out["run_dir"]) / "analysis.json").read_text())
    it = next(s for s in a["series"] if s["lang"] == "it")
    assert it["rename_fix"]["closed"] and it["rename_fix"]["kind"] == "renamed"
    assert it["rename_fix"]["redirects"] == 3 and it["rename_fix"]["added"] == ["Digiuno a intermittenza"]
    assert it["redirects_included"] == 1
    main, old = "Digiuno intermittente", "Digiuno a intermittenza"
    for k, (y, m) in ((0, (2023, 9)), (-1, (2025, 8))):                                # old title yes, synonyms no
        assert it["views"][k] == _value("it", y, m, main) + _value("it", y, m, old)
    assert any("«Digiuno a intermittenza»" in v and "Dieta 16:8" not in v for v in out["verdicts"] if v.startswith("it"))
    assert any(w.startswith("RENAMED it") and "'Digiuno a intermittenza'" in w for w in out["warnings"])
    seen = {}
    monkeypatch.setattr(report, "save_pdf", lambda a, path, title, concl, caveats, ui: seen.update(c=caveats) or FIT)
    cli.main(["report", out["run_dir"], "--conclusion", "x"])
    assert any(c.startswith("Перейменування (it)") and "«Digiuno a intermittenza»" in c for c in seen["c"])
    assert any(c.startswith("Rename (it)") and "'Digiuno a intermittenza'" in c
               for c in interpret.report_caveats(a, "en"))


def test_move_without_a_redirect_leaves_the_gap_open(analyze):
    # fi: moved in 2024-05, the old title was deleted; a synonym redirect with 8 % of the views passed the 5 % gap
    # test, so the gap counted as closed although a 12x step remained.
    from fake_api import _value
    out = analyze("--langs", "pl,fi")
    a = json.loads((Path(out["run_dir"]) / "analysis.json").read_text())
    fi = next(s for s in a["series"] if s["lang"] == "fi")
    assert fi["rename_fix"]["closed"] is False and fi["rename_fix"]["added"] == ["Jaksottainen paasto"]
    assert fi["stats"]["data_start"] == "2024-05" and fi["redirects_included"] == 0
    assert fi["views"][-1] == _value("fi", 2025, 8, "Pätkäpaasto")                     # the synonym is not summed
    assert fi["rename_fix"]["kind"] == "renamed"                                       # page history predates the period
    w = next(w for w in out["warnings"] if w.startswith("SHORT SERIES fi"))
    assert "renamed" in w and "created or renamed" not in w and "--article" in w and "Jaksottainen paasto" in w
    v = next(v for v in out["verdicts"] if v.startswith("fi"))
    assert "стаття перейменована тоді" in v and "створена або" not in v


def test_new_article_is_called_created_not_renamed(analyze, monkeypatch, capsys):
    # hu: page history starts in 2024-03, the month its views start -> created, and no "add the old title" advice.
    out = analyze("--langs", "pl,hu")
    a = json.loads((Path(out["run_dir"]) / "analysis.json").read_text())
    hu = next(s for s in a["series"] if s["lang"] == "hu")
    assert hu["rename_fix"]["kind"] == "created" and hu["rename_fix"]["page_created"] == "2024-03"
    assert any("article created then" in r for r in hu["stats"]["reasons"])
    w = next(w for w in out["warnings"] if w.startswith("SHORT SERIES hu"))
    assert "created" in w and "created or renamed" not in w and "<old title>" not in w
    v = next(v for v in out["verdicts"] if v.startswith("hu"))
    assert "стаття створена тоді" in v
    seen = {}
    monkeypatch.setattr(report, "save_pdf", lambda a, path, title, concl, caveats, ui: seen.update(c=caveats) or FIT)
    cli.main(["report", out["run_dir"], "--conclusion", "x"])
    assert any(c.startswith("Неповний ряд (hu)") and "стаття створена" in c and "або" not in c for c in seen["c"])
    capsys.readouterr()
    en = analyze("--langs", "pl,hu", "--ui", "en")
    assert any("article created then" in v for v in en["verdicts"] if v.startswith("hu"))
