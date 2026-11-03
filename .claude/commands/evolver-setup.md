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

Step 1. Look at the folder (free, read-only). Put the folder path inside double quotes (a Windows path with backslashes is only read correctly inside double quotes; forward slashes also work):

python evolver.py detect "<folder>"

Show the output. Then ask the user ONE question: is this a normal Claude Code agent (CLAUDE.md, skills, commands), or their own agent (its own script and prompt files)? If detect already says which, say so and ask them to confirm.

Step 2, own agent only. Ask for: the instruction files the agent reads (confirm the list detect printed), the command that runs the agent on one message (a script that takes the message and prints the answer), and anything else the tool should know about the agent (optional). Then run, with relative paths and forward slashes:

python evolver.py configure "<folder>" --harness-files <files> --runner "<command>" --notes "<notes>"

Leave out --notes if the user has none. If configure stops with an error, show it and ask the user to correct the answer.

Step 3. Run this, with the folder path inside double quotes. Keep any flags from the arguments after the path, unchanged:

python quickstart.py "<folder>" <flags>

Show the output unchanged. Then list the files the user must review (.evolver\context.md and .evolver\tests.json, plus .evolver\mock_tools.json if it was created) and the exact next command it printed. Do not edit any files yourself and do not run evolver.py run.
