#!/usr/bin/env python3
"""Self-contained smoke test: init demo DB → seed → search → export levels."""
import json, os, subprocess, sys, tempfile

here = os.path.dirname(os.path.abspath(__file__))

def run(*args):
    p = subprocess.run([sys.executable, *args], cwd=here, check=True, capture_output=True, text=True)
    return p.stdout

with tempfile.TemporaryDirectory() as td:
    db = os.path.join(td, "test.db")
    run(os.path.join(here, "init_db.py"), "--db", db)
    run(os.path.join(here, "seed_demo.py"), "--db", db)
    out = run(os.path.join(here, "search.py"), "--db", db, "--levels")
    data = json.loads(out)
    assert data["theses"], "no theses found"
    assert all(("expert" in r and "asset" in r and "stance" in r and "quote" in r) for r in data["theses"])
    assert any(r["level_type"] == "support" for r in data["levels"]), data["levels"]
    print("ok", len(data["theses"]), "theses,", len(data["levels"]), "levels")
