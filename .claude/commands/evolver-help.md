---
description: List the Harness Evolver commands (shows a table, runs nothing)
---
Show this table to the user exactly as written, and run nothing:

| Command | What it does | Cost |
|---|---|---|
| /evolver-help | Show this table | free |
| /evolver-check | Run the tool's own self-test | free, about 2 minutes |
| /evolver-setup <agent folder> | Set up an agent folder: checks your setup and drafts starter tests | a little Claude plan |
| /evolver-report <agent folder> | Show saved results and scores | free |
| /evolver-status <agent folder> | Show whether the continuous loop is on, and what it has done | free |
| /evolver-run <agent folder> | Find failures, propose one fix, test it (review mode) | about $0.5 to $2, several minutes |
| /evolver-apply <run folder> | Apply a proposed fix (a backup is kept) | free |
| /evolver-undo <agent folder> | Reverse the last change that auto-apply made | free |
| /evolver-off <agent folder> | Turn the continuous loop off | free |

Terminal only, because they ask for consent, ask questions, or change the machine:
- python quickstart.py "<agent folder>" --auto   (installs the session-end hook, a daily schedule and auto-apply, after asking)
- python quickstart.py "<agent folder>" --propose-only   (keeps it running but never applies a fix on its own)
- python quickstart.py "<agent folder>" --accept-drafts   (accepts the drafted tests without review: for trying the tool only)
- python evolver.py mine "<agent folder>"   (turns real complaints into tests; you approve each one)

Use a COPY of the agent folder while you learn the tool. These commands work when Claude Code was started in the Harness Evolver folder.
