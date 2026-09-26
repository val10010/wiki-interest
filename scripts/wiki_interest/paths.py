"""Where things live: the skill root, and paths the agent passes on the command line.

scripts/wi cd's to the skill root, so a relative path would silently resolve there
instead of in the agent's working directory. The launcher passes the original
directory in WIKI_INTEREST_CALLER_CWD; user-given paths are resolved against it.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]  # scripts/wiki_interest/paths.py -> skill root


def caller_cwd() -> Path:
    """The directory the agent ran the command from (not the skill root the launcher cd'd to)."""
    return Path(os.environ.get("WIKI_INTEREST_CALLER_CWD") or os.getcwd())


def from_caller(p: str | Path) -> Path:
    """A file path given by the agent (--out, @file): relative to where the command was run."""
    p = Path(p).expanduser()
    return p if p.is_absolute() else caller_cwd() / p


def find_run(spec: str, runs_dir: Path) -> Path:
    """A run directory given by the agent: as given (relative to the caller), then relative to the skill
    root (so the printed `runs/...` keeps working from anywhere), then by name inside runs_dir."""
    p = Path(spec).expanduser()
    tried = [p] if p.is_absolute() else [caller_cwd() / p, SKILL_DIR / p, runs_dir / p.name]
    for c in tried:
        if (c / "analysis.json").is_file():
            return c
    raise FileNotFoundError(errno.ENOENT, "no analysis.json", " or ".join(str(c) for c in tried))
