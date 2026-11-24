"""Print transcript + loudness for a window: python3 tools/window.py transcript.json loudness.csv START END (seconds or m:ss)"""
import json,sys,numpy as np
def ts(x):
    if ':' in x:
        p=[float(v) for v in x.split(':')]; return p[0]*60+p[1] if len(p)==2 else p[0]*3600+p[1]*60+p[2]
    return float(x)
segs=json.load(open(sys.argv[1])); L=np.loadtxt(sys.argv[2],delimiter=','); med=np.median(L[:,1])
a,b=ts(sys.argv[3]),ts(sys.argv[4])
for s in segs:
    if s['end']<a or s['start']>b: continue
    m=L[(L[:,0]>=s['start'])&(L[:,0]<=s['end']),1]
    pk=(m.max()-med) if len(m) else 0
    print(f"{int(s['start']//60):3d}:{s['start']%60:05.2f}-{s['end']%60:05.2f} [{pk:+4.0f}] {s['text']}")
