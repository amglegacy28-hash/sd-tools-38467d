# Auto-refresh

`refresh.py` pulls every live source, rebuilds the board, runs the assertion
suite, and emits the two HTML pages. GitHub Actions runs it twice a day.

Sources are all public and keyless: Sleeper (projections, ADP, players, rosters),
FantasyFootballCalculator (ADP), ESPN (projections, rescored to this league),
Draft Sharks (player news).

**The assertions are a gate, not a report.** If `smoke_test.py` fails the job
stops and nothing is published. A stale-but-correct page beats a fresh broken one.

Order matters: `fetch_news.py` matches news items against the board's player
names, so `model.py` must run first. Running it earlier silently produced zero
news on a clean checkout.
