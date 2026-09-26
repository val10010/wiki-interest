"""evals/run_agent.py: the agent loop and its scoring, without OpenRouter; transcripts must be publishable."""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

pytest.importorskip("openai")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
import run_agent  # noqa: E402


class _Msg:
    """Shape of an OpenAI chat completion message as run_agent uses it."""

    def __init__(self, content=None, command=None):
        self.content = content
        self.tool_calls = [NS(id="c1", function=NS(arguments=json.dumps({"command": command})))] if command else None

    def model_dump(self, exclude_none=True):
        return {"role": "assistant", "content": self.content}


class _Client:
    """Scripted stand-in for openai.OpenAI: returns the next message per call, counts usage."""

    def __init__(self, script):
        self.script = list(script)
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kw):
        assert kw["tools"] == run_agent.TOOLS and kw["messages"][0]["role"] == "system"
        return NS(usage=NS(prompt_tokens=100, completion_tokens=10), choices=[NS(message=self.script.pop(0))])


CASE = {"id": "x", "turns": ["Порівняй pl і cs"], "checks": {
    "commands": ["analyze", "--langs[= ]\\S*pl"], "answer": ["%"], "answer_not": ["<FILL"], "files": ["SKILL.md"]}}


def test_run_case_runs_tools_until_a_final_answer_and_scores_it(monkeypatch):
    monkeypatch.setattr(run_agent, "bash", lambda cmd, runs_dir=None: '{"verdicts": ["pl: +40%"]}')
    client = _Client([_Msg(command='scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs'),
                      _Msg(content="pl росте на +40%.")])
    res = run_agent.run_case(client, "fake/model", CASE)
    assert res["passed"] and res["steps"] == 1 and res["usage"] == {"prompt": 200, "completion": 20}
    assert [m["role"] for m in res["messages"]] == ["system", "user", "assistant", "tool", "assistant"]


def test_run_case_reports_each_failed_check(monkeypatch):
    monkeypatch.setattr(run_agent, "bash", lambda cmd, runs_dir=None: "")
    res = run_agent.run_case(_Client([_Msg(content="<FILL: …> без цифр")]), "fake/model", CASE)
    assert not res["passed"]
    assert [k for k, ok in res["checks"].items() if not ok] == ["cmd:analyze", "cmd:--langs[= ]\\S*pl", "answer:%",
                                                                 "answer_not:<FILL"]


def test_transcripts_are_anonymized():
    raw = json.dumps({"run_dir": f"{run_agent.SKILL}/runs/x", "home": f"{Path.home()}/y"})
    clean = run_agent.anonymize(raw)
    assert str(Path.home()) not in clean and "<skill>/runs/x" in clean


# ------------------------------------------------------------------ isolation, repeats, output limit (iteration 7)
REPORT_CASE = {"id": "r", "turns": ["звіт"], "checks": {"commands": ["report"], "files": ["runs/*/report.pdf"]}}


def test_each_case_gets_its_own_runs_dir(monkeypatch, tmp_path):
    # A PDF left by an earlier run in the skill's runs/ used to satisfy `files: runs/*/report.pdf`.
    (tmp_path / "runs" / "old").mkdir(parents=True)
    (tmp_path / "runs" / "old" / "report.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(run_agent, "SKILL", tmp_path)
    seen = []

    def fake_bash(cmd, runs_dir=None):
        seen.append(runs_dir)
        if "report" in cmd:
            (Path(runs_dir) / "new").mkdir()
            (Path(runs_dir) / "new" / "report.pdf").write_bytes(b"%PDF")
        return "{}"
    monkeypatch.setattr(run_agent, "bash", fake_bash)
    res = run_agent.run_case(_Client([_Msg(content="нічого не запускав")]), "fake/model", REPORT_CASE)
    assert not res["checks"]["file:runs/*/report.pdf"]                  # the stale PDF does not count
    res = run_agent.run_case(_Client([_Msg(command="scripts/wi report runs/x --conclusion c"), _Msg(content="ok")]),
                             "fake/model", REPORT_CASE)
    assert res["checks"]["file:runs/*/report.pdf"] and seen[0] and Path(seen[0]) != tmp_path / "runs"
    assert not Path(seen[0]).exists()                                     # removed after scoring


def test_pass_rates_over_repeats():
    results = [{"id": "a", "passed": ok, "checks": {"cmd:x": True, "answer:y": ok}} for ok in (True, False, True)]
    assert run_agent.pass_rates(results) == {"a": {"passed": "2/3", "checks": {"cmd:x": "3/3", "answer:y": "2/3"}}}


def test_tool_output_is_cut_like_claude_code():
    assert run_agent.TOOL_OUTPUT_LIMIT == 30000
    out = run_agent.bash("printf '%040000d' 0")
    assert len(out) < 30100 and out.endswith("[truncated]")


def test_limits_line_check_does_not_match_platform():
    # Iteration 9 (Haiku subagents): an answer without the limits line passed because "міграція на інші
    # платформи" matched the pattern `плат`. The check must want the limits line itself.
    cases = json.loads((Path(run_agent.SKILL) / "evals" / "cases.json").read_text())
    patterns = {p for c in cases for p in c["checks"]["answer"] if "плат" in p}
    assert patterns, "every case checks the limits line"
    for p in patterns:
        assert not re.search(p, "міграція на інші платформи; платна версія", re.I)
        assert re.search(p, "сигнал цікавості, а не готовності платити", re.I)
        assert re.search(p, "curiosity, not willingness to pay", re.I)
