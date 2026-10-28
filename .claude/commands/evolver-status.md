---
description: Show whether the automatic loop is on for an agent and what it has done (free, read-only). For scores of every run, use /evolver-report.
argument-hint: [agent folder]
---
Show the Harness Evolver state of this agent: $ARGUMENTS

Run only the one command below, by itself: no `ls`, no `cd`, no `&&`, nothing before or after it, because anything extra makes Claude Code ask for permission. If the command fails because evolver.py is not found, tell the user to start Claude Code in the Harness Evolver folder.

If the arguments are empty, run exactly this (it reads the folder from the first line of the file .evolver-agent and says which folder it used):

python evolver.py status

Otherwise run this, with the folder path from the arguments inside double quotes (a Windows path with backslashes is only read correctly inside double quotes; forward slashes also work):

python evolver.py status "<folder>"

It is free, read-only and needs no AI. Show its output as it is, then repeat the verdict line (it starts with "Loop is") and, in one short sentence, what the user can do next. If it says the folder has not been set up, suggest /evolver-setup. If it says no agent folder was given, ask the user for the folder. Do not run anything else.
