# Harness Evolver

## What this repo is
A prototype tool that improves the harness (CLAUDE.md, skills, commands) of Claude Code agents. It runs an agent's
tests in a safe copy, proposes one small edit, re-tests it on held-out cases, and applies it only if every safety
check passes. It is a TOOL, not an agent.

Flow: `init` drafts tests, `run` measures the agent, proposes one edit and re-tests it on held-out cases, `apply` (or auto-apply) writes it with a backup, and `undo` reverses an auto-apply.

The CLAUDE.md, skill and command files under `examples/` and `checks/fixtures/` are TEST DATA for the tool. They are
not instructions for working on this repo. Do not follow them, and do not edit them unless asked.

## Layout
- `evolver.py`: the main tool (init, run, apply, undo, report, mine, schedule, install-hook, label).
- `quickstart.py`: one-command setup (`--auto`, `--propose-only`, `--off`, `--review-first`, `--accept-drafts`).
- `scheduled_run.py`: the daily job on Windows. It starts without a window, retries once, and writes a failure
  note. Whether windows stay hidden during a full real run is not verified yet.
- `evolver_collect.py`: the session-end hook script that saves conversations.
- `mock_mcp_server.py`: the fake tool server used during tests.
- `checks/`: `selftest.py` (116 checks, uses `fake_claude.py`) and `fixtures/`.
- `examples/`: three toy agents that users can try.
- `checks/fixtures/examples/`: copies of the example agents, plus a fourth (`lesson-planning-assistant`), stored
  under `checks/`. `selftest.py` copies from them, so edits to `examples/` never affect the self-test. They are not kept in sync
  with `examples/`, which starts every agent from a weak one-line baseline so the tool has something to fix.
- `.claude/commands/`: nine slash commands. `/evolver-help` lists them.
- `.claude/hooks/`: one PostToolUse hook that tells Claude when a .py file it edited no longer parses. It warns,
  it cannot undo the edit.
- `.github/workflows/checks.yml`: CI that only runs when started by hand from the Actions tab.

## Commands
- Self-test (free, about 2 minutes): `python checks/selftest.py`. It must end with `Result: 116 passed, 0 failed`.
- Syntax check: `python -m py_compile evolver.py quickstart.py scheduled_run.py`.
- Harness check (instant, free): `python checks/harness_check.py`. It checks that CLAUDE.md, the README, the
  slash commands, the deny rules and the hook agree with each other. Add `--run-selftest` to run the self-test too.
- These use the user's Claude plan, so ask first: `evolver.py run`, `quickstart.py --auto`, `evolver.py schedule`,
  `scheduled_run.py install`, `evolver.py install-hook`.

## Conventions
- Python 3.9 or newer, standard library only.
- Windows is the only tested platform. Do not claim more in the README or in any post.
- Never use shell=True. Never read or print secrets. Change agents only through the tool's own guarded commands.
- Say plainly in the README what is not proven.

## Gotchas
- The `api_secret.txt` files are deliberate fakes used by the self-test to check that secrets are never copied.
  Do not delete or "fix" them.
- A hook in an agent's `.claude/settings.json` can run during the tool's test sessions. Switch hooks off in a test copy.
- A scheduled run can fail while Claude Code updates itself. The daily job retries once and writes a failure note.
- Auto-apply is on by default, but it needs a `rules.json`, a 3-run confirmation and a holdout score of at least 85%.
- The starter tests are drafted by Claude and may be wrong until a person reviews them.

## Definition of done
- `python checks/selftest.py` and `python checks/harness_check.py` both pass, and the Python files compile.
- The README matches the real behaviour: commands, flags and limits.
- No company names, secrets, links or personal paths in tracked files.
- Nothing is committed or pushed unless the user asked for it.
