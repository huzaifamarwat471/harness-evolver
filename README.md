# Harness Evolver (Claude Code edition), prototype

> **Status:** prototype for testing. By default a human approves every change. With auto-apply (for example
> `quickstart.py --auto`), a verified fix can be applied on its own, but only when every safety check passes.
> Do not run auto-apply on a production agent until its tests have been reviewed.
> Built by Huzaifa Razaq (R&D). Please share bugs and results.

Improves the harness of **any Claude Code agent**: its `CLAUDE.md`, skills and commands. You give it a few test
cases. It finds what the agent keeps getting wrong, proposes one small fix, tests the fix on cases it has not seen,
and asks you to approve. By default your agent's files are not changed until you run `apply`. With auto-apply on,
a verified fix is applied on its own (backed up, and `undo` reverses it).

## Start here

1. **Check it works** (free, about 2 minutes): `python checks/selftest.py`. Expect `Result: 132 passed, 0 failed`.
2. **Set up an agent:** `python quickstart.py "path/to/a COPY of your agent"`. Claude drafts starter tests, which
   uses a little of your Claude plan.
3. **Run it:** `python evolver.py run "path/to/your agent copy"`. It shows the cost first, proposes one fix at a
   time, and, unless you turned on auto-apply, changes nothing until you run `apply`.

In Claude Code, open this folder and type `/evolver-help`. Please read "Known issues found in testing" below
before you rely on it.

## How it works

1. Runs your agent through Claude Code (`claude -p`) on each test case: once each by default, more with `repeats`.
2. A case counts as a real failure only if it fails **every** run. A flaky case (some runs pass, some fail) is
   ignored unless you set `min_pass_rate`, so it doesn't chase noise.
3. A fixer reads the failures and your agent's `context.md`, and proposes **one small edit** to one harness file.
4. Safety checks run before testing (see below).
5. The edited harness is tested on the train cases and on **holdout** cases the fixer never saw.
6. It is kept only if no score drops, no always-passing case starts failing, and it clearly helps: a test
   passes in more runs, or a failure that repeated across tests happens less (a higher average alone is not
   enough).
   A check that was passing and now fails in two or more runs also blocks it. If the result is a close call,
   the tests involved are run again for both versions, and for those tests the decision uses only the fresh runs.
7. **You approve or reject** each change. It then looks for the next problem.
8. Optional (`"cleanup": true`): at the end it can merge repeated instructions, tested the same way.

## Safety

- **Your agent is never edited by `run`.** Tests use a temporary copy. Results go to `.evolver/runs/`.
- **Only instruction files can be edited:** `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/skills/*/SKILL.md`,
  `.claude/commands/*.md`. Settings, hooks, MCP configs and all other files are **always locked**.
  Subagents (`.claude/agents/`) are locked unless you turn them on.
- **Secrets are never copied** into the test copy (`.env`, keys, `*secret*`, `*credential*`, `*token*` and similar).
  The `.evolver` folder with your tests is not copied either, so the agent can't read the expected answers.
- **During tests the agent can only read its own files and load its skills** (allow-list: Read, Glob, Grep, Skill).
  Bash, PowerShell, editing, writing, web access and scheduling tools are blocked. MCP servers are switched off.
- **Edit limits:** one small edit at a time, size-limited, no copying test content into the harness (that would be
  cheating the test), protected rules can't be removed, skill headers (`---` frontmatter) can't be broken.
- **Safety review:** every change is checked against your protected rules. If the check can't run, the change is refused.
- **`apply` makes a backup first**, and refuses if your files changed since the run started.

## Requirements

- Python 3.9 or newer (no extra packages)
- Claude Code installed and logged in: `claude --version`, then `claude -p "hello"` should answer

## Quick start: check it works (free, no Claude usage)

```
python checks/selftest.py
```
Expect `Result: 132 passed, 0 failed`. This uses a fake Claude, so it costs nothing.

## Try it on the examples (uses Claude usage)

```
python evolver.py run examples/lesson-coach
python evolver.py run examples/email-helper
```
Two different agents: a lesson-feedback coach (CLAUDE.md + a skill) and an email writer (CLAUDE.md + a command).
A third, `examples/finance-assistant`, uses **fake Odoo tools** (see below):
```
python evolver.py run examples/finance-assistant
```

Each example starts from a deliberately weak one-line `CLAUDE.md`, so there is something to fix. Each has
`auto_apply` switched off, so a run only proposes a fix and changes nothing until you run `apply`.

## One-command setup (quickstart)

`quickstart.py` gets any agent folder ready with one command. Run it from the folder that contains `evolver.py`:

    python quickstart.py "path\to\your-agent"

It checks your setup (Python, Claude Code and the options the tool uses) and runs `init` if the agent has no `.evolver` folder yet. `init` asks Claude Code to draft the tests, which uses a little of your Claude plan. Then it prints the files you must review and the exact next command. It never overwrites a file, never runs the evolve loop itself, and keeps the first run review-only.

If the agent uses tools, add their names and your real MCP server's name (`--server`; it must match, so tool names in your instructions still resolve). It drafts `.evolver/mock_tools.json`, and risky-looking tools (delete, send, post, pay...) are left out of "allowed", so a call is blocked:

    python quickstart.py "path\to\your-agent" --tools find_invoice,delete_invoice --server odoo

The allowed / not allowed split is a guess from the names. Check it, and fill in each TODO.

### Turn on the continuous loop

    python quickstart.py "path\to\your-agent" --auto

This accepts the drafted tests, writes a placeholder `rules.json`, installs the session-end hook, schedules a daily run, and turns auto-apply on with a spending cap per run (quickstart uses $3 by default; change it with `--cap`). It shows exactly what it will do and asks first (`--yes` skips the question). Every safety gate stays in force: a fix is applied only if the holdout score, the repeated confirmation runs, the judge-agreement check and `rules.json` all allow it. Every applied fix is backed up, and `python evolver.py undo` reverses it. See "Auto integration" below for the details.
### Turn it off

    python quickstart.py "path\to\your-agent" --propose-only
    python quickstart.py "path\to\your-agent" --off

`--propose-only` keeps the loop running but never applies a fix on its own. `--off` turns off auto-apply, the daily schedule and the session-end hook. Neither deletes saved conversations (`.evolver/inbox/`) or undoes fixes that were already applied.

### Read this before trusting `--auto`

- The tests decide every result. `init` drafts them with Claude from `CLAUDE.md` alone, and they may be wrong. Before the loop runs on a real agent, review `.evolver/context.md` and `.evolver/tests.json`: delete the DRAFT line and keep only the list.
- `--auto` accepts the drafted tests without review and writes a one-line placeholder `rules.json`, so one command sets everything up. A loop that applies fixes against unreviewed tests can move the agent toward the wrong goal. To review first, add `--review-first`. To keep it from applying anything on its own, add `--propose-only`.
- A daily run can spend up to the cap every day, for each agent.
- The hook saves real conversations to `.evolver/inbox/`. It is git-ignored: keep it private.
- Tested so far on Windows, on the examples and on one real agent. A scheduled run firing on its own and applying a fix has not been seen yet.
### Slash commands in Claude Code (optional)

If you work in Claude Code, start it in this folder (`claude`). The commands in `.claude/commands/` appear when you type `/evolver`:

| Command | What it does | Cost |
|---|---|---|
| `/evolver-help` | Lists the commands | free |
| `/evolver-check` | Runs the self-test | free |
| `/evolver-setup <agent folder>` | Same as `quickstart.py`: checks your setup and drafts starter tests | a little Claude plan |
| `/evolver-report <agent folder>` | Shows saved results | free |
| `/evolver-status <agent folder>` | Shows whether the loop is on, and what it has done | free |
| `/evolver-run <agent folder>` | Finds failures and proposes one fix (review mode) | about $0.5 to $2 |
| `/evolver-apply <run folder>` | Applies a proposed fix after you say yes (a backup is kept) | free |
| `/evolver-undo <agent folder>` | Reverses the last change that auto-apply made | free |
| `/evolver-off <agent folder>` | Turns the continuous loop off | free |

- Keep Claude Code in manual mode, so it asks before each command. Commands that spend plan usage or change files wait for an explicit "yes" in the chat.
- `/evolver-run` refuses when the agent has a `rules.json` and auto-apply is on, because that run could change the agent on its own.
- Turning the continuous loop on (`quickstart.py --auto`) stays in a normal terminal. It asks for consent and installs a hook and a scheduled task.
- Status: all nine commands have been tried in a real session, on throwaway agents. `/evolver-apply` should print `Applied.`; if it does not, nothing was written. `/evolver-undo` only reverses a change that auto-apply made.

## Use it on your own agent

1. **Set up:** `python evolver.py init "path/to/your-agent"`
   This finds your harness files and uses Claude to **draft** `.evolver/context.md` and `.evolver/tests.json`.
2. **Review the drafts (important).** The results are only as good as your tests.
   - `context.md`: what the agent does, who uses it, what good looks like, and a `## Protected rules` list.
     Delete the `DRAFT` line when done.
   - `tests.json`: 6 to 12 realistic requests with checks. Replace the draft wrapper with just the list.
3. **Run:** `python evolver.py run "path/to/your-agent"`, then approve or reject each change.
   Or `run --auto --yes`: no questions during the run. The result waits in `proposed.patch`, and nothing in your
   agent changes until you run `apply`. Useful for starting runs from a schedule.
4. **Apply (optional):** read `.evolver/runs/<time>/proposed.patch`, then
   `python evolver.py apply "path/to/your-agent/.evolver/runs/<time>"`
5. Add `.evolver/runs/` and `.evolver/backups/` to your `.gitignore`.

### Any agent, not only Claude Code (your own files and your own runner)

Many agents (for example custom apps) keep their instructions in their own files and run through their own code.
Tell the tool both in `.evolver/config.json`:
```json
{"harness_files": ["prompts/*.md"],
 "runner": {"command": ["{python}", "run_agent.py", "--json"]}}
```
- `harness_files`: the instruction files the tool may edit. Only text files (.md, .txt, .prompt, .yaml),
  never code or settings.
- `runner`: the command that runs your agent on one message, inside a test copy of the folder. The message goes
  in on stdin (or replaces `{input}`); `{python}` means the Python running the tool. It prints the answer, or JSON
  with `"result"` and optionally `"total_cost_usd"`. Your runner must never take real actions (sending messages,
  writing to databases); the tool cannot block that for you.
- See `checks/fixtures/examples/lesson-planning-assistant` for a working example.

### Continual mode: learn from real conversations (optional)

Instead of only using test cases you write, the tool can learn from how people really use your agent:

1. **Collect:** `python evolver.py install-hook "path/to/your-agent"`
   Adds one small `SessionEnd` hook to `.claude/settings.local.json` (your personal settings, not shared).
   When a session ends, it copies the conversation into `.evolver/inbox/` on your computer.
   It never calls an AI, never edits your harness, and does nothing inside the tool's own test sessions.
2. **Mine:** `python evolver.py mine "path/to/your-agent"`
   Looks for moments where a user corrected the agent ("too long", "that's wrong") and drafts test cases from them.
   Emails, phone and ID numbers, and keys are hidden before sending. Cases whose request is not really in the
   conversation are dropped. **You approve each case** before it is added to `tests.json`.
3. **Run:** `python evolver.py run "path/to/your-agent" --auto --yes` (for example once a day), then review
   `proposed.patch` and `apply` when you agree.

The hook only collects. Every fix is still tested, and you still make the final decision.
`.evolver/inbox/` contains real conversations: it is in `.gitignore`, keep it private.

### Agents with tools: fake tools (optional)

Real tools would take real actions during tests (dozens of times per run), so they are always blocked.
Instead, describe **fake versions** of your agent's tools in `.evolver/mock_tools.json`. They have the same names
as the real ones but return pretend data, and every call is recorded:

```json
{"server": "odoo",
 "allowed": ["find_invoice"],
 "tools": [
   {"name": "find_invoice", "description": "Find an invoice by number.",
    "input_schema": {"type": "object", "properties": {"number": {"type": "string"}}},
    "returns": "Invoice 104: Rs 25,000, UNPAID"},
   {"name": "delete_invoice", "description": "Delete an invoice.", "returns": "Invoice deleted."}]}
```
- `server` should match your real MCP server's name, so tool names in your instructions still match.
- Only tools in `allowed` can run. Anything else is blocked by Claude Code, and the attempt is recorded.
- Define risky tools (for example a delete) but leave them out of `allowed`: a call is blocked, recorded, and counts as a failure.
- A test with tool checks and no `mock_tools.json` stops the tool with an error.
- A test case can override answers: `"mock_returns": {"find_invoice": "Invoice 210: PAID"}`.
- New checks: `"must_call_tool": ["find_invoice"]`, `"must_not_call_tool": ["delete_invoice"]` and
  `"max_tool_attempts": {"delete_invoice": 1}`
  (a blocked attempt also counts as "called").
- Real MCP servers are not loaded during tests; only the fake server runs. Some Claude Code versions ignore the switch that turns real tools off (`--strict-mcp-config`): check your version before the first run on an agent with live tools.
- Fake tools return pretend data: logins, real error responses and wrong arguments are not tested.
- Fake tools only work with Claude Code agents, not with a custom runner command.
- Writing `mock_tools.json` by hand is the main setup work. `quickstart.py --tools a,b --server NAME` drafts it: check the allowed / not allowed split and fill in the TODOs.

### Keeping runs cheap

- Before every run the tool prints an estimated cost in dollars, based on this agent's earlier runs (or, when
  there are none, the range seen in our own test runs). The spending cap is the most a run can spend, and one
  close-call re-test is priced separately.
- The judge, fixer and safety review run with a tiny system prompt (`--system-prompt`), so they don't carry Claude
  Code's large built-in prompt on every call. The agent under test keeps its real prompt.
- All rubric questions for one answer are graded in **one** judge call.
- `"repeats": 1` (default) while exploring fixes. With auto-apply on, the final version is confirmed once with 3 runs
  per test before anything is applied.
- `"cleanup": false` (default): merging repeated instructions costs one more full measurement, so it is opt-in.
- `"max_run_cost_usd": 1.0` (default): the run stops safely when this is reached. If the cap stops the 3-run
  confirmation, nothing is auto-applied.
- Turn simple yes/no questions into free rule checks where you can (`must_not_include`, `max_words`).

### Auto integration: auto-apply (on by default) and a daily schedule

A verified fix is written into the agent automatically, but **only if every safety condition holds**
(set `"auto_apply": false` in `.evolver/config.json` to keep suggest-and-approve instead):
- `.evolver/rules.json` exists, so every answer was checked against all hard rules
- the final version was confirmed with at least 3 runs per test (done automatically, even if you explore with 1)
- at least 85% of holdout runs passed (`auto_apply_min_holdout`)
- no test call failed with an error, and the total change is small
- nobody edited the agent's files while the run was going
- if tests use a judge and you have labelled at least 5 of its decisions (`python evolver.py label`), the judge
  must agree with your labels at least 80% of the time (only labels on the current judge questions count).
  With fewer labels, auto-apply still works but warns that the judge was never checked.

When it applies, it makes a backup, writes a note to `.evolver/notifications/` (what changed, scores, how to undo)
and prints it. To reverse it: `python evolver.py undo "path/to/agent"` (refuses if the file was edited since).
If any condition fails, nothing is applied: the run lists the reasons and the fix waits for `apply`, as usual.

**Run it by itself every day:** `python evolver.py schedule "path/to/agent" --time 09:00`
creates a daily Windows Task Scheduler task (on Mac/Linux it prints a cron line). Each day it tests the agent,
proposes a fix, tests it on hidden cases and applies it only if every condition holds. Output goes to
`.evolver/scheduled-runs.log`, applied changes are described in `.evolver/notifications/`.
Remove it with `python evolver.py schedule "path/to/agent" --remove`. Scheduled runs use whatever Claude login the
computer has; if an `ANTHROPIC_API_KEY` is saved on the computer, they bill that key (the command warns you).

### AI answers vary: repeats, pass-rate threshold, and the results database

- `"repeats": 3` runs every test 3 times.
- Without a threshold, a test that passes only some runs is "flaky" and the tool does not try to fix it.
- With `"min_pass_rate": 0.85` in `.evolver/config.json`, a test must pass at least 85% of its runs,
  otherwise it counts as failing and the tool works on it. Each measurement also shows whether the bar is met.
- After each measurement, every failing or flaky test is listed with how many runs passed and which rule broke.
- **Every run of every test is saved** in `.evolver/evals.db` (SQLite, one file): the answer, pass/fail,
  broken rules and tool calls. `python evolver.py report "path/to/agent"` shows each run's scores and cost,
  and the pass rate per test. The database holds real answers: it is in `.gitignore`, keep it private.

### Labels, and checking the judge with your own labels

A test can ask the judge to pick **one label** instead of yes/no, with partial credit:
```json
"label": {"question": "Is the reply relevant to the request?",
          "labels": ["relevant", "ambiguous", "not relevant"],
          "pass": ["relevant"], "partial": {"ambiguous": 0.5}}
```
Every judge decision (yes/no answers and chosen labels) is saved in `.evolver/evals.db`.

**Is the judge right?** `python evolver.py label "path/to/agent"` shows saved answers one by one; you give your own
yes/no or label. It then says how often the judge agrees with you (and where it doesn't). `report` shows the same
"JUDGE CHECK" number. Below about 80% agreement, the judge questions are probably unclear: rewrite them.

### Rules for every answer (`.evolver/rules.json`, optional)

Checks in this file apply to **every** test answer, not just one case, so a fix that improves one behaviour
cannot quietly break another rule:
```json
{"checks": {"must_not_include": ["\u2014", "crew_draft", "crew_dispatch"],
            "max_tool_attempts": {"*": 6},
            "rubric": ["Talks to the user directly as 'you', with no internal notes"]}}
```
`max_tool_attempts` limits how often the agent may try a tool (blocked attempts count), e.g. to catch an agent
retrying a refused command dozens of times. `"*"` means all tools together.

### Use with harness-evolve (an eval-gated skill)

`harness-evolve` has the stronger gate (drift checks, risk tiers, signed verdicts) but needs behavioural eval tasks.
This tool can supply them, safely:
```
python evolver.py export-evals "path/to/agent" --to "path/to/agent/.harness-evolve/evals"
```
Each exported task runs one test through `python evolver.py probe` (isolated copy, fake tools, risky tools blocked)
and passes when the output starts with `PROBE PASS`. harness-evolve runs tasks with a POSIX shell, so on Windows
use Git Bash or WSL.

### Test case format

```json
{"id": "plan_1", "split": "train", "input": "the user's message",
 "checks": {"max_words": 120,
            "must_include": ["Subject:"],
            "must_not_include": ["projector"],
            "rubric": ["A yes/no quality question, answered by a judge model"]}}
```
- `input` can also be a conversation: `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]`
- `split` is optional (`train` or `holdout`). Without it, about 30% of cases become holdout.
- `source` (optional) groups cases from the same conversation, so they never land in both splits.
- `needs_tools: true` skips cases that need real actions (sending email, calling an API).

## Settings (`.evolver/config.json`)

| Setting | Default | Meaning |
|---|---|---|
| `worker_model` | `sonnet` | Model your agent runs on during tests |
| `refiner_model` | `opus` | Model that proposes fixes (few calls, so the strongest model is worth it) |
| `judge_model` | `haiku` | Answers rubric questions and safety reviews |
| `repeats` | `1` | Runs per test case while exploring (more = less noise, more usage). Auto-apply re-confirms the final version with 3 runs |
| `max_rounds` / `attempts_per_round` | `3` / `3` | How long it keeps trying |
| `parallel_calls` | `3` | Claude Code calls at the same time |
| `max_edit_chars` / `max_edit_lines` | `800` / `10` | Size limit of one edit |
| `fixer_file_chars` | `12000` | How much of each harness file the fixer is shown. Raise it for long skill files |
| `fixer_answer_chars` | `1500` | How much of each failing answer the fixer is shown |
| `retest_runs` | `3` | Close calls: extra runs of the tests involved, for both versions (0 turns it off) |
| `retest_max_tests` | `4` | Re-test only when at most this many tests are involved |
| `strict_mcp` | `true` | No MCP servers during tests |
| `tool_whitelist` | `true` | Agent may only use Read, Glob, Grep, Skill during tests |
| `allow_subagents` | `false` | Let the agent use (and the tool edit) subagents |
| `locked_parts` | `[]` | Extra files to lock, e.g. `[".claude/skills/billing/SKILL.md"]` |
| `max_run_cost_usd` | `1.0` | Spending cap for one run |
| `cleanup` | `false` | Merge repeated instructions at the end (one more measurement) |
| `auto_apply` | `true` | Apply a verified fix automatically, only when every safety condition holds |

## Known issues found in testing

These came from watching real runs. Please read them before you rely on the tool.

- **Tested on Windows only,** with a handful of Claude Code agents. Other systems and other agent types are untested.
- **The daily task is new and lightly tested.** `quickstart.py --auto` creates it through `scheduled_run.py` (Windows only).
  In testing it started on time with no console window, retried once after a failure, and wrote a `FAILED_<time>.md` note
  in `.evolver/notifications` when it still failed. It is also set to run as soon as possible after a missed start and to
  run on battery, but that catch-up has not been tested.
- **Earlier versions of the schedule had real problems:** one run never started (cause not found), one crashed while
  Claude Code was updating itself and left no failure notice, and a console window popped up. A full real run through the
  new task, with its many Claude Code calls, has not been checked for hidden windows yet.
- **A failed run is retried once,** which can cost the run again. Check `python evolver.py report` now and then.
- **Hooks may run during tests.** The tool copies an agent's settings into its test runs. If the agent's
  `.claude/settings.json` has hooks, remove them in the copy you test.
- **The tests decide every result.** Starter tests are drafted by Claude from `CLAUDE.md` alone, and the judge is a small
  model. The thresholds (85% holdout, 3-run confirmation) are defaults chosen by the author, not measured.
- **Costs are real.** Each run uses your Claude plan (roughly $0.5 to $2 equivalent in our runs). A daily schedule repeats
  that every day.
- **Not compared with other tools yet.**
- **License: not added yet.**

## Feedback

Open a GitHub issue. Please include your Windows and Python versions, the output of `claude --version`, what you ran,
and the SUMMARY block from the end of the run. Do not paste private agent text.

## Known limits (honest)

- **Results depend on your tests.** Few or weak test cases give weak or misleading results.
- **Tool agents need fake tools** (`mock_tools.json`). Fake data can be cleaner than real data, and the real
  connection (logins, Odoo errors) is not tested.
- **Test calls skip your personal plugins and user-level settings on purpose** (`--setting-sources project`). Whether a personal `~/.claude/CLAUDE.md` is also skipped is not verified.
- **`examples/lesson-coach/api_secret.txt` is a planted fake** (the file says so). The tool must never copy it into tests, and the self-test checks that.
- **MCP switch-off may not be perfect:** some users report `--strict-mcp-config` being ignored in some versions.
- **Conversations in tests are replayed as text** in one message, not as a real multi-turn session.
- **The judge is also Claude.** Grading by the same model family can be too generous. Keep rubric questions strict.
- **Usage:** every run executes the evals at least twice (before, and for each fix idea). Heavy use can reach a
  personal Claude limit; the run then stops safely and nothing is applied.
- **If you trigger runs from a hook,** check the environment variable `EVOLVER_RUNNING`: it is `1` inside the tool's
  own test sessions. Skip your hook then, or each test session would start the tool again in a loop.
- Not handled yet: `CLAUDE.md` files in subfolders, extra files inside skill folders, learning from real conversation logs.
