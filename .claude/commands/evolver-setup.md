---
description: Set up an agent folder. It finds the harness files and drafts tests and context, using a little of your Claude plan. It does not run the loop.
argument-hint: <agent folder> [--tools a,b --server NAME]
---
Set up an agent for Harness Evolver. Arguments: $ARGUMENTS

Rules:
- The current folder must contain quickstart.py and evolver.py. If not, stop and tell the user to start Claude Code in the Harness Evolver folder.
- If the arguments are empty, ask the user for the agent folder and stop.
- If the arguments contain --auto, --accept-drafts, --starter-rules, --off or --yes, stop. Those change settings or the machine and ask questions, so the user must run them in a normal terminal.
- Remind the user in one sentence that this should be a COPY of the agent folder, and that setup uses a little of their Claude plan because Claude drafts the starter tests. Then continue.

Run this, with the folder path inside double quotes (a Windows path with backslashes is only read correctly inside double quotes; forward slashes also work). Keep any flags from the arguments after the path, unchanged:

python quickstart.py "<folder>" <flags>

Show the output unchanged. Then list the files the user must review (.evolver\context.md and .evolver\tests.json, plus .evolver\mock_tools.json if it was created) and the exact next command it printed. Do not edit any files yourself and do not run evolver.py run.
