#!/usr/bin/env python3
"""
scheduled_run.py: the daily job for Harness Evolver, made dependable on Windows.

  python scheduled_run.py install "<agent folder>" [--time 09:00] [--yes] [--print-only]
  python scheduled_run.py remove  "<agent folder>"
  python scheduled_run.py run     "<agent folder>" [--dry]      (this is what the daily task runs)

What it fixes (found by watching real scheduled runs):
  * No console window: the task starts pythonw.exe, and the evolver run is started without a window.
  * One retry: if a run fails (for example Claude Code is updating itself and the program is briefly missing),
    it waits two minutes and tries once more.
  * A failure is never silent: a FAILED_<time>.md note is written to .evolver/notifications.
  * A missed run is caught up: the task is set to start as soon as possible after a missed time.
  * It runs on battery, and a second run cannot start while the first is still going.

The task runs only while you are signed in, and needs no password and no administrator rights.
'install' exits with code 3 if you decline the question, 1 on a problem, 0 when the task was created.
It is created under the same name the older 'evolver.py schedule' used, HarnessEvolver-<agent folder name>,
so 'python evolver.py schedule "<agent folder>" --remove' still removes it.

Use --dry with 'run' (or with 'install') to test the plumbing for free: it runs 'evolver.py --help' instead of a
real run.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCK_SECONDS = 4 * 3600


def stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def task_name(agent):
    return "HarnessEvolver-" + re.sub(r"[^A-Za-z0-9_.-]", "-", Path(agent).name)


def child_python():
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        cand = exe.with_name("python.exe")
        if cand.exists():
            return str(cand)
    return str(exe)


def background_python():
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe":
        cand = exe.with_name("pythonw.exe")
        if cand.exists():
            return str(cand), True
    if exe.name.lower() == "pythonw.exe":
        return str(exe), True
    return str(exe), False


# ---------------------------------------------------------------- run (the daily job)

def tail(path, n):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-n:]


def write_failure(agent, evo, attempts, code, log):
    ndir = evo / "notifications"
    ndir.mkdir(exist_ok=True)
    now = datetime.datetime.now()
    f = ndir / ("FAILED_" + now.strftime("%Y%m%d_%H%M%S") + ".md")
    body = [
        "# Scheduled run FAILED for %s" % Path(agent).name,
        "",
        "- Time: %s" % now.strftime("%Y-%m-%dT%H:%M:%S"),
        "- Attempts: %d" % attempts,
        "- Last result: %s" % (("exit code %s" % code) if isinstance(code, int) else code),
        "- Your agent was not changed by this run.",
        "",
        "What to do: look at `python evolver.py report \"%s\"` and at `.evolver\\scheduled-runs.log`." % agent,
        "A common cause is Claude Code updating itself during the run. The next daily run will try again.",
        "",
        "## Last lines of the log (they may quote your agent's instructions)",
        "",
        "```",
    ] + tail(log, 15) + ["```", ""]
    f.write_text("\n".join(body), encoding="utf-8")
    return f


def run_job(agent, evolver, retries, wait, dry, timeout):
    agent = Path(agent)
    evo = agent / ".evolver"
    if not evo.is_dir():
        print("No .evolver folder in %s" % agent)
        return 2
    log = evo / "scheduled-runs.log"

    def note(msg):
        with open(log, "a", encoding="utf-8") as f:
            f.write("[%s] scheduled_run: %s\n" % (stamp(), msg))

    def status(state, **extra):
        data = {"state": state, "time": stamp()}
        data.update(extra)
        (evo / "last_scheduled_run.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    lock = evo / "scheduled.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime < LOCK_SECONDS:
        note("SKIPPED: a previous run still seems to be going (scheduled.lock is recent)")
        return 0
    lock.write_text(str(os.getpid()), encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    attempts = retries + 1
    code = None
    try:
        for n in range(1, attempts + 1):
            cmd = [child_python(), str(evolver)] + (["--help"] if dry else ["run", str(agent), "--yes", "--auto"])
            note("START attempt %d of %d%s" % (n, attempts, " (dry run)" if dry else ""))
            try:
                with open(log, "ab") as f:
                    r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       creationflags=flags, cwd=str(Path(evolver).resolve().parent), timeout=timeout)
                code = r.returncode
            except subprocess.TimeoutExpired:
                code = "timed out after %d seconds" % timeout
            except OSError as e:
                code = "could not start: %s" % e
            if code == 0:
                note("OK: the run finished (exit code 0)")
                status("ok", attempts=n)
                return 0
            note("FAILED: %s" % (("exit code %s" % code) if isinstance(code, int) else code))
            if n < attempts:
                note("waiting %d seconds, then trying once more" % wait)
                time.sleep(wait)
        f = write_failure(agent, evo, attempts, code, log)
        note("GAVE UP after %d attempt(s). Wrote %s" % (attempts, f.name))
        status("failed", attempts=attempts, last_exit_code=str(code))
        return 1
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- install / remove (Windows task)

def ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def build_install_script(agent, hhmm, evolver, dry=False):
    exe, hidden = background_python()
    h, m = hhmm.split(":")
    args = '"%s" run "%s" --evolver "%s"%s' % (Path(__file__).resolve(), Path(agent).resolve(), Path(evolver).resolve(),
                                              " --dry" if dry else "")
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$action = New-ScheduledTaskAction -Execute %s -Argument %s -WorkingDirectory %s" %
        (ps_quote(exe), ps_quote(args), ps_quote(HERE)),
        "$at = Get-Date -Hour %d -Minute %d -Second 0" % (int(h), int(m)),
        "$trigger = New-ScheduledTaskTrigger -Daily -At $at",
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
        "-StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew",
        "Register-ScheduledTask -TaskName %s -Action $action -Trigger $trigger -Settings $settings "
        "-Description %s -Force | Out-Null" % (ps_quote(task_name(agent)),
                                               ps_quote("Harness Evolver daily run for " + Path(agent).name)),
        "'REGISTERED'",
    ]
    return "\n".join(lines) + "\n", hidden


def run_powershell(script):
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "-"], input=script,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def cmd_install(args):
    agent = Path(args.agent).expanduser().resolve()
    evolver = Path(args.evolver)
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", args.time):
        print("--time must look like 09:00: %r" % args.time)
        return 1
    if not (agent / ".evolver").is_dir():
        print("No .evolver folder in %s. Run quickstart.py first." % agent)
        return 1
    if not evolver.exists():
        print("evolver.py not found at %s" % evolver)
        return 1
    script, hidden = build_install_script(agent, args.time, evolver, args.dry)
    if args.print_only:
        print(script)
        return 0
    if os.name != "nt":
        print("Scheduling with this script works on Windows only for now.")
        return 1
    if args.dry:
        print("FREE TEST TASK: every day at %s this only runs 'evolver.py --help' for %s. It spends nothing and changes nothing." %
              (args.time, agent.name))
    else:
        print("Every day at %s, this runs the full loop on %s by itself:" % (args.time, agent.name))
        print("  test the agent -> propose a fix -> test it on hidden cases -> apply it ONLY if every safety condition holds")
    print("  Task name: %s" % task_name(agent))
    print("  No console window%s. One retry if a run fails. A FAILED note is written if it still fails." %
          ("" if hidden else " (WARNING: pythonw.exe was not found, so a window may appear)"))
    print("  If the computer was off at that time, it runs as soon as possible afterwards.")
    print("  It runs while you are signed in. No password and no administrator rights are needed.")
    print("  Log: %s" % (agent / ".evolver" / "scheduled-runs.log"))
    if not args.yes:
        try:
            ok = input("Create this daily task? [y/N]: ").strip().lower() in ("y", "yes")
        except EOFError:
            ok = False
        if not ok:
            print("Nothing was created.")
            return 3
    r = run_powershell(script)
    if "REGISTERED" not in (r.stdout or ""):
        print("Could not create the task:")
        print((r.stderr or r.stdout or "no output").strip()[:600])
        return 1
    print("Scheduled as Windows task '%s'. To remove it: python evolver.py schedule \"%s\" --remove" %
          (task_name(agent), agent))
    return 0


def cmd_remove(args):
    agent = Path(args.agent).expanduser().resolve()
    if os.name != "nt":
        print("Windows only.")
        return 1
    script = ("try { Unregister-ScheduledTask -TaskName %s -Confirm:$false -ErrorAction Stop; 'REMOVED' } "
              "catch { 'NOT FOUND' }\n" % ps_quote(task_name(agent)))
    r = run_powershell(script)
    print((r.stdout or "").strip() or "no output")
    return 0


def cmd_run(args):
    return run_job(args.agent, args.evolver, args.retries, args.wait, args.dry, args.timeout)


def main():
    ap = argparse.ArgumentParser(description="Dependable daily job for Harness Evolver.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("install", cmd_install), ("remove", cmd_remove), ("run", cmd_run)):
        p = sub.add_parser(name)
        p.add_argument("agent")
        p.add_argument("--evolver", default=str(HERE / "evolver.py"), help="path to evolver.py")
        p.set_defaults(fn=fn)
        if name == "install":
            p.add_argument("--time", default="09:00", help="daily time like 09:00 (default 09:00)")
            p.add_argument("--yes", action="store_true", help="do not ask before creating the task")
            p.add_argument("--print-only", action="store_true", help="show the PowerShell and do nothing")
            p.add_argument("--dry", action="store_true",
                           help="create a FREE test task: it only runs 'evolver.py --help' (no Claude usage, no changes)")
        if name == "run":
            p.add_argument("--dry", action="store_true", help="free plumbing test: runs 'evolver.py --help'")
            p.add_argument("--retries", type=int, default=1, help="extra attempts after a failure (default 1)")
            p.add_argument("--wait", type=int, default=120, help="seconds to wait before a retry (default 120)")
            p.add_argument("--timeout", type=int, default=7200, help="seconds allowed per attempt (default 7200)")
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
