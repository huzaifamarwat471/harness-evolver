"""
Harness Evolver collector hook (SessionEnd).

When a Claude Code session in this agent's folder ends, copy its conversation file into
.evolver/inbox/ so `python evolver.py mine` can later turn real problems into test cases.

It never calls an AI, never edits any harness file, and does nothing inside the tool's own
test sessions (EVOLVER_RUNNING=1), so it can't start a loop. It must be fast: SessionEnd hooks
get a short time budget.
"""
import json
import os
import shutil
import sys
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024


def main():
    if os.environ.get("EVOLVER_RUNNING") == "1":
        return                                   # one of the tool's own test sessions: do nothing
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    transcript = data.get("transcript_path")
    session_id = "".join(ch for ch in str(data.get("session_id", "session")) if ch.isalnum() or ch in "-_")[:80]
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".")
    inbox = project / ".evolver" / "inbox"
    if not transcript or not (project / ".evolver").is_dir():
        return                                   # not set up for the evolver: do nothing
    src = Path(transcript)
    if not src.is_file() or src.stat().st_size > MAX_BYTES:
        return
    inbox.mkdir(exist_ok=True)
    shutil.copy2(src, inbox / f"{session_id}.jsonl")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass                                     # a collector problem must never disturb the user's session
