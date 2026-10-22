#!/usr/bin/env python3
"""
py_compile_check.py: a Claude Code PostToolUse hook for this repo.

After Claude edits or writes a .py file, this checks that the file still parses. If it does not, it prints the
problem to stderr and exits with code 2, which shows the message to Claude so it can fix the file.
It only reads the file: it writes nothing and cannot undo the edit.

Claude Code sends a JSON object on stdin, with the edited file in tool_input.file_path.
The input is read as bytes, so a byte-order mark or UTF-16 text (which some Windows shells produce) still works.
  - nothing on stdin, no path, not a .py file, or the file is gone: exit 0, nothing to check
  - input that cannot be read as JSON: a clear message on stderr and exit 1, so a failure is never silent
  - a syntax error in the edited file: exit 2 with the line number
"""
import ast
import json
import sys


def decode(raw):
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    if b"\x00" in raw:
        return raw.replace(b"\x00", b"").decode("utf-8", "replace")
    return raw.decode("utf-8-sig", "replace")


def main():
    raw = sys.stdin.buffer.read()
    text = decode(raw).strip()
    if not text:
        return 0
    try:
        data = json.loads(text)
    except ValueError:
        sys.stderr.write("py_compile_check: could not read the hook input as JSON, so nothing was checked "
                         "(first bytes: %r)\n" % (raw[:40],))
        return 1
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
