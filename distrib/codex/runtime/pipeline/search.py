#!/usr/bin/env python3
"""Search verified thesis cards and export dated price levels as JSON."""
import argparse, json, sqlite3
from init_db import ensure_schema

def main():
    p=argparse.ArgumentParser(); p.add_argument("query", nargs="?"); p.add_argument("--db",default="financial_theses.db")
    p.add_argument("--expert"); p.add_argument("--asset"); p.add_argument("--stance"); p.add_argument("--from-date"); p.add_argument("--to-date"); p.add_argument("--levels",action="store_true")
    a=p.parse_args(); filters=[]; vals=[]
    if a.expert: filters.append("e.canonical_name LIKE ?"); vals.append(f"%{a.expert}%")
    if a.asset:
        # Exact identifiers (ticker, ISIN, explicit alias) take precedence over fuzzy names.
        filters.append("(a.id IN (SELECT asset_id FROM asset_identifiers WHERE identifier = ? COLLATE NOCASE) OR a.canonical_name LIKE ? OR a.ticker LIKE ?)")
        vals += [a.asset, f"%{a.asset}%", f"%{a.asset}%"]
    if a.stance: filters.append("t.stance=?"); vals.append(a.stance)
    if a.from_date: filters.append("t.asserted_at>=?"); vals.append(a.from_date)
    if a.to_date: filters.append("t.asserted_at<=?"); vals.append(a.to_date)
    where=" AND ".join(filters) or "1=1"
    if a.query:
        where += " AND t.id IN (SELECT rowid FROM thesis_fts WHERE thesis_fts MATCH ?)"; vals.append(a.query)
    select = "t.id,t.asserted_at,e.canonical_name expert,a.canonical_name asset,a.ticker,t.stance,t.summary,t.quote,s.title,s.url,t.start_sec,t.end_sec"
    sql=f"SELECT {select} FROM theses t JOIN sources s ON s.id=t.source_id LEFT JOIN experts e ON e.id=t.expert_id LEFT JOIN assets a ON a.id=t.asset_id WHERE {where} ORDER BY t.asserted_at DESC"
    ensure_schema(a.db)
    with sqlite3.connect(a.db) as c:
        c.row_factory=sqlite3.Row; rows=[dict(x) for x in c.execute(sql,vals)]
        if a.levels:
            ids=[x["id"] for x in rows]
            levels=[]
            if ids:
                marks=','.join('?' for _ in ids)
                levels=[dict(x) for x in c.execute(f"SELECT thesis_id,level_type,price_low,price_high,currency,effective_at,comment FROM thesis_levels WHERE thesis_id IN ({marks}) ORDER BY effective_at",ids)]
            print(json.dumps({"theses":rows,"levels":levels},ensure_ascii=False)); return
    print(json.dumps({"theses":rows},ensure_ascii=False))
if __name__ == "__main__": main()
