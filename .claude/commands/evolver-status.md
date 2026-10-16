---
description: Show whether the continuous loop is on for an agent, and what it has done (read-only)
argument-hint: <agent folder>
---
Report the Harness Evolver state of this agent: $ARGUMENTS

This is read-only: do not edit, run or install anything except the one schtasks query below. If the arguments are empty, ask for the agent folder and stop. If <folder>\.evolver does not exist, say the agent has not been set up (suggest /evolver-setup) and stop.

Check each item and show the results as a small table (item, state):
1. Auto-apply: read <folder>\.evolver\config.json. "auto_apply" true or missing means ON (the default), false means OFF (propose only). Also report max_run_cost_usd (1.0 if missing).
2. Rules: does <folder>\.evolver\rules.json exist? Auto-apply cannot fire without it.
3. Tests: do context.md and tests.json in <folder>\.evolver still look like drafts (context.md starts with a line beginning DRAFT, or tests.json has a "draft" key)? Does <folder>\.evolver\ACCEPTED_UNREVIEWED_DRAFTS.txt exist?
4. Session-end hook: does <folder>\.claude\settings.local.json contain a SessionEnd entry that mentions evolver_collect.py?
5. Saved conversations: how many files are in <folder>\.evolver\inbox (0 if the folder is missing)?
6. Daily schedule (Windows): run schtasks /Query /TN "HarnessEvolver-<last part of the folder path>". An error saying the file cannot be found means there is no task. If schtasks is not available, say "not checked".
7. Last run and last applied change: the newest folder in <folder>\.evolver\runs, and the newest file in <folder>\.evolver\notifications (say "none" if missing).

Then give ONE verdict line:
- "Loop is ON": the daily schedule exists, auto-apply is on, and rules.json exists.
- "Loop is PROPOSE-ONLY": the daily schedule exists, but auto-apply is off or rules.json is missing.
- "Loop is COLLECTING ONLY": the hook is installed but there is no daily schedule.
- "Loop is OFF": neither the hook nor the schedule is installed.
Add a short reason. If the tests were accepted without review, add a one-line warning that fixes are being judged against unreviewed tests.
