#!/usr/bin/env python3
"""Load the official MOEX ISS securities directory into Experts Said.

No MOEX name is inferred: the script stores ISS fields as received.  Existing
indexed assets are linked only by an exact ticker, ISIN, canonical name or a
previously declared alias; ambiguous names are reported and left unlinked.
"""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from init_db import ensure_schema

ISS_URL = (
    "https://iss.moex.com/iss/securities.json?iss.meta=off&iss.only=securities"
    "&securities.columns=secid,shortname,isin,name,group,primary_boardid"
)


def rows_from_iss(payload):
    table = payload.get("securities", payload)
    columns = table.get("columns", [])
    rows = table.get("data", [])
    return [dict(zip(columns, row)) for row in rows]


def normalized(value):
    return value.strip().casefold() if isinstance(value, str) and value.strip() else None


def load_payload(args):
    if args.input:
        return [json.loads(Path(args.input).read_text(encoding="utf-8"))]
    # ISS returns paginated data (usually 100 rows); walking it is essential
    # for a complete resolver rather than a biased first-page sample.
    payloads, start = [], 0
    while True:
        url = f"{ISS_URL}&start={start}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "financial-experts-said/1.0"})
        with urlopen(request, timeout=args.timeout) as response:
            payload = json.load(response)
        batch = rows_from_iss(payload)
        payloads.append(payload)
        if len(batch) < 100:
            break
        start += len(batch)
    return payloads


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="financial_theses.db")
    p.add_argument("--input", help="saved official ISS JSON; useful for deterministic/offline runs")
    p.add_argument("--timeout", type=int, default=45)
    args = p.parse_args()
    payloads = load_payload(args)
    rows = [row for payload in payloads for row in rows_from_iss(payload) if row.get("secid")]
    ensure_schema(args.db)
    linked = ambiguous = 0
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        for row in rows:
            conn.execute(
                """INSERT INTO moex_securities(secid,shortname,name,isin,primary_boardid,group_name,updated_at)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(secid) DO UPDATE SET shortname=excluded.shortname,name=excluded.name,
                   isin=excluded.isin,primary_boardid=excluded.primary_boardid,group_name=excluded.group_name,
                   updated_at=excluded.updated_at""",
                (row.get("secid"), row.get("shortname"), row.get("name"), row.get("isin"), row.get("primary_boardid"), row.get("group"), now),
            )
        assets = conn.execute("SELECT id,canonical_name,ticker,aliases_json FROM assets").fetchall()
        for asset_id, name, ticker, aliases_json in assets:
            aliases = json.loads(aliases_json or "[]")
            terms = {normalized(name), normalized(ticker), *[normalized(x) for x in aliases]}
            terms.discard(None)
            matches = [row for row in rows if terms.intersection({normalized(row.get("secid")), normalized(row.get("isin")), normalized(row.get("shortname")), normalized(row.get("name"))})]
            if len(matches) == 1:
                match = matches[0]
                # A ticker is adopted only from this one exact ISS match. This
                # makes empty model tickers useful without guessing a symbol.
                if not ticker:
                    conn.execute("UPDATE assets SET ticker=? WHERE id=?", (match.get("secid"), asset_id))
                for value, kind in ((match.get("secid"), "ticker"), (match.get("isin"), "isin"), (match.get("shortname"), "alias"), (match.get("name"), "alias")):
                    if value:
                        conn.execute("INSERT OR IGNORE INTO asset_identifiers(asset_id,identifier,identifier_type,source) VALUES(?,?,?,'moex-iss')", (asset_id, value, kind))
                linked += 1
            elif len(matches) > 1:
                ambiguous += 1
    print(json.dumps({"moex_securities_loaded": len(rows), "assets_linked": linked, "assets_ambiguous": ambiguous}, ensure_ascii=False))


if __name__ == "__main__":
    main()
