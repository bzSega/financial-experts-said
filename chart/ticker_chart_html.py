#!/usr/bin/env python3
"""Interactive HTML (TradingView Lightweight Charts): expert levels from FTI DB.
Candles from MOEX ISS (OHLC), price lines per expert level.
"""
import argparse, json, sqlite3, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ISS = "https://iss.moex.com/iss/history/engines/{e}/markets/{m}/securities/{s}.json?from={f}&till={t}"

PRICE_MAP = {
    "Индекс Мосбиржи": ("IMOEX", "stock", "index"),
    "Фьючерсы на IMOEX": ("IMOEX", "stock", "index"),
    "Индекс РТС": ("RTSI", "stock", "index"),
    "Российский рынок акций": ("IMOEX", "stock", "index"),
    "Российский фондовый рынок": ("IMOEX", "stock", "index"),
    "Доллар США": ("USD000UTSTOM", "currency", "selt"),
    "Доллар США к рублю": ("USD000UTSTOM", "currency", "selt"),
    "Рубль к доллару США": ("USD000UTSTOM", "currency", "selt"),
    "Российский рубль": ("USD000UTSTOM", "currency", "selt"),
    "рубль к доллару США": ("USD000UTSTOM", "currency", "selt"),
    "рубль к евро": ("EUR_RUB__TOM", "currency", "selt"),
    "Китайский юань": ("CNYRUB_TOM", "currency", "selt"),
    "Китайский юань к рублю": ("CNYRUB_TOM", "currency", "selt"),
    "ОФЗ": ("RGBI", "stock", "index"),
    "Длинные ОФЗ": ("RGBI", "stock", "index"),
    "Дальний конец кривой ОФЗ": ("RGBI", "stock", "index"),
    "российский долговой рынок": ("RGBI", "stock", "index"),
    "Золото": ("GLDRUB_TOM", "currency", "selt"),
}

# Verbal asset names -> MOEX futures (Brent etc.)
MOEX_FUT_MAP = {
    "Нефть": ("BRZ6", "futures", "forts"),
    "нефть": ("BRZ6", "futures", "forts"),
    "российская нефть": ("BRZ6", "futures", "forts"),
    "российская нефть в китае": ("BRZ6", "futures", "forts"),
    "бензин в россии": ("BRZ6", "futures", "forts"),
}

# canonical display name for merged verbal assets (all -> "Нефть"); keys lowercase
CANON_DISPLAY = {"нефть": "Нефть", "российская нефть": "Нефть",
                  "российская нефть в китае": "Нефть", "бензин в россии": "Нефть",
                  # рубль без указания валюты = рубль к доллару (конвенция проекта);
                  # евро — всегда отдельный актив
                  "доллар сша": "Рубль к доллару США",
                  "доллар сша к рублю": "Рубль к доллару США",
                  "рубль к доллару сша": "Рубль к доллару США",
                  "российский рубль": "Рубль к доллару США",
                  "рубль к доллару сша ": "Рубль к доллару США",
                  "китайский юань к рублю": "Юань к рублю",
                  "китайский юань": "Юань к рублю"}

GOLD_ASSET = "Золото"
GOLD_RUB_G_OZ = 31.1035  # грамм в тройской унции

# Extra verbal -> MOEX instruments (tickers missing in DB)
EXTRA_MOEX = {"Самолет": ("SMLT", "stock", "shares")}

# Verbal asset names -> Stooq symbols (global instruments MOEX doesn't serve)
COINGECKO_MAP = {"Биткоин": ("bitcoin", "usd")}

STOOQ_MAP = {
    "S&P 500": "^spx",
    "DXY": "dx.f",
    "Биткоин": "btcusd",
    "Moderna": "mrna.us",
    "биотех": "ibb.us",
}


def fetch_coingecko(coin, vs, frm, till):
    """Daily candles (close) from CoinGecko public API for crypto assets."""
    import urllib.request, datetime as dt
    f = int(dt.datetime.fromisoformat(frm).timestamp())
    u = int(dt.datetime.fromisoformat(till + "T23:59:59").timestamp())
    url = (f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart/range"
           f"?vs_currency={vs}&from={f}&to={u}")
    with urllib.request.urlopen(url, timeout=30) as r:
        pts = json.load(r)["prices"]
    out, seen = [], set()
    for ms, px in pts:
        d = dt.datetime.fromtimestamp(ms / 1000).date().isoformat()
        if d not in seen:
            seen.add(d)
            out.append((d, px, px, px, px))
    return out

def fetch_candles(sec, e, m, frm, till):
    """Daily candles from MOEX /candles endpoint (fresh data incl. selt/gold)."""
    url = (f"https://iss.moex.com/iss/engines/{e}/markets/{m}/securities/{sec}/"
           f"candles.json?from={frm}&till={till}&interval=24")
    d = json.load(urllib.request.urlopen(url, timeout=30))
    cols = d["candles"]["columns"]
    out = []
    for row in d["candles"]["data"]:
        r = dict(zip(cols, row))
        c = r.get("close")
        if not c or float(c) == 0:
            continue
        out.append({"time": str(r["begin"])[:10],
                    "open": float(r.get("open") or c), "high": float(r.get("high") or c),
                    "low": float(r.get("low") or c), "close": float(c)})
    return out


def fetch(sec, e, m, frm, till):
    try:
        cd = fetch_candles(sec, e, m, frm, till)
        if cd:
            return cd
    except Exception:
        pass
    url = ISS.format(e=e, m=m, s=sec, f=frm, t=till)
    d = json.load(urllib.request.urlopen(url, timeout=30))
    cols = d["history"]["columns"]
    out = {}
    for row in d["history"]["data"]:
        r = dict(zip(cols, row))
        c = r.get("CLOSE")
        if not c or float(c) == 0:  # zero rows from non-liquid boards (LICU/SPEC)
            continue
        out[r["TRADEDATE"]] = {"time": r["TRADEDATE"],
            "open": float(r.get("OPEN") or c), "high": float(r.get("HIGH") or c),
            "low": float(r.get("LOW") or c), "close": float(c)}
    return [out[k] for k in sorted(out)]

def fetch_stooq(sym, frm, till):
    url = (f"https://stooq.com/q/d/l/?s={sym}&d1={frm.replace('-', '')}"
           f"&d2={till.replace('-', '')}&i=d")
    import csv, io
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    text = urllib.request.urlopen(req, timeout=30).read().decode()
    if not text or text.lstrip().startswith(("No data", "<!DOCTYPE", "<html", "<")):
        raise ValueError("no data")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        out.append({"time": r["Date"], "open": float(r["Open"]), "high": float(r["High"]),
                    "low": float(r["Low"]), "close": float(r["Close"])})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--from", dest="frm", default="2026-01-01")
    p.add_argument("--till", default=datetime.now().strftime("%Y-%m-%d"))
    a = p.parse_args()

    with sqlite3.connect(a.db) as conn:
        conn.row_factory = sqlite3.Row
        assets = [dict(r) for r in conn.execute(
            "SELECT DISTINCT a.id, a.canonical_name name FROM assets a "
            "WHERE a.id IN (SELECT asset_id FROM theses)")]
        ids = [x["id"] for x in assets]
        marks = ",".join("?" * len(ids))
        theses = [dict(r) for r in conn.execute(f"""
          SELECT t.id, t.asset_id, a.canonical_name asset_name, a.ticker,
                 e.canonical_name expert, t.asserted_at date,
                 t.stance, t.summary, t.quote, tl.level_type, tl.price_low,
                 tl.price_high, tl.currency, s.url, t.start_sec
          FROM theses t JOIN sources s ON s.id=t.source_id
          LEFT JOIN experts e ON e.id=t.expert_id
          LEFT JOIN assets a ON a.id=t.asset_id
          LEFT JOIN thesis_levels tl ON tl.thesis_id=t.id
          WHERE t.asset_id IN ({marks}) ORDER BY t.asserted_at""", ids)]
        tick = [dict(r) for r in conn.execute(
            "SELECT DISTINCT a.canonical_name name, a.ticker FROM assets a "
            "WHERE a.ticker IS NOT NULL AND a.id IN (SELECT asset_id FROM theses)")]

    prices = {}
    names = set(x["name"] for x in assets)
    lower = {n.lower(): n for n in names}
    def canon(name):  # case-insensitive merge: "нефть" == "Нефть"
        base = lower.get(name.lower(), name)
        return CANON_DISPLAY.get(base.lower(), base)
    for name in names:
        cn = canon(name)
        if name in PRICE_MAP:
            sec, e, m = PRICE_MAP[name]
            try:
                prices[cn] = prices.get(cn) or fetch(sec, e, m, a.frm, a.till)
            except Exception as ex:
                print("price fail", name, ex)
    for t in tick:
        cn = canon(t["name"])
        if cn in prices:
            continue
        try:
            series = fetch(t["ticker"], "stock", "shares", a.frm, a.till)
            if series:
                prices[cn] = series
                print("price ok", t["name"], t["ticker"], len(series))
            else:
                print("price empty (no candles)", t["name"], t["ticker"])
        except Exception as ex:
            print("price fail", t["name"], t["ticker"], ex)
    # MOEX futures (Brent)
    for name, (sec, e, m) in MOEX_FUT_MAP.items():
        cn = canon(name)
        if cn in prices:
            continue
        try:
            prices[cn] = fetch(sec, e, m, a.frm, a.till)
            print("price ok (fut)", cn, sec, len(prices[cn]))
        except Exception as ex:
            print("price fail (fut)", cn, sec, ex)
    # Extra MOEX instruments for verbal assets without ticker in DB
    for name, (sec, e, m) in EXTRA_MOEX.items():
        cn = canon(name)
        if cn in prices:
            continue
        try:
            prices[cn] = fetch(sec, e, m, a.frm, a.till)
            print("price ok (extra)", cn, sec, len(prices[cn]))
        except Exception as ex:
            print("price fail (extra)", cn, sec, ex)
    # normalize thesis asset names to canonical (merged) spelling
    for t in theses:
        t["asset_name"] = canon(t["asset_name"])
    data_assets = sorted(set(t["asset_name"] for t in theses))

    # crypto via CoinGecko (public, daily closes)
    for name, (coin, vs) in COINGECKO_MAP.items():
        cn = canon(name)
        if cn in names and cn not in prices:
            try:
                prices[cn] = fetch_coingecko(coin, vs, a.frm, a.till)
                print("price ok (coingecko)", cn, coin, len(prices[cn]))
            except Exception as ex:
                print("price fail (coingecko)", cn, coin, ex)
    # fallback: Stooq for global/verbal assets (S&P, DXY, US stocks)
    for name, sym in STOOQ_MAP.items():
        cn = canon(name)
        if cn in names and cn not in prices:
            try:
                prices[cn] = fetch_stooq(sym, a.frm, a.till)
                print("price ok (stooq)", cn, sym, len(prices[cn]))
            except Exception as ex:
                print("price fail (stooq)", cn, sym, ex)

    data = {"assets": data_assets, "prices": prices,
            "theses": theses,
            "generated": datetime.now(timezone.utc).isoformat()}
    # Gold fix: expert levels in USD/oz, chart price in RUB/gram -> convert levels.
    # XAU RUB/g = USD/oz / 31.1035 * USDRUB. Heuristic: level < 10000 == USD/oz
    usd = [c["close"] for c in prices.get("Рубль к доллару США", []) if c["close"]]
    if usd:
        rate = usd[-1]
        for t in theses:
            if (t["asset_name"] == GOLD_ASSET and t["price_low"] is not None
                    and t["price_low"] < 10000):
                k = rate / GOLD_RUB_G_OZ
                t["price_low"] = round(t["price_low"] * k, 0)
                if t["price_high"]:
                    t["price_high"] = round(t["price_high"] * k, 0)
                t["currency"] = "RUB/г (пересчёт из $/oz)"
    html = Path(__file__).with_name("template.html").read_text(encoding="utf-8")
    # guard against '</script>' inside quotes breaking the page
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("__DATA__", payload)
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"wrote {a.out} ({len(assets)} assets, {len(theses)} rows, "
          f"{sum(len(v) for v in prices.values())} candles)")

if __name__ == "__main__":
    main()
