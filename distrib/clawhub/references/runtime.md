# financial-experts-said: runtime contract, bootstrap, diagnostics

## Package type reminder

ClawHub release is skills-only: no Python runtime inside this skill. All commands
run from an external, version-pinned runtime resolved via `FES_ROOT`.

## Path contract

| Variable | Meaning | If missing |
|---|---|---|
| `FES_ROOT` | Runtime directory (`pipeline/`, `chart/`) | use env var `FES_ROOT` or ask user for the cloned repo path; never derive from this skill's location |
| `FES_WORKSPACE` | User working directory | propose a safe directory in the current project; never write inside the runtime |
| `FES_DB` | SQLite database | default `$FES_WORKSPACE/fti.db` |

Always build executable paths from `FES_ROOT`. Never run `python3 pipeline/...`
relative to the current directory.

## Bootstrap (skills-only, version-pinned)

Version contract: **ClawHub skill v0.1.1 → Git tag `openclaw-v0.1.1`** (immutable
commit SHA is listed in the GitHub release notes for that tag). Do not clone `main`.

```bash
git clone --depth 1 --branch openclaw-v0.1.1 \
  https://github.com/bzSega/financial-experts-said.git "$FES_ROOT"
export FES_ROOT="$FES_ROOT"
```

Post-clone verification (required):

```bash
test -f "$FES_ROOT/pipeline/init_db.py" && \
test -f "$FES_ROOT/chart/ticker_chart_html.py" && echo "runtime OK"
```

If either file is missing → status `runtime_missing`; do not proceed.

Optional DB init (only with explicit user consent):

```bash
python3 "$FES_ROOT/pipeline/init_db.py" --db "$FES_WORKSPACE/fti.db"
python3 "$FES_ROOT/pipeline/seed_demo.py" --db "$FES_WORKSPACE/fti.db"   # demo data
```

## Dependencies

Python 3.10+ (stdlib only for the pipeline). Charts need internet:
MOEX ISS API + lightweight-charts CDN (Apache 2.0).

## Diagnostics

| Status | Meaning |
|---|---|
| `ready` | runtime, deps and DB available |
| `runtime_missing` | no `FES_ROOT` or required scripts — offer the pinned bootstrap above |
| `dependencies_missing` | python modules missing |
| `database_missing` | offer init/demo seed, only with user consent |
| `source_incomplete` | indexing lacks URL, date or text |
