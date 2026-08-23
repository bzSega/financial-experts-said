#!/usr/bin/env python3
"""Export one-row-per-thesis ticker reports as Markdown, CSV, or JSON."""
import argparse
import csv
import io
import json
import sqlite3
from pathlib import Path
from init_db import ensure_schema

COLUMNS = ["ticker", "asset", "expert", "date", "stance", "entry", "target", "stop",
           "horizon", "summary", "quote", "source", "status"]

def fmt_num(value):
    if value is None:
        return ""
    return f"{value:g}"

def fmt_level(row):
    low = fmt_num(row["price_low"])
    high = fmt_num(row["price_high"])
    price = low if not high or high == low else f"{low}–{high}"
    return " ".join(x for x in (price, row["currency"]) if x)

def source_link(url, start_sec):
    if not url:
        return ""
    if start_sec is None:
        return url
    sec = max(0, int(start_sec))
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}t={sec}s"

def fetch_rows(db, args):
    filters, vals = [], []
    if args.source_external_id:
        filters.append("s.source_external_id = ?"); vals.append(args.source_external_id)
    if args.expert:
        filters.append("e.canonical_name LIKE ?"); vals.append(f"%{args.expert}%")
    if args.ticker:
        filters.append("(a.ticker = ? COLLATE NOCASE OR a.id IN (SELECT asset_id FROM asset_identifiers WHERE identifier = ? COLLATE NOCASE))")
        vals.extend([args.ticker, args.ticker])
    if args.stance:
        filters.append("t.stance = ?"); vals.append(args.stance)
    if args.from_date:
        filters.append("t.asserted_at >= ?"); vals.append(args.from_date)
    if args.to_date:
        filters.append("t.asserted_at <= ?"); vals.append(args.to_date)
    if args.status:
        filters.append("t.extraction_status = ?"); vals.append(args.status)
    where = " AND ".join(filters) or "1=1"
    sql = f"""
      SELECT t.id, a.ticker, a.canonical_name asset, e.canonical_name expert,
             t.asserted_at date, t.stance, t.horizon, t.summary, t.quote,
             s.title source_title, s.url, t.start_sec, t.extraction_status status
      FROM theses t
      JOIN sources s ON s.id=t.source_id
      LEFT JOIN experts e ON e.id=t.expert_id
      LEFT JOIN assets a ON a.id=t.asset_id
      WHERE {where}
      ORDER BY t.asserted_at DESC, COALESCE(a.ticker,a.canonical_name), t.id
    """
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        theses = [dict(r) for r in conn.execute(sql, vals)]
        ids = [r["id"] for r in theses]
        by_thesis = {}
        if ids:
            marks = ",".join("?" for _ in ids)
            q = f"""SELECT thesis_id,level_type,price_low,price_high,currency
                    FROM thesis_levels WHERE thesis_id IN ({marks})
                    ORDER BY thesis_id,level_type,price_low"""
            for level in conn.execute(q, ids):
                by_thesis.setdefault(level["thesis_id"], {}).setdefault(level["level_type"], []).append(fmt_level(level))
    out = []
    for t in theses:
        levels = by_thesis.get(t["id"], {})
        out.append({
            "ticker": t["ticker"] or "",
            "asset": t["asset"] or "",
            "expert": t["expert"] or "",
            "date": t["date"],
            "stance": t["stance"],
            "entry": "; ".join(levels.get("entry", [])),
            "target": "; ".join(levels.get("target", [])),
            "stop": "; ".join(levels.get("stop", [])),
            "horizon": t["horizon"] or "",
            "summary": t["summary"],
            "quote": t["quote"],
            "source": source_link(t["url"], t["start_sec"]) or t["source_title"],
            "status": t["status"],
        })
    return out

def md_escape(value):
    return str(value or "").replace("|", "\\|").replace("\n", " ")

def render_markdown(rows):
    headers = ["Тикер", "Актив", "Эксперт", "Дата", "Позиция", "Вход", "Цель", "Стоп",
               "Горизонт", "Обоснование", "Цитата", "Источник", "Статус"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(row[c]) for c in COLUMNS) + " |")
    return "\n".join(lines) + "\n"

def render_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS)
    writer.writeheader(); writer.writerows(rows)
    return buf.getvalue()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="data/financial_theses.db")
    p.add_argument("--source-external-id"); p.add_argument("--expert"); p.add_argument("--ticker")
    p.add_argument("--stance"); p.add_argument("--from-date"); p.add_argument("--to-date"); p.add_argument("--status")
    p.add_argument("--format", choices=("markdown","csv","json"), default="markdown")
    p.add_argument("--output")
    args = p.parse_args()
    ensure_schema(args.db)
    rows = fetch_rows(args.db, args)
    if args.format == "markdown":
        text = render_markdown(rows)
    elif args.format == "csv":
        text = render_csv(rows)
    else:
        text = json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")

if __name__ == "__main__":
    main()
