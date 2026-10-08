import sys,os,re,math,collections,heapq
sys.path.insert(0,os.environ['TEMP'])
import numpy as np
from bgeom import Geo,CX,CY,LAYERS
RES=0.05;GX0,GY0=-20.0,-21.0;NX=int(round(40/RES));NY=int(round(46/RES))
def ci(x):return int(math.floor((x-GX0)/RES))
def cj(y):return int(math.floor((y-GY0)/RES))
xs=GX0+(np.arange(NX)+0.5)*RES;ys=GY0+(np.arange(NY)+0.5)*RES
XX,YY=np.meshgrid(xs,ys)
def disk_dilate(mask,r):
    k=int(math.ceil(r/RES));yy,xx=np.ogrid[-k:k+1,-k:k+1];ker=((xx*xx+yy*yy)<=(r/RES)**2).astype(np.float32)
    sh=(mask.shape[0]+2*k,mask.shape[1]+2*k)
    a=np.zeros(sh,np.float32);a[k:k+mask.shape[0],k:k+mask.shape[1]]=mask
    kk=np.zeros(sh,np.float32);kk[:ker.shape[0],:ker.shape[1]]=ker
    c=np.fft.irfft2(np.fft.rfft2(a)*np.fft.rfft2(kk),s=sh)
    return c[2*k:2*k+mask.shape[0],2*k:2*k+mask.shape[1]]>0.5
def rectmask(m,x,y,w,h,val=True):
    m[max(0,cj(y-h/2)):cj(y+h/2)+1,max(0,ci(x-w/2)):ci(x+w/2)+1]=val
def circmask(m,x,y,r):
    j0=max(0,cj(y-r)-1);j1=cj(y+r)+2;i0=max(0,ci(x-r)-1);i1=ci(x+r)+2
    m[j0:j1,i0:i1]|=((XX[j0:j1,i0:i1]-x)**2+(YY[j0:j1,i0:i1]-y)**2<=r*r)
def obstacle_map(G,layer,net,inside):
    """foreign copper on this layer (bool grid, uninflated) + outside-of-board"""
    m=~inside
    for it in G.items:
        if it['net']==net and net!='':continue
        if layer not in it['layers']:continue
        if it['kind']=='pad':rectmask(m,it['x'],it['y'],it['w'],it['h'])
        elif it['kind']=='via':circmask(m,it['x'],it['y'],it['r'])
        else:
            n=max(1,int(math.hypot(it['x1']-it['x0'],it['y1']-it['y0'])/0.05))
            for k in range(n+1):
                circmask(m,it['x0']+(it['x1']-it['x0'])*k/n,it['y0']+(it['y1']-it['y0'])*k/n,it['w']/2)
    return m
def bfs(free,src,dst):
    """4-connected flood from src cells; returns path (list of (j,i)) to first dst cell or None"""
    H,W=free.shape;prev={};dq=collections.deque()
    for s in src:
        if free[s]:prev[s]=None;dq.append(s)
    while dq:
        j,i=dq.popleft()
        if dst[j,i]:
            path=[];cur=(j,i)
            while cur is not None:path.append(cur);cur=prev[cur]
            return path[::-1]
        for dj,di in((1,0),(-1,0),(0,1),(0,-1)):
            nj,ni=j+dj,i+di
            if 0<=nj<H and 0<=ni<W and free[nj,ni] and (nj,ni) not in prev:
                prev[(nj,ni)]=(j,i);dq.append((nj,ni))
    return None
def widest(G,layer,net,src_rects,dst_rects,inside,clearance=0.16,wmax=2.4,wmin=0.3):
    obs=obstacle_map(G,layer,net,inside)
    srcm=np.zeros((NY,NX),bool);dstm=np.zeros((NY,NX),bool)
    for r in src_rects:rectmask(srcm,*r)
    for r in dst_rects:rectmask(dstm,*r)
    lo,hi=wmin,wmax;best=None
    cache={}
    def test(w):
        infl=disk_dilate(obs,clearance+w/2)
        free=~infl
        src=[(j,i) for j,i in zip(*np.nonzero(srcm&free))]
        if not src:return None
        return bfs(free,src,dstm&free)
    if test(wmin) is None:return None,0
    for _ in range(7):
        mid=(lo+hi)/2;p=test(mid)
        if p is not None:lo=mid;best=p
        else:hi=mid
    if best is None:best=test(lo)
    return best,lo
def simplify(path,tol=0.15):
    pts=[(GX0+(i+0.5)*RES,GY0+(j+0.5)*RES) for j,i in path]
    out=[pts[0]]
    def dist(p,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1]
        if dx==dy==0:return math.dist(p,a)
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)));return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)
    def rec(a,b):
        if b-a<2:return []
        m=max(range(a+1,b),key=lambda k:dist(pts[k],pts[a],pts[b]))
        if dist(pts[m],pts[a],pts[b])>tol:return rec(a,m)+[pts[m]]+rec(m,b)
        return []
    return [pts[0]]+rec(0,len(pts)-1)+[pts[-1]]

def inside_grid(B):
    from engine import outline_mask
    _,poly=outline_mask(B.t)
    ins=np.zeros((NY,NX),bool);n=len(poly)
    for a in range(n):
        x1,y1=poly[a];x2,y2=poly[(a+1)%n]
        cond=((y1>YY)!=(y2>YY))
        with np.errstate(divide='ignore',invalid='ignore'):
            xint=(x2-x1)*(YY-y1)/(y2-y1)+x1
        ins^=cond&(XX<xint)
    return ins

def path8(free,src,dst):
    """shortest 8-connected path (octile cost) from any src cell to any dst cell inside free"""
    H,W=free.shape;INF=1e18;dist={};pq=[];prev={}
    for sc in src:
        if free[sc]:dist[sc]=0.0;heapq.heappush(pq,(0.0,sc));prev[sc]=None
    nb=[(1,0,1.0),(-1,0,1.0),(0,1,1.0),(0,-1,1.0),(1,1,1.4142),(1,-1,1.4142),(-1,1,1.4142),(-1,-1,1.4142)]
    while pq:
        d,(j,i)=heapq.heappop(pq)
        if d>dist.get((j,i),INF):continue
        if dst[j,i]:
            out=[];cur=(j,i)
            while cur is not None:out.append(cur);cur=prev[cur]
            return out[::-1]
        for dj,di,c in nb:
            nj,ni=j+dj,i+di
            if 0<=nj<H and 0<=ni<W and free[nj,ni]:
                if dj and di and not(free[j+dj,i] and free[j,i+di]):continue
                nd=d+c
                if nd<dist.get((nj,ni),INF):
                    dist[(nj,ni)]=nd;prev[(nj,ni)]=(j,i);heapq.heappush(pq,(nd,(nj,ni)))
    return None
def lane(G,layer,net,src_rects,dst_rects,inside,clearance=0.16,wmax=2.4,wmin=0.3,shrink=0.9):
    path,w=widest(G,layer,net,src_rects,dst_rects,inside,clearance,wmax,wmin)
    if path is None:return None,0
    wt=max(wmin,round(w*shrink,2))
    obs=obstacle_map(G,layer,net,inside);free=~disk_dilate(obs,clearance+wt/2)
    srcm=np.zeros((NY,NX),bool);dstm=np.zeros((NY,NX),bool)
    for r in src_rects:rectmask(srcm,*r)
    for r in dst_rects:rectmask(dstm,*r)
    src=[(j,i) for j,i in zip(*np.nonzero(srcm&free))]
    p8=path8(free,src,dstm&free)
    return p8,wt
