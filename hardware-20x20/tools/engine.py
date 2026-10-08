import sys,os,re,math
sys.path.insert(0,os.environ['TEMP'])
import numpy as np
from pcbutil import toplevel
CX,CY=75.6,47.35
RES=0.1
X0,Y0,X1,Y1=-22.05,-25.05,22.05,25.05
NX,NY=int(round((X1-X0)/RES)),int(round((Y1-Y0)/RES))
def gi(x,y):return int(round((x-X0)/RES)),int(round((y-Y0)/RES))
class Board:
    def __init__(s,path):
        s.path=path;s.t=open(path,encoding='utf8').read();s.load()
    def load(s):
        t=s.t;s.fps={};s.order=[]
        for st,e,h in toplevel(t):
            if h!='footprint':continue
            b=t[st:e]
            ref=re.search(r'\(property "Reference" "([^"]*)"',b).group(1)
            lay=re.search(r'\(layer "([^"]+)"\)',b).group(1)
            fx,fy,fr=re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)',b).groups()
            fx,fy,fr=float(fx),float(fy),float(fr or 0)
            val=re.search(r'\(property "Value" "([^"]*)"',b).group(1)
            sh=re.search(r'\(sheetname "([^"]*)"',b);sh=sh.group(1) if sh else ''
            lib=re.match(r'\(footprint "([^"]+)"',b).group(1)
            pads=[]
            r=math.radians(fr)
            for m in re.finditer(r'\n\t\t\(pad "([^"]*)" (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s*\(size ([-\d.]+) ([-\d.]+)\)([\s\S]*?)\n\t\t\)',b):
                nm,typ,shp,px,py,pa,w,hh,rest=m.groups();px,py,pa,w,hh=float(px),float(py),float(pa or 0),float(w),float(hh)
                x=fx+px*math.cos(r)+py*math.sin(r)-CX;y=fy-px*math.sin(r)+py*math.cos(r)-CY
                if round(pa)%180!=0:w,hh=hh,w
                lm=re.search(r'\(layers ([^)]*)\)',rest);net=re.search(r'\(net "([^"]*)"',rest)
                om=re.search(r'\(offset ([-\d.]+) ([-\d.]+)\)',rest)
                if om: x+=float(om.group(1));y+=float(om.group(2))
                th=typ in('thru_hole','np_thru_hole')
                sides={'F','B'} if th else {'F' if '"F.Cu"' in lm.group(1) else 'B'}
                pads.append(dict(n=nm,x=x,y=y,w=w,h=hh,net=net.group(1) if net else '',sides=sides,th=th,typ=typ))
            s.fps[ref]=dict(ref=ref,s=st,e=e,b=b,layer=lay,x=fx-CX,y=fy-CY,rot=fr,val=val,sheet=sh,lib=lib,pads=pads)
    def netpads(s):
        d={}
        for f in s.fps.values():
            for p in f['pads']:
                d.setdefault(p['net'],[]).append((f['ref'],p))
        return d
def outline_mask(t):
    """returns bool grid of inside-board"""
    poly=[]
    segs=[]
    for st,e,h in toplevel(t):
        b=t[st:e]
        if h in('gr_line','gr_arc') and '"Edge.Cuts"' in b:
            g=lambda k:list(map(float,re.search(r'\(%s ([-\d.]+) ([-\d.]+)\)'%k,b).groups()))
            a=g('start');z=g('end')
            if h=='gr_line': segs.append([a,z])
            else:
                m=g('mid');ax,ay=a;bx,by=m;cx,cy=z
                D=2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
                ux=((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/D
                uy=((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/D
                r=math.hypot(ax-ux,ay-uy)
                a0=math.atan2(ay-uy,ax-ux);am=math.atan2(by-uy,bx-ux);a1=math.atan2(cy-uy,cx-ux)
                def norm(a):return a%(2*math.pi)
                d1=norm(am-a0);d2=norm(a1-a0)
                if d1>d2: d2=d2-2*math.pi  # go the other way
                pts=[[ux+r*math.cos(a0+d2*i/12),uy+r*math.sin(a0+d2*i/12)] for i in range(13)]
                for i in range(12): segs.append([pts[i],pts[i+1]])
    # order into polygon by chaining
    segs=[[(p[0]-CX,p[1]-CY) for p in s] for s in segs]
    pts=[segs[0][0],segs[0][1]];used={0}
    while len(used)<len(segs):
        for i,s in enumerate(segs):
            if i in used:continue
            if math.dist(s[0],pts[-1])<0.01: pts.append(s[1]);used.add(i);break
            if math.dist(s[1],pts[-1])<0.01: pts.append(s[0]);used.add(i);break
        else: break
    xs=np.arange(X0,X1,RES)+RES/2;ys=np.arange(Y0,Y1,RES)+RES/2
    XX,YY=np.meshgrid(xs,ys)  # shape NY,NX
    inside=np.zeros(XX.shape,bool)
    n=len(pts)
    for i in range(n):
        x1,y1=pts[i];x2,y2=pts[(i+1)%n]
        cond=((y1>YY)!=(y2>YY))
        with np.errstate(divide='ignore',invalid='ignore'):
            xint=(x2-x1)*(YY-y1)/(y2-y1)+x1
        inside^=cond&(XX<xint)
    return inside,pts
def dilate(m,r):
    k=int(round(r/RES))
    out=m.copy()
    for dx in range(-k,k+1):
        for dy in range(-k,k+1):
            if dx*dx+dy*dy<=k*k+0.5:
                out|=np.roll(np.roll(m,dx,1),dy,0)
    return out
def rect_mark(g,x,y,w,h,m=0.0):
    i0,j0=gi(x-w/2-m,y-h/2-m);i1,j1=gi(x+w/2+m,y+h/2+m)
    g[max(j0,0):j1+1,max(i0,0):i1+1]=True
def rect_free(g,x,y,w,h,m=0.0):
    i0,j0=gi(x-w/2-m,y-h/2-m);i1,j1=gi(x+w/2+m,y+h/2+m)
    if i0<0 or j0<0 or i1>=NX or j1>=NY:return False
    return not g[j0:j1+1,i0:i1+1].any()
