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


def run(script):
    print("\n>>> %s" % script)
    r = subprocess.run([sys.executable, os.path.join(HERE, script)],
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

    # ORDER MATTERS. fetch_news matches items against the board's player names, so
    # the board has to exist first. Running it earlier silently produced ZERO news
    # on a clean checkout - the file was there, the matching had nothing to match.
    run('model.py')
    try:
        run('fetch_news.py')
    except SystemExit:
        print("  news source unavailable - keeping the previous file rather than shipping none")
    run('variance.py')
    run('smoke_test.py')          # the gate: a failure here stops the deploy
    run('build_live.py')
    run('build_page.py')
    print("\nrefresh complete %s UTC" % datetime.datetime.utcnow().isoformat())
