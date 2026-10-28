#!/usr/bin/env python3
"""
harness_check.py: instant, free checks that this repo's own harness is consistent.

    python checks/harness_check.py                 (under a second, no Claude usage)
    python checks/harness_check.py --run-selftest  (also runs checks/selftest.py, about 2 minutes)

It checks the files that steer Claude Code in THIS repo: CLAUDE.md, the README, the slash commands, the deny
rules and the hook. It does not test the evolver itself: that is checks/selftest.py.

Exit code 0 means every check passed, 1 means at least one failed.
"""
import ast
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = ["CLAUDE.md", "README.md", ".claude/settings.json", "evolver.py", "quickstart.py",
                  "scheduled_run.py", "checks/selftest.py"]

# What the project settings must deny. Loosening this list should be a deliberate act, so it fails here first.
REQUIRED_DENY = [
    "Read(./.env)", "Read(./.env.*)", "Read(**/.env)", "Read(**/.env.*)", "Read(**/api_secret.txt)",
    "Bash(rm -rf *)", "Bash(rm -r*)", "Bash(rm -f*)",
    "Bash(git commit*)", "Bash(git push*)", "Bash(git reset --hard*)",
    "Edit(**/examples/**)",
    "Bash(cat *.env*)", "Bash(type *.env*)", "Bash(Get-Content *.env*)",
    "Bash(Remove-Item*)", "Bash(del *)", "Bash(git clean*)", "Bash(git checkout --*)",
    "Edit(**/checks/fixtures/**)",
    # The same words anywhere in a command, so wrapping it in powershell -Command does not get past them.
    "Bash(*Get-Content*.env*)", "Bash(*cat *.env*)", "Bash(*type *.env*)",
    "Bash(*Remove-Item*)",
    "Bash(*git commit*)", "Bash(*git push*)", "Bash(*git clean*)", "Bash(*git checkout --*)",
    "Bash(*git reset --hard*)", "Bash(*rm -rf*)",
    # Claude must not weaken its own guardrails, read its login file, or use more destructive commands.
    "Edit(**/.claude/settings.json)",
    "Edit(**/.claude/hooks/**)",
    "Read(~/.claude/.credentials.json)",
    "Bash(rmdir*)", "Bash(*rmdir *)", "Bash(rd /s*)", "Bash(*git branch -D*)", "Bash(*git stash drop*)",
]

# The commands that use the user's Claude plan. Settings must make Claude ask before each one.
REQUIRED_ASK = [
    "Bash(python evolver.py run*)", "Bash(python evolver.py schedule*)", "Bash(python evolver.py install-hook*)",
    "Bash(python quickstart.py*)", "Bash(python scheduled_run.py install*)",
]

# The only commands allowed without asking: free and read-only. Anything else belongs on the ask or deny list.
ALLOWED_ONLY = ["Bash(python evolver.py status*)", "Bash(python evolver.py report*)"]

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
                "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name + ((" -> " + detail) if (detail and not ok) else ""))


def read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def main():
    run_selftest = "--run-selftest" in sys.argv

    # 1. required files
    missing = [f for f in REQUIRED_FILES if not (ROOT / f).exists()]
    check("required files exist", not missing, "missing: " + ", ".join(missing))
    if missing:
        print("\nResult: %d passed, %d failed" % (sum(results), len(results) - sum(results)))
        return 1

    claude_md = read(ROOT / "CLAUDE.md")
    readme = read(ROOT / "README.md")
    cmd_dir = ROOT / ".claude" / "commands"
    cmd_files = sorted(cmd_dir.glob("*.md")) if cmd_dir.is_dir() else []
    cmd_names = [p.stem for p in cmd_files]

    # 2. settings.json: valid, and the deny rules are all still there
    try:
        settings = json.loads(read(ROOT / ".claude" / "settings.json"))
        deny = settings.get("permissions", {}).get("deny", [])
        check("settings.json is valid JSON", True)
        gone = [d for d in REQUIRED_DENY if d not in deny]
        check("every required deny rule is present", not gone, "missing: " + "; ".join(gone))
        ask = settings.get("permissions", {}).get("ask", [])
        gone_ask = [a for a in REQUIRED_ASK if a not in ask]
        check("every paid command is on the ask list", not gone_ask, "missing: " + "; ".join(gone_ask))
        allow = settings.get("permissions", {}).get("allow", [])
        extra_allow = [a for a in allow if a not in ALLOWED_ONLY]
        check("the allow list holds only the free read-only commands", not extra_allow,
              "not allowed here (use settings.local.json for personal rules): " + "; ".join(extra_allow))
    except ValueError as e:
        settings = {}
        check("settings.json is valid JSON", False, str(e))

    # 3. hooks: every script a hook points at exists
    hook_cmds = []
    for groups in (settings.get("hooks") or {}).values():
        for group in groups:
            for h in group.get("hooks", []):
                hook_cmds.append(h.get("command", ""))
    bad = []
    for c in hook_cmds:
        for m in re.finditer(r"\.claude/hooks/[A-Za-z0-9_.-]+", c):
            if not (ROOT / m.group(0)).exists():
                bad.append(m.group(0))
    check("every hook script exists (%d hook command(s))" % len(hook_cmds), not bad, "missing: " + ", ".join(bad))

    # 4. slash commands: frontmatter, and $ARGUMENTS wherever an argument hint is given
    problems = []
    for p in cmd_files:
        t = read(p)
        m = re.match(r"---\n(.*?)\n---\n", t, re.S)
        if not m:
            problems.append("%s: no frontmatter" % p.name)
            continue
        fm = m.group(1)
        if not re.search(r"^description:\s*\S", fm, re.M):
            problems.append("%s: no description" % p.name)
        if re.search(r"^argument-hint:", fm, re.M) and "$ARGUMENTS" not in t[m.end():]:
            problems.append("%s: has an argument-hint but never uses $ARGUMENTS" % p.name)
    check("every slash command has valid frontmatter (%d commands)" % len(cmd_files), not problems, "; ".join(problems))

    # 5. command lists agree: files, the /evolver-help table, and the README
    help_t = read(cmd_dir / "evolver-help.md") if (cmd_dir / "evolver-help.md").exists() else ""
    not_in_help = [n for n in cmd_names if "/" + n not in help_t]
    check("/evolver-help lists every command", not not_in_help, "missing: " + ", ".join(not_in_help))
    not_in_readme = [n for n in cmd_names if "/" + n not in readme]
    check("the README lists every command", not not_in_readme, "missing: " + ", ".join(not_in_readme))
    unknown = set()
    for label, t in (("CLAUDE.md", claude_md), ("README.md", readme), ("evolver-help.md", help_t)):
        for m in re.finditer(r"/(evolver-[a-z]+)", t):
            if m.group(1) not in cmd_names:
                unknown.add("%s mentions /%s" % (label, m.group(1)))
    check("no document mentions a command that does not exist", not unknown, "; ".join(sorted(unknown)))

    # 6. "N slash commands" claims match the real number
    wrong = []
    for label, t in (("CLAUDE.md", claude_md), ("README.md", readme)):
        for m in re.finditer(r"\b(%s|\d+)\s+slash commands" % "|".join(NUMBER_WORDS), t, re.I):
            w = m.group(1).lower()
            n = NUMBER_WORDS.get(w, int(w) if w.isdigit() else -1)
            if n != len(cmd_names):
                wrong.append("%s line %d says %s, real count is %d" % (label, line_of(t, m.start()), w, len(cmd_names)))
    check("'N slash commands' claims match the file count", not wrong, "; ".join(wrong))

    # 7. CLAUDE.md layout bullets point at real paths
    stale = []
    for m in re.finditer(r"^- `([^`]+)`:", claude_md, re.M):
        tok = m.group(1)
        if " " in tok or "<" in tok or "*" in tok or tok.startswith("--"):
            continue
        p = ROOT / tok.rstrip("/")
        if tok.endswith("/") and not p.is_dir():
            stale.append(tok)
        elif not tok.endswith("/") and not p.exists():
            stale.append(tok)
    check("CLAUDE.md bullets point at paths that exist", not stale, "missing: " + ", ".join(stale))

    # 8. every .py file parses (no file is written)
    broken = []
    pyfiles = sorted(ROOT.glob("*.py")) + sorted((ROOT / "checks").glob("*.py")) + \
        sorted((ROOT / ".claude" / "hooks").glob("*.py"))
    for p in pyfiles:
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=str(p))
        except SyntaxError as e:
            broken.append("%s line %s" % (p.name, e.lineno))
    check("every Python file parses (%d files)" % len(pyfiles), not broken, "; ".join(broken))

    # 9. the 'no shell=True' rule from CLAUDE.md, as a check instead of a promise
    bad_shell = []
    pat = re.compile("shell" + r"\s*=\s*True")
    for p in pyfiles:
        if p.name == "harness_check.py":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if pat.search(line) and not line.lstrip().startswith("#"):
                bad_shell.append("%s:%d" % (p.name, i))
    check("no use of shell=True", not bad_shell, ", ".join(bad_shell))

    # 10. no secrets or personal paths in the files that steer Claude
    scan = [ROOT / "CLAUDE.md", ROOT / "README.md", ROOT / ".claude" / "settings.json"] + cmd_files + \
        sorted((ROOT / ".claude" / "hooks").glob("*.py"))
    secret = re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}|sk-ant-|AKIA[0-9A-Z]{16}|C:\\Users\\|AppData")
    leaks = []
    for p in scan:
        for i, line in enumerate(read(p).split("\n"), 1):
            if secret.search(line):
                leaks.append("%s:%d" % (p.name, i))
    check("no token formats or personal paths in the harness files", not leaks, ", ".join(leaks))

    # 11. numbers that describe the self-test agree everywhere
    claims = {}
    for label, t in [("CLAUDE.md", claude_md), ("README.md", readme)] + [(p.name, read(p)) for p in cmd_files]:
        for rx in (r"Result:\s*(\d+)\s+passed", r"\b(\d+)\s+checks\b"):
            for m in re.finditer(rx, t):
                n = int(m.group(1))
                if n >= 50:
                    claims.setdefault(n, []).append("%s:%d" % (label, line_of(t, m.start())))
    detail = "; ".join("%d at %s" % (n, ", ".join(w)) for n, w in sorted(claims.items()))
    check("self-test counts agree across the documents (%s)" % (", ".join(map(str, sorted(claims))) or "none found"),
          len(claims) <= 1, detail)

    # 12. the README settings table states the same defaults as the code
    try:
        tree = ast.parse((ROOT / "evolver.py").read_text(encoding="utf-8", errors="replace"))
        defaults = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "DEFAULTS" for t in node.targets):
                defaults = ast.literal_eval(node.value)
        if not isinstance(defaults, dict):
            raise ValueError("DEFAULTS not found in evolver.py")
        section = readme.split("\n## Settings", 1)[1].split("\n## ", 1)[0] if "\n## Settings" in readme else ""
        wrong, rows = [], 0
        for line in section.split("\n"):
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            keys = re.findall(r"`([^`]+)`", cells[0])
            vals = re.findall(r"`([^`]*)`", cells[1])
            if not keys or len(keys) != len(vals):
                continue
            for k, v in zip(keys, vals):
                rows += 1
                if k not in defaults:
                    wrong.append("%s is not a setting in evolver.py" % k)
                    continue
                low = v.lower()
                if low in ("true", "false"):
                    shown = low == "true"
                elif low in ("null", "none"):
                    shown = None
                else:
                    try:
                        shown = ast.literal_eval(v)
                    except (ValueError, SyntaxError):
                        shown = v
                if shown != defaults[k]:
                    wrong.append("%s: README says %s, code says %r" % (k, v, defaults[k]))
        check("README settings table matches the defaults in evolver.py (%d values)" % rows,
              rows > 0 and not wrong, "; ".join(wrong) or "no settings table rows found")
    except (OSError, ValueError, SyntaxError) as e:
        check("README settings table matches the defaults in evolver.py", False, str(e))

    # 13. dry-run the hook: it must catch a broken file and accept a good one, whatever the input encoding
    hook_path = ROOT / ".claude" / "hooks" / "py_compile_check.py"
    if hook_path.exists():
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.py"
            bad.write_text("def broken(:\n", encoding="utf-8")
            good = Path(d) / "good.py"
            good.write_text("print('ok')\n", encoding="utf-8")

            def feed(path, encode=lambda s: s.encode("utf-8")):
                payload = encode(json.dumps({"tool_input": {"file_path": str(path)}}))
                return subprocess.run([sys.executable, str(hook_path)], input=payload, capture_output=True, timeout=60)

            cases = [("broken file", feed(bad), 2), ("good file", feed(good), 0),
                     ("broken file, UTF-8 with BOM", feed(bad, lambda s: b"\xef\xbb\xbf" + s.encode("utf-8")), 2),
                     ("broken file, UTF-16", feed(bad, lambda s: s.encode("utf-16")), 2)]
            wrong = ["%s gave exit %d (wanted %d)" % (n, r.returncode, want) for n, r, want in cases
                     if r.returncode != want]
            if cases[0][1].returncode == 2 and b"Syntax error" not in cases[0][1].stderr:
                wrong.append("the message for a broken file does not say 'Syntax error'")
        check("the hook catches a broken file and accepts a good one (%d dry runs)" % len(cases), not wrong,
              "; ".join(wrong))
    else:
        check("the hook script exists to dry-run", False, "missing: .claude/hooks/py_compile_check.py")

    # 14. slash command descriptions: distinct, short, safe for YAML, and commands that could be confused name each other
    descs = {}
    for p in cmd_files:
        m = re.match(r"---\n(.*?)\n---\n", read(p), re.S)
        d = re.search(r"^description:\s*(.+)$", m.group(1), re.M) if m else None
        descs[p.stem] = d.group(1).strip() if d else ""
    problems, seen = [], {}
    for n, d in descs.items():
        if len(d) > 200:
            problems.append("%s: description is %d characters (limit 200)" % (n, len(d)))
        if ": " in d or " #" in d:
            problems.append("%s: a colon or # inside the description can break the frontmatter" % n)
        if d in seen:
            problems.append("%s and %s have the same description" % (n, seen[d]))
        seen[d] = n
    for a, b in (("evolver-apply", "evolver-undo"), ("evolver-status", "evolver-report"), ("evolver-off", "evolver-undo")):
        if a in descs and b in descs and ("/" + b) not in descs[a] and ("/" + a) not in descs[b]:
            problems.append("%s and %s could be confused, and neither description names the other" % (a, b))
    check("command descriptions are distinct, short, YAML-safe, and confusable pairs name each other", not problems,
          "; ".join(problems))

    # 15. cost ranges quoted in the documents agree with each other
    ranges = {}
    for label, t in [("CLAUDE.md", claude_md), ("README.md", readme)] + [(p.name, read(p)) for p in cmd_files]:
        for m in re.finditer(r"\$(\d+(?:\.\d+)?) to \$(\d+(?:\.\d+)?)", t):
            ranges.setdefault((m.group(1), m.group(2)), []).append("%s:%d" % (label, line_of(t, m.start())))
    check("cost ranges agree across the documents (%s)" % (", ".join("$%s to $%s" % k for k in sorted(ranges)) or "none found"),
          len(ranges) <= 1, "; ".join("$%s to $%s at %s" % (k[0], k[1], ", ".join(v)) for k, v in sorted(ranges.items())))

    # 16. commands hand folder paths to python inside double quotes, never as a raw $ARGUMENTS (a Unix-style shell
    #     drops the backslashes of an unquoted Windows path, and the tool then looks in the wrong place)
    raw = []
    for p in cmd_files:
        for i, line in enumerate(read(p).split("\n"), 1):
            if line.lstrip().startswith("python ") and "$ARGUMENTS" in line:
                raw.append("%s:%d" % (p.name, i))
    check("no command runs python with an unquoted $ARGUMENTS", not raw, "unquoted at " + ", ".join(raw))

    # 17. optional: run the real self-test and compare
    if run_selftest:
        print("running checks/selftest.py (about 2 minutes)...")
        r = subprocess.run([sys.executable, str(ROOT / "checks" / "selftest.py")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=900)
        m = re.search(r"Result:\s*(\d+)\s+passed,\s*(\d+)\s+failed", r.stdout or "")
        if not m:
            check("selftest finished with a Result line", False, "no Result line in its output")
        else:
            passed, failed = int(m.group(1)), int(m.group(2))
            check("selftest has no failures (%d passed, %d failed)" % (passed, failed), failed == 0)
            check("documents state the real self-test count (%d)" % passed,
                  all(n == passed for n in claims), "documents say %s" % ", ".join(map(str, sorted(claims))))

    ok = sum(results)
    print("\nResult: %d passed, %d failed" % (ok, len(results) - ok))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
