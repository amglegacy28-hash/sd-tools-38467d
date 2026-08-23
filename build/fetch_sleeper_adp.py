"""Sleeper's own ADP, for the survival model. Population-matched: these are the
people Giovanni actually drafts against, where FFC is format-matched but drawn
from a different crowd."""
import json, os, urllib.request, datetime
RAW=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data','raw')
def pull(year):
    out={}
    for pos in ('QB','RB','WR','TE'):
        u=("https://api.sleeper.com/projections/nfl/%s?season_type=regular&position[]=%s&order_by=pts_ppr"%(year,pos))
        req=urllib.request.Request(u,headers={'User-Agent':'lionsden/0.1'})
        for r in json.loads(urllib.request.urlopen(req,timeout=60).read()):
            st=r.get('stats') or {}; p=r.get('player') or {}
            a=st.get('adp_ppr')
            if a and a<400:
                nm=((p.get('first_name') or '')+' '+(p.get('last_name') or '')).strip()
                if nm: out[nm]={'adp':a,'pos':pos}
    return out
if __name__=='__main__':
    for y in ('2026','2025'):
        d=pull(y)
        json.dump({'season':y,'pulled_at_utc':datetime.datetime.utcnow().isoformat()+'Z',
                   'source':'Sleeper API stats.adp_ppr','players':d},
                  open(os.path.join(RAW,'adp_sleeper_%s.json'%y),'w'), indent=1, sort_keys=True)
        print("Sleeper ADP %s: %d players"%(y,len(d)))
