"""The in-season data layer: one payload for the free-agent, lineup and league views.

Why this exists separately from board.json: the draft board is 260 players deep
because a 15-round 12-team draft consumes 180. A waiver wire is not 260 players
deep. In week 5 the player who matters is usually one nobody drafted, and the
live page could not see him at all - it only ever received board.json, so 300 of
the 560 projected players were invisible to the tool that exists to find them.

Every field here is either measured or sourced, and carries its basis:
  * season projection  - Sleeper/Rotowire blended with ESPN where both exist
                         (board players only; pool-only players are single-source
                         and flagged "rotowire only")
  * weekly projection  - Sleeper per-week projections, real week keys
  * hit10/hit15/ceiling/floor/sd/startable - MEASURED from real 2025 weekly
                         scores, or absent. Never interpolated.
  * bye                - derived from the 2026 schedule, independently confirmed
                         against the weekly projections (32/32 teams agree)
"""
import json, os, statistics, datetime
import weeklystats

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
CACHE = os.path.join(HERE, "cache")
PLAYABLE = ("QB", "RB", "WR", "TE")


def load_all():
    d = {}
    d["board"] = json.load(open(os.path.join(HERE, "data", "board.json")))
    d["variance"] = json.load(open(os.path.join(HERE, "data", "variance.json")))
    d["proj"] = json.load(open(os.path.join(RAW, "projections_sleeper.json")))
    d["byes"] = json.load(open(os.path.join(RAW, "byes_2026.json")))
    d["pn"] = json.load(open(os.path.join(CACHE, "players_nfl.json")))
    d["sched"] = json.load(open(os.path.join(RAW, "schedule_2026.json")))
    fp = os.path.join(CACHE, "weeklyproj_2026.json")
    d["wproj"] = json.load(open(fp)) if os.path.exists(fp) else {"players": {}, "meta": {}}
    return d


def opponents_by_week(sched):
    """{team: {week: 'vs X' | '@ X'}} - factual, no difficulty rating attached.
    There is still no defensible 2026 defensive-strength metric in this project,
    so this is opponent identity only."""
    out = {}
    for g in sched:
        out.setdefault(g["home"], {})[g["week"]] = "vs " + g["away"]
        out.setdefault(g["away"], {})[g["week"]] = "@ " + g["home"]
    return out


def build():
    D = load_all()
    board = {str(p["player_id"]): p for p in D["board"]["players"]}
    var = D["variance"]["players"]
    byes = D["byes"]
    pn = D["pn"]
    wproj = D["wproj"]["players"]
    opp = opponents_by_week(D["sched"])

    # measured 2025 weekly history, order-independent stats only
    hist, _ = weeklystats.points_list(2025)

    season_proj = {}
    for pos, rows in D["proj"]["players"].items():
        for r in rows:
            season_proj[str(r["player_id"])] = {"pts": r.get("pts_ppr"), "pos": pos,
                                                "name": r.get("name"), "team": r.get("team")}

    pool = {}
    ids = set(season_proj) | set(wproj)
    n_measured = n_board = 0
    for pid in ids:
        sp = season_proj.get(pid) or {}
        b = board.get(pid)
        meta = pn.get(pid) or {}
        pos = (b or {}).get("pos") or sp.get("pos") or (meta.get("fantasy_positions") or [None])[0]
        if pos not in PLAYABLE:
            continue
        team = (b or {}).get("team") or sp.get("team") or meta.get("team")
        name = (b or {}).get("name") or sp.get("name") or \
            ((meta.get("first_name") or "") + " " + (meta.get("last_name") or "")).strip()
        if not name:
            continue
        rec = {
            "n": name, "pos": pos, "tm": team or "",
            "bye": byes.get(team or ""),
            "dcp": meta.get("depth_chart_position"),
            "dco": meta.get("depth_chart_order"),
            "inj": meta.get("injury_status"),
            "injb": meta.get("injury_body_part"),
            "age": meta.get("age"),
            "nu": meta.get("news_updated"),
        }
        # season projection: blended if the player was on the board, else single-source
        if b:
            rec["pts"] = b.get("pts_ppr")
            rec["psrc"] = b.get("src")
            rec["vor"] = b.get("vor")
            rec["tier"] = b.get("tier")
            rec["adp"] = b.get("adp_blend") or b.get("ffc_adp") or b.get("sleeper_adp")
            n_board += 1
        else:
            rec["pts"] = sp.get("pts")
            rec["psrc"] = "rotowire only"     # never blended: not on the board
            rec["vor"] = None
            rec["adp"] = None
        # weekly projections, real week keys, absent means NOT PROJECTED (e.g. bye)
        w = wproj.get(pid) or {}
        if w:
            rec["wp"] = {k: v for k, v in w.items()}
        # measured 2025 evidence
        v = var.get(pid)
        g = hist.get(pid) or []
        if v and v.get("basis") == "MEASURED":
            rec.update({"h10": v.get("hit10"), "h15": v.get("hit15"),
                        "ceil": v.get("ceiling"), "flr": v.get("floor"),
                        "sd": v.get("sd"), "sr": v.get("startable_rate"),
                        "g25": v.get("games"), "mb": "M"})
            n_measured += 1
        elif len(g) >= 8:
            # in the pool but off the board: compute the same order-independent
            # stats here rather than leaving a hole the UI has to guess at
            srt = sorted(g)
            rec.update({"h10": round(sum(1 for x in g if x >= 10) / len(g), 2),
                        "h15": round(sum(1 for x in g if x >= 15) / len(g), 2),
                        "ceil": round(srt[int(len(srt) * 0.85)], 1),
                        "flr": round(srt[int(len(srt) * 0.15)], 1),
                        "sd": round(statistics.pstdev(g), 1),
                        "sr": None,          # needs board baselines; not computed here
                        "g25": len(g), "mb": "M"})
            n_measured += 1
        else:
            rec.update({"g25": len(g), "mb": "N"})

        # ROLE-ADJUSTED FLOOR. A 2025 ten-point rate describes the role a player
        # HAD. HANDOFF S2 named this exact failure - "everyone with a good floor
        # lost the role that produced it: Tonges TE2, Theo Johnson TE2, Franklin
        # SWR3, Vidal RB3" - and the first moves engine went and recommended all
        # of them anyway, because it ranked on the raw 2025 rate.
        #
        # Keep his own measured week-to-week SHAPE, which is genuinely his, and
        # move its LEVEL to the role he holds now, taken from the 2026 weekly
        # projections. Then re-count how often that clears the bar.
        #
        # Validated out of sample: predict a player's 2025 rate from his 2024
        # weeks plus his 2025 role, n=218 players -
        #     2025 rate alone   mean err 0.161   r 0.735   bias +0.047
        #     normal approx     mean err 0.085   r 0.942   bias +0.054
        #     rescaled shape    mean err 0.077   r 0.936   bias +0.004  <- used
        # On the 24% whose rate moved >25 points year to year - the role changes,
        # the only cases this has to get right - naive error is 0.360 against
        # 0.094 rescaled.
        if len(g) >= 8 and w:
            m25 = statistics.mean(g)
            m26 = statistics.mean(list(w.values()))
            if m25 > 0.5:
                k = m26 / m25
                rec["h10a"] = round(sum(1 for x in g if x * k >= 10) / len(g), 2)
                rec["h15a"] = round(sum(1 for x in g if x * k >= 15) / len(g), 2)
                rec["k"] = round(k, 2)
                rec["m25"] = round(m25, 1)
                rec["m26"] = round(m26, 1)
                # WHY it changed, not just that it did. Cross-checked against
                # Sleeper's own depth chart, which is a separate pipeline from the
                # projections: median depth-chart order came out 3.0 for players
                # whose rate fell, 2.0 for flat, 1.0 for risen - so the two agree.
                #
                # But six players whose rate fell are still listed FIRST at their
                # spot: Kittle 80->60%, Goedert 60->33%, Dobbins 60->40%, Ferguson,
                # Henry, Gadsden. They did not lose a job; they are projected to
                # score less in the same one. Calling that "role lost" is the tool
                # claiming to know something it does not - and it would have buried
                # Kittle, who at 60% would be the best bench floor on this roster.
                d = rec["h10a"] - (rec.get("h10") or 0)
                starter = (rec.get("dco") == 1)
                if d <= -0.15 and not starter:
                    rec["role"] = "BACKUP"       # behind someone now
                elif d <= -0.15 and starter:
                    rec["role"] = "LOWER"        # same job, smaller projection
                elif d >= 0.15:
                    rec["role"] = "HIGHER"
                else:
                    rec["role"] = "SAME"
                # PHASE 1 - how much evidence is this resting on? A rate from 8
                # games and one from 17 look identical on screen and are not.
                # Standard error of a proportion; shown as a plus/minus so a thin
                # sample cannot masquerade as a firm number.
                p = rec["h10a"]
                rec["se"] = round((p * (1 - p) / len(g)) ** 0.5, 3)

        rec["opp"] = opp.get(team or "", {})
        pool[pid] = rec

    meta = {
        "built_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_pool": len(pool), "n_on_board": n_board,
        "n_with_2025_history": n_measured,
        "weekly_proj": D["wproj"].get("meta", {}),
        "variance_definition": D["variance"].get("definition"),
        "bases": {
            "pts": "season PPR projection. 'blend' = Rotowire+ESPN equal weight; "
                   "'rotowire only' = single source, off the 260-man draft board",
            "wp": "Sleeper per-week PPR projection, keyed by real NFL week. A week "
                  "absent means NOT PROJECTED (bye, or no projection issued) - not zero",
            "h10/h15/ceil/flr/sd": "MEASURED from real 2025 weekly scores, min 8 games",
            "sr": "startable_rate, measured against this league's own weekly baseline; "
                  "null for pool-only players whose baseline was not computed",
            "mb": "M = has >=8 games of 2025 history. N = does not; nothing is interpolated",
            "h10a": "ROLE-ADJUSTED expected 2026 ten-point rate: his own 2025 weekly shape "
                    "rescaled to his 2026 projected level, then recounted. This is the number "
                    "decisions run on. h10 (the raw 2025 rate) is kept for display only - it "
                    "describes a role the player may no longer have",
            "k": "2026 projected points per game divided by 2025 actual points per game. "
                 "Below ~0.7 means the role shrank; above ~1.3 means it grew",
            "role": "BACKUP (rate fell and he is no longer listed first) / LOWER (rate fell "
                    "but he is still the listed starter - projected to score less in the same "
                    "job) / HIGHER / SAME. Cross-checked against Sleeper's depth chart, a "
                    "separate pipeline: median depth order 3.0 BACKUP, 2.0 SAME, 1.0 HIGHER",
            "se": "standard error of h10a given the number of 2025 games behind it. "
                  "8 games at 30% is +/-16 points; 17 games at 30% is +/-11",
            "opp": "factual 2026 opponent by week. No difficulty rating - none is defensible here",
        },
    }
    out = {"meta": meta, "players": pool}
    json.dump(out, open(os.path.join(HERE, "data", "inseason.json"), "w"),
              separators=(",", ":"), sort_keys=True)
    return out


if __name__ == "__main__":
    o = build()
    m = o["meta"]
    print("in-season pool built")
    print("  players in pool          : %d" % m["n_pool"])
    print("  of which on draft board  : %d" % m["n_on_board"])
    print("  NEW to the tool          : %d  <- invisible to the old PICKUP tab" %
          (m["n_pool"] - m["n_on_board"]))
    print("  with >=8 games of 2025   : %d" % m["n_with_2025_history"])
    print("  weekly projection weeks  : %s" % (m["weekly_proj"].get("weeks_with_data")))
    import collections
    c = collections.Counter(p["pos"] for p in o["players"].values())
    print("  by position              : %s" % dict(sorted(c.items())))
    nw = sum(1 for p in o["players"].values() if not p.get("wp"))
    print("  no weekly projection     : %d (shown as unprojected, never as zero)" % nw)
