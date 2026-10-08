"""Resistor-network analysis of copper nets from filled zones (needs a refilled board).
usage: python rsolve.py board.kicad_pcb ESCn   -> prints loop resistances / current density"""
import sys,os,re,math,collections,time
sys.path.insert(0,os.environ['TEMP'])
import numpy as np
from engine import Board,CX,CY
from pcbutil import toplevel
RES=0.1;GX0,GY0=-20.0,-21.0;NX=int(40/RES);NY=int(46/RES)
LAY=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu'];LI={l:i for i,l in enumerate(LAY)}
RHO=1.72e-8*1e3        # ohm*m -> mOhm*m ... used below in mOhm
TH=[70e-6,35e-6,35e-6,35e-6,35e-6,70e-6]
RSQ=[1.72e-8/t*1e3 for t in TH]    # mOhm per square
G_SQ=[1/r for r in RSQ]            # 1/mOhm
G_LINK=1/0.4                       # via hub link, 1/mOhm  (barrel ~1 mOhm end to end)
def cx(x):return int(math.floor((x-GX0)/RES))
def cy(y):return int(math.floor((y-GY0)/RES))
def raster(pts,mask):
    P=np.array([((x-CX-GX0)/RES,(y-CY-GY0)/RES) for x,y in pts]);n=len(P)
    if n<3:return
    x1=P[:,0];y1=P[:,1];x2=np.roll(x1,-1);y2=np.roll(y1,-1)
    for row in range(max(0,int(y1.min())),min(NY-1,int(y1.max())+1)+1):
        yc=row+0.5;m=((y1<=yc)&(y2>yc))|((y2<=yc)&(y1>yc))
        if not m.any():continue
        xi=x1[m]+(yc-y1[m])*(x2[m]-x1[m])/(y2[m]-y1[m]);xi.sort()
        for a in range(0,len(xi)-1,2):
            xa=max(0,int(round(xi[a])));xb=min(NX,int(round(xi[a+1])))
            if xb>xa:mask[row,xa:xb]^=True
class Net:
    def __init__(s,B,t,net):
        s.net=net;s.m=np.zeros((6,NY,NX),bool);s.vias=[]
        for st,e,h in toplevel(t):
            b=t[st:e]
            if h=='zone':
                n=re.search(r'\(net "([^"]*)"\)',b)
                if not n or n.group(1)!=net:continue
                for m in re.finditer(r'\(filled_polygon\s*\(layer "([^"]+)"\)\s*\(pts([\s\S]*?)\)\s*\)',b):
                    if m.group(1) not in LI:continue
                    pts=[(float(a),float(c)) for a,c in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)',m.group(2))]
                    tmp=np.zeros((NY,NX),bool);raster(pts,tmp);s.m[LI[m.group(1)]]|=tmp
            elif h=='segment':
                a=re.search(r'\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)',b);n=re.search(r'\(net "([^"]*)"',b)
                if a and n and n.group(1)==net and a.group(6) in LI:
                    x0,y0,x1,y1,w=[float(a.group(k))-(CX if k in(1,3) else CY if k in (2,4) else 0) for k in range(1,6)]
                    s.stroke(LI[a.group(6)],x0,y0,x1,y1,w)
            elif h=='via':
                a=re.search(r'\(at ([-\d.]+) ([-\d.]+)\)',b);n=re.search(r'\(net "([^"]*)"',b)
                if n and n.group(1)==net:
                    sz=float(re.search(r'\(size ([\d.]+)\)',b).group(1));x=float(a.group(1))-CX;y=float(a.group(2))-CY
                    s.vias.append((x,y,sz))
        s.pads={}
        for r,f in B.fps.items():
            if abs(f['x'])>25:continue
            for p in f['pads']:
                if p['net']==net:
                    for l in LAY:
                        if p['th'] or (l=='F.Cu' and 'F' in p['sides']) or (l=='B.Cu' and 'B' in p['sides']):
                            s.m[LI[l]][max(0,cy(p['y']-p['h']/2)):cy(p['y']+p['h']/2)+1,max(0,cx(p['x']-p['w']/2)):cx(p['x']+p['w']/2)+1]=True
        s.close()
    def close(s):
        for l in range(6):
            m=s.m[l];d=m.copy()
            d[1:]|=m[:-1];d[:-1]|=m[1:]
            d2=d.copy();d2[:,1:]|=d[:,:-1];d2[:,:-1]|=d[:,1:]
            e=d2.copy();e[1:]&=d2[:-1];e[:-1]&=d2[1:]
            e2=e.copy();e2[:,1:]&=e[:,:-1];e2[:,:-1]&=e[:,1:]
            s.m[l]=m|e2
    def stroke(s,l,x0,y0,x1,y1,w):
        n=max(1,int(math.hypot(x1-x0,y1-y0)/(RES/2)))
        for k in range(n+1):
            x=x0+(x1-x0)*k/n;y=y0+(y1-y0)*k/n
            r=int(math.ceil(w/2/RES));j=cy(y);i=cx(x)
            for dj in range(-r,r+1):
                for di in range(-r,r+1):
                    if (dj*RES)**2+(di*RES)**2<=(w/2)**2+RES*RES and 0<=j+dj<NY and 0<=i+di<NX:s.m[l][j+dj,i+di]=True
def padmask(B,ref_pn_list=None,pred=None,layers=None):
    out=np.zeros((6,NY,NX),bool)
    for r,f in B.fps.items():
        if abs(f['x'])>25:continue
        for p in f['pads']:
            if pred(r,p):
                for l in LAY:
                    if p['th'] or (l=='F.Cu' and 'F' in p['sides']) or (l=='B.Cu' and 'B' in p['sides']):
                        out[LI[l]][max(0,cy(p['y']-p['h']/2)):cy(p['y']+p['h']/2)+1,max(0,cx(p['x']-p['w']/2)):cx(p['x']+p['w']/2)+1]=True
    return out
def solve(N,srcm,snkm,tol=1e-6,maxit=20000,want_field=False):
    """R between source and sink sets (mOhm) in net N"""
    m=N.m.copy();src=srcm&m;snk=snkm&m
    if not src.any() or not snk.any():return None,None
    gl=np.array(G_SQ,np.float64)[:,None,None]
    gx=(m[:,:,:-1]&m[:,:,1:])*gl;gy=(m[:,:-1,:]&m[:,1:,:])*gl
    # via hubs
    hub_cells=[];hub_id=[]
    for h,(x,y,sz) in enumerate(N.vias):
        j,i=cy(y),cx(x)
        for l in range(6):
            if 0<=j<NY and 0<=i<NX and m[l,j,i]:hub_cells.append((l,j,i));hub_id.append(h)
    nh=len(N.vias);hc=np.array(hub_cells,int) if hub_cells else np.zeros((0,3),int);hid=np.array(hub_id,int)
    deg=np.zeros((6,NY,NX));deg[:,:,:-1]+=gx;deg[:,:,1:]+=gx;deg[:,:-1,:]+=gy;deg[:,1:,:]+=gy
    if len(hc):np.add.at(deg,(hc[:,0],hc[:,1],hc[:,2]),G_LINK)
    hdeg=np.zeros(nh)
    if len(hc):np.add.at(hdeg,hid,G_LINK)
    fixed=src|snk
    free=m&~fixed
    def A(v,hv):
        y=deg*v
        y[:,:,:-1]-=gx*v[:,:,1:];y[:,:,1:]-=gx*v[:,:,:-1];y[:,:-1,:]-=gy*v[:,1:,:];y[:,1:,:]-=gy*v[:,:-1,:]
        yh=hdeg*hv
        if len(hc):
            np.add.at(y,(hc[:,0],hc[:,1],hc[:,2]),-G_LINK*hv[hid])
            np.add.at(yh,hid,-G_LINK*v[hc[:,0],hc[:,1],hc[:,2]])
        return y,yh
    v=np.zeros((6,NY,NX));v[src]=1.0;hv=np.zeros(nh)
    y,yh=A(v,hv)
    b=-y*free;bh=-yh
    # hubs with no source connection but links: free too
    x=np.zeros_like(v);xh=np.zeros(nh)
    d=np.where(free&(deg>0),deg,1.0);dh=np.where(hdeg>0,hdeg,1.0)
    def mv(x,xh):
        y,yh=A(x*free,xh);return y*free,yh
    r=b.copy();rh=bh.copy();z=r/d;zh=rh/dh;p=z.copy();ph=zh.copy();rz=(r*z).sum()+(rh*zh).sum();b0=math.sqrt((b*b).sum()+(bh*bh).sum())+1e-30
    for it in range(maxit):
        Ap,Aph=mv(p,ph);alpha=rz/((p*Ap).sum()+(ph*Aph).sum()+1e-300)
        x+=alpha*p;xh+=alpha*ph;r-=alpha*Ap;rh-=alpha*Aph
        if math.sqrt((r*r).sum()+(rh*rh).sum())/b0<tol:break
        z=r/d;zh=rh/dh;rz2=(r*z).sum()+(rh*zh).sum();beta=rz2/rz;rz=rz2;p=z+beta*p;ph=zh+beta*ph
    V=x*free+v;V[snk]=0.0
    # current out of source set
    y,yh=A(V,xh)
    I=float((y*src).sum())
    R=1.0/I if I>0 else None
    if want_field:return R,(V,xh,gx,gy,gl)
    return R,it
def peakK(V,gx,gy,gl,I_amp,R):
    """sheet current density A/mm per layer scaled to I_amp total"""
    sc=I_amp*R   # volts scale: V in 1V -> actual dV = I*R(mOhm) mV; use ratio
    out=[]
    for l in range(6):
        ix=np.abs(gx[l]*(V[l,:,:-1]-V[l,:,1:]));iy=np.abs(gy[l]*(V[l,:-1,:]-V[l,1:,:]))
        # branch current in "units" (1V/1mOhm=1kA); K per unit width: I/RES
        k=np.zeros((NY,NX));k[:,:-1]=np.maximum(k[:,:-1],ix);k[:,1:]=np.maximum(k[:,1:],ix);k[:-1,:]=np.maximum(k[:-1,:],iy);k[1:,:]=np.maximum(k[1:,:],iy)
        out.append(k)
    return out
