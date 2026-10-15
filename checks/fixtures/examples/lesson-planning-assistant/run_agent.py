"""
Lesson Planning Assistant: a small lesson-plan app, built like a real product app (not a Claude Code project).

Its instructions live in prompts/*.md. This script joins them into one system prompt, sends the teacher's
request to the model, and prints the lesson plan.

Usage:
    python run_agent.py "Grade 3 Math, fractions, 35 minutes"
    python run_agent.py --json "..."      # prints {"result": ..., "total_cost_usd": ...} for tools

Model: set LP_MODEL (default: haiku). Uses Claude Code (`claude -p`) with its tools switched off.
For free offline checks, set LP_AGENT_FAKE=1: it returns a canned plan that follows the prompt files literally.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPT_FILES = ["system.md", "format.md", "rules.md"]


def system_prompt():
    return "\n\n".join((HERE / "prompts" / f).read_text(encoding="utf-8").strip() for f in PROMPT_FILES)


def fake_plan(request, prompt):
    """Deterministic stand-in for the model: follows the prompt files literally (for free pipeline checks)."""
    low = prompt.lower()
    block = prompt.split("Use these sections:", 1)[1].split("\n\n", 1)[0] if "Use these sections:" in prompt else ""
    sections = re.findall(r"^- (.+)$", block, flags=re.M)
    long_text = "comprehensive" in low or "explain every section fully" in low
    body = []
    for s in sections or ["Objective", "Main activity"]:
        line = f"{s}: " + ("This part is explained fully with many details for the teacher. " * (6 if long_text else 1))
        body.append(line.strip())
    if "projector" in low or "tablets" in low:
        body.append("Resources: show a video on the projector and give each child a tablet.")
    if "always respond in english" not in low and re.search(r"\b(sabaq|bachon|kya|karwain|hai)\b", request.lower()):
        body.insert(0, "Sabaq ka plan:")
    return f"Lesson plan for: {request}\n" + "\n".join(body)


def run(request):
    prompt = system_prompt()
    if os.environ.get("LP_AGENT_FAKE") == "1":
        return {"result": fake_plan(request, prompt), "total_cost_usd": 0.0}
    claude = shutil.which("claude")
    if not claude:
        raise SystemExit("Could not find the 'claude' command.")
    cmd = [claude, "-p", "--output-format", "json", "--model", os.environ.get("LP_MODEL", "haiku"),
           "--system-prompt", prompt, "--tools", "", "--strict-mcp-config"]
    proc = subprocess.run(cmd, input=request, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=dict(os.environ, DISABLE_AUTOUPDATER="1"), timeout=300)
    if proc.returncode != 0:
        raise SystemExit((proc.stderr or proc.stdout).strip()[:500])
    data = json.loads(proc.stdout)
    if data.get("is_error"):
        raise SystemExit(str(data.get("result"))[:500])
    return {"result": (data.get("result") or "").strip(), "total_cost_usd": data.get("total_cost_usd", 0.0)}


if __name__ == "__main__":
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    request = " ".join(args) if args else sys.stdin.read()
    if not request.strip():
        raise SystemExit('Give a request, e.g. python run_agent.py "Grade 3 Math, fractions, 35 minutes"')
    out = run(request.strip())
    print(json.dumps(out, ensure_ascii=False) if as_json else out["result"])
