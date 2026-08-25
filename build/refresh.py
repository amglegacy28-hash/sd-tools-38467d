"""One-shot refresh: pull every live source, rebuild the board, gate it, emit HTML.

Run by GitHub Actions on a schedule so the waiver screen keeps up without anyone
opening a laptop. Every source is public and keyless. If the assertions fail the
build STOPS - a stale-but-correct page beats a fresh broken one.
"""
import json, os, subprocess, sys, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')
CACHE = os.path.join(HERE, 'cache')
LEAGUE = '1389332111156088832'
UA = {'User-Agent': 'lionsden-refresh/1.0'}


def grab(url, path, label):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    open(path, 'wb').write(body)
    print("  %-26s %8.1f KB" % (label, len(body) / 1024))


def run(script, *args):
    print("\n>>> %s %s" % (script, " ".join(args)))
    r = subprocess.run([sys.executable, os.path.join(HERE, script)] + list(args),
                       capture_output=True, text=True, cwd=HERE)
    sys.stdout.write(r.stdout[-1500:])
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        raise SystemExit("FAILED: %s" % script)


if __name__ == '__main__':
    print("refresh started %s UTC\n" % datetime.datetime.utcnow().isoformat())
    print("live pulls:")
    grab("https://api.sleeper.app/v1/players/nfl", os.path.join(CACHE, 'players_nfl.json'), 'players/nfl')
    grab("https://api.sleeper.app/v1/league/%s/rosters" % LEAGUE,
         os.path.join(RAW, 'rosters_postdraft.json'), 'league rosters')
    grab("https://api.sleeper.app/v1/league/%s/users" % LEAGUE,
         os.path.join(RAW, 'league_users.json'), 'league users')

    for s in ('fetch_proj.py', 'fetch_adp.py', 'fetch_sleeper_adp.py', 'fetch_espn.py'):
        run(s)

    # ---- weekly data -----------------------------------------------------
    # Past seasons are settled and do not change, so they are fetched once and
    # then left alone. Re-pulling 72 requests of 2024 results twice a day is
    # pure waste.
    for season in (2024, 2025):
        if not os.path.exists(os.path.join(CACHE, 'weekly_%d_byweek.json' % season)):
            run('fetch_weekly.py', str(season))
        else:
            print("\n>>> weekly %d actuals already cached (history does not change)" % season)

    # What week is it, actually? Sleeper reports season_type "pre" WITH a week
    # number through August. Reading that as a regular-season week is exactly
    # the plausible-wrong number this project keeps getting caught by, so only
    # "regular" counts and everything else falls back to week 1.
    week, regular = 1, False
    try:
        req = urllib.request.Request("https://api.sleeper.app/v1/state/nfl", headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            state = json.loads(r.read())
        regular = state.get("season_type") == "regular"
        if regular:
            week = max(1, min(18, int(state.get("week") or 1)))
        print("\n  NFL state: %s season, week %s -> %s"
              % (state.get("season_type"), state.get("week"),
                 ("regular week %d" % week) if regular else "pre-season, treating as week 1"))
    except Exception as e:
        print("\n  NFL state unavailable (%r) - assuming week 1" % e)

    # In season, pull this year's actuals too, so the wire is judged on the role
    # a player has NOW and not the one he had last year.
    if regular:
        run('fetch_weekly.py', '2026')

    # Per-week projections change constantly, but only the weeks still ahead
    # matter. fetch_weekly_proj.py merges rather than overwrites, so weeks
    # already fetched survive.
    run('fetch_weekly_proj.py', '2026', '%d-18' % week)

    # ORDER MATTERS. fetch_news matches items against the board's player names, so
    # the board has to exist first. Running it earlier silently produced ZERO news
    # on a clean checkout - the file was there, the matching had nothing to match.
    run('model.py')
    try:
        run('fetch_news.py')
    except SystemExit:
        print("  news source unavailable - keeping the previous file rather than shipping none")
    run('variance.py')
    run('inseason.py')            # free-agency pool: every projected player, not
                                  # just the 260 that were worth drafting
    run('smoke_test.py')          # the gate: a failure here stops the deploy
    run('test_inseason.py')       # second gate, on the weekly data layer
    run('build_live.py')
    run('build_page.py')
    print("\nrefresh complete %s UTC" % datetime.datetime.utcnow().isoformat())
