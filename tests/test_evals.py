"""evals/run_agent.py: transcripts must be publishable (anonymity rule of the case)."""
import json
import sys
from pathlib import Path

import pytest


def test_transcripts_are_anonymized():
    pytest.importorskip("openai")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
    import run_agent
    raw = json.dumps({"run_dir": f"{run_agent.SKILL}/runs/x", "home": f"{Path.home()}/y"})
    clean = run_agent.anonymize(raw)
    assert str(Path.home()) not in clean and "<skill>/runs/x" in clean
