import sys,os,re,math,uuid,collections
import numpy as np
sys.path.insert(0,os.environ['TEMP'])
from bgeom import Geo,CX,CY,LAYERS
SRC=sys.argv[1];DST=sys.argv[2]
G=Geo(SRC);f=G.B.fps;t=G.B.t
u=lambda:str(uuid.uuid4())
A=lambda x,y:(x+CX,y+CY)
ZONES=[];VIAS=[];TRACKS=[];PRIO=[0]
def zone(net,layers,pts,prio=0):
    PRIO[0]+=1;prio=PRIO[0]
    xy=' '.join('(xy %.4f %.4f)'%A(*p) for p in pts)
    ZONES.append('''
	(zone
		(net "%s")
		(layers %s)
		(uuid "%s")
		(hatch edge 0.5)
		(priority %d)
		(connect_pads yes
			(clearance 0.16)
		)
		(min_thickness 0.25)
		(fill yes
			(thermal_gap 0.5)
			(thermal_bridge_width 0.5)
			(island_removal_mode 0)
		)
		(polygon
			(pts
				%s
			)
		)
	)'''%(net,' '.join('"%s"'%l for l in layers),u(),prio,xy))
def rect(x0,y0,x1,y1):return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
def via_ok(x,y,net,size=0.45,drill=0.3,edge=0.5):
    if abs(x)>17.5-edge or y<-19.2+edge or y>22.7-edge:return False
    if G.clearance_at(x,y,net,['F.Cu','B.Cu'],size/2)<0.17:return False
    if not G.hole_ok(x,y,drill):return False
    # keep the through-hole of mounting holes / motor pads clear (their copper is already a pad)
    return True
def put_via(x,y,net,size=0.45,drill=0.3):
    ax,ay=A(x,y)
    VIAS.append('\n\t(via (at %.4f %.4f) (size %s) (drill %s) (layers "F.Cu" "B.Cu") (net "%s") (uuid "%s"))'%(ax,ay,size,drill,net,u()))
    G.add(dict(kind='via',x=x,y=y,r=size/2,drill=drill,net=net,layers=LAYERS))
def place_vias(anchor_rect,net,n,reach=2.5,mind=0.62,inside_bonus=True):
    """put up to n vias for `net` close to the pad rect (x0,y0,x1,y1); returns positions"""
    x0,y0,x1,y1=anchor_rect;cands=[]
    i0=int((x0-reach)*10);i1=int((x1+reach)*10);j0=int((y0-reach)*10);j1=int((y1+reach)*10)
    for i in range(i0,i1+1):
        for j in range(j0,j1+1):
            x=i/10;y=j/10
            d=math.hypot(max(x0-x,0,x-x1),max(y0-y,0,y-y1))
            if d>reach:continue
            cands.append((d,x,y))
    cands.sort();out=[]
    for d,x,y in cands:
        if len(out)>=n:break
        if any(math.hypot(x-a,y-b)<mind for a,b in out):continue
        if not via_ok(x,y,net):continue
        put_via(x,y,net);out.append((x,y))
    return out
def pad_rect(p,grow=0.0):return (p['x']-p['w']/2-grow,p['y']-p['h']/2-grow,p['x']+p['w']/2+grow,p['y']+p['h']/2+grow)
BIG=(-24.0,-26.0,24.0,27.0)
zone('GND',['In1.Cu'],rect(*BIG),0)
zone('+BATT',['In2.Cu'],rect(*BIG),0)
zone('GND',['In3.Cu'],rect(*BIG),0)
zone('GND',['In4.Cu'],rect(*BIG),0)
zone('GND',['B.Cu'],rect(*BIG),0)
zone('+BATT',['F.Cu'],rect(*BIG),0)
def pads_of(ref,net=None,n=None):return [p for p in f[ref]['pads'] if (net is None or p['net']==net) and (n is None or p['n']==n)]
motorpads={p['net']:p for p in f['U3']['pads'] if '/Motor' in p['net']}
nets_q=collections.defaultdict(list)
for q in [r for r in f if r.startswith('Q')]:
    pn={}
    for p in f[q]['pads']:pn.setdefault(p['n'],p['net'])
    hs=pn['3']=='+BATT';nets_q[pn['1'] if hs else pn['3']].append((q,hs))
phase={}
for mot,lst in nets_q.items():
    hsq=[q for q,h in lst if h][0];lsq=[q for q,h in lst if not h][0]
    phase[mot]=dict(hs=hsq,ls=lsq,stack=(f[hsq]['x']==f[lsq]['x'] and f[hsq]['y']==f[lsq]['y']),mp=motorpads[mot])
report=collections.defaultdict(dict)
# ---- phase pours for stacked pairs + link vias (adjacent pads) ; lanes for the others
def reg_rect(net,layer,x0,y0,x1,y1):
    G.add(dict(kind='pad',x=(x0+x1)/2,y=(y0+y1)/2,w=x1-x0,h=y1-y0,net=net,layers=[layer],th=False,typ='smd',ref='ZN',pn=''))
def dist_rect(p,mp):
    dx=max(abs(p['x']-mp['x'])-(p['w']+mp['w'])/2,0);dy=max(abs(p['y']-mp['y'])-(p['h']+mp['h'])/2,0);return math.hypot(dx,dy)
LANES=[]
for mot,d in phase.items():
    if not d['stack']:continue
    mp=d['mp'];sx=1 if mp['x']>0 else -1
    pins=pads_of(d['hs'],mot,'1')
    near=min(dist_rect(p,mp) for p in pins)
    d['near']=near
    if near>2.0:
        LANES.append(mot);continue
    xs=[p['x']-p['w']/2 for p in pins]+[p['x']+p['w']/2 for p in pins];ys=[p['y']-p['h']/2 for p in pins]+[p['y']+p['h']/2 for p in pins]
    padin=mp['x']-sx*mp['w']/2
    y0=min(min(ys),mp['y']-mp['h']/2);y1=max(max(ys),mp['y']+mp['h']/2)
    near_x=max(xs) if sx<0 else min(xs)
    lp=[p for p in pads_of(d['ls'],mot,'3') if p['w']<2.0]
    lxs=[p['x']-p['w']/2 for p in lp]+[p['x']+p['w']/2 for p in lp];lys=[p['y']-p['h']/2 for p in lp]+[p['y']+p['h']/2 for p in lp]
    ly0=min(min(lys),mp['y']-mp['h']/2);ly1=max(max(lys),mp['y']+mp['h']/2);lnear=max(lxs) if sx<0 else min(lxs)
    def bridge(pp):
        bx0=min(p['x']-p['w']/2 for p in pp);bx1=max(p['x']+p['w']/2 for p in pp);by0=min(p['y']-p['h']/2 for p in pp);by1=max(p['y']+p['h']/2 for p in pp)
        cxp=(bx0+bx1)/2;cyp=(by0+by1)/2
        qx=min(max(cxp,mp['x']-mp['w']/2),mp['x']+mp['w']/2);qy=min(max(cyp,mp['y']-mp['h']/2),mp['y']+mp['h']/2)
        near=min(pp,key=lambda p:math.hypot(p['x']-qx,p['y']-qy))
        bar=(bx0-0.15,by0-0.1,bx1+0.15,by1+0.1)
        lx0,lx1=min(near['x'],qx)-0.45,max(near['x'],qx)+0.45
        ly0_,ly1_=min(near['y'],qy)-0.45,max(near['y'],qy)+0.45
        link=(lx0,ly0_,lx1,ly1_)
        patch=(qx-0.35,qy-0.3,qx+0.35,qy+0.3)
        return [bar,link,patch]
    r1=bridge(pins);r2=bridge(lp)
    for k_,rr in enumerate(r1):zone(mot,['F.Cu'],rect(*rr),40+k_);reg_rect(mot,'F.Cu',*rr)
    for k_,rr in enumerate(r2):zone(mot,['B.Cu'],rect(*rr),43+k_);reg_rect(mot,'B.Cu',*rr)
    lk=r1[1];lk2=r2[1]
    ax0=max(lk[0],lk2[0]);ax1=min(lk[2],lk2[2]);ay0=max(lk[1],lk2[1]);ay1=min(lk[3],lk2[3])
    got=place_vias((ax0,ay0,ax1,ay1),mot,6,reach=0.3)
    report['phase_links'][mot]=len(got)
# ---- +BATT vias at the HS drain tabs
for mot,d in phase.items():
    tab=[p for p in pads_of(d['hs'],'+BATT','3') if p['w']>2 and p['h']>2][0]
    got=place_vias(pad_rect(tab),'+BATT',10,reach=0.6)
    report['hs_tab_vias'][d['hs']]=len(got)
# ---- bulk caps
bulk=[r for r in f if '1206' in f[r]['lib']]
for r in bulk:
    side=f[r]['layer']
    for p in f[r]['pads']:
        got=place_vias(pad_rect(p,0.15),p['net'],2,reach=0.4)
        report['bulk_vias'][(r,p['net'])]=len(got)
        if (p['net']=='GND' and side=='F.Cu') or (p['net']=='+BATT' and side=='B.Cu'):
            x0,y0,x1,y1=pad_rect(p,0.5);zone(p['net'],['F.Cu' if side=='F.Cu' else 'B.Cu'],rect(x0,y0,x1,y1))
# ---- phase-C lanes (centre pair -> motor pad), zones along the best path on F.Cu / In1 / In4
import lane as LN
ins=LN.inside_grid(G.B)
def seg_rect(a,b,w):
    dx,dy=b[0]-a[0],b[1]-a[1];L=math.hypot(dx,dy)
    if L<1e-6:return None
    nx,ny=-dy/L*w/2,dx/L*w/2
    ex,ey=dx/L*0.1,dy/L*0.1      # small overlap at the joints
    return [(a[0]-ex+nx,a[1]-ey+ny),(b[0]+ex+nx,b[1]+ey+ny),(b[0]+ex-nx,b[1]+ey-ny),(a[0]-ex-nx,a[1]-ey-ny)]
lane_report={}
def best_lane(layer,net,src,dst,widths):
    best=None
    for w in widths:
        obs=LN.obstacle_map(G,layer,net,ins);free=~LN.disk_dilate(obs,0.16+w/2)
        sm=np.zeros((LN.NY,LN.NX),bool);dm=np.zeros((LN.NY,LN.NX),bool)
        for r in src:LN.rectmask(sm,*r)
        for r in dst:LN.rectmask(dm,*r)
        p8=LN.path8(free,[(j,i) for j,i in zip(*np.nonzero(sm&free))],dm&free)
        if p8:
            pts=LN.simplify(p8,0.1);L=sum(math.dist(a,b) for a,b in zip(pts,pts[1:]))
            if best is None or L/w<best[0]:best=(L/w,w,pts,L)
    return best
for mot in LANES:
    d=phase[mot];net=mot;mp=d['mp']
    dst=[(mp['x'],mp['y'],mp['w'],mp['h'])]
    srcF=[(p['x'],p['y'],p['w'],p['h']) for p in pads_of(d['hs'],net,'1')]
    srcB=[(p['x'],p['y'],p['w'],p['h']) for p in pads_of(d['ls'],net,'3') if p['w']<2.0]
    bF=best_lane('F.Cu',net,srcF,dst,(1.6,1.3,1.0,0.8,0.65,0.5,0.4,0.3))
    lane_report[(net,'F.Cu')]=bF[1:] if bF else None
    pathsF=None
    if bF:
        pathsF=bF[2]
        for a_,b_ in zip(pathsF,pathsF[1:]):
            r=seg_rect(a_,b_,bF[1]+0.5)
            if r:zone(net,['F.Cu'],r,45)
        for a_,b_ in zip(pathsF,pathsF[1:]):
            G.add(dict(kind='seg',x0=a_[0],y0=a_[1],x1=b_[0],y1=b_[1],w=bF[1]+0.5,net=net,layers=['F.Cu']))
    bB=best_lane('B.Cu',net,srcB,dst,(1.6,1.3,1.0,0.8,0.65,0.5,0.4,0.3))
    lane_report[(net,'B.Cu')]=bB[1:] if bB else None
    if bB:
        for a_,b_ in zip(bB[2],bB[2][1:]):
            r=seg_rect(a_,b_,bB[1]+0.5)
            if r:zone(net,['B.Cu'],r,45)
            G.add(dict(kind='seg',x0=a_[0],y0=a_[1],x1=b_[0],y1=b_[1],w=bB[1]+0.5,net=net,layers=['B.Cu']))
    # link vias where F and B lane starts overlap: along the start of the F lane
    ptsF=pathsF or (bB[2] if bB else None)
    if not ptsF:continue
    cand=[]
    for k in range(len(ptsF)-1):
        a_,b_=ptsF[k],ptsF[k+1];L=math.dist(a_,b_);n=max(1,int(L/0.2))
        for m in range(n+1):cand.append((a_[0]+(b_[0]-a_[0])*m/n,a_[1]+(b_[1]-a_[1])*m/n))
    cand=cand[:int(4.0/0.2)]
    vpos=[]
    for (cx_,cy_) in cand:
        for dxx in(-0.3,0,0.3):
            for dyy in(-0.3,0,0.3):
                x=round((cx_+dxx)*20)/20;y=round((cy_+dyy)*20)/20
                if len(vpos)>=8:break
                if any(math.hypot(x-a_,y-b_)<0.62 for a_,b_ in vpos):continue
                if via_ok(x,y,net):put_via(x,y,net);vpos.append((x,y))
    lane_report[(net,'vias')]=len(vpos)
    if vpos:
        vx0=min(x for x,y in vpos)-0.5;vx1=max(x for x,y in vpos)+0.5;vy0=min(y for x,y in vpos)-0.5;vy1=max(y for x,y in vpos)+0.5
        for ly in ('F.Cu','B.Cu','In1.Cu','In4.Cu'):zone(net,[ly],rect(vx0,vy0,vx1,vy1))
        src2=[(x,y,0.45,0.45) for x,y in vpos]
        for layer in('In1.Cu','In4.Cu'):
            best=best_lane(layer,net,src2,dst,(2.0,1.6,1.3,1.0,0.8,0.6))
            lane_report[(net,layer)]=best[1:] if best else None
            if best:
                for a_,b_ in zip(best[2],best[2][1:]):
                    r=seg_rect(a_,b_,best[1]+0.5)
                    if r:zone(net,[layer],r,45)
# ---- write
i=t.rindex('\n)')
open(DST,'w',encoding='utf8').write(t[:i]+''.join(ZONES)+''.join(VIAS)+t[i:])
print('zones',len(ZONES),'vias',len(VIAS))
for k,v in report.items():
    vals=list(v.values());print(k,'n',len(vals),'min',min(vals),'mean %.1f'%(sum(vals)/len(vals)),'zeros',[kk for kk,vv in v.items() if vv==0][:8])

for k,v in lane_report.items():print('lane',k, ('width %.2f length %.1f'%(v[0],v[1]) if isinstance(v,tuple) and len(v)==3 and False else v) if not isinstance(v,tuple) else ('w=%.2f len=%.1f'%(v[0],v[2]) if len(v)==3 else v))
