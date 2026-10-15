"""
Self-test for evolver.py. Uses a fake Claude, so it costs nothing and needs no login.
Run from the project folder:   python checks/selftest.py
"""
import builtins
import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import evolver as ev

os.environ["EVOLVER_FAKE_CLAUDE"] = str(ROOT / "checks" / "fake_claude.py")
passed = failed = skipped = 0


def skip(name, reason):
    global skipped
    print(f"  SKIP  {name}   ({reason})")
    skipped += 1


def posix_shell():
    """harness-evolve runs eval checks in a POSIX shell. On Windows that means Git Bash (WSL bash cannot run Windows paths)."""
    if os.name != "nt":
        return "/bin/sh"
    for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if os.path.exists(candidate):
            return candidate
    return None


def check(name, ok, detail=""):
    global passed, failed
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail and not ok else ""))
    passed += bool(ok)
    failed += not ok


def fresh_copy(example):
    tmp = Path(tempfile.mkdtemp())
    dst = tmp / example
    # the self-test uses its OWN pristine copy of the examples, so your edits to examples/ never affect it
    shutil.copytree(ROOT / "checks" / "fixtures" / "examples" / example, dst)
    os.environ["EVOLVER_FAKE_STATE"] = str(tmp)
    return dst


def run_quietly(argv, answers=()):
    ev.COST.update(usd=0.0, calls=0)
    ev.LIMIT_HIT["reason"] = None
    answers = list(answers)
    original_input = builtins.input
    builtins.input = lambda prompt="": answers.pop(0) if answers else "n"
    out = io.StringIO()
    try:
        with redirect_stdout(out):
            try:
                ev.main(argv)
            except SystemExit:
                pass
    finally:
        builtins.input = original_input
    return out.getvalue()


print("\n1. Finding the harness")
agent = ev.load_agent(fresh_copy("lesson-coach"))
check("finds CLAUDE.md and the skill", set(agent["parts"]) == {"CLAUDE.md", ".claude/skills/lesson-feedback/SKILL.md"})
check("subagent is locked by default", agent["locked_subagents"] == [".claude/agents/reviewer.md"])
check("settings.json is never editable", ".claude/settings.json" not in agent["parts"])
check("3 protected rules read from context.md", len(agent["protected"]) == 3)
check("tool-only case is skipped, not scored", [c["id"] for c in agent["skipped"]] == ["email_head"])

print("\n2. Safe test workspace")
with tempfile.TemporaryDirectory() as tmp:
    ws, secrets = ev.build_workspace(agent["dir"], agent["parts"], tmp)
    check("secret file is not copied", not (ws / "api_secret.txt").exists() and "api_secret.txt" in secrets)
    check(".evolver (tests and answers) is not copied", not (ws / ".evolver").exists())
    check("harness files are copied", (ws / "CLAUDE.md").exists() and (ws / ".claude/settings.json").exists())

print("\n3. Unsafe edits are refused")
skill = ".claude/skills/lesson-feedback/SKILL.md"
def edit(**kw):
    prop = {"file": skill, "action": "replace", "old_text": "give feedback on it.", "new_text": "give short feedback."}
    prop.update(kw)
    return ev.apply_edit(agent, agent["parts"], prop)
check("normal edit is allowed", edit()[1] is None, edit()[1])
check("locked file refused", "not an editable" in (edit(file=".claude/settings.json")[1] or ""))
check("subagent file refused", "not an editable" in (edit(file=".claude/agents/reviewer.md")[1] or ""))
check("too long refused", "too long" in (edit(new_text="x" * 900)[1] or ""))
check("too many lines refused", "too many lines" in (edit(new_text="a\n" * 12)[1] or ""))
check("copying test content refused", "copies text from a test" in
      (edit(new_text="I explain the method on the board for 20 minutes then students solve")[1] or ""))
check("text not found refused", "found 0 times" in (edit(old_text="not in the file")[1] or ""))
check("breaking frontmatter refused", "frontmatter" in
      (edit(old_text="---\nname: lesson-feedback", new_text="name lesson-feedback")[1] or ""))
check("'./' path is understood", edit(file="./" + skill)[1] is None)

print("\n4. Full run on agent 1 (lesson coach: CLAUDE.md + skill)")
lc = fresh_copy("lesson-coach")
before = (lc / skill).read_text(encoding="utf-8")
out = run_quietly(["run", str(lc), "--yes", "--auto"])
runs = sorted((lc / ".evolver" / "runs").iterdir())
final_skill = (runs[-1] / "final" / skill).read_text(encoding="utf-8")
check("no safety failure inside the fake agent", "SAFETY FAILURE" not in out)
check("locked-file idea was rejected", "not an editable harness file" in out)
check("a fix was accepted", "Accepted as version 1" in out, out[-400:])
check("the skill file was improved in the result", "120 words" in final_skill)
check("the real agent was NOT changed by run", (lc / skill).read_text(encoding="utf-8") == before)
check("patch and changelog written", (runs[-1] / "proposed.patch").read_text().strip() != "" and (runs[-1] / "changelog.md").exists())
check("cost of the run is shown and logged", "Cost of this run: $" in out and "Cost of this run" in (runs[-1] / "changelog.md").read_text())

print("\n5. apply writes the result, with a backup")
out = run_quietly(["apply", str(runs[-1])], answers=["y"])
check("skill file now has the approved change", "120 words" in (lc / skill).read_text(encoding="utf-8"))
backups = list((lc / ".evolver" / "backups").rglob("SKILL.md"))
check("backup of the old file exists", len(backups) == 1 and backups[0].read_text(encoding="utf-8") == before)
out = run_quietly(["apply", str(runs[-1])], answers=["y"])
check("applying twice does nothing", "Nothing to apply" in out)

print("\n6. Full run on agent 2 (email helper: a different kind of agent)")
eh = fresh_copy("email-helper")
before = (eh / "CLAUDE.md").read_text(encoding="utf-8")
out = run_quietly(["run", str(eh), "--yes", "--auto"])
runs = sorted((eh / ".evolver" / "runs").iterdir())
check("a fix was accepted", "Accepted as version 1" in out, out[-400:])
check("CLAUDE.md was improved in the result", "Subject:" in (runs[-1] / "final" / "CLAUDE.md").read_text(encoding="utf-8"))
check("the real agent was NOT changed by run", (eh / "CLAUDE.md").read_text(encoding="utf-8") == before)

print("\n7. Human review: saying no keeps the agent unchanged")
lc2 = fresh_copy("lesson-coach")
out = run_quietly(["run", str(lc2), "--yes"], answers=["n", "n", "n", "n", "n", "n"])
runs = sorted((lc2 / ".evolver" / "runs").iterdir())
check("declined changes are not in the result", (runs[-1] / "proposed.patch").read_text().strip() == "")
check("reviewer decline is logged", "declined by reviewer" in (runs[-1] / "changelog.md").read_text())

print("\n8. Agent with fake tools (finance assistant + fake Odoo)")
fa = fresh_copy("finance-assistant")
agent_fa = ev.load_agent(fa)
check("fake tools loaded from mock_tools.json", agent_fa["mock"]["server"] == "odoo" and agent_fa["mock"]["allowed"] == ["find_invoice"])
before = (fa / "CLAUDE.md").read_text(encoding="utf-8")
out = run_quietly(["run", str(fa), "--yes", "--auto"])
runs = sorted((fa / ".evolver" / "runs").iterdir())
check("no safety failure with fake tools", "SAFETY FAILURE" not in out, out[-300:])
check("look-up cases pass using the fake tool's data", "status_104" not in (runs[-1] / "changelog.md").read_text())
check("blocked delete attempts count as failures, then get fixed", "Accepted as version 1" in out, out[-400:])
check("fix forbids deleting records", "Never delete" in (runs[-1] / "final" / "CLAUDE.md").read_text(encoding="utf-8"))
check("the real agent was NOT changed by run", (fa / "CLAUDE.md").read_text(encoding="utf-8") == before)
res = ev.score_response({"checks": {"must_not_call_tool": ["delete_invoice"]}, "messages": []}, "ok", {},
                        {"called": [], "denied": ["delete_invoice"]})
check("a blocked attempt still fails must_not_call_tool", res[0] < 1)
bad = fresh_copy("lesson-coach")
(bad / ".evolver" / "tests.json").write_text('[{"id":"x","input":"hi","checks":{"must_call_tool":["a"]}}, {"id":"y","split":"holdout","input":"yo","checks":{"max_words":5}}]')
out = run_quietly(["run", str(bad), "--yes"])
check("tool checks without mock_tools.json are refused", "no .evolver/mock_tools.json" in out)

print("\n9. Continual: collector hook + mine")
import json as _json, subprocess as _sp
ag = fresh_copy("lesson-coach")
transcript = ag.parent / "session.jsonl"
transcript.write_text("\n".join(_json.dumps(x) for x in [
    {"type": "user", "message": {"role": "user", "content": "Grade 3 Science, magnets. Students test which objects stick to a magnet. Call me on 03001234567."}},
    {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Here is detailed feedback " * 40}]}},
    {"type": "user", "message": {"role": "user", "content": "Too long, I read on my phone."}},
]), encoding="utf-8")
hook_input = _json.dumps({"session_id": "sess1", "transcript_path": str(transcript), "cwd": str(ag)})
collector = str(ROOT / "evolver_collect.py")
env_test = dict(os.environ, EVOLVER_RUNNING="1", CLAUDE_PROJECT_DIR=str(ag))
_sp.run([sys.executable, collector], input=hook_input, text=True, env=env_test)
check("collector does nothing inside the tool's own test sessions", not (ag / ".evolver" / "inbox" / "sess1.jsonl").exists())
env_real = {k: v for k, v in os.environ.items() if k != "EVOLVER_RUNNING"}
env_real["CLAUDE_PROJECT_DIR"] = str(ag)
_sp.run([sys.executable, collector], input=hook_input, text=True, env=env_real)
check("collector copies a real finished conversation into the inbox", (ag / ".evolver" / "inbox" / "sess1.jsonl").exists())
msgs = ev.read_transcript(ag / ".evolver" / "inbox" / "sess1.jsonl")
check("conversation file is read into user/assistant messages", [m["role"] for m in msgs] == ["user", "assistant", "user"])
check("phone numbers are hidden before sending", "03001234567" not in ev.redact(msgs[0]["content"]))
before_tests = len(_json.loads((ag / ".evolver" / "tests.json").read_text()))
out = run_quietly(["mine", str(ag), "--yes"], answers=["y", "y"])
after = _json.loads((ag / ".evolver" / "tests.json").read_text())
check("a real complaint became one new test case (after you said yes)", len(after) == before_tests + 1, out[-300:])
check("a made-up case was rejected", "made it up" in out)
check("mined case keeps its source conversation for a fair split", after[-1]["source"] == "sess1")
out = run_quietly(["mine", str(ag), "--yes"])
check("already processed conversations are not mined again", "No new conversations" in out)
out = run_quietly(["install-hook", str(ag)], answers=["y"])
settings = _json.loads((ag / ".claude" / "settings.local.json").read_text())
check("install-hook adds one SessionEnd hook in settings.local.json", "evolver_collect.py" in _json.dumps(settings["hooks"]["SessionEnd"]))
run_quietly(["install-hook", str(ag)], answers=["y"])
settings = _json.loads((ag / ".claude" / "settings.local.json").read_text())
check("installing twice does not add it twice", len(settings["hooks"]["SessionEnd"]) == 1)

print("\n10. Global rules, retry limits, probe, export to harness-evolve")
m = ev.merge_checks({"max_words": 120, "must_not_include": ["a"]}, {"max_words": 80, "must_not_include": ["\u2014", "a"]})
check("global rules merge into a case (stricter word limit, combined lists)", m == {"max_words": 80, "must_not_include": ["a", "\u2014"]})
r = ev.score_response({"checks": {"max_tool_attempts": {"delete_invoice": 1}}, "messages": []}, "ok", {},
                      {"called": [], "denied": ["delete_invoice"] * 42})
check("retrying a refused tool 42 times fails max_tool_attempts", r[0] < 1 and "tried 42" in str(r[1]))
rg = fresh_copy("lesson-coach")
(rg / ".evolver" / "rules.json").write_text(_json.dumps({"checks": {"must_not_include": ["\u2014"]}}))
check("rules.json applies to every test case", all("\u2014" in c["checks"]["must_not_include"] for c in ev.load_agent(rg)["all_cases"]))
(rg / ".evolver" / "rules.json").write_text(_json.dumps({"checks": {"expected_number": 4}}))
check("rules.json refuses checks that cannot apply to every case", "cannot apply to every case" in run_quietly(["run", str(rg), "--yes"]))

fp = fresh_copy("finance-assistant")
out = run_quietly(["probe", str(fp), "status_104"])
check("probe prints PROBE PASS for a passing case", out.strip().startswith("PROBE PASS status_104"), out[-200:])
out = run_quietly(["probe", str(fp), "delete_dup"])
check("probe prints PROBE FAIL with the reason for a failing case", out.strip().startswith("PROBE FAIL delete_dup") and "delete_invoice" in out, out[-200:])
evdir = fp.parent / "evolve-repo" / ".harness-evolve" / "evals"
out = run_quietly(["export-evals", str(fp), "--to", str(evdir)])
tasks = sorted(evdir.glob("*.json"))
check("export-evals writes one harness-evolve task per test case", len(tasks) == 6)
t = _json.loads((evdir / "evolver-status_104.json").read_text())
check("exported task has id, cluster, input, run and check", {"id", "cluster", "input", "run", "check"} <= set(t))
# run it exactly like harness-evolve does: shell command in the worktree, output in $HE_OUTPUT, then the check
wt = fp.parent / "worktree-copy"
shutil.copytree(fp, wt, ignore=shutil.ignore_patterns(".evolver"))
sh = posix_shell()
if sh is None:
    for name in ("an exported task passes when run the way harness-evolve runs it",
                 "an exported task fails for an agent that tries to delete"):
        skip(name, "needs Git Bash on Windows, like harness-evolve itself")
else:
    def run_like_harness_evolve(task):
        res = _sp.run([sh, "-c", task["run"]], cwd=wt, capture_output=True, text=True)
        chk = _sp.run([sh, "-c", task["check"]], capture_output=True, text=True, env=dict(os.environ, HE_OUTPUT=res.stdout))
        return res, chk
    res, chk = run_like_harness_evolve(t)
    check("an exported task passes when run the way harness-evolve runs it", chk.returncode == 0, (res.stdout + res.stderr).strip())
    t2 = _json.loads((evdir / "evolver-delete_dup.json").read_text())
    res2, chk2 = run_like_harness_evolve(t2)
    check("an exported task fails for an agent that tries to delete", chk2.returncode != 0)

print("\n11. Pass-rate threshold, results database, report")
check("2 of 3 runs passing is 'flaky' without a threshold", ev.case_status([1, 1, 0.9])[0] == "flaky")
check("2 of 3 runs passing FAILS an 85% threshold (so it gets fixed)", ev.case_status([1, 1, 0.9], 0.85)[0] == "fail")
check("3 of 3 runs passing meets an 85% threshold", ev.case_status([1, 1, 1], 0.85)[0] == "pass")
dbag = fresh_copy("email-helper")
cfgp = dbag / ".evolver" / "config.json"
c = _json.loads(cfgp.read_text()); c.update(min_pass_rate=0.85, repeats=2, max_rounds=1); cfgp.write_text(_json.dumps(c))
out = run_quietly(["run", str(dbag), "--yes", "--auto"])
check("the run names each failing test and the rule it broke", "req_1: 0/2 runs passed | broke: includes 'Subject:'" in out, out[-300:])
import sqlite3 as _sq
con = _sq.connect(str(dbag / ".evolver" / "evals.db"))
n_rows = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
n_runs = con.execute("SELECT COUNT(*) FROM runs WHERE cost_usd IS NOT NULL").fetchone()[0]
con.close()
check("every test run is saved in the results database", n_rows >= 12 and n_runs == 1, f"{n_rows} rows, {n_runs} runs")
rep = run_quietly(["report", str(dbag)])
check("report shows runs and pass rate per test", "RUNS" in rep and "req_1" in rep and "runs passed" in rep, rep[-300:])

print("\n12. Auto-apply (only when every safety condition holds) and undo")
def auto_agent(rules=True, repeats=3):
    a = fresh_copy("lesson-coach")
    cp = a / ".evolver" / "config.json"
    c = _json.loads(cp.read_text()); c.update(auto_apply=True, repeats=repeats, max_rounds=1); cp.write_text(_json.dumps(c))
    if rules:
        (a / ".evolver" / "rules.json").write_text(_json.dumps({"checks": {"must_not_include": ["\u2014"]}}))
    return a
skill_path = ".claude/skills/lesson-feedback/SKILL.md"
aa = auto_agent()
orig = (aa / skill_path).read_text(encoding="utf-8")
out = run_quietly(["run", str(aa), "--yes", "--auto"])
check("verified fix is AUTO-APPLIED when every condition holds", "AUTO-APPLIED" in out, out[-400:])
check("the agent's file now has the fix", "120 words" in (aa / skill_path).read_text(encoding="utf-8"))
check("a backup and a notification were written", bool(list((aa / ".evolver" / "backups").rglob("SKILL.md")))
      and bool(list((aa / ".evolver" / "notifications").glob("*.md"))))
(aa / skill_path).write_text((aa / skill_path).read_text(encoding="utf-8") + "\nowner edit\n", encoding="utf-8")
out = run_quietly(["undo", str(aa)])
check("undo refuses if the owner edited the file after auto-apply", "would lose that work" in out, out[-200:])
(aa / skill_path).write_text((aa / skill_path).read_text(encoding="utf-8").replace("\nowner edit\n", ""), encoding="utf-8")
out = run_quietly(["undo", str(aa)])
check("undo restores the old file", "Undone" in out and (aa / skill_path).read_text(encoding="utf-8") == orig, out[-200:])
check("nothing left to undo afterwards", "no auto-applied change" in run_quietly(["undo", str(aa)]))
nb = auto_agent(rules=False)
before_nb = (nb / skill_path).read_text(encoding="utf-8")
out = run_quietly(["run", str(nb), "--yes", "--auto"])
check("no auto-apply without rules.json (and it says why)", "Auto-apply was NOT done" in out and "rules.json" in out
      and (nb / skill_path).read_text(encoding="utf-8") == before_nb, out[-300:])
nr = auto_agent(repeats=1)
out = run_quietly(["run", str(nr), "--yes", "--auto"])
check("with 1 run while exploring, auto-apply first confirms with 3 runs (never decides on 1 run)",
      "Confirming the final version with 3 runs" in out and "AUTO-APPLIED" in out, out[-300:])
nc = auto_agent(repeats=1)
cp = nc / ".evolver" / "config.json"
c = _json.loads(cp.read_text()); c["max_run_cost_usd"] = 0.25; cp.write_text(_json.dumps(c))
before_nc = (nc / skill_path).read_text(encoding="utf-8")
out = run_quietly(["run", str(nc), "--yes", "--auto"])
check("if the spending cap stops the 3-run confirmation, nothing is auto-applied",
      "AUTO-APPLIED" not in out and (nc / skill_path).read_text(encoding="utf-8") == before_nc, out[-400:])
off = fresh_copy("lesson-coach")
cp = off / ".evolver" / "config.json"
c = _json.loads(cp.read_text()); c["auto_apply"] = False; cp.write_text(_json.dumps(c))
(off / ".evolver" / "rules.json").write_text(_json.dumps({"checks": {"must_not_include": ["\u2014"]}}))
before_off = (off / skill_path).read_text(encoding="utf-8")
run_quietly(["run", str(off), "--yes", "--auto"])
check('"auto_apply": false keeps suggest-and-approve: the agent is not changed', (off / skill_path).read_text(encoding="utf-8") == before_off)
check("auto-apply is ON by default and the default spending cap is $1", ev.DEFAULTS["auto_apply"] is True and ev.DEFAULTS["max_run_cost_usd"] == 1.0)
ed = auto_agent()
ag = ev.load_agent(ed)
original_parts = dict(ag["parts"])
(ed / skill_path).write_text("someone else's edit\n", encoding="utf-8")
fake_current = {"train": {"run_rate": 1.0, "counts": {"error": 0}, "score": 1.0},
                "holdout": {"run_rate": 1.0, "counts": {"error": 0}, "score": 1.0}}
why = ev.auto_apply_blockers(ag, original_parts, dict(original_parts, **{skill_path: "new"}), fake_current)
check("never overwrites a file someone edited during the run", any("edited by someone" in w for w in why))

print("\n13. Cheaper runs: one judge call per answer, explore with 1 run, spending cap")
case = {"checks": {"rubric": ["q one", "q two", "q three"]}, "messages": [{"role": "user", "content": "hi"}]}
before_calls = ev.COST["calls"]
sc, res, err = ev.score_response(case, "short answer", dict(ev.DEFAULTS))
check("3 rubric questions are graded in ONE judge call", ev.COST["calls"] - before_calls == 1 and sc == 1.0, str(res))
ch = fresh_copy("email-helper")
cp = ch / ".evolver" / "config.json"
c = _json.loads(cp.read_text()); c.update(repeats=1, max_rounds=1, auto_apply=True); cp.write_text(_json.dumps(c))
(ch / ".evolver" / "rules.json").write_text(_json.dumps({"checks": {"must_not_include": ["\u2014"]}}))
out = run_quietly(["run", str(ch), "--yes", "--auto"])
check("explores with 1 run, then confirms with 3 runs before auto-apply", "Confirming the final version with 3 runs" in out, out[-400:])
check("the cost line comes AFTER the confirmation runs, so it includes them",
      out.find("Cost of this run") > out.find("Confirming the final version"), out[-400:])
check("helpers use the small system prompt, the agent keeps its real one", "COST FAILURE" not in out and "REALISM FAILURE" not in out)
cap = fresh_copy("email-helper")
cp = cap / ".evolver" / "config.json"
c = _json.loads(cp.read_text()); c.update(repeats=1, max_rounds=3, max_run_cost_usd=0.05); cp.write_text(_json.dumps(c))
ev.COST.update(usd=0.0, calls=0)
out = run_quietly(["run", str(cap), "--yes", "--auto"])
check("the spending cap stops the run safely", "Spending cap reached" in out and "Cost of this run" in out, out[-400:])

lim = fresh_copy("email-helper")
cp = lim / ".evolver" / "config.json"
c = _json.loads(cp.read_text()); c.update(repeats=1, max_rounds=1, auto_apply=True); cp.write_text(_json.dumps(c))
(lim / ".evolver" / "rules.json").write_text(_json.dumps({"checks": {"must_not_include": ["\u2014"]}}))
(lim.parent / "fake_limit_after").write_text("20")
ev.LIMIT_HIT["reason"] = None
before_lim = (lim / "CLAUDE.md").read_text(encoding="utf-8")
out = run_quietly(["run", str(lim), "--yes", "--auto"])
calls_after_limit = ev.COST["calls"]
check("a Claude usage limit stops the run with a clear message", "usage limit reached" in out.lower(), out[-400:])
check("after a usage limit nothing is applied", (lim / "CLAUDE.md").read_text(encoding="utf-8") == before_lim)
# 20 calls were allowed; calls already running in parallel when the limit hit may still finish (Windows timing)
check("after a usage limit no more calls are wasted",
      calls_after_limit <= 20 + ev.DEFAULTS["parallel_calls"] + 2, str(calls_after_limit))
ev.LIMIT_HIT["reason"] = None
(lim.parent / "fake_limit_after").unlink()

print("\n14. Answer labels and checking the judge with your own labels")
lab_def = {"question": "Is the reply relevant to the request?", "labels": ["relevant", "ambiguous", "not relevant"],
           "pass": ["relevant"], "partial": {"ambiguous": 0.5}}
check("label credit: pass = 1, partial = 0.5, other = 0",
      (ev.label_credit(lab_def, "relevant"), ev.label_credit(lab_def, "ambiguous"), ev.label_credit(lab_def, "not relevant")) == (1.0, 0.5, 0.0))
la = fresh_copy("email-helper")
tp = la / ".evolver" / "tests.json"
cases = _json.loads(tp.read_text())
for cs in cases:
    cs["checks"]["label"] = lab_def
tp.write_text(_json.dumps(cases))
cp = la / ".evolver" / "config.json"
c = _json.loads(cp.read_text()); c.update(repeats=1, max_rounds=1, auto_apply=False); cp.write_text(_json.dumps(c))
out = run_quietly(["run", str(la), "--yes", "--auto"])
con = _sq.connect(str(la / ".evolver" / "evals.db"))
judged = [_json.loads(r[0]) for r in con.execute("SELECT judged FROM results WHERE judged IS NOT NULL")]
con.close()
check("every judge decision is saved, including the chosen label",
      any(j.get("label: Is the reply relevant to the request?") == "relevant" for j in judged), str(judged[:2]))
out = run_quietly(["label", str(la), "--limit", "2"], answers=["y", "relevant", "n", "relevant"])
check("label command compares your labels with the judge", "Judge agrees with your labels in 3 of 4 checks (75%)" in out, out[-500:])
check("it lists where you and the judge disagree, and warns when agreement is low", "disagree on" in out and "That is low" in out)
check("report shows the judge check", "JUDGE CHECK" in run_quietly(["report", str(la)]))
bad = fresh_copy("email-helper")
bt = bad / ".evolver" / "tests.json"
bc = _json.loads(bt.read_text()); bc[0]["checks"]["label"] = {"question": "q", "labels": ["a"]}; bt.write_text(_json.dumps(bc))
check("a badly written label check is refused with a clear message", '"label" needs' in run_quietly(["run", str(bad), "--yes"]))

print("\n15. Auto-apply only trusts a judge that agrees with your own labels")
_cur_q = "Starts by naming a specific strength that is actually in this lesson plan"
def judged_auto_agent(labels):
    a = fresh_copy("lesson-coach")             # its tests use a rubric question, so a judge is involved
    cp = a / ".evolver" / "config.json"
    c = _json.loads(cp.read_text()); c.update(auto_apply=True, repeats=3, max_rounds=1); cp.write_text(_json.dumps(c))
    (a / ".evolver" / "rules.json").write_text(_json.dumps({"checks": {"must_not_include": ["\u2014"]}}))
    con = ev.db_connect(a / ".evolver")
    for i, (human, judge) in enumerate(labels):
        con.execute("INSERT INTO human_labels VALUES (?,?,?,?,?,?,?,?)",
                    ("old-run", "v0", f"plan_{i}", 1, "rubric: " + _cur_q, human, judge, "2026-10-07T10:00:00"))
    con.commit(); con.close()
    return a
low = judged_auto_agent([("YES", "YES")] * 5 + [("YES", "NO")] * 2)          # 5 of 7 = 71%
before_low = (low / skill_path).read_text(encoding="utf-8")
out = run_quietly(["run", str(low), "--yes", "--auto"])
check("judge agreeing only 71% with your labels BLOCKS auto-apply",
      "Auto-apply was NOT done" in out and "agrees with your own labels only 71%" in out
      and (low / skill_path).read_text(encoding="utf-8") == before_low, out[-500:])
check("the run header shows the judge check", "Judge check: agrees with your labels 71%" in out)
high = judged_auto_agent([("YES", "YES")] * 9 + [("YES", "NO")])               # 9 of 10 = 90%
out = run_quietly(["run", str(high), "--yes", "--auto"])
check("judge agreeing 90% allows auto-apply", "AUTO-APPLIED" in out and "Warning: the judge has not been checked" not in out, out[-400:])
nolab = judged_auto_agent([])
out = run_quietly(["run", str(nolab), "--yes", "--auto"])
note = sorted((nolab / ".evolver" / "notifications").glob("*.md"))
check("with no labels yet, auto-apply works but WARNS that the judge was never checked",
      "AUTO-APPLIED" in out and "Warning: the judge has not been checked" in out
      and bool(note) and "has not been checked against human labels" in note[-1].read_text(encoding="utf-8"), out[-400:])
few = judged_auto_agent([("YES", "NO")] * 3)                                      # 3 labels: too few to judge
out = run_quietly(["run", str(few), "--yes", "--auto"])
check("fewer than 5 labels: agreement is not used yet (warning instead of blocking)", "AUTO-APPLIED" in out, out[-400:])

stale = judged_auto_agent([])
con = ev.db_connect(stale / ".evolver")
for i in range(7):
    con.execute("INSERT INTO human_labels VALUES (?,?,?,?,?,?,?,?)",
                ("old-run", "v0", f"plan_{i}", 1, "rubric: an OLD question that was rewritten", "YES", "NO", "2026-10-07T10:00:00"))
con.commit(); con.close()
out = run_quietly(["run", str(stale), "--yes", "--auto"])
check("labels on a rewritten (old) judge question don't block auto-apply", "AUTO-APPLIED" in out, out[-400:])

print("\n16. Any agent: your own instruction files and your own runner (custom-runner app)")
os.environ["LP_AGENT_FAKE"] = "1"          # the test agent's free offline mode
lpa = fresh_copy("lesson-planning-assistant")
ag = ev.load_agent(lpa)
check("finds the agent's own prompt files (harness_files)", set(ag["parts"]) == {"prompts/system.md", "prompts/format.md", "prompts/rules.md"})
check("the runner code itself is never editable", "run_agent.py" not in ag["parts"])
before_fmt = (lpa / "prompts" / "format.md").read_text(encoding="utf-8")
out = run_quietly(["run", str(lpa), "--yes", "--auto"])
check("runs the agent through its own command", "Agent runs with YOUR command" in out and "run_agent.py" in out, out[:600])
check("finds the too-long plans and fixes the prompt file", "Accepted as version 1" in out and "prompts/format.md" in out, out[-600:])
runs = sorted((lpa / ".evolver" / "runs").iterdir())
check("the fix is in the prompt file of the result", "under 250 words" in (runs[-1] / "final" / "prompts" / "format.md").read_text(encoding="utf-8"))
check("other planted problems are still reported (no false success)", "Check for understanding" in out)
bad_cfg = fresh_copy("lesson-planning-assistant")
cp = bad_cfg / ".evolver" / "config.json"
c = _json.loads(cp.read_text()); c["harness_files"] = ["prompts/*.md", "run_agent.py"]; cp.write_text(_json.dumps(c))
check("listing a code file as a harness file is refused", "Only instruction text files can be edited" in run_quietly(["run", str(bad_cfg), "--yes"]))
c["harness_files"] = ["prompts/*.md"]; c["runner"] = "python run_agent.py"; cp.write_text(_json.dumps(c))
check("a badly written runner setting is refused with an example", '"runner" must look like' in run_quietly(["run", str(bad_cfg), "--yes"]))
del os.environ["LP_AGENT_FAKE"]

print("\n17. Daily schedule (auto integration)")
sa = fresh_copy("email-helper")
script, logf = ev.write_schedule_script(sa)
body = script.read_text(encoding="utf-8")
check("schedule writes a run script that runs the full loop unattended", "run" in body and "--auto --yes" in body and str(logf) in body)
out = run_quietly(["schedule", str(sa), "--time", "25:99"])
check("schedule refuses a wrong time", "--time must look like 09:00" in out)
out = run_quietly(["schedule", str(sa)], answers=["n"])
check("schedule asks before creating anything, and explains what will run", "Nothing was scheduled" in out and "auto-apply" in out.lower())
check("schedule warns when rules.json is missing (so auto-apply can never happen)", "no .evolver/rules.json" in out)

print("\n18. init on a brand new agent")
tmp = Path(tempfile.mkdtemp()) / "new-agent"
tmp.mkdir()
(tmp / "CLAUDE.md").write_text("You are a helpful assistant.\n", encoding="utf-8")
os.environ["EVOLVER_FAKE_STATE"] = str(tmp.parent)
out = run_quietly(["init", str(tmp)])
check(".evolver created with drafts", (tmp / ".evolver" / "context.md").exists() and (tmp / ".evolver" / "tests.json").exists())
out = run_quietly(["run", str(tmp), "--yes"])
check("run refuses unreviewed drafts", "still a draft" in out)
out = run_quietly(["init", str(tmp)])
check("init never overwrites existing files", "Nothing was overwritten" in out)

print(f"\nResult: {passed} passed, {failed} failed" + (f", {skipped} skipped" if skipped else ""))
sys.exit(1 if failed else 0)
