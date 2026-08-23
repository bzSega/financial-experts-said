#!/usr/bin/env python3
"""Build the strict model prompt for one source; the model call stays outside the importer."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Raw source JSON: source metadata and text, no theses")
    parser.add_argument("--model", choices=("GLM", "Terra"), required=True)
    parser.add_argument("--output", type=Path, help="Write prompt to a UTF-8 file instead of stdout")
    parser.add_argument("--db", type=Path, help="FTI DB: inject canonical asset/expert dictionary to prevent duplicates")
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    required = ("source_type", "source_title", "source_url", "published_at", "text")
    missing = [name for name in required if not source.get(name)]
    if missing:
        raise SystemExit("Cannot build importable extraction: missing " + ", ".join(missing))

    schema = {
        "source_type": source["source_type"],
        "source_title": source["source_title"],
        "source_url": source["source_url"],
        "source_external_id": source.get("source_external_id"),
        "published_at": source["published_at"],
        "text": "<copy the source text exactly>",
        "theses": [{
            "expert": {"name": "", "aliases": [], "role": ""},
            "asset": {"name": "", "type": "equity|bond|commodity|currency|index|crypto|macro|other", "ticker": "", "aliases": []},
            "asserted_at": source["published_at"],
            "stance": "buy|overweight|hold|underweight|sell|watch|neutral|unclear",
            "summary": "neutral, factual summary",
            "quote": "verbatim fragment from source text, WITHOUT [HH:MM:SS] timestamps",
            "start_sec": None,
            "end_sec": None,
            "levels": [{"level_type": "entry|target|stop|support|resistance|range", "price_low": 0, "price_high": None, "currency": "", "effective_at": source["published_at"], "comment": ""}],
            "tags": ["valuation|macro|earnings|dividend|technical|risk|other"],
            "extraction_status": "verified|needs_review|unknown"
        }]
    }
    # Segments are kept in the durable raw-source artifact, but are already represented
    # by [HH:MM:SS] markers in text. Do not send the duplicate array to the model.
    prompt_source = {key: source[key] for key in (*required, "source_external_id") if key in source}
    # Auto-captions often contain rolling duplicate fragments. The raw ``text``
    # remains in the source artifact; only the model view is normalised.
    prompt_source["text"] = source.get("extraction_text", source["text"])

    registry_block = ""
    if args.db:
        import sqlite3
        with sqlite3.connect(args.db) as conn:
            assets = conn.execute("""
                SELECT a.canonical_name, a.ticker,
                       (SELECT GROUP_CONCAT(identifier, ' | ') FROM asset_identifiers ai
                         WHERE ai.asset_id = a.id) aliases
                FROM assets a ORDER BY a.canonical_name""").fetchall()
            experts = [r[0] for r in conn.execute(
                "SELECT canonical_name FROM experts ORDER BY canonical_name") if r[0]]
        lines = [f"- {name}" + (f" (тикер: {tk})" if tk else "")
                 + (f" [также называется: {al}]" if al else "")
                 for name, tk, al in assets]
        registry_block = f"""
Canonical asset registry (ALREADY EXISTS in the index):
{chr(10).join(lines)}

Canonical expert registry (ALREADY EXISTS in the index):
{chr(10).join('- ' + e for e in experts)}

Classification rules:
- If a thesis is about an asset already in the registry, use EXACTLY the canonical name from the registry (copy-paste), even if the source words it differently (e.g. 'рубль', 'доллар к рублю' -> use the registry's currency name for USD/RUB).
- 'рубль'/'курс рубля' without an explicit other currency means USD/RUB; euro is a separate asset.
- Create a genuinely new asset name ONLY if the thesis matches nothing in the registry.
- Same for experts: reuse the canonical expert name; do not shorten (Василий != separate person).
"""
    prompt = f"""You are the extraction stage of Experts Said. Model label: {args.model}.
Return exactly one JSON object, no Markdown and no commentary. Use the schema below.

Rules:
- Inspect the entire source; create one card per independent recommendation, scenario, warning, or price level.
- Never invent an expert, ticker, price, currency, publication date, URL, or quote. Use null/empty values only where the schema allows; otherwise create a card with extraction_status='unknown' or omit it.
- Leave asset.ticker empty unless the ticker itself is spoken or written in the source. A separate importer resolves unambiguous MOEX matches.
- quote must be verbatim and sufficient to verify the card. Do not turn a discussion question into a recommendation.
- A price level must be numeric and stated in the source. Keep entry/target/stop/support/resistance/range separate.
- asserted_at and effective_at use the supplied publication time unless the source explicitly names another date.
- Preserve source text byte-for-byte in the text field.
- Never include [HH:MM:SS] timestamp markers inside quotes: quote only the spoken words, timestamps go to start_sec/end_sec.
{registry_block}
JSON schema example:\n{json.dumps(schema, ensure_ascii=False)}

Source to process:\n{json.dumps(prompt_source, ensure_ascii=False)}
"""
    if args.output:
        args.output.write_text(prompt, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
