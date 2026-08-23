---
name: financial-experts-said
description: >
  Index and audit public financial experts' YouTube and Telegram claims:
  extract source-backed verbatim call cards, search a local SQLite history,
  and chart recorded price levels against market prices. Use for indexing a
  supplied source, querying an existing thesis database, or visualizing its
  recorded levels. Requires the financial-experts-said runtime and database;
  never invent quotes, source URLs, dates, or investment conclusions.
---

# financial-experts-said

Runtime + issues + releases: [github.com/bzSega/financial-experts-said](https://github.com/bzSega/financial-experts-said)

Financial experts talk every day. Do you remember a month later who promised IMOEX at 2000 — and whether it happened?

Финансовые эксперты говорят каждый день. А вы помните через месяц, кто обещал IMOEX 2000 — и сбылось ли?

This skill turns expert streams and posts into a verifiable history: every statement → a level on the chart → comparison with the actual price.

## Modes

| User request | Mode | Check first |
|---|---|---|
| "Index this stream/post" | ingestion | transcript/text, URL, date, author; network permission if needed → [references/pipeline.md](references/pipeline.md) |
| "What did X say about Y?" | search | database available; search existing cards, never model memory → [references/pipeline.md](references/pipeline.md) |
| "Chart IMOEX levels" | chart | database has theses/levels; user understands period and asset → [references/chart.md](references/chart.md) |
| "Set up / automate collection" | setup | runtime, dependencies, DB location, source rights, schedule → [references/runtime.md](references/runtime.md) |

## Runtime preflight (before ANY command)

1. Resolve `FES_ROOT` (directory with `pipeline/` and `chart/`):
   - bundled plugin: derive absolute path from this skill's location (plugin root contains `runtime/pipeline`);
   - skills-only: use `FES_ROOT` env var or ask the user for the cloned repo path. Never run `python3 pipeline/...` relative to the current directory.
2. Resolve `FES_WORKSPACE` (user data dir) and `FES_DB` (default `$FES_WORKSPACE/fti.db`). Never write inside the plugin directory.
3. Report one status: `ready` · `runtime_missing` (offer bootstrap: clone repo / see references/runtime.md) · `dependencies_missing` · `database_missing` (offer init or demo seed — only with explicit user consent) · `source_incomplete` (indexing lacks URL/date/text).
4. Do not install dependencies, create the DB, or download sources without user confirmation.

## Data rules (invariant)

- A card contains: expert, asset, stance, date, **verbatim** quote, source URL.
- No URL or date → no import; return as draft with a list of missing fields.
- Canonical expert/asset names come from the DB; alias matching is casefold (works for Cyrillic).
- Telegram `source_external_id` = `telegram:<numerical_channel_id>:<message_id>`.
- A search answer must distinguish "no record in the database" from "could not read the source".
- HTML output escapes DOM insertions, validates embedded JSON, guards `</script>`.

## Financial boundary

This plugin records and compares public statements with prices. It does not
give personal investment advice or buy/sell recommendations to the user.
