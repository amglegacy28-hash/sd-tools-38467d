"""Pull FFC ADP (2026 PPR 12-team) and record its provenance."""
import json, os, urllib.request, datetime
URL = "https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year=2026"
RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
req = urllib.request.Request(URL, headers={"User-Agent": "lionsden/0.1"})
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())
d["_provenance"] = {"url": URL, "pulled_at_utc": datetime.datetime.utcnow().isoformat()+"Z"}
with open(os.path.join(RAW, "adp_ffc.json"), "w") as fh:
    json.dump(d, fh, indent=2, sort_keys=True)
m = d["meta"]
print("FFC: %s %d-team | %d drafts | window %s..%s | %d players"
      % (m["type"], m["teams"], m["total_drafts"], m["start_date"], m["end_date"], len(d["players"])))
