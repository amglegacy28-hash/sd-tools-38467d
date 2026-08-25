"""One way to read weekly actuals, so nothing re-invents the week-index bug.

fetch_weekly.py writes {pid: {week: {"p": pts, "s": snaps, "o": opp}}}. Anything
that needs weekly numbers goes through here. `points_by_week` is the honest
primitive; `points_list` exists only for callers that genuinely do not care about
which week a score came from (hit rates, dispersion) - and it is named so that a
caller who DOES care cannot reach for it by accident.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")


def path(season):
    return os.path.join(CACHE, "weekly_%d_byweek.json" % season)


def load(season):
    """Full payload. Raises if the season was never fetched - never silently empty."""
    fp = path(season)
    if not os.path.exists(fp):
        raise FileNotFoundError(
            "no weekly cache for %d. Run: python3 fetch_weekly.py %d" % (season, season))
    return json.load(open(fp))


def points_by_week(season):
    """{pid: {int week: points}} - the only safe form for anything per-week."""
    d = load(season)
    return {pid: {int(w): r["p"] for w, r in wks.items()}
            for pid, wks in d["players"].items()}, d["meta"]


def points_list(season):
    """{pid: [points]} in week order. Week identity is DISCARDED - use only for
    order-independent statistics (hit rates, mean, sd)."""
    byw, meta = points_by_week(season)
    return {pid: [v for _, v in sorted(wks.items())] for pid, wks in byw.items()}, meta


def snaps_by_week(season):
    d = load(season)
    return {pid: {int(w): r["s"] for w, r in wks.items() if "s" in r}
            for pid, wks in d["players"].items()}
