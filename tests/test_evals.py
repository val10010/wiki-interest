"""evals/run_agent.py: the agent loop and its scoring, without OpenRouter; transcripts must be publishable."""
import json
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
    monkeypatch.setattr(run_agent, "bash", lambda cmd: '{"verdicts": ["pl: +40%"]}')
    client = _Client([_Msg(command='scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs'),
                      _Msg(content="pl росте на +40%.")])
    res = run_agent.run_case(client, "fake/model", CASE)
    assert res["passed"] and res["steps"] == 1 and res["usage"] == {"prompt": 200, "completion": 20}
    assert [m["role"] for m in res["messages"]] == ["system", "user", "assistant", "tool", "assistant"]


def test_run_case_reports_each_failed_check(monkeypatch):
    monkeypatch.setattr(run_agent, "bash", lambda cmd: "")
    res = run_agent.run_case(_Client([_Msg(content="<FILL: …> без цифр")]), "fake/model", CASE)
    assert not res["passed"]
    assert [k for k, ok in res["checks"].items() if not ok] == ["cmd:analyze", "cmd:--langs[= ]\\S*pl", "answer:%",
                                                                 "answer_not:<FILL"]


def test_transcripts_are_anonymized():
    raw = json.dumps({"run_dir": f"{run_agent.SKILL}/runs/x", "home": f"{Path.home()}/y"})
    clean = run_agent.anonymize(raw)
    assert str(Path.home()) not in clean and "<skill>/runs/x" in clean
