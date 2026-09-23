"""End-to-end check of the skill with a cheap tool-using model via OpenRouter.

The model gets SKILL.md as its instructions and a single `bash` tool that runs in
the skill directory — the same situation as a real agent (Claude Code, etc.).
Each case is scored by simple checks: which commands were run, what the final
answer mentions, which files were produced. Transcripts go to evals/transcripts/.

  export OPENROUTER_API_KEY=...
  .venv/bin/python evals/run_agent.py                                   # default: anthropic/claude-haiku-4.5
  .venv/bin/python evals/run_agent.py --model qwen/qwen3-coder:free --case fasting_pl_cs
"""
import argparse
import glob
import json
import os
import re
import subprocess
import time
from pathlib import Path

from openai import OpenAI

SKILL = Path(__file__).resolve().parent.parent
OUT = SKILL / "evals" / "transcripts"

TOOLS = [{"type": "function", "function": {
    "name": "bash",
    "description": "Run a shell command in the skill directory. Returns stdout+stderr.",
    "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                   "required": ["command"]}}}]

SYSTEM = ("You are a research assistant for founders of B2C apps. You have the skill below. "
          "The skill directory is the current working directory.\n\n" + (SKILL / "SKILL.md").read_text())


def bash(cmd: str) -> str:
    try:
        p = subprocess.run(cmd, shell=True, cwd=SKILL, capture_output=True, text=True, timeout=300)
        out = (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        out = "ERROR: timeout"
    return out[:8000] + ("\n...[truncated]" if len(out) > 8000 else "")


def anonymize(text: str) -> str:
    """Strip local paths (they contain the OS user name) so transcripts can be published."""
    for path, alias in ((str(SKILL), "<skill>"), (str(Path.home()), "~")):
        text = text.replace(path, alias)
    return text


def run_case(client, model, case, max_steps=12):
    messages = [{"role": "system", "content": SYSTEM}]
    commands, answers, usage = [], [], {"prompt": 0, "completion": 0}
    t0 = time.time()
    for turn in case["turns"]:
        messages.append({"role": "user", "content": turn})
        for _ in range(max_steps):
            r = client.chat.completions.create(model=model, messages=messages, tools=TOOLS, temperature=0)
            if r.usage:
                usage["prompt"] += r.usage.prompt_tokens; usage["completion"] += r.usage.completion_tokens
            msg = r.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                answers.append(msg.content or "")
                break
            for tc in msg.tool_calls:
                cmd = json.loads(tc.function.arguments or "{}").get("command", "")
                commands.append(cmd)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": bash(cmd)})
    joined_cmds, final = "\n".join(commands), "\n".join(answers)
    c = case["checks"]
    results = {f"cmd:{p}": bool(re.search(p, joined_cmds)) for p in c.get("commands", [])}
    results |= {f"answer:{p}": bool(re.search(p, final, re.I)) for p in c.get("answer", [])}
    results |= {f"answer_not:{p}": not re.search(p, final, re.I) for p in c.get("answer_not", [])}
    results |= {f"file:{p}": bool(glob.glob(str(SKILL / p))) for p in c.get("files", [])}
    return {"id": case["id"], "model": model, "passed": all(results.values()), "checks": results,
            "steps": len(commands), "seconds": round(time.time() - t0, 1), "usage": usage,
            "commands": commands, "answer": final, "messages": messages}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="anthropic/claude-haiku-4.5")
    ap.add_argument("--case", action="append")
    args = ap.parse_args()
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    cases = json.loads((SKILL / "evals" / "cases.json").read_text())
    if args.case:
        cases = [c for c in cases if c["id"] in args.case]
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for case in cases:
        res = run_case(client, args.model, case)
        name = f"{case['id']}__{args.model.replace('/', '_')}.json"
        (OUT / name).write_text(anonymize(json.dumps(res, ensure_ascii=False, indent=1, default=str)))
        summary.append({k: res[k] for k in ("id", "passed", "steps", "seconds", "usage", "checks")})
        print(("PASS " if res["passed"] else "FAIL ") + case["id"], res["checks"], flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
