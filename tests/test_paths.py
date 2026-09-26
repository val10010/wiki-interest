"""paths.py + scripts/wi: where venv, runs and cache go (README, iteration 7: the skill used to fail in a read-only dir)."""
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from wiki_interest import paths

ROOT = Path("/opt/skills/wiki-interest")
HOME = str(Path.home())


def test_writable_root_keeps_everything_in_the_skill_dir():
    d = paths.data_dirs(ROOT, {}, writable=True)
    assert d == {"home": ROOT, "runs": ROOT / "runs", "cache": ROOT / ".cache"}


def test_read_only_root_uses_xdg_dirs():
    d = paths.data_dirs(ROOT, {}, writable=False)
    assert d["home"] == Path(HOME, ".local/share/wiki-interest") and d["runs"] == d["home"] / "runs"
    assert d["cache"] == Path(HOME, ".cache/wiki-interest")
    d = paths.data_dirs(ROOT, {"XDG_DATA_HOME": "/xd", "XDG_CACHE_HOME": "/xc"}, writable=False)
    assert d == {"home": Path("/xd/wiki-interest"), "runs": Path("/xd/wiki-interest/runs"),
                 "cache": Path("/xc/wiki-interest")}


def test_env_overrides():
    d = paths.data_dirs(ROOT, {"WIKI_INTEREST_HOME": "/h", "WIKI_INTEREST_RUNS": "/r"}, writable=False)
    assert d == {"home": Path("/h"), "runs": Path("/r"), "cache": Path("/h/.cache")}
    assert paths.data_dirs(ROOT, {"WIKI_INTEREST_CACHE": "/c"}, writable=True)["cache"] == Path("/c")


def test_launcher_works_from_a_read_only_skill_dir(tmp_path):
    real = Path(__file__).resolve().parents[1]
    skill = tmp_path / "skill"
    shutil.copytree(real / "scripts", skill / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(real / "requirements.txt", skill)
    data = tmp_path / "xdg" / "wiki-interest"
    data.mkdir(parents=True)
    (data / ".venv").symlink_to(real / ".venv")                   # an already installed venv, found in the XDG dir
    run = data / "runs" / "r1"
    run.mkdir(parents=True)
    (run / "analysis.json").write_text(json.dumps({"created": "x", "period": {}, "series": []}))
    skill.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        env = {**os.environ, "XDG_DATA_HOME": str(tmp_path / "xdg"), "XDG_CACHE_HOME": str(tmp_path / "xc"),
               "PYTHONDONTWRITEBYTECODE": "1"}
        env.pop("WIKI_INTEREST_HOME", None), env.pop("WIKI_INTEREST_RUNS", None)
        p = subprocess.run([str(skill / "scripts" / "wi"), "runs"], cwd=tmp_path, capture_output=True, text=True,
                           timeout=600, env=env)
    finally:
        skill.chmod(stat.S_IRWXU)
    assert [r["run_dir"] for r in json.loads(p.stdout)] == [str(run)], p.stdout + p.stderr
    assert not (skill / ".venv").exists()
