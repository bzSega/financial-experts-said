#!/usr/bin/env python3
"""Build distrib/codex and distrib/claude-code from a single source.

Single source of truth: skills/financial-experts-said + pipeline/ + chart/.
Each package gets a bundled runtime copy (runtime/) so the skill can execute
predictably after installation. Fails if a skill references missing files.
"""
import os, re, shutil, sys, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_SKILL = os.path.join(ROOT, "skills", "financial-experts-said")
RUNTIME_DIRS = ["pipeline", "chart"]
RUNTIME_FILES = ["requirements.txt"]
VERSION = "0.1.0"
DESCRIPTION = "Index and audit public financial experts' claims: source-backed verbatim call cards, local SQLite history, charts of recorded levels vs market prices."

BAD = {".git", "__pycache__", ".venv", "venv", "node_modules", ".DS_Store"}
BAD_EXT = (".db", ".log", ".png.tmp", ".html.tmp")
BAD_NAMES = {"fti.db", "financial_theses.db"}

def copy_clean(src, dst):
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in BAD]
        rel = os.path.relpath(dirpath, src)
        for f in filenames:
            if f in BAD_NAMES or f.endswith(BAD_EXT): continue
            s = os.path.join(dirpath, f)
            d = os.path.join(dst, rel if rel != "." else "", f)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)

def check_refs(skill_dir, pkg_root):
    ok = True
    for md in [os.path.join(skill_dir, "SKILL.md")] + [
        os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(skill_dir, "references")) for f in fs
    ]:
        text = open(md, encoding="utf-8").read()
        for ref in re.findall(r"\]\((references/[^)#]+)\)", text):
            if not os.path.exists(os.path.join(skill_dir, ref)):
                print(f"FAIL broken ref {ref} in {md}"); ok = False
    return ok

def build(pkg, manifest_rel, manifest):
    pkg_dir = os.path.join(ROOT, "distrib", pkg)
    if os.path.exists(pkg_dir): shutil.rmtree(pkg_dir)
    skill_dst = os.path.join(pkg_dir, "skills", "financial-experts-said")
    os.makedirs(skill_dst)
    copy_clean(SRC_SKILL, skill_dst)
    for d in RUNTIME_DIRS:
        copy_clean(os.path.join(ROOT, d), os.path.join(pkg_dir, "runtime", d))
    for f in RUNTIME_FILES:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(pkg_dir, "runtime", f))
    mdir = os.path.join(pkg_dir, os.path.dirname(manifest_rel))
    os.makedirs(mdir, exist_ok=True)
    manifest = dict(manifest, version=VERSION, description=DESCRIPTION)
    json.dump(manifest, open(os.path.join(pkg_dir, manifest_rel), "w"), indent=2, ensure_ascii=False)
    if not check_refs(skill_dst, pkg_dir): sys.exit(1)
    n = sum(len(fs) for _, _, fs in os.walk(pkg_dir))
    print(f"built distrib/{pkg}: {n} files")

CLAUDE_MANIFEST = {"name": "financial-experts-said", "author": {"name": "Sergei Mikhailov", "url": "https://github.com/bzSega"}}
CODEX_MANIFEST = {
    "name": "financial-experts-said",
    "author": {"name": "Sergei Mikhailov", "url": "https://github.com/bzSega"},
    "homepage": "https://github.com/bzSega/financial-experts-said",
    "repository": "https://github.com/bzSega/financial-experts-said",
    "license": "MIT",
    "keywords": ["finance", "experts", "expert-calls", "charts", "moex"],
    "skills": "./skills/",
    "interface": {
        "displayName": "Financial Experts Said",
        "shortDescription": "What did financial experts say — and were they right?",
        "longDescription": "Source-backed, local SQLite history of expert claims: extract verbatim call cards from supplied sources, search the local database, chart recorded levels against market prices. Bundled Python runtime included; the plugin does not download or verify sources on its own.",
        "developerName": "Sergei Mikhailov",
        "category": "Productivity",
        "websiteURL": "https://github.com/bzSega/financial-experts-said",
        "defaultPrompt": [
            "Check whether the financial-experts-said runtime and local thesis database are ready.",
            "Index this supplied transcript into source-backed draft call cards; do not import cards missing a source URL or date.",
            "Search the local thesis database for what experts said about gold last month.",
            "Build an interactive chart from recorded IMOEX levels in the local database."
        ]
    }
}

if __name__ == "__main__":
    build("codex", os.path.join(".codex-plugin", "plugin.json"), CODEX_MANIFEST)
    build("claude-code", os.path.join(".claude-plugin", "plugin.json"), CLAUDE_MANIFEST)
    print("OK")
