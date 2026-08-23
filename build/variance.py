"""Outcome variance and upside from REAL 2025 weekly scores.

Upside is measured POSITION-RELATIVE, against this league's own starter demand:
in any given week the baseline at each position is the score of the Nth-best
player there, where N is how many that position actually starts league-wide
(QB12 / RB31 / WR51 / TE14, from model.py). "Startable" therefore means what it
means in THIS league, not against a position-blind points threshold.

Players without >=8 games of 2025 history are LABELLED, never interpolated.
"""
import json, os, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
MIN_GAMES = 8


def weekly_baselines(weekly, pid_pos, starters):
    """Per week, per position: the score of the Nth-best player = startable line."""
    byweek = collections.defaultdict(lambda: collections.defaultdict(list))
    for pid, games in weekly.items():
        pos = pid_pos.get(pid)
        if not pos:
            continue
        for wk, pts in enumerate(games):
            byweek[wk][pos].append(pts)
    base = {}
    for wk, posmap in byweek.items():
        base[wk] = {}
        for pos, vals in posmap.items():
            vals.sort(reverse=True)
            n = starters.get(pos, 12)
            base[wk][pos] = vals[min(n - 1, len(vals) - 1)]
    return base


def build():
    weekly = json.load(open(os.path.join(CACHE, "weekly_2025.json")))
    board = json.load(open(os.path.join(HERE, "data", "board.json")))
    starters = board["starters_consumed"]
    pid_pos = {str(p["player_id"]): p["pos"] for p in board["players"]}
    # positions for baseline need the whole league, not just board players
    allproj = json.load(open(os.path.join(HERE, "data", "raw", "projections_sleeper.json")))
    for pos, rows in allproj["players"].items():
        for r in rows:
            pid_pos.setdefault(str(r["player_id"]), pos)

    base = weekly_baselines(weekly, pid_pos, starters)

    out, by_pos = {}, collections.defaultdict(list)
    for p in board["players"]:
        pid = str(p["player_id"])
        g = weekly.get(pid, [])
        if len(g) >= MIN_GAMES:
            srt = sorted(g)
            startable = sum(1 for wk, pts in enumerate(g)
                            if pts >= base.get(wk, {}).get(p["pos"], 99)) / len(g)
            rec = {"basis": "MEASURED", "games": len(g),
                   "mean": round(statistics.mean(g), 1),
                   "sd": round(statistics.pstdev(g), 1),
                   "ceiling": round(srt[int(len(srt) * 0.85)], 1),
                   "floor": round(srt[int(len(srt) * 0.15)], 1),
                   "startable_rate": round(startable, 2),
                   # A bench player's real job: clear 10 points in a spot start.
                   # Season projection cannot see this - 140 points spread over 17
                   # quiet weeks is useless in a bye week.
                   "hit10": round(sum(1 for x in g if x >= 10) / len(g), 2),
                   "hit15": round(sum(1 for x in g if x >= 15) / len(g), 2)}
            by_pos[p["pos"]].append(rec)
        else:
            rec = {"basis": "NO 2025 HISTORY", "games": len(g), "fallback": "positional median"}
        out[p["player_id"]] = rec

    fallback = {pos: {"startable_rate": round(statistics.median(r["startable_rate"] for r in recs), 2),
                      "sd": round(statistics.median(r["sd"] for r in recs), 1),
                      "n_measured": len(recs)}
                for pos, recs in by_pos.items()}
    json.dump({"min_games": MIN_GAMES, "definition":
               "startable_rate = share of 2025 weeks the player outscored this league's "
               "own weekly starter baseline at his position (QB12/RB31/WR51/TE14)",
               "fallback_by_pos": fallback, "players": out},
              open(os.path.join(HERE, "data", "variance.json"), "w"), indent=2, sort_keys=True)
    return out, fallback, board


if __name__ == "__main__":
    out, fb, board = build()
    meas = sum(1 for r in out.values() if r["basis"] == "MEASURED")
    print("measured: %d of %d board players | no 2025 history: %d\n" % (meas, len(out), len(out) - meas))
    print("positional medians (startable = beat this league's weekly starter line):")
    for pos, v in sorted(fb.items()):
        print("   %-3s startable_rate=%.2f  weekly sd=%-5.1f  (n=%d)" % (pos, v["startable_rate"], v["sd"], v["n_measured"]))
    print("\nLATE UPSIDE (ADP > 100) that median VOR could not see:")
    print("%-22s %-4s %-7s %-8s %-8s %-7s %s" % ("player","pos","adp","startbl","ceiling","sd","vor"))
    rows = []
    for p in board["players"]:
        a = p.get("ffc_adp") or p.get("sleeper_adp")
        r = out.get(p["player_id"])
        if a and a > 100 and r and r["basis"] == "MEASURED" and r["games"] >= 10:
            rows.append((r["startable_rate"], r["ceiling"], p["name"], p, r))
    for sr, ce, nm, p, r in sorted(rows, key=lambda x: (-x[0], -x[1]))[:14]:
        print("%-22s %-4s %-7.1f %-8.2f %-8.1f %-7.1f %.0f"
              % (nm, p["pos"], p.get("ffc_adp") or 0, sr, ce, r["sd"], p["vor"]))
