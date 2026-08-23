"""Render the board as a self-contained page. No server, no network, phone-first."""
import json, os, datetime, html

HERE = os.path.dirname(os.path.abspath(__file__))
B = json.load(open(os.path.join(HERE, "data", "board.json")))
RAW = os.path.join(HERE, "data", "raw")
draft = json.load(open(os.path.join(RAW, "draft.json")))
users = {u["user_id"]: u["display_name"] for u in json.load(open(os.path.join(RAW, "league_users.json")))}
slot_of = draft["draft_order"]
name_by_slot = {v: users[k] for k, v in slot_of.items()}

BASIS = {"Allos": "MEASURED", "Antonio93": "MEASURED", "LewisS19": "MEASURED",
         "PeterPlays": "MEASURED", "mstasik": "MEASURED",
         "CaptFilipina": "THIN", "mondaymorningtears23": "THIN", "KHUFF1": "THIN",
         "BigPoppaTrash": "COACHED", "lenall": "COACHED", "GLat3": "NO HISTORY"}
NOTE = {"COACHED": "no draft history; commish (Antonio93, measured) expected to advise in person"}

T, R, ME = 12, 15, 9
order = []
for r in range(1, R + 1):
    for s in (range(1, T + 1) if r % 2 else range(T, 0, -1)):
        order.append((r, s))
mine = [i + 1 for i, (r, s) in enumerate(order) if s == ME]
gap_short = [name_by_slot[order[i - 1][1]] for i in range(mine[0] + 1, mine[1])]

g = B["generated_from"]
built = datetime.datetime.now().strftime("%a %d %b %Y, %H:%M")

rows = []
for p in B["players"]:
    e = p.get("edge_pts")
    ecls = "e-pos" if (e is not None and e >= 8) else ("e-neg" if (e is not None and e <= -8) else "e-flat")
    etxt = ("%+.0f" % e) if e is not None else "—"
    rows.append({
        "n": p["name"], "pos": p["pos"], "tm": p.get("team") or "",
        "vor": p["vor"], "pts": p["pts_ppr"], "tier": p["tier"], "pt": p.get("pos_tier"),
        "ffc": p.get("ffc_adp"), "sl": p.get("sleeper_adp"),
        "e": etxt, "ec": ecls, "zone": p["zone"],
    })

DATA = json.dumps(rows, separators=(",", ":"))

page = """<title>Lions Den Draft Board</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;600&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{
  --ground:#f4f5f7; --panel:#ffffff; --panel-2:#eceef1; --line:#d5d9df;
  --ink:#171a1f; --ink-2:#5b636e; --ink-3:#878f9a;
  --gold:#a8761b; --gold-soft:#f0e2c6;
  --good:#1c6b45; --good-bg:#dbeee3; --bad:#9c2f2f; --bad-bg:#f5dcdc;
  --warn:#8a5a12; --warn-bg:#f8ecd6;
}
:root:not([data-theme="light"]){ }
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#14161a; --panel:#1c1f25; --panel-2:#23272e; --line:#31363f;
  --ink:#eef0f3; --ink-2:#a3abb6; --ink-3:#767e8a;
  --gold:#e0a94a; --gold-soft:#3a2f1a;
  --good:#5fd196; --good-bg:#17301f; --bad:#f08a8a; --bad-bg:#341a1a;
  --warn:#e8b866; --warn-bg:#332813;
}}
:root[data-theme="dark"]{
  --ground:#14161a; --panel:#1c1f25; --panel-2:#23272e; --line:#31363f;
  --ink:#eef0f3; --ink-2:#a3abb6; --ink-3:#767e8a;
  --gold:#e0a94a; --gold-soft:#3a2f1a;
  --good:#5fd196; --good-bg:#17301f; --bad:#f08a8a; --bad-bg:#341a1a;
  --warn:#e8b866; --warn-bg:#332813;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,-apple-system,sans-serif;
  font-size:15px;line-height:1.45;-webkit-text-size-adjust:100%}
.wrap{max-width:920px;margin:0 auto;padding:0 14px 72px}
header{padding:20px 0 12px;border-bottom:2px solid var(--gold)}
.eyebrow{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--gold);font-weight:600}
h1{font-family:Oswald,"Arial Narrow",sans-serif;font-weight:600;font-size:34px;
  margin:.18em 0 .1em;letter-spacing:.01em;text-wrap:balance;line-height:1.05}
.sub{color:var(--ink-2);font-size:13.5px;margin:0}
.slots{display:flex;flex-wrap:wrap;gap:5px;margin:14px 0 0}
.slot{font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;
  background:var(--panel);border:1px solid var(--line);border-radius:3px;padding:3px 7px;
  font-variant-numeric:tabular-nums}
.slot.first{border-color:var(--gold);color:var(--gold);background:var(--gold-soft)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;
  padding:14px 16px;margin:14px 0}
.card h2{font-family:Oswald,sans-serif;font-weight:600;font-size:15px;letter-spacing:.05em;
  text-transform:uppercase;margin:0 0 8px;color:var(--ink)}
.card.warn{background:var(--warn-bg);border-color:var(--warn)}
.card.warn h2{color:var(--warn)}
.card p{margin:0 0 8px;font-size:13.5px;color:var(--ink-2)}
.card p:last-child{margin-bottom:0}
.card b{color:var(--ink)}
.prov{display:grid;gap:7px;font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink-2)}
.prov div{display:flex;gap:8px;flex-wrap:wrap}
.prov span:first-child{color:var(--ink-3);min-width:92px}
.gaps{display:grid;gap:6px;font-size:13px}
.gapline{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.tag{font-family:"IBM Plex Mono",monospace;font-size:10px;font-weight:600;letter-spacing:.07em;
  padding:2px 6px;border-radius:3px;text-transform:uppercase;white-space:nowrap}
.t-MEASURED{background:var(--good-bg);color:var(--good)}
.t-THIN{background:var(--warn-bg);color:var(--warn)}
.t-COACHED{background:var(--gold-soft);color:var(--gold)}
.t-NO{background:var(--bad-bg);color:var(--bad)}
.filters{position:sticky;top:0;z-index:10;background:var(--ground);
  padding:10px 0 8px;display:flex;gap:6px;flex-wrap:wrap;border-bottom:1px solid var(--line)}
button.f{font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;cursor:pointer;
  background:var(--panel);color:var(--ink-2);border:1px solid var(--line);
  border-radius:3px;padding:6px 11px;letter-spacing:.04em}
button.f[aria-pressed="true"]{background:var(--gold);color:var(--ground);border-color:var(--gold)}
button.f:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.tierhead{display:flex;align-items:baseline;gap:9px;margin:20px 0 5px;
  padding-bottom:4px;border-bottom:1px solid var(--line)}
.tierhead .tn{font-family:Oswald,sans-serif;font-size:17px;font-weight:600;letter-spacing:.06em;
  text-transform:uppercase}
.tierhead .tc{font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink-3)}
table{width:100%;border-collapse:collapse}
thead th{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-3);text-align:right;padding:5px 4px;font-weight:600}
thead th:first-child{text-align:left}
td{padding:7px 4px;border-bottom:1px solid var(--line);font-size:14px;
  font-variant-numeric:tabular-nums;text-align:right}
td:first-child{text-align:left}
tr.lottery td{opacity:.62}
.pname{font-weight:500}
.pmeta{font-family:"IBM Plex Mono",monospace;font-size:10.5px;color:var(--ink-3);
  letter-spacing:.03em;display:block}
.num{font-family:"IBM Plex Mono",monospace;font-size:13px}
.vor{font-weight:600}
.echip{font-family:"IBM Plex Mono",monospace;font-size:12px;font-weight:600;
  padding:2px 6px;border-radius:3px}
.e-pos{background:var(--good-bg);color:var(--good)}
.e-neg{background:var(--bad-bg);color:var(--bad)}
.e-flat{color:var(--ink-3)}
.zsplit{margin:26px 0 4px;padding:9px 12px;background:var(--warn-bg);border:1px solid var(--warn);
  border-radius:5px;font-size:12.5px;color:var(--warn);font-weight:500}
footer{margin-top:32px;padding-top:14px;border-top:1px solid var(--line);
  font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink-3);line-height:1.7}
@media (max-width:560px){
  h1{font-size:27px} body{font-size:14px}
  td{padding:7px 3px;font-size:13.5px} .hide-s{display:none}
}
</style>
<div class="wrap">
<header>
  <div class="eyebrow">The Lions Den &middot; 12-team &middot; full PPR</div>
  <h1>Draft Board &mdash; Slot 9</h1>
  <p class="sub">Snake, 15 rounds, 90-second clock &middot; Sat 22 Aug 2026, 8:30 PM &middot; QB/RB/RB/WR/WR/TE + 3&nbsp;FLEX, no K, no DEF</p>
  <div class="slots">__SLOTS__</div>
</header>

<div class="card">
  <h2>Where the numbers came from</h2>
  <div class="prov">
    <div><span>Projections</span><span>__PROJ__</span></div>
    <div><span>ADP (FFC)</span><span>__FFC__</span></div>
    <div><span>ADP (Sleeper)</span><span>__SL__</span></div>
    <div><span>Replacement</span><span>__REPL__</span></div>
    <div><span>Built</span><span>__BUILT__</span></div>
  </div>
</div>

<div class="card warn">
  <h2>Read this before you trust a row</h2>
  <p><b>The board is reliable through about pick 120 (round 10).</b> After that it is not, and this is measured, not guessed: through pick 60 the median player the market takes has a VOR of <b>+68</b>; from 121&ndash;180 it is <b>&minus;55</b>. The field is deliberately buying upside and handcuff insurance that a median points projection cannot price. Rows past pick 120 are greyed out for that reason &mdash; treat them as a shortlist, not an order.</p>
  <p><b>VOR near zero is noise.</b> Replacement sits at 157.3 for both WR and TE, so the curve goes flat and small point differences swing rankings wildly. Trust tiers over ranks.</p>
  <p><b>One projection source.</b> Everything here is Rotowire via Sleeper. No blend, no second opinion &mdash; a miss by Rotowire is a miss on this whole sheet.</p>
</div>

<div class="card">
  <h2>The six picks that decide every turn</h2>
  <p>From slot 9 the same three managers pick between each of your back-to-back pairs &mdash; twice each, seven times over the draft. This is the gap your &ldquo;can I wait?&rdquo; question always runs through.</p>
  <div class="gaps">__GAPS__</div>
  <p style="margin-top:10px">The other eight managers fill the 16-pick gap over the turn, four of them measured. <b>Basis labels are evidence, not decoration</b> &mdash; MEASURED means 15 real picks in this league last year; NO HISTORY means no drafts found anywhere.</p>
</div>

<div class="filters">
  <button class="f" data-p="ALL" aria-pressed="true">ALL</button>
  <button class="f" data-p="RB" aria-pressed="false">RB</button>
  <button class="f" data-p="WR" aria-pressed="false">WR</button>
  <button class="f" data-p="TE" aria-pressed="false">TE</button>
  <button class="f" data-p="QB" aria-pressed="false">QB</button>
</div>
<div id="board"></div>

<footer>
  Value over replacement, measured from this league&rsquo;s own starter demand: 12 teams &times; (1 QB, 2 RB, 2 WR, 1 TE, 3 FLEX) = 108 starters.<br>
  VALUE = projected points above what the market hands you at that player&rsquo;s ADP. Positive means the board rates him higher than his price.<br>
  Nothing on this page is a forecast of results. Every number is traceable to a source and a date above.
</footer>
</div>
<script>
const D=__DATA__;
const board=document.getElementById('board');
let filt='ALL';
function render(){
  const rows=D.filter(r=>filt==='ALL'||r.pos===filt);
  let html='',tier=null,shownSplit=false;
  const key=filt==='ALL'?'tier':'pt';
  rows.forEach((r,i)=>{
    if(r[key]!==tier){
      if(tier!==null) html+='</tbody></table>';
      tier=r[key];
      const n=rows.filter(x=>x[key]===tier).length;
      html+='<div class="tierhead"><span class="tn">Tier '+tier+'</span><span class="tc">'+n+' player'+(n>1?'s':'')+'</span></div>';
      html+='<table><thead><tr><th>Player</th><th>VOR</th><th class="hide-s">Proj</th><th>FFC</th><th class="hide-s">Sleep</th><th>Value</th></tr></thead><tbody>';
    }
    html+='<tr class="'+(r.zone==='lottery'?'lottery':'')+'">'
      +'<td><span class="pname">'+r.n+'</span><span class="pmeta">'+r.pos+(r.tm?' &middot; '+r.tm:'')+'</span></td>'
      +'<td class="num vor">'+r.vor.toFixed(0)+'</td>'
      +'<td class="num hide-s">'+r.pts.toFixed(0)+'</td>'
      +'<td class="num">'+(r.ffc?r.ffc.toFixed(1):'—')+'</td>'
      +'<td class="num hide-s">'+(r.sl?r.sl.toFixed(0):'—')+'</td>'
      +'<td><span class="echip '+r.ec+'">'+r.e+'</span></td></tr>';
  });
  html+='</tbody></table>';
  board.innerHTML=html;
}
document.querySelectorAll('button.f').forEach(b=>b.addEventListener('click',()=>{
  filt=b.dataset.p;
  document.querySelectorAll('button.f').forEach(x=>x.setAttribute('aria-pressed',x===b?'true':'false'));
  render();
}));
render();
</script>
"""

slots = "".join('<span class="slot%s">%d.%02d &nbsp;#%d</span>'
                % (" first" if i == 0 else "", order[ov-1][0], (ov-1) % T + 1, ov)
                for i, ov in enumerate(mine))
gaps = ""
for m in gap_short[:3]:
    b = BASIS[m]
    cls = "t-NO" if b == "NO HISTORY" else "t-" + b
    extra = NOTE.get(b, "")
    gaps += ('<div class="gapline"><b>%s</b><span class="tag %s">%s</span>'
             '<span style="color:var(--ink-3);font-size:12px">2 picks%s</span></div>'
             % (html.escape(m), cls, b, (" &middot; " + extra) if extra else ""))

repl = B["replacement"]
page = (page.replace("__SLOTS__", slots).replace("__GAPS__", gaps)
        .replace("__PROJ__", "Rotowire via Sleeper &middot; season PPR &middot; updated " + g["projections"]["updated_utc"][:16].replace("T", " ") + " UTC")
        .replace("__FFC__", "FantasyFootballCalculator &middot; PPR 12-team &middot; %d drafts &middot; %s" % (g["adp_ffc"]["drafts"], g["adp_ffc"]["window"]))
        .replace("__SL__", "Sleeper stats.adp_ppr &middot; format/size not documented &mdash; population match, not format match")
        .replace("__REPL__", "QB13 %.0f &middot; RB32 %.0f &middot; WR52 %.0f &middot; TE15 %.0f pts" % (repl["QB"], repl["RB"], repl["WR"], repl["TE"]))
        .replace("__BUILT__", built)
        .replace("__DATA__", DATA))

out = os.path.join(HERE, "board.html")
open(out, "w").write(page)
print("wrote %s  (%.0f KB, %d players)" % (out, len(page)/1024, len(rows)))
