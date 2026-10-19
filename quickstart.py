#!/usr/bin/env python3
"""
quickstart.py: get any agent folder ready for Harness Evolver with one command.

Usage (run it from the folder that contains evolver.py):
    python quickstart.py <agent folder>
    python quickstart.py <agent folder> --tools find_invoice,delete_invoice --server odoo
    python quickstart.py <agent folder> --accept-drafts
    python quickstart.py <agent folder> --auto --accept-drafts --starter-rules
    python quickstart.py <agent folder> --propose-only     (keep it running, never apply fixes)
    python quickstart.py <agent folder> --off              (turn the whole loop off)

What it does:
  1. Checks your setup: Python, Claude Code, and the Claude Code options the tool needs.
  2. Runs `evolver.py init` if the agent has no .evolver folder yet. init asks Claude Code to draft
     the tests, so it uses a little of your Claude plan. Existing files are never overwritten.
  3. With --tools (and --server, the name of your real MCP server), drafts .evolver/mock_tools.json
     (risky-looking tools are left out of "allowed").
  4. With --accept-drafts, accepts the drafted tests WITHOUT human review (clearly marked).
  5. With --auto, turns on the continuous loop: the session-end hook, a daily scheduled run, and
     auto-apply with a spending cap. Every safety gate of the tool stays in force.
     Add --propose-only to keep the loop running but never apply a fix on its own.
  5b. --propose-only (alone) stops auto-applying but keeps the loop proposing fixes.
      --off (alone) turns everything off: auto-apply, the daily schedule and the session-end hook.
  6. Without --auto, keeps the first run review-only and prints what to review next.

The script itself makes no Claude calls and never runs the evolve loop.
Use a COPY of the agent folder while you learn the tool.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Claude Code options the tool uses. Missing ones mean Claude Code is too old.
NEEDED_FLAGS = ["--setting-sources", "--tools", "--disallowedTools", "--strict-mcp-config", "--output-format"]

# Words that make a tool name look like it changes something. This is a guess: you review the file.
STRONG_RISKY = {
    "delete", "remove", "drop", "destroy", "wipe", "purge", "send", "post", "publish",
    "dispatch", "deploy", "merge", "push", "pay", "transfer", "refund", "cancel",
}
WEAK_RISKY = {
    "clear", "reset", "submit", "approve", "grant", "revoke", "write", "update", "edit",
    "modify", "create", "add", "set", "assign", "close", "file",
}
# A read-style word makes a weak-risky word harmless (read_file). get_or_create is a judgment call.
READ_WORDS = {
    "read", "get", "list", "find", "search", "fetch", "view", "show", "status", "lookup",
    "query", "check", "describe", "investigate", "draft", "review",
}

SECRET_NAME = re.compile(r"(^\.env)|\.pem$|\.key$|\.pfx$|id_rsa|secret|credential|token", re.I)

# A deliberately minimal placeholder so auto-apply is allowed. Add real rules for your agent.
STARTER_RULES = {"checks": {"max_tool_attempts": {"*": 6}}}

problems = []


def say(level, text):
    print("  %-5s %s" % (level, text))


def fail(text):
    say("FAIL", text)
    problems.append(text)


def tool_words(name):
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", name)
    return {p.lower() for p in parts}


def is_risky(name):
    words = tool_words(name)
    if words & STRONG_RISKY:
        return True
    return bool(words & WEAK_RISKY) and not (words & READ_WORDS)


def check_python():
    v = sys.version_info
    if v >= (3, 8):
        say("PASS", "Python %d.%d.%d" % (v[0], v[1], v[2]))
    else:
        fail("Python 3.8 or newer is needed (you have %d.%d)" % (v[0], v[1]))


def run_text(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    return (r.stdout or "") + (r.stderr or "")


def check_claude():
    """Returns True if Claude Code was found."""
    path = shutil.which("claude")
    if not path:
        say("WARN", "Claude Code ('claude') was not found on PATH. Install it and log in before running the tool.")
        return False
    try:
        version = run_text([path, "--version"]).strip().splitlines()
        say("PASS", "Claude Code found: %s" % (version[0] if version else path))
        help_text = run_text([path, "--help"])
    except (OSError, subprocess.TimeoutExpired) as e:
        say("WARN", "Could not run 'claude --help' (%s)" % e)
        return True
    missing = [f for f in NEEDED_FLAGS if f not in help_text]
    if missing:
        say("WARN", "Your Claude Code does not list: %s. Update Claude Code before running the tool." % ", ".join(missing))
    else:
        say("PASS", "Claude Code supports the options the tool uses")
    say("INFO", "Login is not checked here. The first run says 'Checking Claude Code... OK' or tells you what is wrong.")
    return True


def check_agent(agent):
    if not agent.is_dir():
        fail("Agent folder not found: %s" % agent)
        return False
    has_instructions = (agent / "CLAUDE.md").exists() or (agent / ".claude").is_dir()
    if has_instructions:
        say("PASS", "Agent folder has CLAUDE.md or .claude")
    else:
        say("WARN", "No CLAUDE.md or .claude folder. If this is a custom app, it needs the 'runner' and "
                    "'harness_files' settings (see the README).")
    secrets = []
    for p in agent.rglob("*"):
        try:
            depth = len(p.relative_to(agent).parts)
        except ValueError:
            continue
        if depth > 3 or ".evolver" in p.parts or ".git" in p.parts or "node_modules" in p.parts:
            continue
        if p.is_file() and SECRET_NAME.search(p.name):
            secrets.append(str(p.relative_to(agent)))
    if secrets:
        say("WARN", "Secret-looking files here: %s. The tool never copies them into test runs, "
                    "but do not share or commit this folder." % ", ".join(secrets[:5]))
    return True


def run_init(agent, evolver):
    evo = agent / ".evolver"
    if evo.exists():
        say("PASS", ".evolver already exists, so init was skipped (nothing is overwritten)")
        return True
    say("INFO", "Running: python evolver.py init (it asks Claude Code to draft the tests, which uses a little plan usage)")
    print()
    r = subprocess.run([sys.executable, str(evolver), "init", str(agent)])
    print()
    if r.returncode != 0:
        fail("evolver.py init failed (exit %d)" % r.returncode)
        return False
    say("PASS", "init created the .evolver folder with drafts")
    return True


def draft_mock_tools(evo, server, names):
    path = evo / "mock_tools.json"
    if path.exists():
        say("PASS", "mock_tools.json already exists, left as it is")
        return False
    tools = [{
        "name": n,
        "description": "TODO: what this tool does",
        "input_schema": {"type": "object", "properties": {}},
        "returns": "TODO: a pretend answer this tool returns",
    } for n in names]
    allowed = [n for n in names if not is_risky(n)]
    blocked = [n for n in names if is_risky(n)]
    path.write_text(json.dumps({"server": server, "allowed": allowed, "tools": tools}, indent=2) + "\n",
                    encoding="utf-8")
    say("PASS", "Drafted .evolver/mock_tools.json (server '%s', %d tools)" % (server, len(names)))
    say("INFO", "Allowed: %s" % (", ".join(allowed) or "(none)"))
    if blocked:
        say("INFO", "Defined but NOT allowed (a call is blocked and counts as a failure): %s" % ", ".join(blocked))
    say("WARN", "The allowed / not allowed split is a guess from the tool names. Check it before the first run.")
    return True


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def drafts_remaining(evo):
    """Why the tool would still treat the setup as an unreviewed draft."""
    why = []
    ctx = evo / "context.md"
    if ctx.exists():
        lines = ctx.read_text(encoding="utf-8-sig").splitlines()
        if lines and lines[0].strip().upper().startswith("DRAFT"):
            why.append("context.md still starts with the DRAFT line")
    tj = evo / "tests.json"
    if tj.exists():
        try:
            data = read_json(tj)
        except ValueError:
            data = None
        if isinstance(data, dict) and "draft" in data:
            why.append("tests.json is still wrapped in the draft object")
    return why


def accept_drafts(evo):
    """Accept the AI-drafted tests and context without human review. Originals are kept."""
    backup = evo / "drafts-original"
    backup.mkdir(exist_ok=True)
    changed = False
    ctx = evo / "context.md"
    if ctx.exists():
        text = ctx.read_text(encoding="utf-8-sig")
        lines = text.splitlines(True)
        if lines and lines[0].strip().upper().startswith("DRAFT"):
            shutil.copy2(str(ctx), str(backup / "context.md"))
            ctx.write_text("".join(lines[1:]).lstrip("\r\n"), encoding="utf-8")
            say("PASS", "Removed the DRAFT line from context.md")
            changed = True
    tj = evo / "tests.json"
    if tj.exists():
        try:
            data = read_json(tj)
        except ValueError as e:
            fail("tests.json is not valid JSON (%s)" % e)
            return False
        if isinstance(data, dict) and "draft" in data:
            if isinstance(data.get("tests"), list):
                shutil.copy2(str(tj), str(backup / "tests.json"))
                tj.write_text(json.dumps(data["tests"], indent=2) + "\n", encoding="utf-8")
                say("PASS", "Unwrapped tests.json to just the list (%d tests)" % len(data["tests"]))
                changed = True
            else:
                fail("tests.json has a 'draft' key but no 'tests' list, so it was left alone")
                return False
    if changed:
        marker = evo / "ACCEPTED_UNREVIEWED_DRAFTS.txt"
        marker.write_text(
            "The drafted tests and context were accepted WITHOUT human review on %s by quickstart.py --accept-drafts.\n"
            "They were written by Claude from CLAUDE.md alone and may be wrong.\n"
            "Review context.md and tests.json, then delete this file. Originals are in drafts-original/.\n"
            % datetime.now().strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
        say("WARN", "These tests were drafted by Claude from CLAUDE.md alone and nobody has reviewed them. "
                    "Wrong tests can make the tool accept bad changes. Review them soon (see ACCEPTED_UNREVIEWED_DRAFTS.txt).")
    elif (evo / "ACCEPTED_UNREVIEWED_DRAFTS.txt").exists():
        say("WARN", "The drafts were already accepted earlier WITHOUT review (see ACCEPTED_UNREVIEWED_DRAFTS.txt)")
    else:
        say("PASS", "Nothing to accept: the drafts were already reviewed")
    return True


def keep_first_run_safe(evo):
    rules, cfg = evo / "rules.json", evo / "config.json"
    if not rules.exists():
        say("PASS", "No rules.json, so nothing can be auto-applied: the first run only proposes fixes")
        return
    if not cfg.exists():
        say("WARN", "rules.json exists but config.json does not. Create .evolver/config.json containing "
                    '{"auto_apply": false} before the first run, or a verified fix may be applied automatically.')
        return
    try:
        data = read_json(cfg)
    except ValueError as e:
        say("WARN", "config.json is not valid JSON (%s). Fix it before running." % e)
        return
    if data.get("auto_apply") is False:
        say("PASS", "auto_apply is already false: the first run only proposes fixes")
        return
    data["auto_apply"] = False
    cfg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    say("PASS", 'Set "auto_apply": false in config.json for the first run (turn it on later when you trust the tests)')


def ask_yes(prompt):
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def setup_auto(agent, evolver, evo, cap, run_time, starter, assume_yes, apply_on):
    """Turn on the continuous loop. Returns True when done, None if the user declined, False on failure."""
    rules, cfg = evo / "rules.json", evo / "config.json"
    plan = []
    if apply_on and not rules.exists():
        if starter:
            plan.append("write a minimal placeholder .evolver/rules.json (a retry limit only; add real rules for your agent)")
        else:
            say("WARN", "No rules.json: the daily loop will run but can only PROPOSE fixes. Auto-apply cannot fire "
                        "until you add .evolver/rules.json (or rerun with --starter-rules for a minimal placeholder).")
    cfg_data = None
    new_cap = None
    if cfg.exists():
        try:
            cfg_data = read_json(cfg)
        except ValueError as e:
            fail("config.json is not valid JSON (%s)" % e)
            return False
        old_cap = cfg_data.get("max_run_cost_usd")
        new_cap = old_cap if isinstance(old_cap, (int, float)) and old_cap >= cap else cap
        plan.append('set "auto_apply": %s and "max_run_cost_usd": %s in config.json (saved copy: config.json.before-quickstart)'
                    % ("true" if apply_on else "false", new_cap))
    else:
        say("WARN", "No config.json, so settings were not changed. Defaults apply (the spending cap per run is $1).")
    plan.append("install the session-end hook (it saves finished conversations to .evolver/inbox, with no AI and no edits)")
    if apply_on:
        plan.append("schedule a DAILY run%s that applies verified fixes on its own" % (" at %s" % run_time if run_time else ""))
    else:
        plan.append("schedule a DAILY run%s that only PROPOSES fixes (nothing is written to the agent)" % (" at %s" % run_time if run_time else ""))

    print()
    print("  This will:")
    for p in plan:
        print("    - %s" % p)
    if apply_on:
        print("  Each daily run can use up to $%s of your Claude plan. Every fix is backed up and 'undo' reverses it." %
              (new_cap if new_cap is not None else "1"))
    else:
        print("  Each daily run can use up to $%s of your Claude plan. Fixes are only proposed." %
              (new_cap if new_cap is not None else "1"))
    if not assume_yes and not ask_yes("  Turn on the continuous loop? [y/N]: "):
        print("\n  Nothing was installed, and config.json was not changed.")
        return None

    if apply_on and not rules.exists() and starter:
        rules.write_text(json.dumps(STARTER_RULES, indent=2) + "\n", encoding="utf-8")
        say("PASS", "Wrote a minimal placeholder rules.json")
    if cfg_data is not None:
        backup = evo / "config.json.before-quickstart"
        if not backup.exists():
            shutil.copy2(str(cfg), str(backup))
        cfg_data["auto_apply"] = apply_on
        cfg_data["max_run_cost_usd"] = new_cap
        cfg.write_text(json.dumps(cfg_data, indent=2) + "\n", encoding="utf-8")
        say("PASS", "auto_apply is %s, spending cap $%s per run" % ("ON" if apply_on else "OFF (propose-only)", new_cap))

    print()
    say("INFO", "Running: python evolver.py install-hook (it may ask you to confirm)")
    r = subprocess.run([sys.executable, str(evolver), "install-hook", str(agent)])
    if r.returncode != 0:
        fail("install-hook failed (exit %d)" % r.returncode)
        return False
    say("PASS", "Session-end hook installed")

    print()
    say("INFO", "Running: python evolver.py schedule (it asks before creating anything)")
    cmd = [sys.executable, str(evolver), "schedule", str(agent)]
    if run_time:
        cmd += ["--time", run_time]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        say("WARN", "schedule did not finish (exit %d). Run it yourself: python evolver.py schedule \"%s\"" % (r.returncode, agent))
    else:
        say("PASS", "Daily run scheduled (see its output above for the time and how to remove it)")
    return True


def set_auto_apply(evo, value, suffix):
    """Set auto_apply in config.json, keeping a copy of the file as it was. Returns True on success."""
    cfg = evo / "config.json"
    if not cfg.exists():
        say("WARN", "No config.json, so there is no auto_apply setting to change (the first run only proposes without rules.json).")
        return False
    try:
        data = read_json(cfg)
    except ValueError as e:
        fail("config.json is not valid JSON (%s)" % e)
        return False
    if data.get("auto_apply") is value:
        say("PASS", "auto_apply is already %s" % ("ON" if value else "OFF"))
        return True
    backup = evo / ("config.json.before-quickstart-" + suffix)
    if not backup.exists():
        shutil.copy2(str(cfg), str(backup))
    data["auto_apply"] = value
    cfg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    say("PASS", "auto_apply is now %s" % ("ON" if value else "OFF (fixes are only proposed)"))
    return True


def remove_hook(agent):
    """Remove only Harness Evolver's SessionEnd entry from .claude/settings.local.json."""
    path = agent / ".claude" / "settings.local.json"
    if not path.exists():
        say("PASS", "No .claude/settings.local.json, so there is no hook to remove")
        return
    try:
        data = read_json(path)
    except ValueError as e:
        say("WARN", "settings.local.json is not valid JSON (%s). Remove the SessionEnd entry by hand." % e)
        return
    hooks = data.get("hooks") if isinstance(data, dict) else None
    entries = hooks.get("SessionEnd") if isinstance(hooks, dict) else None
    if not isinstance(entries, list):
        say("PASS", "No SessionEnd hook found")
        return
    keep = [e for e in entries if "evolver_collect.py" not in json.dumps(e)]
    if len(keep) == len(entries):
        say("PASS", "No Harness Evolver hook found in settings.local.json")
        return
    backup = path.with_name("settings.local.json.before-quickstart-off")
    if not backup.exists():
        shutil.copy2(str(path), str(backup))
    if keep:
        hooks["SessionEnd"] = keep
    else:
        del hooks["SessionEnd"]
        if not hooks:
            del data["hooks"]
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    say("PASS", "Removed the Harness Evolver session-end hook (your other settings were left alone)")


def run_off(agent, evolver, assume_yes):
    evo = agent / ".evolver"
    print("\n  This will turn the continuous loop OFF for this agent:")
    print("    - set \"auto_apply\": false (a copy of config.json is kept)")
    print("    - remove the daily scheduled task, if there is one")
    print("    - remove the session-end hook from .claude/settings.local.json (your other settings stay)")
    print("  It does not delete anything else, and it does not undo fixes that were already applied.")
    if not assume_yes and not ask_yes("  Turn it off? [y/N]: "):
        print("\n  Nothing was changed.")
        return 0
    print()
    if evo.is_dir():
        set_auto_apply(evo, False, "off")
    else:
        say("WARN", "No .evolver folder here, so there are no settings to change")
    print()
    say("INFO", "Running: python evolver.py schedule --remove")
    r = subprocess.run([sys.executable, str(evolver), "schedule", str(agent), "--remove"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    for line in out.splitlines():
        print("        " + line)
    up = out.upper()
    if r.returncode != 0:
        say("WARN", "schedule --remove did not finish (exit %d). There may be no scheduled task for this agent." % r.returncode)
    elif "SUCCESS" in up:
        say("PASS", "Scheduled task removed")
    elif "ERROR" in up or "CANNOT FIND" in up or "NO SUCH" in up:
        say("INFO", "No scheduled task was found for this agent, so there was nothing to remove")
    else:
        say("INFO", "schedule --remove finished (see its message above)")
    print()
    remove_hook(agent)
    print("\nDONE. The loop is off for: %s" % agent)
    inbox = evo / "inbox"
    if inbox.is_dir():
        print("  - Saved conversations are still in %s. Delete that folder if you do not want to keep them." % inbox)
    print("  - Fixes that were already applied stay. To reverse the last one: python evolver.py undo \"%s\"" % agent)
    print("  - To turn it on again: python quickstart.py \"%s\" --auto" % agent)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Get an agent folder ready for Harness Evolver.")
    ap.add_argument("agent", help="path to the agent folder (use a copy while learning)")
    ap.add_argument("--tools", default="", help="comma-separated tool names the agent calls, e.g. find_invoice,delete_invoice")
    ap.add_argument("--server", default="",
                    help="name of your REAL MCP server, like odoo or crew (required with --tools; it must match so "
                         "tool names in your instructions still resolve)")
    ap.add_argument("--accept-drafts", action="store_true",
                    help="accept the AI-drafted tests and context WITHOUT review (marked, with originals kept)")
    ap.add_argument("--auto", action="store_true",
                    help="turn on the continuous loop: session-end hook, daily scheduled run, auto-apply")
    ap.add_argument("--propose-only", action="store_true",
                    help="never apply fixes on its own: with --auto the loop only proposes; alone it switches auto-apply off")
    ap.add_argument("--off", action="store_true",
                    help="turn the continuous loop off: auto-apply, the daily schedule and the session-end hook")
    ap.add_argument("--starter-rules", action="store_true",
                    help="with --auto: write a minimal placeholder rules.json so auto-apply is allowed")
    ap.add_argument("--cap", type=float, default=3.0, help="with --auto: spending cap per run in dollars (default 3.0)")
    ap.add_argument("--time", default="", help="with --auto: time of the daily run, like 09:00")
    ap.add_argument("--yes", action="store_true", help="with --auto or --off: do not ask before changing things")
    ap.add_argument("--evolver", default=str(Path(__file__).resolve().with_name("evolver.py")), help="path to evolver.py")
    args = ap.parse_args()

    agent = Path(args.agent).expanduser().resolve()
    evolver = Path(args.evolver)
    names = []
    for n in [t.strip() for t in args.tools.split(",") if t.strip()]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", n):
            print("Tool names may only use letters, digits, _ and -: %r" % n)
            return 1
        if n not in names:
            names.append(n)
    if names and not args.server:
        print("--tools needs --server: give the name of your real MCP server (for example odoo or crew). "
              "It must match, so tool names in your instructions still resolve.")
        return 1
    if names and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,30}", args.server):
        print("--server must be a simple name like odoo or crew: %r" % args.server)
        return 1
    if not 0.5 <= args.cap <= 20:
        print("--cap must be between 0.5 and 20 dollars: %r" % args.cap)
        return 1
    if args.time and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", args.time):
        print("--time must look like 09:00: %r" % args.time)
        return 1
    if (args.starter_rules or args.time) and not args.auto:
        print("--starter-rules and --time only make sense together with --auto.")
        return 1
    if args.yes and not (args.auto or args.off):
        print("--yes only makes sense together with --auto or --off.")
        return 1
    if args.off and (args.auto or args.propose_only or args.accept_drafts or args.tools):
        print("--off cannot be combined with --auto, --propose-only, --accept-drafts or --tools.")
        return 1

    # turning things off needs no setup checks
    if args.off:
        if not agent.is_dir():
            print("Agent folder not found: %s" % agent)
            return 1
        if not evolver.exists():
            print("evolver.py not found at %s (run this from the repo folder, or pass --evolver)" % evolver)
            return 1
        print("\nHarness Evolver quickstart --off for: %s" % agent)
        return run_off(agent, evolver, args.yes)
    if args.propose_only and not args.auto:
        if not agent.is_dir():
            print("Agent folder not found: %s" % agent)
            return 1
        if not (agent / ".evolver").is_dir():
            print("No .evolver folder in %s, so there is nothing to change." % agent)
            return 1
        print("\nHarness Evolver quickstart --propose-only for: %s\n" % agent)
        ok = set_auto_apply(agent / ".evolver", False, "propose-only")
        print("\nThe loop keeps running (if it is scheduled) but fixes are only proposed.")
        print("To turn auto-apply back on: python quickstart.py \"%s\" --auto" % agent)
        return 0 if ok else 1

    print("\nHarness Evolver quickstart for: %s\n" % agent)
    print("1. Checking your setup")
    check_python()
    if not evolver.exists():
        fail("evolver.py not found at %s (run this from the repo folder, or pass --evolver)" % evolver)
    found = check_claude()
    if args.auto and not found:
        fail("--auto needs Claude Code installed and logged in")
    if not check_agent(agent) or problems:
        print("\nStopped: fix the FAIL lines above and run it again.")
        return 1

    print("\n2. Setting up .evolver")
    if not run_init(agent, evolver):
        print("\nStopped: fix the problem above and run it again.")
        return 1
    evo = agent / ".evolver"

    print("\n3. Fake tools")
    if names:
        draft_mock_tools(evo, args.server, names)
    else:
        say("INFO", "No --tools given. If the agent calls tools, rerun with --tools name1,name2 --server NAME "
                    "(real tools are always blocked during tests; see the README section 'Agents with tools').")

    if args.accept_drafts:
        print("\n3b. Accepting the drafted tests WITHOUT review")
        if not accept_drafts(evo):
            print("\nStopped: fix the problem above and run it again.")
            return 1

    remaining = drafts_remaining(evo)

    if args.auto:
        print("\n4. Continuous loop")
        if remaining:
            for w in remaining:
                say("WARN", w)
            print("\nStopped before turning the loop on: the tests are still unreviewed drafts, and the loop "
                  "would be refused every day.")
            print("Either review them (delete the DRAFT line in context.md, keep only the list in tests.json),")
            print("or rerun with --accept-drafts to accept them without review.")
            return 0
        apply_on = not args.propose_only
        result = setup_auto(agent, evolver, evo, args.cap, args.time, args.starter_rules, args.yes, apply_on)
        if result is False:
            return 1
        if result is None:
            return 0
        print("\nDONE. The loop is on for: %s" % agent)
        print("  - See what it did:      python evolver.py report \"%s\"" % agent)
        if apply_on:
            print("  - Reverse the last fix: python evolver.py undo \"%s\"" % agent)
            print("  - Never apply on its own, keep proposing: python quickstart.py \"%s\" --propose-only" % agent)
        else:
            print("  - Fixes are only proposed. To let it apply them: python quickstart.py \"%s\" --auto" % agent)
        print("  - Turn everything off:  python quickstart.py \"%s\" --off" % agent)
        if (evo / "ACCEPTED_UNREVIEWED_DRAFTS.txt").exists():
            print("  - Remember: the tests were accepted WITHOUT review. Read tests.json and context.md soon.")
        return 0

    print("\n4. First-run safety")
    keep_first_run_safe(evo)

    if remaining:
        print("\nDONE. Before the first run, review these (the tool refuses to run unreviewed drafts):")
        print("  - %s : delete the DRAFT line; check the agent description and protected rules" % (evo / "context.md"))
        print("  - %s : keep only the list; check the 6 to 12 requests and their checks (the tests decide every result)" % (evo / "tests.json"))
    else:
        print("\nDONE. The drafts are accepted. Check these files before you trust the results:")
        print("  - %s" % (evo / "context.md"))
        print("  - %s" % (evo / "tests.json"))
    if names:
        print("  - %s : fill in each TODO description and pretend answer" % (evo / "mock_tools.json"))
    print("\nThen run (review mode: it shows the cost estimate and asks before spending anything):")
    print('  python evolver.py run "%s"' % agent)
    print("\nAny fix waits in proposed.patch. Apply it only after you have read it; 'undo' reverses a change that auto-apply made; after a manual apply the old file is in .evolver/backups.")
    print("To turn on the continuous loop later: python quickstart.py \"%s\" --auto" % agent)
    return 0


if __name__ == "__main__":
    sys.exit(main())
