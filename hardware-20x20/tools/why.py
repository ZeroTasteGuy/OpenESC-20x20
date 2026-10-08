import sys,os,ast,collections;sys.path.insert(0,os.environ['TEMP'])
from router import *
R=Router(sys.argv[1]);log=sys.argv[2]
R._edge=disk_dilate(~R.inside,0.35);R._edgev=disk_dilate(~R.inside,0.55)
viaok0=(R.ocv==0)&~R._edgev
rows=[]
for line in open(log):
    if not line.startswith("('FAIL'"):continue
    _,net,pa,pb=ast.literal_eval(line)
    R.remove_net(net)
    viaok=((R.ocv==0)&~R._edgev)
    res=[]
    for (x,y) in (pa,pb):
        pad=[p for p in R.items if p['kind']=='pad' and abs(p['x']-x)<0.06 and abs(p['y']-y)<0.06 and p['net']==net]
        if not pad:res.append(('?',0,0));continue
        p=pad[0];l=p['layers'][0]
        mk=np.zeros((NY,NX),bool);mk[cy(p['y']-p['h']/2):cy(p['y']+p['h']/2)+1,cx(p['x']-p['w']/2):cx(p['x']+p['w']/2)+1]=True
        fr=((R.occ['sig'][l]==0)&~R._edge)|mk
        cur=mk.copy()
        for it in range(600):
            nx=cur.copy();nx[1:]|=cur[:-1];nx[:-1]|=cur[1:];nx[:,1:]|=cur[:,:-1];nx[:,:-1]|=cur[:,1:];nx&=fr
            if (nx==cur).all():break
            cur=nx
        res.append((p['ref']+'.'+p['pn'],round(cur.sum()*RES*RES,1),int((cur&viaok).sum())))
    R.restore_net(net)
    rows.append((net,res))
for r in rows:print(r)
