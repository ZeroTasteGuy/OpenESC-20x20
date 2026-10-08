import sys,os,re,math
sys.path.insert(0,os.environ['TEMP'])
from engine import *
B=Board('4in1.kicad_pcb')
inside,pts=outline_mask(B.t)
isP=lambda r:re.match(r'(C|R|TP)\d',r) is not None
small=[r for r,f in B.fps.items() if isP(r) or r in('U12','U13','U14','U15') or re.search('QFN-2',f['lib'])]
def rect_dist(a,b):
    dx=max(abs(a[0]-b[0])-(a[2]+b[2])/2,0);dy=max(abs(a[1]-b[1])-(a[3]+b[3])/2,0);return math.hypot(dx,dy)
big=[(p['x'],p['y'],p['w'],p['h']) for p in B.fps['U3']['pads'] if p['n']!='11']
def segd(p,a,b):
    ax,ay=a;bx,by=b;px,py=p;dx,dy=bx-ax,by-ay
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy+1e-12)));return math.hypot(px-ax-t*dx,py-ay-t*dy)
segs=[(pts[i],pts[(i+1)%len(pts)]) for i in range(len(pts))]
def edge_dist(r):
    best=9e9
    for p in B.fps[r]['pads']:
        for sx in(-1,1):
            for sy in(-1,1):
                c=(p['x']+sx*p['w']/2,p['y']+sy*p['h']/2)
                best=min(best,min(segd(c,a,b) for a,b in segs))
    return best
res=[]
for r in small:
    f=B.fps[r]
    d_pad=min(rect_dist((p['x'],p['y'],p['w'],p['h']),b) for p in f['pads'] for b in big)
    d_edge=edge_dist(r)
    res.append((r,d_pad,d_edge))
bad=[x for x in res if x[1]<3.0-0.01 or x[2]<2.0-0.01]
print('small parts',len(res),'violations',len(bad))
for r,dp,de in sorted(bad,key=lambda x:min(x[1]-3,x[2]-2))[:25]:print(r,'pad %.2f edge %.2f'%(dp,de))
print('min pad dist %.2f  min edge dist %.2f'%(min(x[1] for x in res),min(x[2] for x in res)))
