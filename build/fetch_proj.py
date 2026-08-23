"""Pull season-long projections + Sleeper ADP. Source: Sleeper API (company: rotowire).

Stdlib only. Records the source company and last_modified date so the sheet can
cite them, per CLAUDE.md: never an unattributed number.
"""
import json, os, urllib.request, datetime

BASE = "https://api.sleeper.com/projections/nfl/2026?season_type=regular&position[]=%s&order_by=pts_ppr"
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")

def fetch(pos):
    req = urllib.request.Request(BASE % pos, headers={"User-Agent": "lionsden/0.1"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())

if __name__ == "__main__":
    out, meta = {}, {}
    for pos in ("QB", "RB", "WR", "TE"):
        rows = fetch(pos)
        keep = []
        for r in rows:
            s = r.get("stats") or {}
            if not s.get("pts_ppr"):
                continue
            p = r.get("player") or {}
            keep.append({
                "player_id": r["player_id"],
                "name": ("%s %s" % (p.get("first_name",""), p.get("last_name",""))).strip(),
                "pos": pos,
                "team": r.get("team"),
                "pts_ppr": s.get("pts_ppr"),
                "gp": s.get("gp"),
                "adp_ppr": s.get("adp_ppr"),
                "company": r.get("company"),
                "last_modified": r.get("last_modified"),
            })
        out[pos] = keep
        lm = max((k["last_modified"] for k in keep if k["last_modified"]), default=None)
        meta[pos] = {
            "n_with_projection": len(keep),
            "n_total_returned": len(rows),
            "company": sorted({k["company"] for k in keep}),
            "last_modified_utc": datetime.datetime.utcfromtimestamp(lm/1000).isoformat()+"Z" if lm else None,
        }
        print("  %-3s projected=%-4d of %-4d  source=%s  updated=%s"
              % (pos, len(keep), len(rows), meta[pos]["company"], meta[pos]["last_modified_utc"]))

    payload = {"pulled_at_utc": datetime.datetime.utcnow().isoformat()+"Z",
               "endpoint": BASE % "{POS}", "meta": meta, "players": out}
    with open(os.path.join(RAW, "projections_sleeper.json"), "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    tot = sum(len(v) for v in out.values())
    print("\n  total projected players: %d" % tot)
