# financial-experts-said: графики и визуализация

Визуализация экспертных уровней из базы financial-experts-said (SQLite).

## Когда использовать
«Нарисуй уровни по IMOEX», «график по эксперту X», «интерактивный HTML по уровням».

## Использование
```bash
# PNG-график
python3 chart/ticker_chart.py --db fti.db --asset IMOEX --out chart.png

# Интерактивный HTML (свечи MOEX + уровни экспертов, фильтры, табы)
python3 chart/ticker_chart_html.py --db fti.db --out dashboard.html

# Реестр-дашборд (таблица тезисов + детализация + мини-графики уровней)
python3 pipeline/dashboard.py --db fti.db --output dashboard.html
```
HTML-графика использует `lightweight-charts` с CDN — нужен интернет при открытии.

## Правила отображения
1. Свежая дата эксперта — сплошные линии, ранние — пунктир.
2. Фильтры «актив», «эксперт», «актив+эксперт»; мобильная вёрстка.
3. Дайджест до графика: последняя цена + 3 свежих тезиса.
4. Подписи уровней на правой шкале.
5. Табы «Графики»/«Покрытие»: у обеих панелей класс `tabpane`, активная — `tabpane active`; переключатель снимает `active` у всех `.tabpane`.

## Источники цен
- MOEX ISS `/candles` PRIMARY (interval=24), fallback `/history`; тикер из БД (assets.ticker).
- Словесные активы → мапы в скрипте (Золото→GLDRUB_TOM, Нефть→BRZ6, ОФЗ→RGBI и т.п.) как fallback.
- Золото: уровни в $/oz → пересчёт в ₽/г (уровень <10000 трактуем как $/oz), помечать «пересчёт».
- Нулевые свечи отбрасывать; пустые серии — «price empty», не «ok».
- Не котируются на MOEX: S&P 500, DXY, Moderna (stooq-fallback в PNG-скрипте).

## Обязательные проверки перед отправкой HTML
1. Embedded JSON валиден, `</script>`-guard стоит.
2. Даты через Date.parse, не строками.
3. Все вставки в DOM через esc().
