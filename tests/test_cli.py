"""End-to-end through the CLI on the fake API: what the agent actually sees.

Most tests are regressions for problems found in review and in Haiku 4.5 runs (README).
"""
import json
from pathlib import Path

import pytest

from wiki_interest import cli, report, wiki

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


def test_next_hint_uses_launcher(analyze):
    assert analyze("--langs", "pl")["next"].startswith("scripts/wi report ")


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


def test_argparse_errors_are_json_too(capsys):
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
