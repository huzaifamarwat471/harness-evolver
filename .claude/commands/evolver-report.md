---
description: Show saved results for an agent (free, read-only)
argument-hint: <agent folder>
---
Show the saved results for this agent: $ARGUMENTS

The current folder must contain evolver.py; if it does not, stop and tell the user to start Claude Code in the Harness Evolver folder. If the arguments are empty, ask for the agent folder and stop.

Run this (folder paths with spaces must be in double quotes):

python evolver.py report $ARGUMENTS

Show the output unchanged, then explain it in 3 short bullets:
- Each run row shows the score before and after (train, then holdout, the cases the fix has not seen).
- The per-test table is the FIRST measurement of the latest run, before any fix, so a FAIL there is the problem the tool found, not the result.
- Run folders are under <agent folder>\.evolver\runs\ and hold the changelog and proposed.patch.

Do not edit any files.
