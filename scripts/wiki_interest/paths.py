"""Where things live: the skill root, generated data (venv, runs, cache), and paths the agent
passes on the command line.

scripts/wi cd's to the skill root, so a relative path would silently resolve there
instead of in the agent's working directory. The launcher passes the original
directory in WIKI_INTEREST_CALLER_CWD; user-given paths are resolved against it.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Mapping

SKILL_DIR = Path(__file__).resolve().parents[2]  # scripts/wiki_interest/paths.py -> skill root


def data_dirs(root: Path, env: Mapping[str, str], writable: bool) -> dict[str, Path]:
    """home (venv + runs), runs and cache. A writable skill root keeps everything in it, as before.
    A read-only one (installed system-wide, mounted read-only) moves them to the XDG dirs:
    ${XDG_DATA_HOME:-~/.local/share}/wiki-interest and ${XDG_CACHE_HOME:-~/.cache}/wiki-interest.
    WIKI_INTEREST_HOME / _RUNS / _CACHE override. scripts/wi applies the same rule to the venv."""
    if env.get("WIKI_INTEREST_HOME"):
        home = Path(env["WIKI_INTEREST_HOME"]).expanduser()
        cache = home / ".cache"
    elif writable:
        home, cache = root, root / ".cache"
    else:
        home = Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "wiki-interest"
        cache = Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "wiki-interest"
    runs = Path(env["WIKI_INTEREST_RUNS"]).expanduser() if env.get("WIKI_INTEREST_RUNS") else home / "runs"
    if env.get("WIKI_INTEREST_CACHE"):
        cache = Path(env["WIKI_INTEREST_CACHE"]).expanduser()
    return {"home": home, "runs": runs, "cache": cache}


DIRS = data_dirs(SKILL_DIR, os.environ, os.access(SKILL_DIR, os.W_OK))


def caller_cwd() -> Path:
    """The directory the agent ran the command from (not the skill root the launcher cd'd to)."""
    return Path(os.environ.get("WIKI_INTEREST_CALLER_CWD") or os.getcwd())


def from_caller(p: str | Path) -> Path:
    """A file path given by the agent (--out, @file): relative to where the command was run."""
    p = Path(p).expanduser()
    return p if p.is_absolute() else caller_cwd() / p


def find_run(spec: str, runs_dir: Path) -> Path:
    """A run directory given by the agent. `runs/<name>` (what the tool prints) is looked up in the configured
    runs directory first: with WIKI_INTEREST_RUNS set (evals give each case its own), a stale runs/<name> in the
    caller's directory or the skill root must not win. Then as given (relative to the caller), relative to the
    skill root, and by name inside runs_dir."""
    p = Path(spec).expanduser()
    if p.is_absolute():
        tried = [p]
    else:
        tried = [caller_cwd() / p, SKILL_DIR / p, runs_dir / p.name]
        if p.parts[:1] == ("runs",) and len(p.parts) > 1:
            tried.insert(0, runs_dir.joinpath(*p.parts[1:]))
    for c in tried:
        if (c / "analysis.json").is_file():
            return c
    raise FileNotFoundError(errno.ENOENT, "no analysis.json", " or ".join(dict.fromkeys(str(c) for c in tried)))
