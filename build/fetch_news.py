"""Player news from dated, attributed roundups.

Attribution is anchored on SECTION HEADERS ("Player Name, POS, Team"), never on
names appearing in prose. Prose matching was tried twice and failed at roughly a
20-25% error rate - most dangerously it gave TEE Higgins the season-ending ACL
that belonged to JAYDEN Higgins, which would have wiped a top-40 player off the
board for someone else's injury.

Tone is three-way and derived from EXPLICIT language only, after reading every
item in the feed. Keyword sentiment was tried and got it wrong both ways: it
tagged Kenneth Walker and Malik Nabers negative on plainly positive text, and
missed Alvin Kamara's "expected to sideline Kamara for a month" because the
pattern only knew "expected to miss".
"""
import json, os, re, collections, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'data', 'raw')
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
SOURCES = [
    ("https://www.draftsharks.com/article/fantasy-football-risers-and-fallers",
     "Draft Sharks, Risers and Fallers"),
    ("https://www.draftsharks.com/article/fantasy-football-draft-strategy-guide",
     "Draft Sharks, 12-Team PPR Draft Guide"),
]

CAUTION = re.compile(
    r"(will miss|expected to miss|could miss|expected to sideline|is sidelined|"
    r"has been sidelined|out for the (season|year)|season-ending|could be suspended|"
    r"under league review|placed on (ir|pup)|week-to-week|"
    r"miss(ing)? (the )?(first|multiple|several|a couple)|"
    r"lowered (his|our) (floor|baseline)|nudged down|took a (small )?hit|shaved|"
    r"no longer (a |looks )?safe|losing work|lost (projected )?targets|fallen behind|"
    r"won'?t be a fantasy|less exciting|threatens? his availability)", re.I)

BOOST = re.compile(
    r"(has overtaken|overtaken|favorite to lead|in line for a bigger role|bigger role|"
    r"opens? the door|chance to open|clear top[- ]?(two|three)|we raised|raised (his|our)|"
    r"climbed|he'?s up to|moved up|good news for|impressive camp|has been active|"
    r"looked explosive|avoided the pup|has flipped|more optimistic|drawn praise|"
    r"will play week 1|full go|cleared)", re.I)

HDR = re.compile(r"^([A-Z][A-Za-z\.'\-]+(?: [A-Z][A-Za-z\.'\-]+){1,3})\s*,\s*(QB|RB|WR|TE)s?\s*,\s*[A-Z]")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'ignore')


def main():
    board = [p['name'] for p in json.load(open(os.path.join(HERE, 'data', 'board.json')))['players']]
    exact = {n.lower(): n for n in board}
    news, meta = {}, []

    for url, label in SOURCES:
        try:
            h = fetch(url)
        except Exception as e:
            print("  FAILED %s -> %r" % (label, e)); continue
        d = re.search(r'dateModified"?\s*:\s*"([^"]+)', h) or re.search(r'datePublished"?\s*:\s*"([^"]+)', h)
        date = d.group(1)[:10] if d else 'undated'
        meta.append({'source': label, 'url': url, 'date': date})

        body = re.sub(r'<(script|style|nav|header|footer)[^>]*>.*?</\1>', '', h, flags=re.S)
        text = re.sub(r'<[^>]+>', '\n', body)
        for a, z in (('&nbsp;', ' '), ('&amp;', '&'), ('&#039;', "'"), ('&rsquo;', "'"), ('&quot;', '"')):
            text = text.replace(a, z)
        raw = [l.strip() for l in text.split('\n') if l.strip()]

        hits = 0
        for i, line in enumerate(raw):
            m = HDR.match(line)
            if not m:
                continue
            who = exact.get(m.group(1).lower())
            if not who or who in news:
                continue
            chunk = []
            for j in range(i + 1, min(i + 7, len(raw))):
                if HDR.match(raw[j]):
                    break
                if len(raw[j]) >= 35:
                    chunk.append(raw[j])
                if len(' '.join(chunk)) > 240:
                    break
            if not chunk:
                continue
            txt = ' '.join(chunk)[:340]

            def about_him(mm):
                """The flag must describe HIM. Dalton Schultz and C.J. Stroud were
                both flagged over Jayden Higgins' ACL, which helps one of them."""
                if not mm:
                    return False
                lead = txt[:mm.start()]
                sur = who.split()[-1]
                tail = lead[-70:]
                others = [o for o in board if o != who and (o in tail or o.split()[-1] in tail)]
                return (sur in tail or who in tail or mm.start() < 45) and not others

            mc, mb = CAUTION.search(txt), BOOST.search(txt)
            tone = 'caution' if about_him(mc) else ('boost' if about_him(mb) else 'note')
            news[who] = {'text': txt, 'source': label, 'date': date,
                         'tone': tone, 'anchor': 'section header'}
            hits += 1
        print("  %-42s %s  -> %d from headers" % (label, date, hits))

    json.dump({'pulled_at_utc': datetime.datetime.utcnow().isoformat() + 'Z',
               'method': 'Verbatim excerpt anchored on the source section header. '
                         'Tone from explicit language only, and required to describe the player himself.',
               'sources': meta, 'news': news},
              open(os.path.join(RAW, 'news.json'), 'w'), indent=1, sort_keys=True)
    print("\nattached %d   tone: %s" % (len(news), dict(collections.Counter(v['tone'] for v in news.values()))))


if __name__ == '__main__':
    main()
