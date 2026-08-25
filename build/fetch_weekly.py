"""Weekly actuals, KEYED BY REAL WEEK NUMBER.

Replaces the weekly half of fetch_extras.py, which appended scores to a bare
list per player. That list contained only the weeks a player recorded stats, so
its index was NOT the week number - 574 of 575 players in the 2025 cache have
fewer than 18 entries. variance.py read the index as the week and built its
per-week positional baselines from a mixture of different real weeks. Measured
effect: the WR bucket fell from 172 players at index 0 to 15 at index 16, so the
"WR51" startable line decayed from 9.5 to 1.5 and late buckets passed almost
everybody. hit10/hit15 were unaffected (order-independent), but startable_rate
was wrong wherever it mattered most.

Also keeps what the old fetcher threw away: offensive snaps, games active, and
the opponent. In season those are the evidence that a player's role is real NOW,
which a prior-year scoring rate cannot see.

Shape:
  {"meta": {...}, "players": {pid: {"4": {"p": 12.3, "s": 41, "o": "TEN"}}}}

Weeks that return nothing are recorded in meta.weeks_empty, never as zeros. A
week the NFL has not played yet is missing data, not a week everybody scored 0.
"""
import json, os, sys, time, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
POS = ("QB", "RB", "WR", "TE")
ENDPOINT = ("https://api.sleeper.com/stats/nfl/%d/%d?season_type=regular"
            "&position[]=%s&order_by=pts_ppr")


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "lionsden/0.2"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read())
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def fetch_season(season, weeks=range(1, 19), verbose=True):
    players, empty, got = {}, [], []
    for wk in weeks:
        rows = []
        for pos in POS:
            try:
                rows += get(ENDPOINT % (season, wk, pos))
            except Exception as e:
                print("   %d wk%-2d %-3s FAILED %r" % (season, wk, pos, e))
            time.sleep(0.05)
        n = 0
        for r in rows:
            pid = r.get("player_id")
            st = r.get("stats") or {}
            pts = st.get("pts_ppr")
            # Trust the row's own week field over the loop counter.
            w = r.get("week", wk)
            if pid is None or pts is None:
                continue
            rec = {"p": round(pts, 2)}
            if st.get("off_snp") is not None:
                rec["s"] = int(st["off_snp"])
            if r.get("opponent"):
                rec["o"] = r["opponent"]
            players.setdefault(str(pid), {})[str(w)] = rec
            n += 1
        (got if n else empty).append(wk)
        if verbose:
            print("   %d week %-2d  %d player-games" % (season, wk, n))
    meta = {"season": season, "endpoint": ENDPOINT,
            "weeks_with_data": got, "weeks_empty": empty,
            "fetched_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "note": "week keys are the real NFL week from the API row, not a list index"}
    return {"meta": meta, "players": players}


def path(season):
    return os.path.join(CACHE, "weekly_%d_byweek.json" % season)


def main(seasons):
    for s in seasons:
        print("season %d:" % s)
        out = fetch_season(s)
        json.dump(out, open(path(s), "w"))
        m = out["meta"]
        n8 = sum(1 for v in out["players"].values() if len(v) >= 8)
        print("  players=%d  with>=8wk=%d  weeks_with_data=%s  weeks_empty=%s\n"
              % (len(out["players"]), n8, m["weeks_with_data"], m["weeks_empty"]))


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]] or [2024, 2025]
    main(args)
