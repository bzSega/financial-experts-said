#!/usr/bin/env python3
"""Create the local Experts Said SQLite database."""
import argparse
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS experts (
  id INTEGER PRIMARY KEY, canonical_name TEXT NOT NULL UNIQUE,
  aliases_json TEXT NOT NULL DEFAULT '[]', role TEXT, sources_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY, canonical_name TEXT NOT NULL UNIQUE,
  asset_type TEXT NOT NULL CHECK(asset_type IN ('equity','bond','commodity','currency','index','crypto','macro','other')),
  ticker TEXT, aliases_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS assets_ticker_unique ON assets(ticker) WHERE ticker IS NOT NULL;
CREATE TABLE IF NOT EXISTS asset_identifiers (
  asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  identifier TEXT NOT NULL COLLATE NOCASE,
  identifier_type TEXT NOT NULL CHECK(identifier_type IN ('ticker','alias','isin')),
  source TEXT NOT NULL DEFAULT 'source',
  PRIMARY KEY(asset_id, identifier)
);
CREATE INDEX IF NOT EXISTS asset_identifiers_lookup_idx ON asset_identifiers(identifier COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS moex_securities (
  secid TEXT PRIMARY KEY COLLATE NOCASE,
  shortname TEXT,
  name TEXT,
  isin TEXT,
  primary_boardid TEXT,
  group_name TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS moex_securities_isin_idx ON moex_securities(isin);
CREATE TABLE IF NOT EXISTS sources (
  id INTEGER PRIMARY KEY, source_type TEXT NOT NULL CHECK(source_type IN ('podcast','youtube','news','expert_post','telegram','website','messenger','other')),
  title TEXT NOT NULL, url TEXT NOT NULL, published_at TEXT, analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  text_hash TEXT NOT NULL, source_external_id TEXT, is_complete INTEGER NOT NULL DEFAULT 1, missing_fields_json TEXT NOT NULL DEFAULT '[]',
  UNIQUE(source_type, url, text_hash)
);
CREATE TABLE IF NOT EXISTS analysis_runs (
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id), model TEXT NOT NULL CHECK(model IN ('GLM','Terra')),
  prompt_version TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at TEXT,
  validation_result TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS theses (
  id INTEGER PRIMARY KEY, source_id INTEGER NOT NULL REFERENCES sources(id), expert_id INTEGER REFERENCES experts(id),
  asset_id INTEGER REFERENCES assets(id), asserted_at TEXT NOT NULL,
  stance TEXT NOT NULL CHECK(stance IN ('buy','overweight','hold','underweight','sell','watch','neutral','unclear')),
  horizon TEXT, confidence REAL, summary TEXT NOT NULL, quote TEXT NOT NULL,
  start_sec REAL, end_sec REAL, extraction_status TEXT NOT NULL DEFAULT 'verified'
    CHECK(extraction_status IN ('verified','needs_review','unknown','skipped')),
  UNIQUE(source_id, expert_id, asset_id, quote)
);
CREATE TABLE IF NOT EXISTS thesis_levels (
  id INTEGER PRIMARY KEY, thesis_id INTEGER NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
  level_type TEXT NOT NULL CHECK(level_type IN ('entry','target','stop','support','resistance','range')),
  price_low REAL NOT NULL, price_high REAL, currency TEXT NOT NULL,
  effective_at TEXT NOT NULL, comment TEXT
);
CREATE INDEX IF NOT EXISTS thesis_levels_chart_idx ON thesis_levels(effective_at, level_type);
CREATE UNIQUE INDEX IF NOT EXISTS thesis_levels_no_duplicates ON thesis_levels(
  thesis_id, level_type, price_low, COALESCE(price_high, -1), currency, effective_at
);
CREATE TABLE IF NOT EXISTS thesis_tags (
  thesis_id INTEGER NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
  tag TEXT NOT NULL CHECK(tag IN ('valuation','macro','earnings','dividend','technical','risk','other')),
  PRIMARY KEY(thesis_id, tag)
);
CREATE VIRTUAL TABLE IF NOT EXISTS thesis_fts USING fts5(summary, quote, content='');
"""

def ensure_schema(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sources)")}
        if "source_external_id" not in columns:
            conn.execute("ALTER TABLE sources ADD COLUMN source_external_id TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS sources_external_identity_unique ON sources(source_type, source_external_id) WHERE source_external_id IS NOT NULL")
        conn.execute("INSERT OR IGNORE INTO asset_identifiers(asset_id,identifier,identifier_type,source) SELECT id, ticker, 'ticker', 'legacy-assets' FROM assets WHERE ticker IS NOT NULL AND ticker != ''")
    return path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="financial_theses.db")
    args = parser.parse_args()
    path = ensure_schema(args.db)
    print(f"initialized {path}")

if __name__ == "__main__":
    main()
