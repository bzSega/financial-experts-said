#!/usr/bin/env python3
"""Build a self-contained interactive HTML Experts Said registry."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from init_db import ensure_schema


def source_link(url, start_sec):
    if not url:
        return ""
    if start_sec is None:
        return url
    return f"{url}{'&' if '?' in url else '?'}t={max(0, int(start_sec))}s"


def load_records(db):
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        theses = conn.execute("""
            SELECT t.id,t.asserted_at,t.stance,t.horizon,t.confidence,t.summary,t.quote,
                   t.start_sec,t.end_sec,t.extraction_status,a.ticker,
                   a.canonical_name asset,a.asset_type,e.canonical_name expert,
                   s.title source_title,s.url source_url,s.source_type
            FROM theses t JOIN sources s ON s.id=t.source_id
            LEFT JOIN assets a ON a.id=t.asset_id LEFT JOIN experts e ON e.id=t.expert_id
            ORDER BY t.asserted_at DESC,COALESCE(a.ticker,a.canonical_name),t.id
        """).fetchall()
        levels = conn.execute("""
            SELECT thesis_id,level_type,price_low,price_high,currency,effective_at,comment
            FROM thesis_levels ORDER BY effective_at,level_type,price_low
        """).fetchall()
        tags = conn.execute("SELECT thesis_id,tag FROM thesis_tags ORDER BY tag").fetchall()
    records = {r["id"]: dict(r) for r in theses}
    for value in records.values():
        value["levels"], value["tags"] = [], []
        value["source"] = source_link(value.pop("source_url"), value["start_sec"])
    for level in levels:
        if level["thesis_id"] in records:
            records[level["thesis_id"]]["levels"].append(dict(level))
    for tag in tags:
        if tag["thesis_id"] in records:
            records[tag["thesis_id"]]["tags"].append(tag["tag"])
    return list(records.values())


def render(records, generated_at):
    data = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Experts Said</title><style>
:root{{color-scheme:dark;--bg:#101217;--panel:#181c24;--line:#303745;--ink:#eef1f7;--muted:#9ea8ba;--blue:#71a8ff;--green:#51d49a;--red:#ff7f88;--amber:#ffc66d}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 Inter,system-ui,sans-serif}}a{{color:var(--blue)}}header{{padding:26px max(22px,calc((100vw - 1400px)/2));border-bottom:1px solid var(--line)}}h1{{font-size:24px;margin:0 0 5px}}.sub,.muted{{color:var(--muted)}}main{{max-width:1400px;margin:auto;padding:18px 22px 36px}}.filters{{display:grid;grid-template-columns:1.4fr repeat(4,1fr) auto;gap:10px;background:var(--panel);padding:14px;border:1px solid var(--line);border-radius:12px;margin-bottom:14px}}input,select,button{{min-width:0;color:var(--ink);background:#10141c;border:1px solid var(--line);border-radius:7px;padding:9px}}button{{cursor:pointer;background:#263d64;border-color:#3b5f95}}.layout{{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(320px,.9fr);gap:14px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}}.table-wrap{{overflow:auto;max-height:70vh}}table{{border-collapse:collapse;width:100%;min-width:880px}}th{{position:sticky;top:0;background:#202632;color:var(--muted);font-size:12px;text-align:left}}td,th{{padding:10px;border-bottom:1px solid #272d38;vertical-align:top}}tbody tr{{cursor:pointer}}tbody tr:hover,tbody tr.selected{{background:#202b3d}}.ticker{{font-weight:700}}.buy,.overweight{{color:var(--green)}}.sell,.underweight{{color:var(--red)}}.watch,.unclear,.review{{color:var(--amber)}}#detail{{padding:16px;min-height:300px}}#detail h2{{font-size:18px;margin:0 0 5px}}blockquote{{margin:12px 0;padding:10px 12px;border-left:3px solid var(--blue);background:#131721;white-space:pre-wrap}}.levels{{margin:12px 0;padding-left:18px}}.chart-title{{margin:18px 0 5px;font-weight:700}}svg{{display:block;width:100%;height:230px;background:#11151d;border:1px solid var(--line);border-radius:8px}}.empty{{padding:22px;color:var(--muted)}}footer{{color:var(--muted);padding-top:12px;font-size:12px}}@media(max-width:950px){{.layout{{grid-template-columns:1fr}}.filters{{grid-template-columns:1fr 1fr}}}}</style></head><body><header><h1>Experts Said</h1><div class="sub">Исторический реестр высказываний экспертов, не инвестиционная рекомендация</div></header><main><section class="filters"><input id="ticker" placeholder="Тикер или актив, например PLZL"><input id="from" type="date" title="С даты"><input id="to" type="date" title="По дату"><select id="expert"><option value="">Все эксперты</option></select><select id="stance"><option value="">Все позиции</option></select><select id="status"><option value="">Все статусы</option></select><button id="reset">Сбросить</button></section><div class="sub" id="count"></div><div class="layout"><section class="card"><div class="table-wrap"><table><thead><tr><th>Дата</th><th>Тикер / актив</th><th>Эксперт</th><th>Позиция</th><th>Уровни</th><th>Статус</th></tr></thead><tbody id="rows"></tbody></table></div></section><aside class="card" id="detail"><div class="empty">Выбери строку — здесь будут цитата, источник, уровни и график по активу.</div></aside></div><footer>Сформировано {generated_at} · Источник: локальная база Experts Said</footer></main><script>const DATA={data};const $=id=>document.getElementById(id),qp=new URLSearchParams(location.search);const names={{buy:'покупать',overweight:'перевес',hold:'держать',underweight:'недовес',sell:'продавать',watch:'ждать',neutral:'нейтрально',unclear:'неясно'}};const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));const date=s=>(s||'').slice(0,10),fmt=n=>Number.isFinite(+n)?new Intl.NumberFormat('ru-RU').format(+n):'';const level=l=>`${{l.level_type}}: ${{fmt(l.price_low)}}${{l.price_high!=null&&l.price_high!==l.price_low?'–'+fmt(l.price_high):''}} ${{l.currency||''}}`;function options(id,values,render=x=>x){{for(const v of [...new Set(values.filter(Boolean))].sort()){{let o=document.createElement('option');o.value=v;o.textContent=render(v);$(id).append(o)}}}}options('expert',DATA.map(x=>x.expert));options('stance',DATA.map(x=>x.stance),x=>names[x]||x);options('status',DATA.map(x=>x.extraction_status));for(const id of ['ticker','from','to','expert','stance','status'])if(qp.get(id))$(id).value=qp.get(id);function filter(){{const f=Object.fromEntries(['ticker','from','to','expert','stance','status'].map(k=>[k,$(k).value.trim()])),n=f.ticker.toLowerCase();return DATA.filter(x=>(!n||`${{x.ticker||''}} ${{x.asset||''}}`.toLowerCase().includes(n))&&(!f.from||date(x.asserted_at)>=f.from)&&(!f.to||date(x.asserted_at)<=f.to)&&(!f.expert||x.expert===f.expert)&&(!f.stance||x.stance===f.stance)&&(!f.status||x.extraction_status===f.status))}}function renderTable(){{const list=filter(),body=$('rows');$('count').textContent=`Показано ${{list.length}} из ${{DATA.length}} тезисов`;body.innerHTML=list.map(x=>`<tr data-id="${{x.id}}"><td>${{esc(date(x.asserted_at))}}</td><td><span class="ticker">${{esc(x.ticker||'—')}}</span><br>${{esc(x.asset||'—')}}</td><td>${{esc(x.expert||'—')}}</td><td class="${{esc(x.stance)}}">${{esc(names[x.stance]||x.stance)}}</td><td>${{x.levels.map(level).map(esc).join('<br>')||'—'}}</td><td class="${{x.extraction_status==='needs_review'?'review':''}}">${{esc(x.extraction_status)}}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">Нет данных для выбранного среза.</td></tr>';for(const r of body.querySelectorAll('tr[data-id]'))r.onclick=()=>show(+r.dataset.id);const u=new URL(location);for(const[k,v]of Object.entries(f=Object.fromEntries(['ticker','from','to','expert','stance','status'].map(k=>[k,$(k).value.trim()]))))v?u.searchParams.set(k,v):u.searchParams.delete(k);history.replaceState(null,'',u);if(list.length===1)show(list[0].id)}}function chart(asset){{const p=DATA.filter(x=>x.asset===asset).flatMap(x=>x.levels.map(l=>({{...l,expert:x.expert,date:date(x.asserted_at)}}))).filter(x=>Number.isFinite(+x.price_low));if(!p.length)return '<div class="empty">Для этого актива в базе нет числовых уровней.</div>';const cur=p[0].currency,a=p.filter(x=>x.currency===cur),values=a.flatMap(x=>[+x.price_low,x.price_high==null?+x.price_low:+x.price_high]),lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1,ds=[...new Set(a.map(x=>x.date))].sort(),x=d=>40+(ds.indexOf(d)/Math.max(1,ds.length-1))*300,y=v=>190-((v-lo)/span)*150;return `<div class="chart-title">Уровни экспертов: ${{esc(asset)}} (${{esc(cur)}})</div><svg viewBox="0 0 360 230"><text x="4" y="42" fill="#9ea8ba" font-size="11">${{fmt(hi)}}</text><text x="4" y="194" fill="#9ea8ba" font-size="11">${{fmt(lo)}}</text><line x1="40" y1="40" x2="340" y2="40" stroke="#303745"/><line x1="40" y1="190" x2="340" y2="190" stroke="#303745"/>${{a.map(q=>`<g><circle cx="${{x(q.date)}}" cy="${{y(q.price_low)}}" r="5" fill="#71a8ff"><title>${{esc(q.date+' · '+q.expert+' · '+level(q))}}</title></circle><text x="${{x(q.date)-15}}" y="210" fill="#9ea8ba" font-size="10">${{esc(q.date.slice(5))}}</text></g>`).join('')}}</svg>`}}function show(id){{const x=DATA.find(z=>z.id===id);if(!x)return;for(const z of document.querySelectorAll('tr.selected'))z.classList.remove('selected');document.querySelector(`tr[data-id="${{id}}"]`)?.classList.add('selected');const source=x.source?`<a href="${{esc(x.source)}}" target="_blank" rel="noreferrer">Открыть источник${{x.start_sec!=null?' с таймкода':''}}</a>`:'Источник не указан';$('detail').innerHTML=`<h2>${{esc(x.ticker||x.asset||'Актив')}}</h2><div class="muted">${{esc(date(x.asserted_at))}} · ${{esc(x.expert||'эксперт не указан')}} · <span class="${{esc(x.stance)}}">${{esc(names[x.stance]||x.stance)}}</span></div><p>${{esc(x.summary)}}</p><blockquote>${{esc(x.quote)}}</blockquote><div>${{source}}</div><ul class="levels">${{x.levels.map(l=>`<li>${{esc(level(l))}}${{l.comment?' — '+esc(l.comment):''}}</li>`).join('')||'<li>Ценовые уровни не названы</li>'}}</ul><div class="muted">Статус: ${{esc(x.extraction_status)}}${{x.tags.length?' · теги: '+esc(x.tags.join(', ')):''}}</div>${{chart(x.asset)}}`}}for(const id of ['ticker','from','to','expert','stance','status'])$(id).addEventListener('input',renderTable);$('reset').onclick=()=>{{for(const id of ['ticker','from','to','expert','stance','status'])$(id).value='';renderTable()}};renderTable();</script></body></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/financial_theses.db")
    parser.add_argument("--output", default="financial-experts-said-dashboard.html")
    args = parser.parse_args()
    ensure_schema(args.db)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    records = load_records(args.db)
    output.write_text(render(records, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")), encoding="utf-8")
    print(f"wrote {output} ({len(records)} theses)")


if __name__ == "__main__":
    main()
