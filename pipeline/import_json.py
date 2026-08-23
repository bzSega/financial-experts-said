#!/usr/bin/env python3
"""Import one already-extracted source. Does not call an LLM."""
import argparse, hashlib, json, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from init_db import ensure_schema

TYPES = {"podcast","youtube","news","expert_post","telegram","website","messenger","other"}
STANCES = {"buy","overweight","hold","underweight","sell","watch","neutral","unclear"}
LEVELS = {"entry","target","stop","support","resistance","range"}
ASSET_TYPES = {"equity","bond","commodity","currency","index","crypto","macro","other"}

def iso(value, field):
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise ValueError(f"{field} must be ISO-8601 date/time")
    return value

def norm_name(name):
    """Canonical form for dedup: trim, collapse whitespace, casefold (Unicode).
    'нефть' == 'Нефть', ' рубль к доллару ' == 'рубль к доллару'."""
    return " ".join((name or "").split()).casefold()

def one_id(conn, table, name, **fields):
    # exact hit first (fast path, preserves stored spelling)
    row = conn.execute(f"SELECT id FROM {table} WHERE canonical_name=?", (name,)).fetchone()
    if row: return row[0]
    # 1) asset_identifiers alias/ticker match (Unicode case-insensitive in Python:
    # SQLite COLLATE NOCASE / LOWER are ASCII-only and miss Cyrillic)
    if table == "assets":
        target_stripped = norm_name(name)
        for aid, ident in conn.execute(
                "SELECT asset_id, identifier FROM asset_identifiers"):
            if norm_name(ident) == target_stripped:
                return aid
    # 2) Unicode case/space-insensitive dedup (SQLite NOCASE/LOWER are ASCII-only!)
    target = norm_name(name)
    for rid, stored in conn.execute(f"SELECT id, canonical_name FROM {table}"):
        if norm_name(stored) == target:
            return rid
    cols = ["canonical_name", *fields]
    marks = ",".join("?" for _ in cols)
    conn.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({marks})", (name, *fields.values()))
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

def ticker_in_source(ticker, text):
    return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])", text, re.IGNORECASE))


def register_asset_identifiers(conn, asset_id, asset):
    """Keep source-provided tickers and aliases searchable without guessing MOEX matches."""
    identifiers = []
    if asset.get("ticker"):
        identifiers.append((asset["ticker"].strip(), "ticker"))
    for alias in asset.get("aliases", []):
        if isinstance(alias, str) and alias.strip():
            identifiers.append((alias.strip(), "alias"))
    for identifier, identifier_type in identifiers:
        conn.execute(
            "INSERT OR IGNORE INTO asset_identifiers(asset_id,identifier,identifier_type,source) VALUES(?,?,?,'source')",
            (asset_id, identifier, identifier_type),
        )

TS_MARK = re.compile(r"\[\d{2}:\d{2}:\d{2}\]")
GT_MARK = re.compile(r"&gt;&gt;|>>")


def normalize_quote(s):
    """Collapse timestamps, speaker marks and whitespace for verbatim comparison."""
    return re.sub(r"\s+", " ", GT_MARK.sub(" ", TS_MARK.sub(" ", s))).strip()


def build_verification_text(extraction):
    """Build a continuous, duplicate-free verification text from caption lines.

    YouTube auto-captions repeat the tail of the previous cue inside the next
    one (rolling duplicates). Word-level suffix/prefix dedup (bounded window)
    removes them so a verbatim quote spanning several cues still matches.
    """
    lines = [l.split("] ", 1)[-1] for l in extraction.splitlines()]
    out_words = []
    for line in lines:
        words = normalize_quote(line).split()
        if not words:
            continue
        overlap = 0
        for size in range(min(len(out_words), len(words), 40), 2, -1):
            if out_words[-size:] == words[:size]:
                overlap = size
                break
        added = words[overlap:]
        if added:
            out_words.extend(added)
    return " ".join(out_words)


def validate(doc):
    missing = [k for k in ("source_type","source_title","source_url","published_at","text") if not doc.get(k)]
    if doc.get("source_type") not in TYPES: raise ValueError("unsupported source_type")
    if not missing: iso(doc["published_at"], "published_at")
    invalid_quotes = []
    for index, t in enumerate(doc.get("theses", [])):
        for field in ("summary","quote","asserted_at","stance"):
            if not t.get(field): raise ValueError(f"thesis missing {field}")
        iso(t["asserted_at"], "asserted_at")
        if t["stance"] not in STANCES: raise ValueError("unsupported stance")
        verification_text = doc.get("quote_verification_text", doc["text"])
        if normalize_quote(t["quote"]) not in normalize_quote(verification_text):
            invalid_quotes.append(index)
        for level in t.get("levels", []):
            if level.get("level_type") not in LEVELS: raise ValueError("unsupported level_type")
            for field in ("price_low","currency","effective_at"):
                if level.get(field) is None: raise ValueError(f"level missing {field}")
            iso(level["effective_at"], "effective_at")
    return missing, invalid_quotes

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path); p.add_argument("--db", default="financial_theses.db")
    p.add_argument("--source", type=Path, help="Authoritative source JSON; restores text for quote validation")
    p.add_argument("--model", choices=("GLM","Terra"), required=True)
    p.add_argument("--prompt-version", default="v1")
    args = p.parse_args(); doc = json.loads(args.input.read_text())
    if args.source:
        source_doc = json.loads(args.source.read_text(encoding="utf-8"))
        doc["text"] = source_doc["text"]
        extraction = source_doc.get("extraction_text", source_doc["text"])
        doc["quote_verification_text"] = build_verification_text(extraction)
    missing, invalid_quotes = validate(doc)
    text_hash = hashlib.sha256(doc["text"].encode()).hexdigest()
    external_id = doc.get("source_external_id")
    ensure_schema(args.db)
    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        cur = conn.execute("INSERT OR IGNORE INTO sources(source_type,title,url,published_at,text_hash,source_external_id,is_complete,missing_fields_json) VALUES(?,?,?,?,?,?,?,?)", (doc["source_type"],doc["source_title"],doc["source_url"],doc.get("published_at"),text_hash,external_id,not bool(missing),json.dumps(missing)))
        if external_id:
            row = conn.execute("SELECT id FROM sources WHERE source_type=? AND source_external_id=?", (doc["source_type"],external_id)).fetchone()
        else:
            row = None
        if row is None:
            # fallback: same source_type + identical URL (external_id conventions drift)
            row = conn.execute("SELECT id FROM sources WHERE source_type=? AND url=?", (doc["source_type"],doc["source_url"])).fetchone()
        source = row[0]
        result = "valid" if not missing and not invalid_quotes else "valid_with_quote_skips" if not missing else "incomplete"
        run = conn.execute("INSERT INTO analysis_runs(source_id,model,prompt_version,completed_at,validation_result) VALUES(?,?,?,?,?)", (source,args.model,args.prompt_version,datetime.now(timezone.utc).isoformat(),result)).lastrowid
        created = skipped = unverified_tickers = 0
        verification_text = doc.get("quote_verification_text", doc["text"])
        for t in doc.get("theses", []):
            if normalize_quote(t["quote"]) not in normalize_quote(verification_text):
                skipped += 1
                continue
            expert_id = one_id(conn,"experts",t["expert"]["name"],aliases_json=json.dumps(t["expert"].get("aliases",[])),role=t["expert"].get("role"),sources_json="[]") if t.get("expert") else None
            asset = dict(t["asset"]) if t.get("asset") else None
            if asset and asset.get("ticker") and not ticker_in_source(asset["ticker"], verification_text):
                # The extractor is not an authority on symbols. MOEX may add a
                # ticker later, but a ticker absent from the source is ignored.
                asset["ticker"] = ""
                unverified_tickers += 1
            asset_id = one_id(conn,"assets",asset["name"],asset_type=asset.get("type","other"),ticker=asset.get("ticker") or None,aliases_json=json.dumps(asset.get("aliases",[]))) if asset else None
            if asset_id:
                register_asset_identifiers(conn, asset_id, asset)
            cur = conn.execute("INSERT OR IGNORE INTO theses(source_id,expert_id,asset_id,asserted_at,stance,horizon,confidence,summary,quote,start_sec,end_sec,extraction_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (source,expert_id,asset_id,t["asserted_at"],t["stance"],t.get("horizon"),t.get("confidence"),t["summary"],t["quote"],t.get("start_sec"),t.get("end_sec"),t.get("extraction_status","verified")))
            thesis = conn.execute("SELECT id FROM theses WHERE source_id=? AND expert_id IS ? AND asset_id IS ? AND quote=?", (source,expert_id,asset_id,t["quote"])).fetchone()[0]
            if cur.rowcount: created += 1; conn.execute("INSERT INTO thesis_fts(rowid,summary,quote) VALUES(?,?,?)", (thesis,t["summary"],t["quote"]))
            for level in t.get("levels",[]): conn.execute("INSERT OR IGNORE INTO thesis_levels(thesis_id,level_type,price_low,price_high,currency,effective_at,comment) VALUES(?,?,?,?,?,?,?)",(thesis,level["level_type"],level["price_low"],level.get("price_high"),level["currency"],level["effective_at"],level.get("comment")))
            for tag in t.get("tags",[]): conn.execute("INSERT OR IGNORE INTO thesis_tags(thesis_id,tag) VALUES(?,?)",(thesis,tag if tag in {"valuation","macro","earnings","dividend","technical","risk","other"} else "other"))
    print(json.dumps({"source_id":source,"analysis_run_id":run,"theses_created":created,"theses_skipped_invalid_quote":skipped,"unverified_model_tickers_ignored":unverified_tickers,"missing_fields":missing}, ensure_ascii=False))

if __name__ == "__main__": main()
