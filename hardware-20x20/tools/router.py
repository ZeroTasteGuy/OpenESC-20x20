"""Grid router driven by KiCad's own ratsnest (DRC 'unconnected_items').
Layers routed: F.Cu, In1.Cu, In4.Cu, B.Cu.  Vias are through vias 0.40/0.20."""
import sys,os,re,math,json,uuid,heapq,collections,time,subprocess
sys.path.insert(0,os.environ['TEMP'])
import numpy as np
from engine import Board,CX,CY
from pcbutil import toplevel
SOFTW=5.0;RES=0.05;GX0,GY0=-20.0,-21.0;NX=int(round(40/RES));NY=int(round(46/RES))
RL=['F.Cu','In1.Cu','In4.Cu','B.Cu'];LI={l:i for i,l in enumerate(RL)}
VIA_D,VIA_DR=0.35,0.20
# track widths / clearances per class and layer index
W={'sig':[0.16,0.16,0.16,0.16],'pow':[0.30,0.25,0.25,0.30]}
CLR=[0.20,0.16,0.16,0.20]
def R_of(cls,l):return CLR[l]+W[cls][l]/2
FINE=os.environ.get('FINE')=='1'
if FINE:
    W={'sig':[0.10]*4,'pow':[0.2]*4};CLR=[0.12]*4
R_VIA=0.5*VIA_D+(0.34-0.175 if FINE else 0.20)
def cx(x):return int(math.floor((x-GX0)/RES))
def cy(y):return int(math.floor((y-GY0)/RES))
xs=GX0+(np.arange(NX)+0.5)*RES;ys=GY0+(np.arange(NY)+0.5)*RES
XX,YY=np.meshgrid(xs,ys)
_disc={}
def disc(r):
    k=int(math.ceil(r/RES))+1
    if r not in _disc:
        yy,xx=np.mgrid[-k:k+1,-k:k+1];_disc[r]=(((xx*RES)**2+(yy*RES)**2)<=r*r,k)
    return _disc[r]
def disk_dilate(mask,r):
    k=int(math.ceil(r/RES));yy,xx=np.ogrid[-k:k+1,-k:k+1];ker=((xx*xx+yy*yy)<=(r/RES)**2).astype(np.float32)
    sh=(mask.shape[0]+2*k,mask.shape[1]+2*k)
    a=np.zeros(sh,np.float32);a[k:k+mask.shape[0],k:k+mask.shape[1]]=mask
    kk=np.zeros(sh,np.float32);kk[:ker.shape[0],:ker.shape[1]]=ker
    c=np.fft.irfft2(np.fft.rfft2(a)*np.fft.rfft2(kk),s=sh)
    return c[2*k:2*k+mask.shape[0],2*k:2*k+mask.shape[1]]>0.5
def raster_poly(pts,mask):
    P=np.array([((x-CX-GX0)/RES,(y-CY-GY0)/RES) for x,y in pts]);n=len(P)
    if n<3:return
    x1=P[:,0];y1=P[:,1];x2=np.roll(x1,-1);y2=np.roll(y1,-1)
    for row in range(max(0,int(y1.min())),min(NY-1,int(y1.max())+1)+1):
        yc=row+0.5;m=((y1<=yc)&(y2>yc))|((y2<=yc)&(y1>yc))
        if not m.any():continue
        xi=x1[m]+(yc-y1[m])*(x2[m]-x1[m])/(y2[m]-y1[m]);xi.sort()
        for a in range(0,len(xi)-1,2):
            xa=max(0,int(round(xi[a])));xb=min(NX,int(round(xi[a+1])))
            if xb>xa:mask[row,xa:xb]=True
class Router:
    def __init__(s,path):
        s.path=path;s.B=Board(path);s.t=s.B.t;s.fps=s.B.fps
        s.items=[];s.by_net=collections.defaultdict(list)
        s.occ={c:[np.zeros((NY,NX),np.int16) for _ in RL] for c in W};s.ocv=np.zeros((NY,NX),np.int16)
        s.new_segments=[];s.new_vias=[]
        s.soft=[np.zeros((NY,NX),np.float32) for _ in RL]
        s.load()
    # ------------------------------------------------------------- geometry
    def load(s):
        from engine import outline_mask
        _,poly=outline_mask(s.t)
        ins=np.zeros((NY,NX),bool);n=len(poly)
        for a in range(n):
            x1,y1=poly[a];x2,y2=poly[(a+1)%n];cond=((y1>YY)!=(y2>YY))
            with np.errstate(divide='ignore',invalid='ignore'):xint=(x2-x1)*(YY-y1)/(y2-y1)+x1
            ins^=cond&(XX<xint)
        s.inside=ins
        for r,f in s.fps.items():
            if abs(f['x'])>25:continue
            for p in f['pads']:
                if p['n']=='' and not p['th']:continue
                lays=[l for l in RL if (p['th'] or (l=='F.Cu' and 'F' in p['sides']) or (l=='B.Cu' and 'B' in p['sides']))]
                s.add(dict(kind='pad',x=p['x'],y=p['y'],w=p['w'],h=p['h'],net=p['net'],layers=[LI[l] for l in lays],ref=r,pn=p['n'],th=p['th']))
        for st,e,h in toplevel(s.t):
            b=s.t[st:e]
            if h=='via':
                a=re.search(r'\(at ([-\d.]+) ([-\d.]+)\)',b);sz=float(re.search(r'\(size ([\d.]+)\)',b).group(1));n_=re.search(r'\(net "([^"]*)"',b)
                s.add(dict(kind='via',x=float(a.group(1))-CX,y=float(a.group(2))-CY,r=sz/2,net=n_.group(1) if n_ else '',layers=[0,1,2,3]))
            elif h=='segment':
                a=re.search(r'\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)',b);n_=re.search(r'\(net "([^"]*)"',b)
                if a and a.group(6) in LI:
                    s.add(dict(kind='seg',x0=float(a.group(1))-CX,y0=float(a.group(2))-CY,x1=float(a.group(3))-CX,y1=float(a.group(4))-CY,w=float(a.group(5)),net=n_.group(1) if n_ else '',layers=[LI[a.group(6)]]))
        # protected phase copper: filled zones of motor nets
        s.zone_cells=collections.defaultdict(lambda:np.zeros((NY,NX),bool))
        for st,e,h in toplevel(s.t):
            if h!='zone':continue
            b=s.t[st:e];net=re.search(r'\(net "([^"]*)"\)',b)
            if not net:continue
            net=net.group(1)
            for m in re.finditer(r'\(filled_polygon\s*\(layer "([^"]+)"\)\s*\(pts([\s\S]*?)\)\s*\)',b):
                if m.group(1) not in LI:continue
                pts=[(float(a),float(c)) for a,c in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)',m.group(2))]
                raster_poly(pts,s.zone_cells[(net,LI[m.group(1)])])
        for (net,l),mk in list(s.zone_cells.items()):
            if '/Motor' in net:s.soft[l]+=mk.astype(np.float32)
    # ------------------------------------------------------------- occupancy
    def _apply(s,it,d):
        k=it['kind']
        if k=='zone':
            l=it['layers'][0]
            for c in W:s.occ[c][l]+=(it['infl'][c].astype(np.int16)*d)
            s.ocv+=it['inflv'].astype(np.int16)*d
            return
        for c in W:
            for l in it['layers']:
                s._shape(s.occ[c][l],it,R_of(c,l),d)
        s._shape(s.ocv,it,R_VIA,d)
    def _shape(s,arr,it,R,d):
        k=it['kind']
        if k=='pad':
            j0=max(0,cy(it['y']-it['h']/2-R));j1=min(NY-1,cy(it['y']+it['h']/2+R));i0=max(0,cx(it['x']-it['w']/2-R));i1=min(NX-1,cx(it['x']+it['w']/2+R))
            arr[j0:j1+1,i0:i1+1]+=d
        elif k=='via':
            rv=it['r']+(0.05 if it['r']>0.2 else 0);m,kk=disc(round(rv+R,3));j=cy(it['y']);i=cx(it['x'])
            j0,j1,i0,i1=j-kk,j+kk+1,i-kk,i+kk+1;mj0=max(0,-j0);mi0=max(0,-i0);j0=max(0,j0);i0=max(0,i0);j1=min(NY,j1);i1=min(NX,i1)
            if j1>j0 and i1>i0:arr[j0:j1,i0:i1]+=(m[mj0:mj0+(j1-j0),mi0:mi0+(i1-i0)].astype(np.int16)*d)
        elif k=='seg':
            rr=it['w']/2+R
            j0=max(0,cy(min(it['y0'],it['y1'])-rr));j1=min(NY-1,cy(max(it['y0'],it['y1'])+rr));i0=max(0,cx(min(it['x0'],it['x1'])-rr));i1=min(NX-1,cx(max(it['x0'],it['x1'])+rr))
            if j1<j0 or i1<i0:return
            px=XX[j0:j1+1,i0:i1+1];py=YY[j0:j1+1,i0:i1+1];dx=it['x1']-it['x0'];dy=it['y1']-it['y0'];L2=dx*dx+dy*dy+1e-12
            t=np.clip(((px-it['x0'])*dx+(py-it['y0'])*dy)/L2,0,1)
            arr[j0:j1+1,i0:i1+1]+=(((px-it['x0']-t*dx)**2+(py-it['y0']-t*dy)**2)<=rr*rr).astype(np.int16)*d
    def add(s,it):
        s.items.append(it);s.by_net[it['net']].append(it);s._apply(it,1)
    def remove_net(s,net):
        for it in s.by_net[net]:s._apply(it,-1)
    def restore_net(s,net):
        for it in s.by_net[net]:s._apply(it,1)
    # ------------------------------------------------------------- search
    def free_arrays(s,cls):
        edge=~s.inside
        return [(s.occ[cls][l]==0)&~disk_dilate(edge,0.3+W[cls][l]/2) for l in range(4)]
    def route(s,net,src,dst_cells=None,dst_via_plane=False,cls='sig',margin=8.0,maxexp=200000,flood=None,rank='',exempt=None):
        """src: list of (layer,j,i) start cells; dst_cells: dict layer-> boolean mask of goal cells;
        dst_via_plane: finish by dropping a via anywhere possible (plane connection)"""
        if not hasattr(s,'_edge'):s._edge=disk_dilate(~s.inside,0.35);s._edgev=disk_dilate(~s.inside,0.55)
        free=[(s.occ[cls][l]==0)&~s._edge for l in range(4)]
        viaok=(s.ocv==0)&~s._edgev
        if exempt is not None:
            for l in range(4):free[l]=free[l]|((s.occ[cls][l]==0)&exempt)
        pts=[(j,i) for l,j,i in src]
        J0=max(0,min(j for j,i in pts)-int(margin/RES));J1=min(NY-1,max(j for j,i in pts)+int(margin/RES))
        I0=max(0,min(i for j,i in pts)-int(margin/RES));I1=min(NX-1,max(i for j,i in pts)+int(margin/RES))
        if dst_cells:
            for l,mk in dst_cells.items():
                jj,ii=np.nonzero(mk)
                if len(jj):
                    J0=min(J0,max(0,int(jj.min())-int(2/RES)));J1=max(J1,min(NY-1,int(jj.max())+int(2/RES)));I0=min(I0,max(0,int(ii.min())-int(2/RES)));I1=max(I1,min(NX-1,int(ii.max())+int(2/RES)))
        # heuristic target: centroid of goal cells (or none)
        tgt=None
        if dst_cells:
            allj=[];alli=[]
            for l,mk in dst_cells.items():
                jj,ii=np.nonzero(mk[J0:J1+1,I0:I1+1])
                if len(jj):allj+=list(jj+J0);alli+=list(ii+I0)
            if allj and len(allj)<3000:tgt=(allj,alli)
        def h(j,i):
            if tgt is None:return 0.0
            return min(math.hypot(j-a,i-b) for a,b in zip(tgt[0][::max(1,len(tgt[0])//40)],tgt[1][::max(1,len(tgt[1])//40)]))*RES*0.95
        INF=1e18;g={};prev={};pq=[]
        for l,j,i in src:
            if free[l][j,i] or True:
                g[(l,j,i)]=0.0;prev[(l,j,i)]=None;heapq.heappush(pq,(h(j,i),0.0,(l,j,i)))
        nb=[(1,0,RES),(-1,0,RES),(0,1,RES),(0,-1,RES),(1,1,RES*1.4142),(1,-1,RES*1.4142),(-1,1,RES*1.4142),(-1,-1,RES*1.4142)]
        n=0
        while pq:
            f_,d,(l,j,i)=heapq.heappop(pq)
            if d>g.get((l,j,i),INF):continue
            n+=1
            if n>maxexp:return None
            if dst_cells and l in dst_cells and dst_cells[l][j,i]:
                return s._extract(prev,(l,j,i),None)
            if dst_via_plane and viaok[j,i] and all(free[ll][j,i] or True for ll in range(4)):
                # drop a via here
                return s._extract(prev,(l,j,i),(j,i))
            fl=free[l];sf=s.soft[l]
            for dj,di,c in nb:
                nj,ni=j+dj,i+di
                if nj<J0 or nj>J1 or ni<I0 or ni>I1:continue
                if not fl[nj,ni]:continue
                if dj and di and not(fl[j+dj,i] and fl[j,i+di]):continue
                nd=d+c*(1.0+SOFTW*sf[nj,ni]);key=(l,nj,ni)
                if nd<g.get(key,INF):
                    g[key]=nd;prev[key]=(l,j,i);heapq.heappush(pq,(nd+h(nj,ni),nd,key))
            if viaok[j,i]:
                for l2 in range(4):
                    if l2==l:continue
                    if not free[l2][j,i]:continue
                    key=(l2,j,i);nd=d+1.6+0.15*abs(l2-l)
                    if nd<g.get(key,INF):
                        g[key]=nd;prev[key]=(l,j,i);heapq.heappush(pq,(nd+h(j,i),nd,key))
        return None
    def _extract(s,prev,end,via_end):
        cells=[];cur=end
        while cur is not None:cells.append(cur);cur=prev[cur]
        cells=cells[::-1];return cells,via_end
    # ------------------------------------------------------------- emit
    def emit(s,net,cells,via_end,cls='sig'):
        segs=[];vias=[]
        def P(l,j,i):return (GX0+(i+0.5)*RES,GY0+(j+0.5)*RES)
        run=[cells[0]]
        def flush(run):
            if len(run)<2:return
            l=run[0][0]
            pts=[P(*c) for c in run]
            # merge collinear points
            out=[pts[0]]
            for k in range(1,len(pts)-1):
                a=out[-1];b=pts[k];c=pts[k+1]
                if abs((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))>1e-7:out.append(b)
            out.append(pts[-1])
            for a,b in zip(out,out[1:]):segs.append((a[0],a[1],b[0],b[1],l))
        for a,b in zip(cells,cells[1:]):
            if a[0]==b[0]:run.append(b)
            else:
                flush(run);vias.append(P(a[0],a[1],a[2]));run=[b]
        flush(run)
        if via_end:vias.append(P(0,via_end[0],via_end[1]))
        return segs,vias
    def commit(s,net,segs,vias,cls='sig'):
        for (x0,y0,x1,y1,l) in segs:
            it=dict(kind='seg',x0=x0,y0=y0,x1=x1,y1=y1,w=W[cls][l],net=net,layers=[l])
            s.add(it);s.new_segments.append((net,it))
        for (x,y) in vias:
            it=dict(kind='via',x=x,y=y,r=VIA_D/2,net=net,layers=[0,1,2,3]);s.add(it);s.new_vias.append((net,it))
    def write(s,out):
        t=s.t;txt=''
        for net,it in s.new_segments:
            txt+='\n\t(segment (start %.4f %.4f) (end %.4f %.4f) (width %s) (layer "%s") (net "%s") (uuid "%s"))'%(it['x0']+CX,it['y0']+CY,it['x1']+CX,it['y1']+CY,it['w'],RL[it['layers'][0]],net,uuid.uuid4())
        for net,it in s.new_vias:
            txt+='\n\t(via (at %.4f %.4f) (size %s) (drill %s) (layers "F.Cu" "B.Cu") (net "%s") (uuid "%s"))'%(it['x']+CX,it['y']+CY,VIA_D,VIA_DR,net,uuid.uuid4())
        i=t.rindex('\n)');open(out,'w',encoding='utf8').write(t[:i]+txt+t[i:])
