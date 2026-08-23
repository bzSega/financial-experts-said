# Архитектура

## Конвейер
```
Первоисточник (YouTube .srt/.vtt, Telegram-пост, статья)
  → captions_to_source.py / вручную → source JSON (schema/source.schema.json)
  → build_extraction_prompt.py (канонсправочник активов/экспертов из БД)
  → LLM-извлечение карточек (stance, summary, дословная цитата, уровни)
  → import_json.py (валидация цитат, алиас-матчинг, импорт)
  → SQLite (theses, thesis_levels, assets, experts, sources)
  → chart/ticker_chart{,_html}.py — PNG / интерактивный HTML (свечи MOEX ISS + уровни)
```

## Схема БД (init_db.py)
- sources — первоисточники (тип, URL, хэш текста, source_external_id)
- experts / assets — канонические имена + aliases_json
- asset_identifiers — тикеры/ISIN/алиасы для матчинга
- theses — тезисы: expert, asset, stance, asserted_at, summary, quote (UNIQUE по source+expert+asset+quote)
- thesis_levels — уровни: level_type (support/resistance/entry/target/stop/range), price_low/high, currency, effective_at
- thesis_fts — полнотекстовый поиск

## Анти-дубликация (3 уровня)
1. Канонсправочник в промпте извлечения — модель обязана использовать точные имена из БД.
2. Алиас-матчинг в import_json (one_id): точное имя → asset_identifiers → casefold. ВАЖНО: SQL NOCASE/LOWER ASCII-only, кириллицу сравнивать только в Python.
3. Семантический мерж дублей вручную (UPDATE theses + дедуп identifiers + DELETE, с бэкапом БД).

## Источники цен
MOEX ISS: /candles PRIMARY (interval=24) → /history fallback. Тикер из assets.ticker; словесные активы — мапы fallback в chart/ticker_chart_html.py. Не котируются на MOEX: S&P 500, DXY, Moderna (stooq-fallback).
