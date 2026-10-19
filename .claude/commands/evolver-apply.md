---
description: Apply a proposed fix from a finished run (writes into the agent, with a backup)
argument-hint: <run folder, as printed at the end of a run>
---
Apply the proposed change from this run folder: $ARGUMENTS

1. If the arguments are empty, ask the user for the run folder (it is printed at the end of a run and lives under <agent folder>\.evolver\runs\) and stop.
2. Show the contents of proposed.patch in that folder, unchanged. If it is empty, say "nothing to apply" and stop.
3. Say: "This writes the change into the agent's files. A backup is kept in <agent folder>\.evolver\backups." Ask the user to reply "yes" to apply. Do not continue without an explicit yes.
4. Then pipe a single y into the tool's own confirmation question, using the Bash form: echo y | python evolver.py apply "<run folder>". Do not use the PowerShell form ("y" | python ...): in testing it printed nothing and applied nothing.
5. Show the output unchanged. The change was applied ONLY if the output contains the word Applied. If it does not, say clearly that nothing was applied and do not claim success. If it was applied, name the backup folder it mentions, and say that python evolver.py undo "<agent folder>" reverses a change that auto-apply made, and that after a manual apply the old file is in the backups folder.
