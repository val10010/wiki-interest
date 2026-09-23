"""Shared fixtures. Import paths (scripts/, tests/) come from pyproject.toml."""
import json

import pytest

from fake_api import fake_get_json
from wiki_interest import cli, pipeline, wiki


@pytest.fixture
def fake(monkeypatch, tmp_path):
    """Deterministic Wikimedia API (see fake_api.py); no network."""
    monkeypatch.setattr(wiki, "get_json", fake_get_json)
    return tmp_path


@pytest.fixture
def runs(fake, monkeypatch):
    """Run directories go to a temp dir instead of the skill's runs/."""
    monkeypatch.setattr(pipeline, "RUNS_DIR", fake / "runs")
    return fake / "runs"


@pytest.fixture
def analyze(runs, capsys):
    """analyze('--langs', 'pl,cs', ...) -> parsed JSON summary, as the agent sees it."""
    def run(*argv):
        cli.main(["analyze", "--topic", "Intermittent fasting", "--end", "2025-08", *argv])
        return json.loads(capsys.readouterr().out)
    return run


@pytest.fixture
def series_with():
    """Minimal series dict with overridable stats, for text-generation tests."""
    def make(**st):
        base = {"direction": "flat", "growth_pct": 0.0, "growth_share_pct": 0.0, "trend_annual_pct": 0.0,
                "median_monthly": 5000, "reliability": "high", "reliability_cap": None, "score": 9,
                "seasonal_peaks": [], "spikes": []}
        return {"lang": "pl", "title": "T", "topic": "t", "stats": base | st}
    return make
