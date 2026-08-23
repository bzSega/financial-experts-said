#!/usr/bin/env python3
"""Validate built distributions: manifests, refs, no secrets/db, smoke test on temp DB."""
import json, os, re, subprocess, sys, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL = []

def check(cond, msg):
    print(("OK  " if cond else "FAIL") + " " + msg)
    if not cond: FAIL.append(msg)

for pkg, manifest_rel, name_field in [("codex", ".codex-plugin/plugin.json", "name"), ("claude-code", ".claude-plugin/plugin.json", "name")]:
    p = os.path.join(ROOT, "distrib", pkg)
    check(os.path.isdir(p), f"{pkg}: package exists")
    m = json.load(open(os.path.join(p, manifest_rel)))
    check(m[name_field] == "financial-experts-said", f"{pkg}: name matches dir")
    check(m["version"] == "0.1.1", f"{pkg}: version bumped")
    check(os.path.isdir(os.path.join(p, "skills", "financial-experts-said")), f"{pkg}: skill present")
    check(os.path.isfile(os.path.join(p, "runtime", "pipeline", "init_db.py")), f"{pkg}: bundled runtime present")
    # refs
    skill_dir = os.path.join(p, "skills", "financial-experts-said")
    for md in [os.path.join(skill_dir, "SKILL.md")] + [
        os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(skill_dir, "references")) for f in fs
    ]:
        for ref in re.findall(r"\]\((references/[^)#]+)\)", open(md, encoding="utf-8").read()):
            check(os.path.exists(os.path.join(skill_dir, ref)), f"{pkg}: ref {ref}")
    # no user data
    for dp, _, fs in os.walk(p):
        for f in fs:
            check(not f.endswith((".db", ".log")), f"{pkg}: clean ({f})") if f.endswith((".db", ".log")) else None

# smoke: init -> seed -> search on temp workspace using bundled runtime
rt = os.path.join(ROOT, "distrib", "codex", "runtime")
with tempfile.TemporaryDirectory() as ws:
    db = os.path.join(ws, "fti.db")
    r1 = subprocess.run([sys.executable, os.path.join(rt, "pipeline", "init_db.py"), "--db", db], capture_output=True, text=True)
    check(r1.returncode == 0, "smoke: init_db")
    r2 = subprocess.run([sys.executable, os.path.join(rt, "pipeline", "seed_demo.py"), "--db", db], capture_output=True, text=True)
    check(r2.returncode == 0 and "5 theses" in r2.stdout, f"smoke: seed ({r2.stdout.strip()})")
    r3 = subprocess.run([sys.executable, os.path.join(rt, "pipeline", "search.py"), "золото", "--db", db], capture_output=True, text=True)
    check(r3.returncode == 0 and '"asset": "Золото"' in r3.stdout, "smoke: search finds gold")

sys.exit(1 if FAIL else 0)
