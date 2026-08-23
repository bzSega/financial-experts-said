# financial-experts-said: runtime contract, bootstrap, diagnostics

## Path contract

| Variable | Meaning | If missing |
|---|---|---|
| `FES_ROOT` | Runtime directory (`pipeline/`, `chart/`) | bundled: absolute path from plugin root (`runtime/`); skills-only: env var `FES_ROOT` or ask user for the cloned repo path |
| `FES_WORKSPACE` | User working directory | propose a safe directory in the current project; never write inside the plugin |
| `FES_DB` | SQLite database | default `$FES_WORKSPACE/fti.db` |

Always build executable paths from `FES_ROOT`. Never run `python3 pipeline/...`
relative to the current directory.

## Bootstrap (skills-only)

```bash
git clone https://github.com/bzSega/financial-experts-said.git ~/fes
export FES_ROOT=~/fes
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
| `runtime_missing` | no `FES_ROOT` or required scripts — offer bootstrap |
| `dependencies_missing` | python modules missing |
| `database_missing` | offer init/demo seed, only with user consent |
| `source_incomplete` | indexing lacks URL, date or text |
