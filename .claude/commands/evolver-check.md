---
description: Self-test of the tool itself, using a fake Claude (free, about 2 minutes). It does not test any agent.
---
Run this from the current folder. The folder must contain evolver.py; if it does not, stop and tell the user to start Claude Code in the Harness Evolver folder.

python checks\selftest.py

Do not edit any files. Show the last 8 lines of the output unchanged. Then say in one sentence whether it ended with "Result: 116 passed, 0 failed". This check uses a fake Claude, so it costs nothing.
