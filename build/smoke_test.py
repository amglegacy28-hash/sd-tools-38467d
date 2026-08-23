"""Assertions on the board. Cross-checks turned into tests, per BRIEF.md S5.4."""
import json, os, sys, re
HERE = os.path.dirname(os.path.abspath(__file__))
B = json.load(open(os.path.join(HERE, "data", "board.json")))
RAW = os.path.join(HERE, "data", "raw")
fails = []

def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (("  -- " + detail) if detail else ""))
    if not cond:
        fails.append(name)

# 1. starter demand must reconcile exactly: 12 teams x 9 starting slots = 108
sc = B["starters_consumed"]
total = sum(sc.values())
check("starters consumed == 12 teams x 9 starters == 108", total == 108, "got %d (%s)" % (total, sc))

# 2. flex allocation must equal 3 x 12 = 36
flex = sum(B["flex_allocation"].values())
check("flex spots allocated == 36", flex == 36, "got %d" % flex)

# 3. this league has no K/DEF - none may appear on the board
bad = [p["name"] for p in B["players"] if p["pos"] not in ("QB", "RB", "WR", "TE")]
check("no K/DEF on the board (league has no such slots)", not bad, str(bad[:5]))

# 4. board must cover a full 180-pick draft
check("board covers >= 180 players", len(B["players"]) >= 180, "got %d" % len(B["players"]))

# 5. VOR must be monotonically non-increasing (board is sorted by it)
v = [p["vor"] for p in B["players"]]
check("board sorted by VOR descending", all(v[i] >= v[i+1] for i in range(len(v)-1)))

# 6. tiers must be contiguous and non-decreasing down the board
t = [p["tier"] for p in B["players"]]
check("tiers non-decreasing down the board", all(t[i] <= t[i+1] for i in range(len(t)-1)))
check("tier numbering starts at 1", t[0] == 1, "starts at %d" % t[0])

# 7. every player carries a projection source
check("every player has pts_ppr", all(isinstance(p.get("pts_ppr"), (int, float)) for p in B["players"]))
check("provenance recorded for projections and ADP",
      bool(B["generated_from"]["projections"]["updated_utc"]) and bool(B["generated_from"]["adp_ffc"]["window"]))

# 8. CROSS-CHECK vs an independent source: VOR rank should correlate strongly with
#    market ADP. Strong-but-imperfect is the expected signature; either extreme is a bug.
pairs = [(i, p["ffc_adp"]) for i, p in enumerate(B["players"]) if p.get("ffc_adp")]
n = len(pairs)
adp_rank = {id(x): r for r, x in enumerate(sorted(pairs, key=lambda z: z[1]))}
d2 = sum((vr - adp_rank[id(x)]) ** 2 for vr, x in [(i, x) for i, x in enumerate(sorted(pairs, key=lambda z: z[0]))])
rho = 1 - (6 * d2) / (n * (n * n - 1))
check("VOR rank vs FFC ADP rank: Spearman rho in [0.60, 0.98]", 0.60 <= rho <= 0.98, "rho=%.3f over n=%d" % (rho, n))

# 9. last year's draft in THIS league: 180 picks, all skill, no K/DEF - the
#    empirical basis for check 3.
picks = json.load(open(os.path.join(RAW, "prior_draft_picks.json")))
pos = {p["metadata"].get("position") for p in picks}
check("prior draft: exactly 180 picks", len(picks) == 180, "got %d" % len(picks))
check("prior draft: no K/DEF was ever drafted", pos <= {"QB", "RB", "WR", "TE"}, str(sorted(pos)))

print("\n%d/%d checks passed" % (9 + 4 - len(fails), 13))
sys.exit(1 if fails else 0)
