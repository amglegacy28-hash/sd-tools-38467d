"""Outcome variance and upside from REAL 2025 weekly scores.

Upside is measured POSITION-RELATIVE, against this league's own starter demand:
in any given week the baseline at each position is the score of the Nth-best
player there, where N is how many that position actually starts league-wide
(QB12 / RB31 / WR51 / TE14, from model.py). "Startable" therefore means what it
means in THIS league, not against a position-blind points threshold.

Players without >=8 games of 2025 history are LABELLED, never interpolated.
"""
import json, os, statistics, collections
import weeklystats

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
MIN_GAMES = 8
SEASON = 2025


def weekly_baselines(weekly_by_week, pid_pos, starters):
    """Per REAL week, per position: the score of the Nth-best player = startable line.

    `weekly_by_week` is {pid: {int week: pts}}. It used to be a bare list whose
    INDEX was read as the week; it is not, because a player only has an entry for
    weeks he recorded stats. See fetch_weekly.py for the measured damage.

    A week with fewer than N players at a position has no Nth-best player. The
    old code fell back to `vals[len(vals)-1]` - the WORST player present - which
    silently turned the startable line into a floor that everybody cleared. That
    week is now reported as having NO baseline, and callers skip it.
    """
    byweek = collections.defaultdict(lambda: collections.defaultdict(list))
    for pid, wks in weekly_by_week.items():
        pos = pid_pos.get(pid)
        if not pos:
            continue
        for wk, pts in wks.items():
            byweek[int(wk)][pos].append(pts)
    base, thin = {}, []
    for wk, posmap in byweek.items():
        base[wk] = {}
        for pos, vals in posmap.items():
            n = starters.get(pos, 12)
            if len(vals) < n:
                thin.append((wk, pos, len(vals), n))
                continue
            vals.sort(reverse=True)
            base[wk][pos] = vals[n - 1]
    return base, thin


def build():
    weekly, wmeta = weeklystats.points_by_week(SEASON)
    board = json.load(open(os.path.join(HERE, "data", "board.json")))
    starters = board["starters_consumed"]
    pid_pos = {str(p["player_id"]): p["pos"] for p in board["players"]}
    # positions for baseline need the whole league, not just board players
    allproj = json.load(open(os.path.join(HERE, "data", "raw", "projections_sleeper.json")))
    for pos, rows in allproj["players"].items():
        for r in rows:
            pid_pos.setdefault(str(r["player_id"]), pos)

    base, thin = weekly_baselines(weekly, pid_pos, starters)
    if thin:
        print("weeks with too few players to define a startable line (skipped, not faked):")
        for wk, pos, have, need in sorted(thin):
            print("   wk%-3d %-3s %d present, need %d" % (wk, pos, have, need))

    out, by_pos = {}, collections.defaultdict(list)
    for p in board["players"]:
        pid = str(p["player_id"])
        wks = weekly.get(pid, {})
        g = [v for _, v in sorted(wks.items())]
        if len(g) >= MIN_GAMES:
            srt = sorted(g)
            # Only weeks that HAVE a defensible baseline count, in numerator and
            # denominator alike. A week we cannot judge is dropped, not passed.
            judged = [(wk, pts) for wk, pts in sorted(wks.items())
                      if base.get(int(wk), {}).get(p["pos"]) is not None]
            startable = (sum(1 for wk, pts in judged
                             if pts >= base[int(wk)][p["pos"]]) / len(judged)) if judged else None
            rec = {"basis": "MEASURED", "games": len(g),
                   "weeks_judged": len(judged),
                   "mean": round(statistics.mean(g), 1),
                   "sd": round(statistics.pstdev(g), 1),
                   "ceiling": round(srt[int(len(srt) * 0.85)], 1),
                   "floor": round(srt[int(len(srt) * 0.15)], 1),
                   "startable_rate": (round(startable, 2) if startable is not None else None),
                   # A bench player's real job: clear 10 points in a spot start.
                   # Season projection cannot see this - 140 points spread over 17
                   # quiet weeks is useless in a bye week.
                   "hit10": round(sum(1 for x in g if x >= 10) / len(g), 2),
                   "hit15": round(sum(1 for x in g if x >= 15) / len(g), 2)}
            by_pos[p["pos"]].append(rec)
        else:
            rec = {"basis": "NO 2025 HISTORY", "games": len(g), "fallback": "positional median"}
        out[p["player_id"]] = rec

    fallback = {pos: {"startable_rate": round(statistics.median(
                          [r["startable_rate"] for r in recs if r["startable_rate"] is not None]), 2),
                      "sd": round(statistics.median(r["sd"] for r in recs), 1),
                      "n_measured": len(recs)}
                for pos, recs in by_pos.items()}
    json.dump({"min_games": MIN_GAMES, "season": SEASON,
               "weekly_source": wmeta,
               "definition":
               "startable_rate = share of the player's JUDGED 2025 weeks in which he "
               "outscored this league's own baseline at his position that real week "
               "(QB12/RB31/WR51/TE14). A week with fewer than N players at the position "
               "has no baseline and is excluded from numerator and denominator; "
               "weeks_judged reports how many weeks actually counted.",
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
