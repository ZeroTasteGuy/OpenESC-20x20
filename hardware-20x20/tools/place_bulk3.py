import sys,os,re,math,uuid
sys.path.insert(0,os.environ['TEMP'])
from engine import *
from freemap import build_occ
from pcbutil import toplevel
SRC=os.environ.get('SRC','4in1.kicad_pcb');DST=os.environ.get('DST','4in1_bulk2.kicad_pcb')
EDGE=float(os.environ.get('EDGE','0.6'));NMAX=int(os.environ.get('NMAX','30'));LIM=float(os.environ.get('LIM','9.0'))
t=open(SRC,encoding='utf8').read()
o=open('../hardware/4in1.kicad_pcb',encoding='utf8').read()
blocks=[]
for s,e,h in toplevel(o):
    if h=='footprint':
        b=o[s:e]
        if b.startswith('(footprint "Capacitor_SMD:C_1206_3216Metric"') and '(path "' not in b: blocks.append(b)
fpat=re.compile(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)')
def retarget(b,x,y,th):
    m0=fpat.search(b);old=float(m0.group(3) or 0)
    head=b[:m0.start()]+'\n\t\t(at %.3f %.3f %g)'%(x,y,th);rest=b[m0.end():]
    def sh(m):
        a=float(m.group(3) or 0);n=((a-old+th+180)%360)-180
        if n==-180:n=180
        return '(at %s %s %g)'%(m.group(1),m.group(2),n)
    return head+re.sub(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)',sh,rest)
# existing 1206 bulk parts in the SRC board are re-placed too (C2,C3,C6 and any CB*)
B0=Board(SRC)
old=[r for r,f in B0.fps.items() if '1206' in f['lib']]
cut=[]
for r in old:
    f=B0.fps[r];cut.append((f['s'],f['e']))
for s,e in sorted(cut,reverse=True):
    q=s
    while t[q-1] in '\t\n ':q-=1
    t=t[:q]+t[e:]
# keep the schematic-linked blocks for C2,C3,C6 (they carry paths)
keep={r:B0.fps[r]['b'] for r in old if not r.startswith('CB')}
pool=list(keep.items())
k=1
while len(pool)<NMAX:
    b=blocks[(k-1)%len(blocks)]
    b=re.sub(r'\(uuid "[^"]+"\)',lambda m:'(uuid "%s")'%uuid.uuid4(),b)
    b=re.sub(r'(\(property "Reference" )"[^"]*"',r'\1"CB%d"'%k,b,count=1)
    pool.append(('CB%d'%k,b));k+=1
new=''
for ref,b in pool: new+='\n\t'+retarget(b,CX+40,CY,0)
i=t.index('\n\t(gr_line');t=t[:i]+new+t[i:]
open(DST,'w',encoding='utf8').write(t)
B=Board(DST);fps=B.fps
BULK=[r for r,_ in pool];MARG=0.1
occ,inside=build_occ(B,MARG,skip=set(BULK))
def bbox_fill(f):
    sm=[p for p in f['pads'] if not p['th']]
    big=len(sm)>=5 or f['ref']=='U14' or '1206' in f['lib']
    if not big or f['ref']=='U3' or len(sm)<2:return
    xs0=min(p['x']-p['w']/2 for p in sm);xs1=max(p['x']+p['w']/2 for p in sm)
    ys0=min(p['y']-p['h']/2 for p in sm);ys1=max(p['y']+p['h']/2 for p in sm)
    rect_mark(occ[f['layer'][0]],(xs0+xs1)/2,(ys0+ys1)/2,xs1-xs0,ys1-ys0,0.15)
for f in fps.values():
    if f['ref'] not in BULK and abs(f['x'])<22: bbox_fill(f)
eb=dilate(~inside,EDGE)
for sd in 'FB': occ[sd]|=eb
f0=fps[BULK[0]];loc=[]
for m in re.finditer(r'\n\t\t\(pad "([^"]*)" (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s*\(size ([-\d.]+) ([-\d.]+)\)([\s\S]*?)\n\t\t\)',f0['b']):
    nm,typ,shp,px,py,pa,w,hh,rest=m.groups()
    net=re.search(r'\(net "([^"]*)"',rest).group(1)
    loc.append((nm,float(px),float(py),float(w),float(hh),net))
print('bulk pad nets',[(a,n) for a,_,_,_,_,n in loc])
def geo(th,side):
    r=math.radians(th);out=[]
    for nm,px,py,w,hh,net in loc:
        if side=='B':py=-py
        dx=px*math.cos(r)+py*math.sin(r);dy=-px*math.sin(r)+py*math.cos(r)
        sw=round(th)%180==90
        out.append((nm,dx,dy,hh if sw else w,w if sw else hh,net))
    return out
xs=np.arange(X0,X1,RES)+RES/2;ys=np.arange(Y0,Y1,RES)+RES/2
XX,YY=np.meshgrid(xs,ys)
# distance fields to the MOSFET pads a bulk cap must serve
def field(net,names):
    pts=[(p['x'],p['y']) for r,f in fps.items() if r.startswith('Q') for p in f['pads'] if p['net']==net and p['n'] in names]
    d=np.full(XX.shape,1e3)
    for (px,py) in pts:d=np.minimum(d,np.hypot(XX-px,YY-py))
    return d
DB=field('+BATT',('3',));DG=field('GND',('1',))
def shift(a,dx,dy):
    oi,oj=int(round(dx/RES)),int(round(dy/RES))
    out=np.full(a.shape,1e3)
    j0=max(0,-oj);j1=min(a.shape[0],a.shape[0]-oj);i0=max(0,-oi);i1=min(a.shape[1],a.shape[1]-oi)
    out[j0:j1,i0:i1]=a[j0+oj:j1+oj,i0+oi:i1+oi]
    return out
def integral(g):
    S=np.zeros((NY+1,NX+1),np.int32);S[1:,1:]=g.astype(np.int32).cumsum(0).cumsum(1);return S
def valid_map(S,rects):
    ok=np.ones((NY,NX),bool)
    for dx,dy,w,h in rects:
        oi,oj=int(round(dx/RES)),int(round(dy/RES))
        a=int(math.ceil((w/2+MARG)/RES-1e-9));b=int(math.ceil((h/2+MARG)/RES-1e-9))
        j0=np.arange(NY)+oj-b;j1=np.arange(NY)+oj+b+1
        i0=np.arange(NX)+oi-a;i1=np.arange(NX)+oi+a+1
        inb_j=(j0>=0)&(j1<=NY);inb_i=(i0>=0)&(i1<=NX)
        j0c=np.clip(j0,0,NY);j1c=np.clip(j1,0,NY);i0c=np.clip(i0,0,NX);i1c=np.clip(i1,0,NX)
        win=S[j1c][:,i1c]-S[j0c][:,i1c]-S[j1c][:,i0c]+S[j0c][:,i0c]
        ok&=(win==0)&inb_j[:,None]&inb_i[None,:]
    return ok
placed=[]
quad=lambda x,y:(0 if x<0 else 1)+(0 if y<0 else 2)
qcount=[0,0,0,0];hcount=[0,0]
variants=[(side,th) for side in 'FB' for th in (0,90)]
while len(placed)<NMAX:
    best=None
    for side,th in variants:
        g=geo(th,side)
        bx0=min(dx-w/2 for _,dx,dy,w,h,_ in g);bx1=max(dx+w/2 for _,dx,dy,w,h,_ in g);by0=min(dy-h/2 for _,dx,dy,w,h,_ in g);by1=max(dy+h/2 for _,dx,dy,w,h,_ in g)
        rect=[((bx0+bx1)/2,(by0+by1)/2,bx1-bx0,by1-by0)]
        S=integral(occ[side]);ok=valid_map(S,rect)
        okm=ok[:,::-1]
        wx=bx1-bx0
        c=np.zeros(XX.shape)
        for nm,dx,dy,w,h,net in g:
            c+=shift(DB if net=='+BATT' else DG,dx,dy)
        # side penalty: MOSFET pads that are mostly top -> bottom caps pay 1.5 mm via
        if side=='B':c+=float(os.environ.get('BPEN','1.5'))
        ax=np.abs(XX)
        valid=ok&okm&((ax<0.06)|(ax*2>=wx+0.25))&(XX>=-1e-9)
        if hcount[0]-hcount[1]>=2: valid&=(YY>=0)
        elif hcount[1]-hcount[0]>=2: valid&=(YY<0)
        if not valid.any():continue
        Qi=(XX>=0).astype(int)+2*(YY>=0).astype(int)
        pen=0.6*np.maximum(0,np.array(qcount)[Qi]-5)
        cost=np.where(valid,c+pen,1e9)
        j,i=np.unravel_index(np.argmin(cost),cost.shape)
        if best is None or cost[j,i]<best[0]:best=(cost[j,i],xs[i],ys[j],side,th,rect)
    if best is None or best[0]>LIM*2:break
    cst,x,y,side,th,rect=best
    x=round(float(x),2);y=round(float(y),2)
    xl=[x] if abs(x)<0.06 else [x,-x]
    if len(placed)+len(xl)>NMAX:break
    for X in xl:
        for dx,dy,w,h in rect:rect_mark(occ[side],X+dx,y+dy,w,h,MARG)
        placed.append((side,X,y,th,cst));qcount[quad(X,y)]+=1;hcount[0 if y<0 else 1]+=1
print('placed',len(placed),'top/bottom half',hcount,'quadrant counts',qcount,'mean pair cost %.1f'%(sum(p[4] for p in placed)/max(1,len(placed))))
# write poses
t=open(DST,encoding='utf8').read()
def flipb(b):
    m0=fpat.search(b);head=b[:m0.end()];rest=b[m0.end():]
    for kk in('Cu','Mask','Paste','SilkS','Fab','CrtYd','Adhes'):
        head=head.replace('"F.%s"'%kk,'"B.%s"'%kk);rest=rest.replace('"F.%s"'%kk,'"B.%s"'%kk)
    rest=re.sub(r'\((at|start|end|mid|center|xy) ([-\d.]+) ([-\d.]+)((?: [-\d.]+)?)\)',lambda m:'(%s %s %s%s)'%(m.group(1),m.group(2),('%g'%(-float(m.group(3)))),m.group(4)),rest)
    return head+rest
B2=Board(DST);edits=[]
# order refs: keep C2,C3,C6 first
for k,(side,x,y,th,_) in enumerate(placed):
    ref=BULK[k];f=B2.fps[ref];b=retarget(f['b'],0,0,0)
    if side=='B':b=flipb(b)
    edits.append((f['s'],f['e'],retarget(b,x+CX,y+CY,th)))
for k in range(len(placed),len(BULK)):
    f=B2.fps[BULK[k]];edits.append((f['s'],f['e'],''))
for s,e,nb in sorted(edits,reverse=True):t=t[:s]+nb+t[e:]
open(DST,'w',encoding='utf8').write(t)
print('written',DST)
