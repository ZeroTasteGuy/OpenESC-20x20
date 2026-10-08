"""usage: python drive.py in.kicad_pcb drc.json out.kicad_pcb [maxpairs]"""
import sys,os,re,json,math,time
sys.path.insert(0,os.environ['TEMP'])
import numpy as np
from router import *
src_pcb,drcj,out=sys.argv[1:4];maxp=int(sys.argv[4]) if len(sys.argv)>4 else 9999
R=Router(src_pcb)
d=json.load(open(drcj));pairs=[]
def parse(it):
    ds=it['description'];m=re.match(r'(?:PTH pad|Pad) (\S+) \[([^\]]*)\] of (\S+)',ds)
    if m:
        pos=(it['pos']['x']-CX,it['pos']['y']-CY);ref=m.group(3);pn=m.group(1)
        cands=[p for p in R.items if p['kind']=='pad' and p['ref']==ref and p['pn']==pn]
        if not cands:return None
        p=min(cands,key=lambda p:math.hypot(p['x']-pos[0],p['y']-pos[1]))
        return dict(t='pad',p=p,net=m.group(2),pos=pos)
    m=re.match(r'Zone \[([^\]]*)\] on (\S+)',ds)
    if m and m.group(2) in LI:
        return dict(t='zone',net=m.group(1),layer=LI[m.group(2)],pos=(it['pos']['x']-CX,it['pos']['y']-CY))
    return None
for u in d['unconnected_items']:
    a,b=[parse(i) for i in u['items']]
    if a is None or b is None:continue
    pairs.append((a,b))
def padcells(p,shrink=0.0):
    out=[]
    for l in p['layers']:
        mk=np.zeros((NY,NX),bool)
        mk[max(0,cy(p['y']-p['h']/2+shrink)):cy(p['y']+p['h']/2-shrink)+1,max(0,cx(p['x']-p['w']/2+shrink)):cx(p['x']+p['w']/2-shrink)+1]=True
        out.append((l,mk))
    return out
def length(pr):
    a,b=pr;return math.hypot(a['pos'][0]-b['pos'][0],a['pos'][1]-b['pos'][1])
import random
ordr=os.environ.get('ORDER','len')
if ordr=='len':pairs.sort(key=length)
elif ordr=='rev':pairs.sort(key=length,reverse=True)
else:random.seed(int(ordr));random.shuffle(pairs)
ok=fail=0;log=[]
t0=time.time()
for a,b in pairs[:maxp]:
    net=a['net'] if a['net'] else b['net']
    if a['t']=='zone' and b['t']=='zone':continue
    if a['t']=='zone':a,b=b,a
    cls='pow' if net in('+10V','+3V3') else 'sig'
    R.remove_net(net)
    ownv=[it for it in R.by_net[net] if it['kind']=='via']
    for it in ownv:R._shape(R.ocv,it,0.3,1)
    try:
        src=[];ex=np.zeros((NY,NX),bool)
        p=a['p']
        for l,mk in padcells(p,0.05):
            jj,ii=np.nonzero(mk);sel=range(0,len(jj),max(1,len(jj)//300))
            src+=[(l,int(jj[k]),int(ii[k])) for k in sel]
        ex|=disk_dilate(padcells(p)[0][1],0.9)&R.inside
        res=None
        if net=='GND' and b['t']=='pad' and b['p']['th']==False and False:pass
        if net=='GND':
            res=R.route(net,src,dst_via_plane=True,cls=cls,margin=4.0,exempt=ex)
        else:
            dst={}
            if b['t']=='pad':
                for l,mk in padcells(b['p'],0.05):dst[l]=dst.get(l,np.zeros((NY,NX),bool))|mk
                ex|=disk_dilate(padcells(b['p'])[0][1],0.9)&R.inside
            else:
                mk=R.zone_cells.get((net,b['layer']))
                if mk is None:raise RuntimeError('no zone')
                dst[b['layer']]=mk
            res=R.route(net,src,dst_cells=dst,cls=cls,margin=6.0,exempt=ex)
        if res is None and cls=='pow':
            res=R.route(net,src,dst_cells=dst,cls='sig',margin=6.0,exempt=ex);cls='sig'
    finally:
        for it in ownv:R._shape(R.ocv,it,0.3,-1)
        R.restore_net(net)
    if res is None:
        fail+=1;log.append(('FAIL',net,a['pos'],b['pos']));continue
    cells,ve=res
    segs,vias=R.emit(net,cells,ve,cls)
    def P_(c):return (GX0+(c[2]+0.5)*RES,GY0+(c[1]+0.5)*RES)
    p0=P_(cells[0]);pa=(a['p']['x'],a['p']['y']);segs.insert(0,(pa[0],pa[1],p0[0],p0[1],cells[0][0]))
    if ve is None and b['t']=='pad':
        p1=P_(cells[-1]);pb=(b['p']['x'],b['p']['y']);segs.append((p1[0],p1[1],pb[0],pb[1],cells[-1][0]))
    R.commit(net,segs,vias,cls);ok+=1
print('routed',ok,'failed',fail,'time %.0fs'%(time.time()-t0))
for l in log:print(l)
R.write(out)
