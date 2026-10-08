import sys,os,re
sys.path.insert(0,os.environ['TEMP'])
from engine import Board
p=sys.argv[1];B=Board(p);t=B.t;edits=[]
n=0
for r,f in B.fps.items():
    b=f['b']
    if f['layer']=='F.Cu' and 'mirror' in b:
        nb=re.sub(r'\(justify mirror\)','',b)
        nb=re.sub(r'(\(justify[^)]*?) mirror',r'\1',nb)
        if nb!=b:edits.append((f['s'],f['e'],nb));n+=1
for s,e,nb in sorted(edits,reverse=True):t=t[:s]+nb+t[e:]
open(p,'w',encoding='utf8').write(t);print('text fixed in',n,'footprints')
