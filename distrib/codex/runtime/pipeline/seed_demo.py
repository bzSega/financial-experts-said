#!/usr/bin/env python3
"""Seed demo database with sample theses/levels for showcase (IMOEX + Gold, matches README screenshot)."""
import sqlite3, argparse, datetime, hashlib

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    a = p.parse_args()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn = sqlite3.connect(a.db)
    conn.execute("INSERT OR IGNORE INTO experts(canonical_name, role, created_at) VALUES('Demo Expert','аналитик',?)", (now,))
    conn.execute("INSERT OR IGNORE INTO assets(canonical_name, asset_type, ticker, created_at) VALUES('Индекс Мосбиржи','index','IMOEX',?)", (now,))
    src = conn.execute("INSERT INTO sources(source_type,title,url,published_at,analyzed_at,text_hash,is_complete,source_external_id) VALUES('youtube','Demo source','https://example.com/demo',?,?, 'x',1,'demo:1')", (now, now))
    src_id = src.lastrowid
    exp = conn.execute("SELECT id FROM experts WHERE canonical_name='Demo Expert'").fetchone()[0]
    ast = conn.execute("SELECT id FROM assets WHERE canonical_name='Индекс Мосбиржи'").fetchone()[0]
    items = [
        ("watch", "Демо-тезис: эксперт допускает снижение индекса к поддержке 2000 пунктов.", "Демо-цитата 1: дословный фрагмент источника.", ("support", 2000.0, None)),
        ("neutral", "Демо-тезис: нейтральная позиция без уровней.", "Демо-цитата 2: дословный фрагмент источника.", None),
        ("buy", "Демо-тезис: цель 2400 пунктов при улучшении геополитики.", "Демо-цитата 3: дословный фрагмент источника.", ("target", 2400.0, None)),
    ]
    for stance, summary, quote, lvl in items:
        cur = conn.execute("INSERT INTO theses(source_id,expert_id,asset_id,asserted_at,stance,summary,quote,extraction_status) VALUES(?,?,?,?,?,?,?,'verified')", (src_id, exp, ast, now, stance, summary, quote))
        conn.execute("INSERT INTO thesis_fts(rowid,summary,quote) VALUES(?,?,?)", (cur.lastrowid, summary, quote))
        if lvl:
            conn.execute("INSERT INTO thesis_levels(thesis_id,level_type,price_low,price_high,currency,effective_at) VALUES(?,?,?,?,?,?)", (cur.lastrowid, lvl[0], lvl[1], lvl[2], 'points', now))

    # --- Gold demo (matches README screenshot) ---
    conn.execute("INSERT OR IGNORE INTO assets(canonical_name, asset_type, ticker, created_at) VALUES('Золото','commodity','GLDRUB_TOM',?)", (now,))
    gold = conn.execute("SELECT id FROM assets WHERE canonical_name='Золото'").fetchone()[0]
    gsrc = conn.execute("INSERT INTO sources(source_type, title, url, published_at, text_hash) VALUES('youtube','Demo stream','https://example.com/demo-stream',?,?)",
        (now, hashlib.sha256(b'demo-gold').hexdigest())).lastrowid
    d1 = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)).isoformat()
    d2 = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)).isoformat()
    t1 = conn.execute("INSERT INTO theses(source_id,expert_id,asset_id,asserted_at,stance,summary,quote,extraction_status) VALUES(?,?,?,?,?,?,?,'verified')",
        (gsrc, exp, gold, d1, 'buy', 'Золото — убежище, цель 9000 ₽/г', 'золото здесь может отчасти быть убежищем')).lastrowid
    t2 = conn.execute("INSERT INTO theses(source_id,expert_id,asset_id,asserted_at,stance,summary,quote,extraction_status) VALUES(?,?,?,?,?,?,?,'verified')",
        (gsrc, exp, gold, d2, 'watch', 'Диапазон 7800–8200 ₽/г', 'диапазон мы, наверное, можем увидеть')).lastrowid
    conn.execute("INSERT INTO thesis_levels(thesis_id,level_type,price_low,price_high,currency,effective_at) VALUES(?,?,?,?,?,?)", (t1, 'target', 8900.0, 9100.0, 'RUB', d1))
    conn.execute("INSERT INTO thesis_levels(thesis_id,level_type,price_low,price_high,currency,effective_at) VALUES(?,?,?,?,?,?)", (t2, 'range', 7800.0, 8200.0, 'RUB', d2))

    conn.execute("INSERT INTO thesis_fts(rowid,summary,quote) VALUES(?,?,?)", (t1, 'Золото — убежище, цель 9000 ₽/г', 'золото здесь может отчасти быть убежищем'))
    conn.execute("INSERT INTO thesis_fts(rowid,summary,quote) VALUES(?,?,?)", (t2, 'Диапазон 7800–8200 ₽/г', 'диапазон мы, наверное, можем увидеть'))
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM theses").fetchone()[0]
    m = conn.execute("SELECT COUNT(*) FROM thesis_levels").fetchone()[0]
    print(f"seeded: {n} theses, {m} levels in {a.db}")

if __name__ == "__main__":
    main()
