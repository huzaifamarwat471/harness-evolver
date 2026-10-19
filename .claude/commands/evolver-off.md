---
description: Turn the continuous loop off (auto-apply, daily schedule, session-end hook)
argument-hint: <agent folder>
---
Turn Harness Evolver off for this agent: $ARGUMENTS

The current folder must contain quickstart.py and evolver.py. If the arguments are empty, ask for the agent folder and stop.

Tell the user what will happen, then ask them to reply "yes":
- "auto_apply" is set to false in .evolver\config.json (a copy is kept).
- The daily scheduled task is removed, if there is one.
- Only the tool's own session-end hook is removed from .claude\settings.local.json; other settings stay.
- Saved conversations in .evolver\inbox and fixes that were already applied are NOT touched.

After an explicit yes, run (folder paths with spaces must be in double quotes):

python quickstart.py $ARGUMENTS --off --yes

Show the output unchanged. Then, only if the folder .evolver\inbox exists, remind the user that saved conversations are still there and can be deleted if they are not wanted.
