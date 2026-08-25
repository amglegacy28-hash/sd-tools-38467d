"""Per-WEEK projections. The in-season half of the projection picture.

The draft tool only ever needed season totals. A waiver tool does not: "who helps
me THIS week" and "who should I stash for NEXT week" are different questions from
"who is best over the season", and a season total cannot answer either. A player
on bye in week 6 has a fine season projection and is worth nothing to you that
week.

Source is Sleeper's own projections endpoint, the same provider as the season
numbers already in data/raw/projections_sleeper.json, so weekly and season views
do not disagree for sourcing reasons.

Shape: {"meta": {...}, "players": {pid: {"6": 12.4, "7": 11.8}}}
Weeks that return nothing go in meta.weeks_empty. A player absent from a week is
absent - not zero. Callers must distinguish "projected zero" from "not projected",
because a bye week and a missing fetch look identical if you coerce them.
"""
import json, os, sys, time, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
POS = ("QB", "RB", "WR", "TE")
ENDPOINT = ("https://api.sleeper.com/projections/nfl/%d/%d?season_type=regular"
            "&position[]=%s&order_by=pts_ppr")


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lionsden/0.2"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def path(season):
    return os.path.join(CACHE, "weeklyproj_%d.json" % season)


def fetch(season, weeks, verbose=True):
    players, empty, got = {}, [], []
    for wk in weeks:
        n = 0
        for pos in POS:
            try:
                rows = get(ENDPOINT % (season, wk, pos))
            except Exception as e:
                print("   %d wk%-2d %-3s FAILED %r" % (season, wk, pos, e))
                continue
            for r in rows:
                pid = r.get("player_id")
                pts = (r.get("stats") or {}).get("pts_ppr")
                if pid is None or pts is None:
                    continue
                players.setdefault(str(pid), {})[str(r.get("week", wk))] = round(pts, 2)
                n += 1
            time.sleep(0.05)
        (got if n else empty).append(wk)
        if verbose:
            print("   %d week %-2d  %d projections" % (season, wk, n))
    return players, got, empty


def merge_save(season, players, got, empty):
    """Merge into any existing file so an in-season partial refresh does not
    destroy the weeks it did not ask for."""
    fp = path(season)
    prev = json.load(open(fp)) if os.path.exists(fp) else {"players": {}, "meta": {}}
    for pid, wks in players.items():
        prev["players"].setdefault(pid, {}).update(wks)
    prevgot = set(prev["meta"].get("weeks_with_data") or [])
    prev["meta"] = {
        "season": season, "endpoint": ENDPOINT,
        "weeks_with_data": sorted(prevgot | set(got)),
        "weeks_empty_last_run": empty,
        "fetched_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "per-week PPR projections; a player absent from a week is not projected, not zero",
    }
    json.dump(prev, open(fp, "w"))
    return prev


if __name__ == "__main__":
    season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    if len(sys.argv) > 2:
        weeks = [int(w) for w in sys.argv[2].split("-")]
        weeks = range(weeks[0], (weeks[-1] if len(weeks) > 1 else weeks[0]) + 1)
    else:
        weeks = range(1, 19)
    print("weekly projections %d, weeks %d..%d:" % (season, weeks[0], weeks[-1]))
    pl, got, empty = fetch(season, weeks)
    out = merge_save(season, pl, got, empty)
    print("  players=%d  weeks_with_data=%s  empty_this_run=%s"
          % (len(out["players"]), out["meta"]["weeks_with_data"], empty))
