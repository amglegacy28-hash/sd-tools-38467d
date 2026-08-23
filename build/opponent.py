"""Opponent model. Measured where measurable, labelled where not (BRIEF.md S3)."""
import json, os, re, statistics, random

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")

BASIS = {"Allos": "MEASURED", "Antonio93": "MEASURED", "LewisS19": "MEASURED",
         "PeterPlays": "MEASURED", "mstasik": "MEASURED",
         "CaptFilipina": "THIN", "mondaymorningtears23": "THIN", "KHUFF1": "THIN",
         "BigPoppaTrash": "COACHED", "lenall": "COACHED", "GLat3": "NO HISTORY",
         "Gunit28": "SELF"}
# Giovanni, 2026-08-20: commish (Antonio93) will be advising these two in person.
COACHED_BY = {"BigPoppaTrash": "Antonio93", "lenall": "Antonio93"}


def norm(n):
    n = n.lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\.?\b", "", n)
    n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


def load_prior():
    picks = json.load(open(os.path.join(RAW, "prior_draft_picks.json")))
    users = {u["user_id"]: u["display_name"] for u in json.load(open(os.path.join(RAW, "prior_league_users.json")))}
    adp25 = json.load(open(os.path.join(RAW, "adp_ffc_2025.json")))
    adp_by = {norm(p["name"]): p for p in adp25["players"]}
    rows = []
    for p in picks:
        md = p.get("metadata") or {}
        nm = ("%s %s" % (md.get("first_name", ""), md.get("last_name", ""))).strip()
        a = adp_by.get(norm(nm))
        rows.append({"pick": p["pick_no"], "round": p["round"],
                     "manager": users.get(p.get("picked_by"), "?"),
                     "name": nm, "pos": md.get("position"),
                     "adp": a["adp"] if a else None})
    return rows, adp25


def tendencies(rows):
    """Per-manager: reach vs ADP, and positional mix. Measured only."""
    out = {}
    by_mgr = {}
    for r in rows:
        by_mgr.setdefault(r["manager"], []).append(r)
    for mgr, rs in by_mgr.items():
        deltas = [r["pick"] - r["adp"] for r in rs if r["adp"]]
        pos = {}
        for r in rs:
            pos[r["pos"]] = pos.get(r["pos"], 0) + 1
        early = [r for r in rs if r["round"] <= 6]
        edeltas = [r["pick"] - r["adp"] for r in early if r["adp"]]
        out[mgr] = {
            "n_picks": len(rs), "n_matched_adp": len(deltas),
            # negative = reaches (drafts ahead of ADP); positive = waits
            "reach_mean": round(statistics.mean(deltas), 2) if deltas else None,
            "reach_sd": round(statistics.pstdev(deltas), 2) if len(deltas) > 1 else None,
            "reach_early": round(statistics.mean(edeltas), 2) if edeltas else None,
            "pos_mix": pos,
        }
    return out


if __name__ == "__main__":
    rows, adp25 = load_prior()
    m = adp25["meta"]
    matched = sum(1 for r in rows if r["adp"])
    print("2025 ADP: %d drafts, window %s..%s  (draft was 2025-08-16 -- ADP POSTDATES IT)"
          % (m["total_drafts"], m["start_date"], m["end_date"]))
    print("picks matched to a 2025 ADP: %d of 180\n" % matched)
    t = tendencies(rows)
    print("MEASURED TENDENCY, last year, this league")
    print("(reach: negative = takes players EARLIER than ADP)")
    print("%-22s %-7s %-9s %-9s %-9s %s" % ("manager", "picks", "reach", "sd", "R1-6", "positions"))
    order = sorted(t.items(), key=lambda kv: (kv[1]["reach_mean"] is None, kv[1]["reach_mean"] or 0))
    for mgr, v in order:
        if mgr == "?":
            continue
        mix = " ".join("%s%d" % (k, n) for k, n in sorted(v["pos_mix"].items(), key=lambda x: -x[1]))
        print("%-22s %-7d %-9s %-9s %-9s %s"
              % (mgr, v["n_picks"],
                 ("%+.1f" % v["reach_mean"]) if v["reach_mean"] is not None else "--",
                 ("%.1f" % v["reach_sd"]) if v["reach_sd"] else "--",
                 ("%+.1f" % v["reach_early"]) if v["reach_early"] is not None else "--", mix))
    json.dump(t, open(os.path.join(HERE, "data", "tendencies.json"), "w"), indent=2, sort_keys=True)
