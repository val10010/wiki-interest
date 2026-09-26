# Haiku 4.5 run, 2026-09-26 (iteration 9, after the review fixes of iterations 7–8)

One file per case from `evals/cases.json`, two runs each (a, b). Each holds the model's final answer verbatim and
the shell commands it ran, as reported by the model itself; local paths are replaced by `<skill>`.

Setup: Claude Haiku 4.5 as a Claude Code subagent, a fresh local clone of the repository per run (shared venv and
HTTP cache), the prompt = "you have this skill at <path>, read its SKILL.md first and follow it, run commands from
that directory, end with the list of commands" + the user request, nothing else. The follow-up case was run as two
turns of one conversation. Scored with the checks of `cases.json` (the same regular expressions `run_agent.py`
uses) and read by hand against the tool's `verdicts`; the scoring is in README, iteration 9.

Not the same harness as `evals/run_agent.py`: the subagent has all Claude Code tools (it read SKILL.md with the
file reader, not with `cat`), and one run (fasting, a) executed its commands in the main checkout instead of its
clone, which changes nothing in the data (same code and cache) but shows that a model does not always keep to the
directory it was given.
