#!/usr/bin/env python3
"""
py_compile_check.py: a Claude Code PostToolUse hook for this repo.

After Claude edits or writes a .py file, this checks that the file still parses. If it does not, it prints the
problem to stderr and exits with code 2, which shows the message to Claude so it can fix the file.
It only reads the file: it writes nothing and cannot undo the edit. It never blocks anything else.

Claude Code sends a JSON object on stdin, with the edited file in tool_input.file_path.
Anything unexpected (no JSON, no path, not a .py file, file gone) exits 0 quietly.
"""
import ast
import json
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    path = ((data or {}).get("tool_input") or {}).get("file_path") or ""
    if not str(path).endswith(".py"):
        return 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            source = f.read()
    except OSError:
        return 0
    try:
        ast.parse(source, filename=path)
    except SyntaxError as e:
        sys.stderr.write("Syntax error in %s, line %s: %s. Please fix it.\n" % (path, e.lineno, e.msg))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
