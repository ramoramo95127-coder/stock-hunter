# ruff: noqa: E501

from fastapi.responses import HTMLResponse


def dashboard() -> HTMLResponse:
    return HTMLResponse(_PAGE)


_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width">
  <title>Stock Hunter</title>
  <style>
    :root{color-scheme:dark}*{box-sizing:border-box}body{font-family:system-ui;margin:0;background:#0b1020;color:#eef2ff}
    main{max-width:1160px;margin:auto;padding:24px}header{display:flex;justify-content:space-between;align-items:center}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:20px 0}
    .card,.stat{background:#151c31;border:1px solid #29324f;border-radius:14px;padding:18px}.card{margin:12px 0}
    .prime{border-color:#34d399}.muted,small{color:#9ca3af}.state,.good{color:#34d399}.bad{color:#fb7185}
    button{background:#334155;color:white;border:0;border-radius:8px;padding:9px 12px;cursor:pointer}.enter{background:#047857}
    .levels{display:flex;gap:18px;flex-wrap:wrap}.levels span{white-space:nowrap}h1,h2,h3{margin-top:0}
    body.light{background:#f8fafc;color:#111827}body.light .card,body.light .stat{background:white;border-color:#d1d5db}
  </style>
</head>
<body><main>
  <header><div><h1>Stock Hunter</h1><div class="muted">Best opportunities now — not a prediction</div></div>
  <button onclick="document.body.classList.toggle('light')">Theme</button></header>
  <section class="grid" id="stats"></section>
  <h2 id="status">Loading…</h2><section id="cards"></section>
</main>
<script>
const money=x=>x==null?'—':'$'+Number(x).toFixed(2);
function statCard(label,x){return `<article class="stat"><small>${label}</small><h2>${x.success_rate}%</h2><div class="levels"><span class="good">✓ ${x.successful}</span><span class="bad">✕ ${x.stopped}</span><span>Open ${x.open}</span></div><small>${x.total} signals · ${x.manual} manual</small></article>`}
async function enter(symbol,price){const value=prompt(`Actual entry price for ${symbol}`,price||'');if(!value)return;const r=await fetch('/api/v1/trades/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol,entry:Number(value)})});alert(r.ok?'Entry recorded and now tracked':'Could not record entry')}
async function load(){try{
  const [cardsResponse,statsResponse]=await Promise.all([fetch('/api/v1/opportunity-cards?limit=5'),fetch('/api/v1/performance')]);
  if(!cardsResponse.ok||!statsResponse.ok)throw new Error('API unavailable');
  const items=await cardsResponse.json(),stats=await statsResponse.json();
  document.getElementById('stats').innerHTML=statCard('Today',stats.day)+statCard('This week',stats.week)+statCard('This month',stats.month);
  document.getElementById('status').textContent=items.length?`${items.length} opportunities ranked`:'No qualified opportunity now';
  document.getElementById('cards').innerHTML=items.map(x=>`<article class="card ${x.state==='prime_candidate'?'prime':''}">
    <h2>#${x.rank} ${x.symbol}</h2><b class="state">${x.state.replaceAll('_',' ')}</b> · Confidence ${x.confidence.toFixed(1)}
    <p>${x.explanation}</p><div class="levels"><span>Entry ${money(x.entry_low)}–${money(x.entry_high)}</span><span class="good">Target ${money(x.target)}</span><span class="bad">Stop ${money(x.stop)}</span></div>
    <p><b>Primary catalyst:</b> ${x.catalyst.replaceAll('_',' ')}</p><p><b>Why now:</b><br>${x.reasons.slice(0,4).join('<br>')}</p>
    <p><b>What next:</b> ${x.what_next}</p><p><b>Invalidation:</b> ${x.invalidation}</p><small>${x.risk_note}</small><br><br>
    <button class="enter" onclick="enter('${x.symbol}',${x.current_price||0})">I entered this trade</button></article>`).join('');
}catch(e){document.getElementById('status').textContent='System unavailable'}}
load();setInterval(load,10000)
</script></body></html>"""
