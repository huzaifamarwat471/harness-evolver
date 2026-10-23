---
description: Reverse the last change that auto-apply made, from its backup. Only for auto-applied changes, and it refuses if the file was edited since.
argument-hint: <agent folder>
---
Reverse the last auto-applied change for this agent: $ARGUMENTS

The current folder must contain evolver.py. If the arguments are empty, ask for the agent folder and stop.

Tell the user what undo does, then ask them to reply "yes":
- It restores the files changed by the last auto-apply from the backup.
- It refuses if the file was edited after the auto-apply, so nothing the user wrote is lost.
- It does NOT reverse a manual apply. For that, the old file is in <agent folder>\.evolver\backups and can be copied back by hand.

After an explicit yes, run this, with the folder path inside double quotes (a Windows path with backslashes is only read correctly inside double quotes; forward slashes also work):

python evolver.py undo "<folder>"

Show the output unchanged. If it refuses, explain why in one sentence and do not try to force it.
