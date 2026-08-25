"""Build the live draft companion: one self-contained page, client-side only."""
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
B = json.load(open(os.path.join(HERE, "data", "board.json")))
V = json.load(open(os.path.join(HERE, "data", "variance.json")))
draft = json.load(open(os.path.join(RAW, "draft.json")))
league = json.load(open(os.path.join(RAW, "league.json")))
users = {u["user_id"]: u["display_name"] for u in json.load(open(os.path.join(RAW, "league_users.json")))}
byes = json.load(open(os.path.join(RAW, "byes_2026.json")))
try:
    _dsn = json.load(open(os.path.join(RAW, "notes_draftsharks.json")))
    NOTES, NOTES_META = _dsn["notes"], _dsn
except FileNotFoundError:
    NOTES, NOTES_META = {}, {}
try:
    NEWS = json.load(open(os.path.join(RAW, "news.json")))["news"]
except FileNotFoundError:
    NEWS = {}
# Structured situation data straight from Sleeper's own player file. This is the
# honest, free version of "camp news": depth-chart role, injury designation and
# when news last broke. It is NOT reporting - there is no prose here, no source
# to cite beyond Sleeper itself, and no coordinator or scheme information.
PLAYERS_NFL = json.load(open(os.path.join(HERE, "cache", "players_nfl.json")))
sched = json.load(open(os.path.join(RAW, "schedule_2026.json")))
# Factual weeks 15-17 opponents. NO difficulty rating: there is no defensible
# 2026 defensive-strength metric in this project, and inventing one would be
# exactly the kind of number CLAUDE.md forbids. Opponent names only.
playoff = {}
for g in sched:
    if g["week"] in (15, 16, 17):
        playoff.setdefault(g["home"], {})[g["week"]] = "vs " + g["away"]
        playoff.setdefault(g["away"], {})[g["week"]] = "@ " + g["home"]
PO = {t: " / ".join(v.get(w, "BYE") for w in (15, 16, 17)) for t, v in playoff.items()}

DRAFT_ID = draft["draft_id"]
ME_ID = [k for k, v in users.items() if v == "Gunit28"][0]
slot_of = {users[k]: v for k, v in draft["draft_order"].items()}
name_by_slot = {v: users[k] for k, v in draft["draft_order"].items()}

BASIS = {"Allos": "MEASURED", "Antonio93": "MEASURED", "LewisS19": "MEASURED",
         "PeterPlays": "MEASURED", "mstasik": "MEASURED",
         "CaptFilipina": "THIN", "mondaymorningtears23": "THIN", "KHUFF1": "THIN",
         "BigPoppaTrash": "COACHED", "lenall": "COACHED", "GLat3": "NO HISTORY",
         "Gunit28": "SELF"}
# measured dispersion (F-test vs pool variance, last year's 180 picks)
NOISE = {"LewisS19": 0.60, "mstasik": 1.50}

players = []
for p in B["players"]:
    v = V["players"].get(str(p["player_id"])) or {}
    # Survival runs on the BLEND, measured as the most accurate of the three
    # against last year's real picks (mean error 11.40 vs 13.37 FFC / 14.00 Sleeper).
    adp = p.get("adp_blend") or p.get("ffc_adp") or p.get("sleeper_adp")
    players.append({
        "id": str(p["player_id"]), "n": p["name"], "pos": p["pos"], "tm": p.get("team") or "",
        "vor": p["vor"], "pts": p["pts_ppr"],
        "roto": p.get("pts_roto"), "espn": p.get("pts_espn"), "gap": p.get("src_gap"),
        "vr": p.get("vor_roto"), "ve": p.get("vor_espn"), "tier": p["tier"], "pt": p.get("pos_tier"),
        "adp": adp, "ffc": p.get("ffc_adp"), "sl": p.get("sleeper_adp"),
        "sd": max(p.get("ffc_stdev") or 9.0, 1.0),
        "sr": v.get("startable_rate"), "ceil": v.get("ceiling"), "floor": v.get("floor"),
        "h10": v.get("hit10"), "h15": v.get("hit15"),
        "vb": "M" if v.get("basis") == "MEASURED" else "N",
        "bye": byes.get(p.get("team") or "", None),
        "dcp": (PLAYERS_NFL.get(str(p["player_id"])) or {}).get("depth_chart_position"),
        "dco": (PLAYERS_NFL.get(str(p["player_id"])) or {}).get("depth_chart_order"),
        "inj": (PLAYERS_NFL.get(str(p["player_id"])) or {}).get("injury_status"),
        "injb": (PLAYERS_NFL.get(str(p["player_id"])) or {}).get("injury_body_part"),
        "nu": (PLAYERS_NFL.get(str(p["player_id"])) or {}).get("news_updated"),
        "age": (PLAYERS_NFL.get(str(p["player_id"])) or {}).get("age"),
        "note": NOTES.get(p["name"]),
        "news": (NEWS.get(p["name"]) or {}).get("text"),
        "newsd": (NEWS.get(p["name"]) or {}).get("date"),
        "newsflag": (NEWS.get(p["name"]) or {}).get("tone"),
        "po": PO.get(p.get("team") or "", ""),
        "zone": p["zone"],
    })

CFG = {
    "draft_id": DRAFT_ID, "me_id": ME_ID, "me": "Gunit28", "slot": slot_of["Gunit28"],
    "teams": 12, "rounds": 15,
    "slots_by_pick": {}, "basis": BASIS, "noise": NOISE,
    "name_by_slot": {str(k): v for k, v in name_by_slot.items()},
    "roster": league["roster_positions"],
    "start_time": draft["start_time"],
    "prov": B["generated_from"],
    "user_names": users,
    "league_id": league["league_id"],
    "roster_by_owner": {r["owner_id"]: r["roster_id"] for r in json.load(open(os.path.join(RAW, "league_rosters.json"))) if r.get("owner_id")},
}
T, R = 12, 15
for r in range(1, R + 1):
    for i, s in enumerate(range(1, T + 1) if r % 2 else range(T, 0, -1)):
        CFG["slots_by_pick"][str((r - 1) * T + i + 1)] = s

# In-season pool. Built by inseason.py, and deliberately NOT board.json: the
# free-agency screen exists to find players who were never worth drafting.
_IS = json.load(open(os.path.join(HERE, "data", "inseason.json")))

# Ship only the fields the page reads. inseason.json keeps everything for the
# python side; embedding all of it cost 331 KB, of which 123 KB was per-week
# opponent strings nothing on this screen uses. This page gets opened on a phone
# during a first-come-first-served scramble - weight is a feature, not a detail.
_FA_FIELDS = ("n", "pos", "tm", "bye", "dcp", "dco", "inj", "pts",
              "wp", "h10", "h15", "ceil", "flr", "sd", "sr", "g25", "mb")


def _slim(rec):
    out = {}
    for k in _FA_FIELDS:
        v = rec.get(k)
        # Absent means unknown to the page, which is exactly what null means
        # here - so drop it rather than shipping the word "null" 500 times.
        if v is None or v == "" or v == {}:
            continue
        if k == "mb" and v != "M":
            continue          # only "has 2025 history" needs saying
        if k == "g25" and not v:
            continue
        out[k] = v
    return out


_FAPOOL = {pid: _slim(r) for pid, r in _IS["players"].items()}

page = open(os.path.join(HERE, "live_template.html")).read()
page = page.replace("__CFG__", json.dumps(CFG, separators=(",", ":")))
page = page.replace("__FAPOOL__", json.dumps(_FAPOOL, separators=(",", ":")))
page = page.replace("__FAMETA__", json.dumps(_IS["meta"], separators=(",", ":")))
page = page.replace("__PLAYERS__", json.dumps(players, separators=(",", ":")))
page = page.replace("__PULLED__", datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"))
page = page.replace("__BUILT__", datetime.datetime.now().strftime("%a %d %b, %H:%M"))
page = page.replace("__PROJUPD__", B["generated_from"]["projections"]["updated_utc"][:16].replace("T", " "))
page = page.replace("__FFCWIN__", B["generated_from"]["adp_ffc"]["window"])
page = page.replace("__FFCN__", str(B["generated_from"]["adp_ffc"]["drafts"]))
out = os.path.join(HERE, "live.html")
open(out, "w").write(page)

# Syntax-check the emitted JS. A block edit once swallowed a variable
# declaration and the page still "built" fine - it just died at runtime.
import re as _re, subprocess as _sp, tempfile as _tf
_m = _re.search(r"<script>(.*)</script>", page, _re.S)
if _m:
    with _tf.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
        fh.write(_m.group(1)); _tmp = fh.name
    try:
        r = _sp.run(["node", "--check", _tmp], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("JS SYNTAX ERROR in live.html:\n" + r.stderr)
        print("  js syntax: OK")
    except FileNotFoundError:
        print("  js syntax: SKIPPED (node not found)")
    # required globals must survive future block edits
    for _name in ("let picks", "function render", "function poll", "function simulate", "rebuildPickMap",
                  "function viewFA", "function weekLineup", "function faRows", "function faBind",
                  "function viewLineup", "function viewLeague", "function lineupStats", "function ncdf"):
        if _name not in _m.group(1):
            raise SystemExit("MISSING from emitted JS: " + _name)
    print("  js globals: OK")
# No placeholder may survive into the shipped page. A missed __X__ renders as
# literal text and the JS dies at parse time.
import re as _re2
_left = _re2.findall(r"__[A-Z][A-Z0-9_]*__", page)
if _left:
    raise SystemExit("UNREPLACED PLACEHOLDERS in live.html: %s" % sorted(set(_left)))
print("  placeholders: all replaced")
print("  in-season pool: %d players (%d never on the draft board)"
      % (_IS["meta"]["n_pool"], _IS["meta"]["n_pool"] - _IS["meta"]["n_on_board"]))
print("wrote %s (%.0f KB) draft_id=%s me=%s slot=%d" % (out, len(page)/1024, DRAFT_ID, ME_ID, CFG["slot"]))
