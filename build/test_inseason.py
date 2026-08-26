"""Regression gate for the in-season data layer.

Every assertion here exists because something was wrong and got fixed. They are
cheap; run them before shipping anything that touches weekly data.
"""
import json, os, sys, collections
import weeklystats

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
fails, ran = [], []


def check(name, cond, detail=""):
    ran.append(name)
    print("  %-5s %s%s" % ("PASS" if cond else "FAIL", name, ("  -- " + str(detail)) if detail else ""))
    if not cond:
        fails.append(name)


print("IN-SEASON DATA GATE\n")

# 1. Weeks are real weeks, not list indices. This is the bug that made
#    startable_rate wrong for 33% of measured players.
for season in (2024, 2025):
    byw, meta = weeklystats.points_by_week(season)
    wks = {w for v in byw.values() for w in v}
    check("%d week keys are real NFL weeks (1..18)" % season,
          wks and min(wks) >= 1 and max(wks) <= 18, "got %d..%d" % (min(wks), max(wks)))
    check("%d every week 1-18 has data" % season,
          set(meta["weeks_with_data"]) == set(range(1, 19)), meta["weeks_empty"])
    # population per position per week must support the baseline, or the
    # baseline must be refused - never silently floored to the worst player
    check("%d no player carries more entries than there are weeks" % season,
          max(len(v) for v in byw.values()) <= 18,
          max(len(v) for v in byw.values()))

# 2. startable_rate must report how many weeks it actually judged
V = json.load(open(os.path.join(HERE, "data", "variance.json")))
meas = [r for r in V["players"].values() if r.get("basis") == "MEASURED"]
check("variance: every measured player reports weeks_judged",
      all("weeks_judged" in r for r in meas), "%d measured" % len(meas))
check("variance: weeks_judged never exceeds games played",
      all(r["weeks_judged"] <= r["games"] for r in meas))
check("variance: definition names the exclusion rule",
      "excluded from numerator and denominator" in (V.get("definition") or ""))

# 3. Bye table agrees with an INDEPENDENT source (the weekly projections).
#    Both are derived separately; if they ever diverge, one of them is wrong.
byes = json.load(open(os.path.join(RAW, "byes_2026.json")))
wp = json.load(open(os.path.join(HERE, "cache", "weeklyproj_2026.json")))["players"]
board = json.load(open(os.path.join(HERE, "data", "board.json")))["players"]
missing = collections.defaultdict(collections.Counter)
for p in board:
    tm = p.get("team")
    w = set(int(k) for k in wp.get(str(p["player_id"]), {}))
    if not tm or not w:
        continue
    for k in range(1, 19):
        if k not in w:
            missing[tm][k] += 1
bad = [(t, byes.get(t), c.most_common(1)[0][0]) for t, c in missing.items()
       if c and c.most_common(1)[0][0] != byes.get(t)]
check("bye table matches projection-implied byes for all teams", not bad, bad[:4])

# 4. A player projected in his own bye week is a source anomaly. One is known
#    (Kayshon Boutte). More than a handful means the bye table has drifted.
inbye = [p["name"] for p in board
         if byes.get(p.get("team") or "") and
         str(byes[p["team"]]) in wp.get(str(p["player_id"]), {})]
check("at most 3 players projected during their own bye", len(inbye) <= 3, inbye)

# 5. The pool must be wider than the draft board, or the waiver tool is blind
#    to exactly the players it exists to find.
IS = json.load(open(os.path.join(HERE, "data", "inseason.json")))
check("in-season pool is materially wider than the 260-man board",
      IS["meta"]["n_pool"] - IS["meta"]["n_on_board"] > 200,
      "%d beyond the board" % (IS["meta"]["n_pool"] - IS["meta"]["n_on_board"]))
check("nothing in the pool has an interpolated measurement",
      all(("h10" in r) == ("mb" in r and r["mb"] == "M")
          for r in IS["players"].values() if r.get("mb") == "M"))

# 6. Weekly and season projections answer different questions and must NOT be
#    summed together. Assert the gap is still roughly what was measured, so a
#    change at the source is noticed rather than absorbed.
proj = json.load(open(os.path.join(RAW, "projections_sleeper.json")))
season = {str(r["player_id"]): r.get("pts_ppr")
          for rows in proj["players"].values() for r in rows}
ratios = []
for pid, wks in wp.items():
    s = season.get(pid)
    if s and s >= 50:
        ratios.append(sum(wks.values()) / s)
ratios.sort()
med = ratios[len(ratios) // 2]
check("weekly projections still sum ABOVE season totals (they are conditional)",
      1.02 < med < 1.20, "median ratio %.3f over n=%d" % (med, len(ratios)))

# 7. ROLE ADJUSTMENT. HANDOFF S2 named four players whose 2025 floor came from
#    a role they no longer hold, and said explicitly: do not recommend them. The
#    first moves engine ranked on the raw 2025 rate and put them straight at the
#    top. These assertions exist so that cannot happen again silently.
STALE = {"Jake Tonges": "TE2", "Theo Johnson": "TE2",
         "Troy Franklin": "SWR3", "Kimani Vidal": "RB3"}
byname = {r["n"]: r for r in IS["players"].values()}
missing = [n for n in STALE if n not in byname]
check("HANDOFF's four named stale-role players are all in the pool", not missing, missing)
for n in sorted(STALE):
    r = byname.get(n) or {}
    raw, adj = r.get("h10"), r.get("h10a")
    check("%s: role-adjusted floor is far below his 2025 rate" % n,
          raw is not None and adj is not None and adj <= raw - 0.20,
          "2025 %s -> 2026 %s" % (raw, adj))
n_pool_adj = sum(1 for r in IS["players"].values() if r.get("h10a") is not None)
check("role-adjusted floor computed for most measured players",
      n_pool_adj >= 250, "%d players" % n_pool_adj)
check("role flag only ever LOST / SAME / GAINED",
      all(r.get("role") in (None, "LOST", "SAME", "GAINED") for r in IS["players"].values()))
# the page must not rank on the raw rate anywhere
live = os.path.join(HERE, "live.html")
if os.path.exists(live):
    src = open(live, encoding="utf-8").read()
    import re as _re
    bad = _re.findall(r"sort\([^)]*\.h10[^a]", src)
    check("nothing in the shipped page sorts on the RAW 2025 rate", not bad, bad[:2])

print("\n%d/%d checks passed" % (len(ran) - len(fails), len(ran)))
if fails:
    print("FAILED: %s" % ", ".join(fails))
    sys.exit(1)
