"""The board: replacement level MEASURED from starter demand, VOR, tiers.

No assumed positional values. Replacement is derived by filling this league's
actual 12 x (1QB/2RB/2WR/1TE/3FLEX) starter demand greedily from the projection,
then taking the next man at each position. See BRIEF.md S4.1.
"""
import json, os, re, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")

TEAMS = 12
FLEX_ELIGIBLE = ("RB", "WR", "TE")


def norm(name):
    """Normalise a player name for cross-source matching."""
    n = name.lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\.?\b", "", n)
    n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


def load():
    proj = json.load(open(os.path.join(RAW, "projections_sleeper.json")))
    # Second, independent source. Rotowire alone was driving the roster shape:
    # ESPN projects top-60 RBs +29.6 points higher on average, and TEs 6 lower,
    # so a Rotowire-only board systematically under-drafts backs and over-drafts
    # tight ends. Neither source has evidence of being the better one, so they
    # are averaged with equal weight and single-source players are flagged.
    try:
        espn = json.load(open(os.path.join(RAW, "projections_espn.json")))["players"]
        espn_n = {norm(k): v for k, v in espn.items()}
    except FileNotFoundError:
        espn_n = {}
    ffc = json.load(open(os.path.join(RAW, "adp_ffc.json")))
    league = json.load(open(os.path.join(RAW, "league.json")))
    players = []
    n_blend = n_single = 0
    for pos, rows in proj["players"].items():
        for r in rows:
            d = dict(r)
            e = espn_n.get(norm(d["name"]))
            if e and e["pos"] == pos:
                d["pts_roto"] = d["pts_ppr"]
                d["pts_espn"] = e["pts"]
                d["pts_ppr"] = round((d["pts_roto"] + d["pts_espn"]) / 2.0, 1)
                d["src"] = "blend"
                d["src_gap"] = round(d["pts_espn"] - d["pts_roto"], 1)
                n_blend += 1
            else:
                d["pts_roto"] = d["pts_ppr"]; d["pts_espn"] = None
                d["src"] = "rotowire only"; d["src_gap"] = None
                n_single += 1
            players.append(d)
    print("projection blend: %d players from BOTH sources, %d from Rotowire alone"
          % (n_blend, n_single))
    ffc_by = {}
    for p in ffc["players"]:
        ffc_by[norm(p["name"])] = p
    matched = 0
    for p in players:
        f = ffc_by.get(norm(p["name"]))
        if f and f["position"] == p["pos"]:
            p["ffc_adp"] = f["adp"]
            p["ffc_stdev"] = f.get("stdev")
            p["ffc_high"] = f.get("high")
            p["ffc_low"] = f.get("low")
            matched += 1
        else:
            p["ffc_adp"] = None
    # ADP BLEND. Survival runs on this, not on FFC alone. Measured against last
    # year's real 180 picks in this league: FFC alone mean error 13.37 / 90th
    # 36.50, Sleeper alone 14.00 / 35.10, the average 11.40 / 27.50. Sleeper is
    # typically closer (better median at every position) but has fatter tails;
    # FFC is steadier but biased - it puts tight ends about 21 ranks later than
    # Sleeper drafters actually take them. Averaging beats either.
    for p in players:
        if p.get("sleeper_adp") is None:
            _s = p.get("adp_ppr")
            p["sleeper_adp"] = _s if (_s and _s < 400) else None
        sa = p.get("sleeper_adp") if p.get("sleeper_adp") and p["sleeper_adp"] < 400 else None
        fa = p.get("ffc_adp")
        p["adp_blend"] = round((fa + sa) / 2.0, 1) if (fa and sa) else (fa or sa)
    return players, proj, ffc, league, matched


def starter_demand(league):
    from collections import Counter
    rp = Counter(league["roster_positions"])
    return {"QB": rp.get("QB", 0), "RB": rp.get("RB", 0), "WR": rp.get("WR", 0),
            "TE": rp.get("TE", 0), "FLEX": rp.get("FLEX", 0)}


def replacement_levels(players, demand):
    """Fill base starters, then allocate FLEX greedily to the best available."""
    by_pos = {}
    for p in players:
        by_pos.setdefault(p["pos"], []).append(p)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda x: -x["pts_ppr"])

    used = {pos: demand.get(pos, 0) * TEAMS for pos in ("QB", "RB", "WR", "TE")}
    flex_slots = demand["FLEX"] * TEAMS
    cursor = dict(used)
    flex_taken = {"RB": 0, "WR": 0, "TE": 0}
    for _ in range(flex_slots):
        best, best_pos = None, None
        for pos in FLEX_ELIGIBLE:
            i = cursor[pos]
            if i < len(by_pos.get(pos, [])):
                cand = by_pos[pos][i]
                if best is None or cand["pts_ppr"] > best["pts_ppr"]:
                    best, best_pos = cand, pos
        if best is None:
            break
        cursor[best_pos] += 1
        flex_taken[best_pos] += 1

    repl = {}
    for pos in ("QB", "RB", "WR", "TE"):
        idx = cursor[pos]              # next man after the last starter
        lst = by_pos.get(pos, [])
        repl[pos] = lst[idx]["pts_ppr"] if idx < len(lst) else (lst[-1]["pts_ppr"] if lst else 0.0)
    return repl, cursor, flex_taken, by_pos


def kmeans_1d(values, k, iters=60):
    """Deterministic 1-D k-means (Jenks-style natural breaks) on a sorted list."""
    if len(values) <= k:
        return list(range(len(values)))
    lo, hi = min(values), max(values)
    cents = [lo + (hi - lo) * i / (k - 1) for i in range(k)]
    assign = [0] * len(values)
    for _ in range(iters):
        changed = False
        for i, v in enumerate(values):
            best = min(range(k), key=lambda c: abs(v - cents[c]))
            if best != assign[i]:
                assign[i] = best
                changed = True
        for c in range(k):
            grp = [v for v, a in zip(values, assign) if a == c]
            if grp:
                cents[c] = sum(grp) / len(grp)
        if not changed:
            break
    return assign


def apply_tiers(rows, k, field):
    """Assign contiguous tier numbers down a VOR-sorted list."""
    if not rows:
        return
    assign = kmeans_1d([r["vor"] for r in rows], k)
    t, prev = 1, assign[0]
    for r, a in zip(rows, assign):
        if a != prev:
            t += 1
            prev = a
        r[field] = t


def main():
    players, proj, ffc, league, matched = load()
    demand = starter_demand(league)
    repl, cursor, flex_taken, by_pos = replacement_levels(players, demand)

    print("STARTER DEMAND (12 teams):", demand)
    print("\nFLEX allocation - which positions actually won the 36 flex spots:")
    for pos, n in sorted(flex_taken.items(), key=lambda kv: -kv[1]):
        print("   %-3s %2d of 36" % (pos, n))
    print("\nSTARTERS CONSUMED, and therefore REPLACEMENT LEVEL:")
    for pos in ("QB", "RB", "WR", "TE"):
        print("   %-3s starters=%-3d  replacement = %s%d at %6.1f pts"
              % (pos, cursor[pos], pos, cursor[pos]+1, repl[pos]))

    for p in players:
        p["vor"] = round(p["pts_ppr"] - repl[p["pos"]], 1)

    # PER-SOURCE VOR. Each source gets its OWN replacement levels, derived the
    # same way from this league's starter demand, so "what would ESPN draft" is
    # a real independent answer and not the blend wearing a different hat.
    for key, field in (("roto", "pts_roto"), ("espn", "pts_espn")):
        sub = [dict(q, pts_ppr=q[field]) for q in players if q.get(field)]
        if len(sub) < 100:
            continue
        r2, c2, f2, _ = replacement_levels(sub, demand)
        for p in players:
            v = p.get(field)
            p["vor_" + key] = round(v - r2[p["pos"]], 1) if v else None
        print("  %-5s replacement: QB%d %.0f  RB%d %.0f  WR%d %.0f  TE%d %.0f"
              % (key, c2["QB"]+1, r2["QB"], c2["RB"]+1, r2["RB"],
                 c2["WR"]+1, r2["WR"], c2["TE"]+1, r2["TE"]))

    # cover a full 180-pick draft plus a bench-depth buffer
    board = sorted(players, key=lambda x: -x["vor"])[:260]
    apply_tiers(board, 14, "tier")
    for pos in ("QB", "RB", "WR", "TE"):
        grp = [p for p in board if p["pos"] == pos]
        apply_tiers(grp, min(9, max(2, len(grp) // 6)), "pos_tier")

    out = {
        "generated_from": {
            "projections": {"source": "BLEND: Rotowire (via Sleeper) and ESPN, equal weight, rescored to full PPR",
                            "updated_utc": proj["meta"]["RB"]["last_modified_utc"],
                            "endpoint": proj["endpoint"]},
            "adp_ffc": {"source": "FantasyFootballCalculator API, PPR 12-team",
                        "drafts": ffc["meta"]["total_drafts"],
                        "window": "%s..%s" % (ffc["meta"]["start_date"], ffc["meta"]["end_date"]),
                        "url": ffc["_provenance"]["url"]},
            "adp_sleeper": {"source": "Sleeper API stats.adp_ppr (same payload as projections)"},
        },
        "league": {"teams": TEAMS, "roster": league["roster_positions"],
                   "scoring": "full PPR (rec 1.0), pass_td 4, no TE premium"},
        "replacement": repl, "starters_consumed": cursor, "flex_allocation": flex_taken,
        "tier_method": "1-D k-means natural breaks on VOR (k=14 overall, per-position k<=9)",
        "ffc_matched": matched,
        "players": board,
        "model_limit": "Median-point VOR is reliable through ~pick 120. Beyond that the market buys upside/handcuff contingency that median projections do not price; late-round ordering is NOT trustworthy yet.",
    }
    # --- market comparison: FFC vs Sleeper's own ADP, and value in POINTS ---
    byvor = sorted(board, key=lambda x: -x["vor"])
    def vor_at(rank):
        i = max(0, min(len(byvor) - 1, int(round(rank)) - 1))
        return byvor[i]["vor"]
    for p in board:
        # Sleeper uses 999.0 as a sentinel for "no ADP / undrafted" - not a value.
        sa = p.get("adp_ppr")
        p["sleeper_adp"] = sa if (sa and sa < 400) else None
        a = p.get("ffc_adp") or p.get("sleeper_adp")
        # value denominated in projected points, NOT rank: near replacement the
        # VOR curve is flat and rank deltas exaggerate wildly.
        p["edge_pts"] = round(p["vor"] - vor_at(a), 1) if a else None
        if p.get("ffc_adp") and p.get("sleeper_adp"):
            p["adp_disagree"] = round(p["sleeper_adp"] - p["ffc_adp"], 1)
        else:
            p["adp_disagree"] = None
    # honest zone flag: median-point VOR degrades badly after ~pick 120
    for p in board:
        a = p.get("ffc_adp") or p.get("sleeper_adp") or 999
        p["zone"] = "core" if a <= 120 else "lottery"

    with open(os.path.join(HERE, "data", "board.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print("ADP name-match: %d of %d FFC players matched to a projection" % (matched, len(ffc["players"])))
    print("board.json written: %d players" % len(board))


if __name__ == "__main__":
    main()
