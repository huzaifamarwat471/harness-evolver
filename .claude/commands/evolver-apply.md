---
description: Apply a proposed fix from a finished run (writes into the agent, with a backup)
argument-hint: <run folder, as printed at the end of a run>
---
Apply the proposed change from this run folder: $ARGUMENTS

1. If the arguments are empty, ask the user for the run folder (it is printed at the end of a run and lives under <agent folder>\.evolver\runs\) and stop.
2. Show the contents of proposed.patch in that folder, unchanged. If it is empty, say "nothing to apply" and stop.
3. Say: "This writes the change into the agent's files. A backup is kept in <agent folder>\.evolver\backups." Ask the user to reply "yes" to apply. Do not continue without an explicit yes.
4. Then pipe a single y into the tool's own confirmation question (PowerShell: "y" | python evolver.py apply "<run folder>"; bash: echo y | python evolver.py apply "<run folder>").
5. Show the output unchanged, and the backup folder it mentions. Say that python evolver.py undo "<agent folder>" reverses a change that auto-apply made, and that after a manual apply the old file is in the backups folder.
