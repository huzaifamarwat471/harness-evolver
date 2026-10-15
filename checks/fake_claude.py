"""
A fake `claude` command used only by checks/selftest.py. It costs nothing and needs no login.
It imitates `claude -p --output-format json` well enough to test every path of evolver.py,
and it fails loudly if a secret file or the .evolver test folder ever reaches the agent's workspace.
"""
import json
import os
import sys
from pathlib import Path


def reply(text, error=False):
    print(json.dumps({"type": "result", "is_error": error, "result": text, "total_cost_usd": 0.01}))
    sys.exit(0)


args = sys.argv[1:]
prompt = sys.stdin.read()
blocked = args[args.index("--disallowedTools") + 1].split(",") if "--disallowedTools" in args else []
if not {"Bash", "PowerShell", "Write", "Edit"} <= set(blocked):
    reply("SAFETY FAILURE: Bash/PowerShell/Write/Edit were not blocked", error=True)
allowed = args[args.index("--tools") + 1].split(",") if "--tools" in args else None
if allowed is None or not set(filter(None, allowed)) <= {"Read", "Glob", "Grep", "Skill"}:
    reply("SAFETY FAILURE: no allow-list, or it allows a risky tool", error=True)

cwd = Path.cwd()
state = Path(os.environ.get("EVOLVER_FAKE_STATE", cwd)) / "fake_state.json"
st = json.loads(state.read_text()) if state.exists() else {}

# helper calls (judge, fixer, safety) run with no tools at all (--tools ""); they must use the small system prompt
helper_call = "--tools" in args and args[args.index("--tools") + 1] == ""
if helper_call and "--system-prompt" not in args:
    reply("COST FAILURE: helper call sent without the small --system-prompt", error=True)
if not helper_call and "--system-prompt" in args:
    reply("REALISM FAILURE: the agent under test must keep Claude Code's own system prompt", error=True)
if "CRITERIA:" in prompt and "strict, impartial grader" in prompt:
    response = prompt.split("AGENT RESPONSE:\n---\n")[1].split("\n---")[0]
    n = len([l for l in prompt.split("CRITERIA:")[1].split("For each criterion")[0].splitlines() if l.strip()])
    verdict = "YES" if len(response.split()) <= 120 else "NO"
    reply("\n".join(f"{i}: {verdict}" for i in range(1, n + 1)))
limit_file = Path(os.environ.get("EVOLVER_FAKE_STATE", cwd)) / "fake_limit_after"
if limit_file.exists():
    left = int(limit_file.read_text() or 0)
    if left <= 0:
        print(json.dumps({"is_error": True, "result": "You've hit your individual spend limit. Usage limit reached."}))
        sys.exit(0)
    limit_file.write_text(str(left - 1))
if "LABELS:" in prompt and "choose ONE label" in prompt:
    response = prompt.split("AGENT RESPONSE:\n---\n")[1].split("\n---")[0]
    labels = [l.strip() for l in prompt.split("LABELS:")[1].splitlines()[0].split("|")]
    reply(labels[0] if len(response.split()) <= 120 else labels[-1])
if "Reply with exactly: OK" in prompt:
    reply("OK")
if "safety reviewer" in prompt:
    reply("YES" if "ignore all previous" in prompt.lower() else "NO")
if "strict, impartial grader" in prompt:
    response = prompt.split("AGENT RESPONSE:\n---\n")[1].split("\n---")[0]
    reply("YES" if len(response.split()) <= 120 else "NO")
if "helping set up automatic testing" in prompt:
    reply(json.dumps({"context_md": "# Agent: Draft\n\n## What this agent does\nHelps.\n\n## Who uses it\nStaff.\n\n"
                                    "## What a good response looks like\n- Short\n\n## Protected rules\n- Be kind",
                      "tests": [{"id": f"t{i}", "input": f"request {i}", "checks": {"max_words": 100}} for i in range(1, 9)]}))
if "Rewrite the file so it is shorter" in prompt:
    text = prompt.split("---\n", 3)[-1].rsplit("\n---", 1)[0] if prompt.count("---") >= 4 else ""
    reply(text[: max(1, len(text) - 5)])
if "finding REAL problems" in prompt:
    first_user = next((l.split("USER: ", 1)[1] for l in prompt.splitlines() if "] USER: " in l), "")
    reply(json.dumps({"cases": [
        {"input": first_user, "checks": {"max_words": 60}, "evidence": "Too long, I read on my phone."},
        {"input": "A request the user never sent", "checks": {"max_words": 60}, "evidence": "made up"}]}))
if "improving the harness" in prompt:
    n = st.get("refiner_calls", 0) + 1
    st["refiner_calls"] = n
    state.write_text(json.dumps(st))
    if n == 1:   # first idea tries to edit a locked file: must be rejected
        reply(json.dumps({"pattern": "x", "file": ".claude/settings.json", "action": "add", "old_text": "",
                          "new_text": "{}", "reason": "x", "expected_fixes": []}))
    if "FILE: .claude/skills/lesson-feedback/SKILL.md" in prompt:
        reply(json.dumps({"pattern": "answers too long", "file": ".claude/skills/lesson-feedback/SKILL.md",
                          "action": "replace", "old_text": "When a teacher shares a lesson plan, give feedback on it.",
                          "new_text": "When a teacher shares a lesson plan, give kind feedback in under 120 words, "
                                      "in simple English: one real strength first, then one or two ideas that need no extra materials.",
                          "reason": "busy teachers read on phones", "expected_fixes": ["plan_1", "plan_2"]}))
    if "FILE: prompts/format.md" in prompt:
        reply(json.dumps({"pattern": "plans far too long for a phone", "file": "prompts/format.md", "action": "replace",
                          "old_text": "Write a detailed, comprehensive lesson plan and explain every section fully so the teacher has all the information.",
                          "new_text": "Write a short lesson plan, under 250 words, that a teacher can read on a phone.",
                          "reason": "teachers read on WhatsApp", "expected_fixes": ["g1_counting"]}))
    if "Odoo" in prompt:
        reply(json.dumps({"pattern": "tries to delete records", "file": "CLAUDE.md", "action": "add", "old_text": "",
                          "new_text": "Never delete, cancel or change invoices. If asked, explain you cannot and suggest the finance team.",
                          "reason": "protected rule", "expected_fixes": ["delete_dup", "remove_104"]}))
    reply(json.dumps({"pattern": "missing subject line", "file": "CLAUDE.md", "action": "add", "old_text": "",
                      "new_text": "Always start with a Subject: line, keep emails under 150 words, and use only facts from the request.",
                      "reason": "staff send these directly", "expected_fixes": ["req_1"]}))

def call_mock(config_path, tool, arguments):
    """Talk to the real mock_mcp_server.py exactly like Claude Code would (JSON-RPC over stdin/stdout)."""
    import subprocess
    cfg = json.loads(Path(config_path).read_text())
    server = next(iter(cfg["mcpServers"].values()))
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool, "arguments": arguments}}]
    out = subprocess.run([server["command"], *server["args"]], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                         capture_output=True, text=True).stdout.splitlines()
    return json.loads(out[-1])["result"]["content"][0]["text"]


# ---- otherwise this is the agent being tested: it must run in a clean workspace
if any("secret" in f.name.lower() or f.name.startswith(".env") for f in cwd.rglob("*")) or (cwd / ".evolver").exists():
    reply("SAFETY FAILURE: secret or test files were copied into the workspace", error=True)
harness = ""
for f in [cwd / "CLAUDE.md", *cwd.glob(".claude/skills/*/SKILL.md")]:
    if f.exists():
        harness += f.read_text(encoding="utf-8")
if "--mcp-config" in args:
    if "--strict-mcp-config" not in args:
        reply("SAFETY FAILURE: fake tools used without --strict-mcp-config", error=True)
    if os.environ.get("EVOLVER_RUNNING") != "1":
        reply("SAFETY FAILURE: test session not marked with EVOLVER_RUNNING", error=True)
    allowed_mcp = args[args.index("--allowedTools") + 1].split(",") if "--allowedTools" in args else []
    config = args[args.index("--mcp-config") + 1]
    low = prompt.lower()
    if any(w in low for w in ("delete", "remove", "cancel")):
        if "never delete" in harness.lower():
            reply("I can't delete or cancel invoices. Please contact the finance team.")
        if "mcp__odoo__delete_invoice" in allowed_mcp:
            reply("SAFETY FAILURE: delete_invoice should never be allowed", error=True)
        print(json.dumps({"is_error": False, "total_cost_usd": 0.01,
                          "permission_denials": [{"tool_name": "mcp__odoo__delete_invoice"}],
                          "result": "I need your permission to delete invoice 104."}))
        sys.exit(0)
    number = "210" if "210" in prompt else "104"
    text = call_mock(config, "find_invoice", {"number": number})
    reply(f"Here is what Odoo says: {text}")
if "email" in harness.lower():
    body = "Dear parents, the school is closed. Regards, [Name]"
    reply(("Subject: School notice\n" + body) if "Subject:" in harness else body + " " + "word " * 10)
if "120 words" in harness:
    reply("Using a real plant is a strong start. Next class, ask pairs to label parts. " * 2)
reply("Here is detailed feedback. " + "More detail here. " * 70)
