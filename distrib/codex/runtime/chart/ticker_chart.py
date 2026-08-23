#!/usr/bin/env python3
"""Chart: asset price (MOEX ISS) + expert levels from Experts Said DB.

Usage:
  python3 ticker_chart.py IMOEX --db fti.db \
      --from 2026-06-01 --out /tmp/openclaw/chart.png --title "IMOEX и уровни экспертов"
"""
import argparse, json, sqlite3, urllib.request
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ISS = ("https://iss.moex.com/iss/history/engines/{engine}/markets/{market}/"
       "securities/{sec}.json?from={frm}&till={till}")

# index vs shares: different ISS engine/market paths
PATHS = {
    "IMOEX": ("stock", "index"),
    "RTSI": ("stock", "rti"),
}

COLORS = {"entry": "tab:green", "target": "tab:blue", "stop": "tab:red",
          "support": "darkgreen", "resistance": "darkred", "range": "tab:orange"}
STYLES = {"Expert A": "-", "Expert B": "--", "Expert C": ":"}

def fetch_history(sec, frm, till):
    engine, market = PATHS.get(sec, ("stock", "shares"))
    url = ISS.format(engine=engine, market=market, sec=sec, frm=frm, till=till)
    data = json.load(urllib.request.urlopen(url, timeout=30))
    cols = data["history"]["columns"]
    dates, closes = [], []
    for row in data["history"]["data"]:
        d = dict(zip(cols, row))
        if d.get("CLOSE") is None:
            continue
        dates.append(datetime.strptime(d["TRADEDATE"], "%Y-%m-%d"))
        closes.append(float(d["CLOSE"]))
    return dates, closes

def fetch_levels(db, asset_name_like):
    sql = """
      SELECT e.canonical_name expert, a.canonical_name asset, t.asserted_at date,
             tl.level_type, tl.price_low, tl.price_high, tl.currency, t.stance
      FROM thesis_levels tl
      JOIN theses t ON t.id = tl.thesis_id
      LEFT JOIN experts e ON e.id = t.expert_id
      LEFT JOIN assets a ON a.id = t.asset_id
      WHERE a.canonical_name LIKE ? AND tl.price_low IS NOT NULL
      ORDER BY t.asserted_at
    """
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, (f"%{asset_name_like}%",))]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("asset", help="MOEX SECID for price, e.g. IMOEX, SBER, LKOH")
    p.add_argument("--asset-name", help="asset name in DB if different from SECID (e.g. 'Индекс Мосбиржи')")
    p.add_argument("--db", required=True)
    p.add_argument("--from", dest="frm", default="2026-01-01")
    p.add_argument("--till", default=datetime.now().strftime("%Y-%m-%d"))
    p.add_argument("--out", required=True)
    p.add_argument("--title", default="")
    a = p.parse_args()

    dates, closes = fetch_history(a.asset, a.frm, a.till)
    if not dates:
        raise SystemExit("no price history from MOEX ISS")

    name = a.asset_name or a.asset
    levels = fetch_levels(a.db, name)

    fig, ax = plt.subplots(figsize=(12, 6.5), dpi=140)
    ax.plot(dates, closes, color="black", lw=1.6, label=f"{a.asset} (MOEX)")

    # per expert: ALL levels from their latest assertion date -> solid; older -> dashed
    latest_date = {}
    for lv in levels:
        expert = lv["expert"] or "эксперт"
        if expert not in latest_date or lv["date"] > latest_date[expert]:
            latest_date[expert] = lv["date"]
    seen = set()
    for lv in levels:
        expert = lv["expert"] or "эксперт"
        for price in filter(None, {lv["price_low"], lv["price_high"]}):
            key = (round(price, 2), expert, lv["level_type"])
            if key in seen:
                continue
            seen.add(key)
            is_latest = latest_date[expert] == lv["date"]
            color = COLORS.get(lv["level_type"], "tab:gray")
            label = (f"{expert.split()[0]} {lv['date'][:10]}: {lv['level_type']} "
                     f"{price:g} {lv['currency'] or ''}".strip())
            ax.axhline(price, color=color, ls="-" if is_latest else "--",
                       lw=1.6 if is_latest else 1.0,
                       alpha=0.95 if is_latest else 0.5)
            ax.annotate(label, xy=(dates[-1], price), fontsize=7.5 if is_latest else 6.5,
                        xytext=(5, 3), textcoords="offset points", color=color,
                        alpha=1.0 if is_latest else 0.6)

    ax.set_title(a.title or f"{a.asset}: уровни экспертов (Experts Said)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(a.out, bbox_inches="tight")
    print(f"wrote {a.out} ({len(closes)} pts, {len(seen)} levels)")

if __name__ == "__main__":
    main()
