---
description: Run the improve loop on an agent copy (review mode, uses about $1 to $4 of your Claude plan)
argument-hint: <agent folder>
---
Run Harness Evolver on this agent: $ARGUMENTS

Do these checks first, and stop at the first one that fails:
1. The current folder must contain evolver.py. If the arguments are empty, ask for the agent folder and stop.
2. Read <folder>\.evolver\context.md and <folder>\.evolver\tests.json. If context.md still starts with a line beginning DRAFT, or tests.json is still an object with a "draft" key, stop and tell the user the drafts must be reviewed first (the tool refuses to run on unreviewed drafts).
3. Read <folder>\.evolver\config.json and look for <folder>\.evolver\rules.json. If rules.json exists and "auto_apply" is true or missing, STOP. This run could apply a fix to the agent on its own. Tell the user, and suggest running python quickstart.py "<folder>" --propose-only in a terminal before trying again.
4. Tell the user this run takes several minutes and uses roughly $1 to $4 of their Claude plan, then wait for an explicit "yes" in the chat. Do not continue without it.

Then run:

python evolver.py run "<folder>" --yes --auto

The tool normally asks questions. --yes and --auto make it non-interactive, and after the checks above the result is only proposed, never applied. It takes several minutes: run it in the background if the shell tool offers that, and check on it until it finishes. If it still times out, tell the user to run the same command in a normal terminal.

When it finishes, show the SUMMARY section unchanged, name the run folder, and say the proposed change is in proposed.patch inside it. Do not apply anything: the user decides with /evolver-apply.
