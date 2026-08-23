"""ESPN 2026 season projections, rescored to THIS league (full PPR, 4pt pass TD).

Independent of Rotowire. ESPN's own appliedTotal uses ESPN default scoring, so
raw stats are rescored here rather than trusting their headline number.
"""
import json, os, urllib.request, datetime

HERE=os.path.dirname(os.path.abspath(__file__))
RAW=os.path.join(HERE,"data","raw"); CACHE=os.path.join(HERE,"cache")
URL="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/players?view=kona_player_info"
POS={1:'QB',2:'RB',3:'WR',4:'TE',5:'K',16:'DST'}
# ESPN stat ids
PASS_YD,PASS_TD,INT = '3','4','20'
RUSH_YD,RUSH_TD      = '24','25'
REC,REC_YD,REC_TD    = '53','42','43'
FUM                  = '72'

def ppr(s):
    g=lambda k: float(s.get(k) or 0)
    return (g(PASS_YD)*0.04 + g(PASS_TD)*4 - g(INT)*2
            + g(RUSH_YD)*0.1 + g(RUSH_TD)*6
            + g(REC)*1.0 + g(REC_YD)*0.1 + g(REC_TD)*6
            - g(FUM)*2)

def main():
    fp=os.path.join(CACHE,"espn_raw.json")
    if not os.path.exists(fp):
        req=urllib.request.Request(URL, headers={
            "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept":"application/json",
            "x-fantasy-filter":'{"players":{"limit":1500,"sortPercOwned":{"sortAsc":false,"sortPriority":1}}}',
            "x-fantasy-source":"kona","x-fantasy-platform":"kona-PROD"})
        with urllib.request.urlopen(req, timeout=120) as r:
            open(fp,'wb').write(r.read())
    d=json.load(open(fp))
    out={}
    for p in d:
        pos=POS.get(p.get('defaultPositionId'))
        if pos not in ('QB','RB','WR','TE'): continue
        st=[s for s in (p.get('stats') or [])
            if s.get('statSourceId')==1 and s.get('statSplitTypeId')==0 and s.get('seasonId')==2026]
        if not st: continue
        raw=st[0].get('stats') or {}
        pts=ppr(raw)
        if pts<=0: continue
        out[p['fullName']]={'pos':pos,'pts':round(pts,1),
                            'espn_default':round(st[0].get('appliedTotal') or 0,1)}
    payload={'source':'ESPN kona_player_info, 2026 season projections, rescored to full PPR / 4pt pass TD',
             'url':URL,'pulled_at_utc':datetime.datetime.utcnow().isoformat()+'Z','players':out}
    json.dump(payload, open(os.path.join(RAW,'projections_espn.json'),'w'), indent=2, sort_keys=True)
    print("ESPN players with a 2026 projection: %d"%len(out))
    top=sorted(out.items(), key=lambda kv:-kv[1]['pts'])[:8]
    for n,v in top: print("   %-24s %-3s ppr=%-7.1f (espn default %.1f)"%(n,v['pos'],v['pts'],v['espn_default']))

if __name__=='__main__': main()
