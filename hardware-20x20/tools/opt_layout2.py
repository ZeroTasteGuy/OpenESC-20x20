import sys,os,re,math,random,json
sys.path.insert(0,os.environ['TEMP'])
import numpy as np
from engine import Board,outline_mask,CX,CY
from pcbutil import toplevel
random.seed(int(os.environ.get('SEED','7')))
OUTL=float(os.environ.get('OUTLIER','0.12'))
P=sys.argv[1] if len(sys.argv)>1 else '4in1.kicad_pcb'
OUT=sys.argv[2] if len(sys.argv)>2 else P
PASSES=int(os.environ.get('PASSES','8'))
# ---------------------------------------------------------------- grid
RES=0.05;GX0,GY0=-20.0,-21.0;NX=int(round(40/RES));NY=int(round(45.6/RES))
M=0.10                      # margin on every pad rect (gap >= ~0.17 mm)
def ci(x):return int(math.floor((x-GX0)/RES))
def cj(y):return int(math.floor((y-GY0)/RES))
def rect_idx(x,y,w,h,m):
    return cj(y-h/2-m),cj(y+h/2+m),ci(x-w/2-m),ci(x+w/2+m)
def mark(g,x,y,w,h,m,val=True):
    j0,j1,i0,i1=rect_idx(x,y,w,h,m)
    g[max(j0,0):j1+1,max(i0,0):i1+1]=val
def addc(g,x,y,w,h,m,d):
    j0,j1,i0,i1=rect_idx(x,y,w,h,m)
    g[max(j0,0):j1+1,max(i0,0):i1+1]+=d
def hit(st,dy,x,y,w,h,m):
    j0,j1,i0,i1=rect_idx(x,y,w,h,m)
    if j0<0 or i0<0 or j1>=NY or i1>=NX:return True
    return st[j0:j1+1,i0:i1+1].any() or (dy[j0:j1+1,i0:i1+1]>0).any()
def disk_dilate(mask,r):
    k=int(math.ceil(r/RES));yy,xx=np.ogrid[-k:k+1,-k:k+1];ker=((xx*xx+yy*yy)<=(r/RES)**2).astype(np.float32)
    sh=(mask.shape[0]+2*k,mask.shape[1]+2*k)
    a=np.zeros(sh,np.float32);a[k:k+mask.shape[0],k:k+mask.shape[1]]=mask
    kk=np.zeros(sh,np.float32);kk[:ker.shape[0],:ker.shape[1]]=ker
    c=np.fft.irfft2(np.fft.rfft2(a)*np.fft.rfft2(kk),s=sh)
    return c[2*k:2*k+mask.shape[0],2*k:2*k+mask.shape[1]]>0.5
# ---------------------------------------------------------------- board
B=Board(P);fps=B.fps
t_src=B.t
inside_unused,poly=outline_mask(t_src)
xs=GX0+(np.arange(NX)+0.5)*RES;ys=GY0+(np.arange(NY)+0.5)*RES
XX,YY=np.meshgrid(xs,ys)
inside=np.zeros((NY,NX),bool)
n=len(poly)
for a in range(n):
    x1,y1=poly[a];x2,y2=poly[(a+1)%n]
    cond=((y1>YY)!=(y2>YY))
    with np.errstate(divide='ignore',invalid='ignore'):
        xint=(x2-x1)*(YY-y1)/(y2-y1)+x1
    inside^=cond&(XX<xint)
isP=lambda r:re.match(r'(C|R|TP)\d',r) is not None
BULK={'C2','C3','C6'}
MOV=[r for r in fps if (isP(r) and r not in BULK) or r=='U14' or (os.environ.get('MOVIC') and re.search('QFN-2',fps[r]['lib']))]
FIXED=[r for r in fps if r not in MOV]
chan={'ESC4':(-1,-1),'ESC2':(1,-1),'ESC3':(-1,1),'ESC1':(1,1)}
# ---------------------------------------------------------------- part models
def parse_pads(f):
    out=[]
    for m in re.finditer(r'\n\t\t\(pad "([^"]*)" (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)\s*\(size ([-\d.]+) ([-\d.]+)\)([\s\S]*?)\n\t\t\)',f['b']):
        nm,typ,shp,px,py,pa,w,hh,rest=m.groups()
        px,py,pa,w,hh=float(px),float(py),float(pa or 0),float(w),float(hh)
        net=re.search(r'\(net "([^"]*)"',rest);net=net.group(1) if net else ''
        if f['layer']=='B.Cu': py=-py
        out.append(dict(n=nm,px=px,py=py,a0=pa-f['rot'],w=w,h=hh,net=net,th=typ in('thru_hole','np_thru_hole')))
    return out
for r,f in fps.items(): f['lp']=parse_pads(f)
def geom(ref,x,y,th,side):
    f=fps[ref];r=math.radians(th);out=[]
    for p in f['lp']:
        py=p['py'] if side=='F' else -p['py']
        dx=p['px']*math.cos(r)+py*math.sin(r);dy=-p['px']*math.sin(r)+py*math.cos(r)
        sw=round(p['a0']+th)%180==90
        out.append((x+dx,y+dy,(p['h'] if sw else p['w']),(p['w'] if sw else p['h'])))
    return out
# ---------------------------------------------------------------- static occupancy
ST={'F':np.zeros((NY,NX),bool),'B':np.zeros((NY,NX),bool)}
ST_small={'F':None,'B':None}
out_edge=~inside
edgeband=disk_dilate(out_edge,2.0)|out_edge          # small parts: >=2 mm from the outline
kp=np.zeros((NY,NX),bool)
for p in fps['U3']['pads']:
    if p['n']!='11': mark(kp,p['x'],p['y'],p['w'],p['h'],0.0)
kp=disk_dilate(kp,3.0)                                # small parts: >=3 mm from motor / battery pads
gum=np.zeros((NY,NX),bool)
for hx in(-10,10):
    for hy in(-10,10): gum|=((XX-hx)**2+(YY-hy)**2<=3.4**2)
for sd in 'FB': ST[sd]|=edgeband|kp|gum|disk_dilate(out_edge,0.3)
def fixed_marks():
    for r in FIXED:
        f=fps[r]
        if abs(f['x'])>25:continue
        pads=[(p['x'],p['y'],p['w'],p['h'],p['sides'],p['typ']) for p in f['pads']]
        for x,y,w,h,sides,typ in pads:
            for sd in sides: mark(ST[sd],x,y,w,h,M)
        sm=[q for q in pads if q[5]=='smd']
        big=len(sm)>=5 or r.startswith('Rsense') or '1206' in f['lib']
        if big and r!='U3' and sm:
            x0=min(x-w/2 for x,y,w,h,s_,t_ in sm);x1=max(x+w/2 for x,y,w,h,s_,t_ in sm)
            y0=min(y-h/2 for x,y,w,h,s_,t_ in sm);y1=max(y+h/2 for x,y,w,h,s_,t_ in sm)
            fab='B.Fab' if f['layer']=='B.Cu' else 'F.Fab';rr=math.radians(f['rot'])
            for m in re.finditer(r'\((?:fp_line|fp_rect)\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)[\s\S]*?\(layer "%s"\)'%re.escape(fab),f['b']):
                a=list(map(float,m.groups()))
                for qx,qy in((a[0],a[1]),(a[2],a[3])):
                    ax=f['x']+qx*math.cos(rr)+qy*math.sin(rr);ay=f['y']-qx*math.sin(rr)+qy*math.cos(rr)
                    x0=min(x0,ax);x1=max(x1,ax);y0=min(y0,ay);y1=max(y1,ay)
            if r=='J1': y0=f['y']-0.3
            mark(ST[f['layer'][0]],(x0+x1)/2,(y0+y1)/2,x1-x0,y1-y0,0.15)
fixed_marks()
DY={'F':np.zeros((NY,NX),np.int16),'B':np.zeros((NY,NX),np.int16)}
# ---------------------------------------------------------------- ownership / targets
def find(lib_pat,sheet):
    for r,f in fps.items():
        if re.search(lib_pat,f['lib']) and f['sheet']==sheet:return r
MCU={ch:find('QFN-28','/%s/'%ch) for ch in chan};GD={ch:find('QFN-24','/%s/'%ch) for ch in chan}
GROUP={}

for r in('U15','C4','C51','C76','C81','C93'):GROUP[r]='LDO'
for r in('U13','U14','C47','C86','C74','C75','R120','R121'):GROUP[r]='BUCK'
OWN={'INA':{'U12','Rsense1','Rsense2'},'LDO':{'U15'},'BUCK':{'U13','U14'}}
GLOBAL={'GND','+3V3','+10V','+BATT','/CSA+'}
netpads={}
for r,f in fps.items():
    for p in f['pads']: netpads.setdefault(p['net'],[]).append((r,p))
def owner_set(ref):
    f=fps[ref]
    if f['sheet'] in('/ESC1/','/ESC2/','/ESC3/','/ESC4/'):
        ch=f['sheet'].strip('/');return {MCU[ch],GD[ch]}
    return OWN.get(GROUP.get(ref),set())
def static_targets(ref,pad):
    net=pad['net']
    if net=='GND' or net.startswith('unconnected') or re.match(r'/M\d$',net) or net=='/CURR':return []
    own=owner_set(ref);res=[]
    cand=[(r2,p2) for r2,p2 in netpads.get(net,[]) if r2 not in MOV and not (r2=='U3')]
    ownc=[(r2,p2) for r2,p2 in cand if r2 in own]
    use=ownc if ownc else ([] if (net in GLOBAL or re.search(r'/Motor[ABC]$',net)) else cand)
    return [(p2['x'],p2['y']) for r2,p2 in use]
def weight(ref):
    f=fps[ref];nets=[p['net'] for p in f['pads']]
    if ref=='U14':return 9.0
    if os.environ.get('MOVIC') and re.search('QFN-2',f['lib']):return 12.0
    if any(('U13-CB' in n or 'U13-SW' in n) for n in nets):return 7.0
    if any('U13-FB' in n for n in nets):return 4.0
    if any(('U12-' in n) for n in nets) and ref!='U12':return 4.0
    if ref in('C74','C47','C86'):return 6.0
    if any('-VB' in n for n in nets):return 7.0
    if f['val']=='15R':return 2.5
    if ref.startswith('TP'):return 1.0
    if any(n in('+3V3','+10V','+BATT') for n in nets) and ref.startswith('C'):return 7.0
    if any('vdda' in n for n in nets):return 5.0
    if any('NRST' in n or 'BOOT0' in n for n in nets):return 2.0
    if any('FB' in n for n in nets):return 1.5
    return 1.0
MP={}   # movable models
for r in MOV:
    f=fps[r]
    tg=[static_targets(r,p) for p in f['lp']]
    MP[r]=dict(ref=r,tg=tg,w=weight(r),side0=f['layer'][0],twin=None)
# twin mapping for channel templates (ESC4->ESC1, ESC2->ESC3)
def norm(net,ch):
    n=net.replace('/%s/'%ch,'/')
    m=re.match(r'Net-\((U\d+)-(.+)\)',n)
    if m:n='Net-(%s-%s)'%('MCU' if 'QFN-28' in fps[m.group(1)]['lib'] else 'GD',m.group(2))
    m=re.match(r'Net-\((Q\d+)-G\)',n)
    if m:
        pn={}
        for a,c in re.findall(r'\n\t\t\(pad "([^"]*)" [\s\S]*?\(net "([^"]*)"\)',fps[m.group(1)]['b']):pn.setdefault(a,c)
        hs=pn['3']=='+BATT';mot=pn['1'] if hs else pn['3'];n='Net-(Q:%s%s-G)'%(mot[-1],'H' if hs else 'L')
    if re.match(r'/M\d$',n):n='/MSIG'
    if n.startswith('unconnected'):n='unconnected'
    return n
def sig(r):
    f=fps[r];ch=f['sheet'].strip('/')
    return (f['val'],f['lib'].split(':')[1],tuple(sorted(norm(p['net'],ch) for p in f['pads'] if not p['net'].startswith('unconnected'))))
bych={ch:[r for r in MOV if fps[r]['sheet']=='/%s/'%ch] for ch in chan}
smap={ch:{sig(r):r for r in rs} for ch,rs in bych.items()}
TWIN={'ESC4':'ESC1','ESC2':'ESC3'} if os.environ.get('TWINS') else {}
VARS=[];DERIVED={}
for ch,rs in bych.items():
    if ch in TWIN:
        for r in rs:
            if r.startswith('TP'):continue
            tw=smap[TWIN[ch]][sig(r)];MP[r]['twin']=tw;DERIVED[tw]=r
for r in MOV:
    if r not in DERIVED:VARS.append(r)
for tw in DERIVED:MP[tw]['derived']=True
print('movable',len(MOV),'optimised variables',len(VARS),'(rest are rotated copies)')
# ---------------------------------------------------------------- cost
ICW=float(os.environ.get('ICW','4.0'))
HOME={}
if os.environ.get('MOVIC'):
    for ch,(sx,sy) in chan.items():
        HOME[MCU[ch]]=(sx*float(os.environ.get('MCUX','2.3')),sy*float(os.environ.get('MCUY','14.0')))
        HOME[GD[ch]]=(sx*float(os.environ.get('GDX','2.3')),sy*float(os.environ.get('GDY','9.0')))
POS={}   # ref -> (x,y,th,side) for variables and derived twins
def passive_pad_positions():
    d={}
    for r,(x,y,th,sd) in POS.items():
        for k,(px,py,w,h) in enumerate(geom(r,x,y,th,sd)):d.setdefault(fps[r]['lp'][k]['net'],[]).append((r,px,py))
    return d
def cost(r,x,y,th,side,pp=None):
    m=MP[r];c=0.0
    if r in HOME:c+=ICW*math.hypot(x-HOME[r][0],y-HOME[r][1])
    gs=geom(r,x,y,th,side)
    for k,(px,py,w,h) in enumerate(gs):
        tg=m['tg'][k]
        if tg:
            dd=min(math.hypot(px-tx,py-ty) for tx,ty in tg)
            c+=m['w']*dd+OUTL*m['w']*max(0.0,dd-2.5)**2
        elif pp is not None:
            net=fps[r]['lp'][k]['net']
            if net not in GLOBAL and not net.startswith('unconnected') and net!='GND':
                oth=[(qx,qy) for (q,qx,qy) in pp.get(net,[]) if q!=r and q!=m['twin'] and q not in DERIVED]
                if oth:c+=0.6*min(math.hypot(px-qx,py-qy) for qx,qy in oth)
    if fps[r]['layer'][0]=='B' or True:
        if side!='B':c+=(2.0 if r.startswith('C') else 5.0)   # IC side is the bottom: other-side parts pay a penalty
    return c
def twin_pose(x,y,th,side):return (-x,-y,(th+180)%360,side)
def valid(r,x,y,th,side,twin_ok=True):
    st=ST[side];dy=DY[side]
    gs=geom(r,x,y,th,side)
    for (px,py,w,h) in gs:
        if hit(st,dy,px,py,w,h,M):return False
    tw=MP[r]['twin']
    if tw:
        tx,ty,tth,ts=twin_pose(x,y,th,side)
        gt=geom(tw,tx,ty,tth,ts)
        for (px,py,w,h) in gt:
            if hit(ST[ts],DY[ts],px,py,w,h,M):return False
        # parts of the pair must not overlap each other (near the board centre)
        for (a,b,w1,h1) in gs:
            for (c,d,w2,h2) in gt:
                if side==ts and abs(a-c)<(w1+w2)/2+2*M and abs(b-d)<(h1+h2)/2+2*M:return False
    return True
def apply(r,x,y,th,side,d):
    for (px,py,w,h) in geom(r,x,y,th,side):addc(DY[side],px,py,w,h,M,d)
    tw=MP[r]['twin']
    if tw:
        tx,ty,tth,ts=twin_pose(x,y,th,side)
        for (px,py,w,h) in geom(tw,tx,ty,tth,ts):addc(DY[ts],px,py,w,h,M,d)
def put(r,x,y,th,side):
    POS[r]=(x,y,th,side);apply(r,x,y,th,side,1)
    tw=MP[r]['twin']
    if tw:POS[tw]=twin_pose(x,y,th,side)
def lift(r):
    x,y,th,side=POS.pop(r);apply(r,x,y,th,side,-1)
    tw=MP[r]['twin']
    if tw:POS.pop(tw,None)
    return (x,y,th,side)
def sides_for(r):
    if os.environ.get('ONLYB'):
        w=MP[r]['w']
        f_ok=bool(os.environ.get('NONCRIT_F')) and w<=2.0 and r not in GROUP and not r.startswith('U')
        if not f_ok:return ('B',)
    return ('B','F')
def candidates(r,cur=None,wide=False):
    m=MP[r];pts=[]
    tgs=[t for tg in m['tg'] for t in tg]
    seen=set()
    base=[HOME[r]] if r in HOME else (tgs if tgs else [(0.0,0.0)])
    for (tx,ty) in base[:4]:
        for rad in ((0.0,0.3,0.5,0.8,1.2,1.7,2.4,3.2) if not wide else (0.0,1.0,2.0,3.0,4.5,6.0,8.0,10.0,12.0)):
            for k in range(0,360,30 if rad>0 else 360):
                x=tx+rad*math.cos(math.radians(k));y=ty+rad*math.sin(math.radians(k))
                key=(round(x/0.05),round(y/0.05))
                if key in seen:continue
                seen.add(key);pts.append((round(x*20)/20,round(y*20)/20))
    if cur:
        x0,y0=cur[0],cur[1]
        for dx in(-0.6,-0.3,-0.15,0,0.15,0.3,0.6):
            for dy in(-0.6,-0.3,-0.15,0,0.15,0.3,0.6):
                pts.append((round((x0+dx)*20)/20,round((y0+dy)*20)/20))
    return pts
def best_pose(r,cur=None,wide=False):
    best=None
    pp=passive_pad_positions()
    for side in sides_for(r):
        for (x,y) in candidates(r,cur,wide):
            for th in (0,90,180,270):
                if not valid(r,x,y,th,side):continue
                c=cost(r,x,y,th,side,pp)
                if best is None or c<best[0]:best=(c,x,y,th,side)
    return best
def scan_pose(r):
    best=None;pp=passive_pad_positions()
    for side in sides_for(r):
        for xi in range(-170,171,2):
            for yi in range(-200,231,2):
                x=xi*0.1;y=yi*0.1
                for th in (0,90,180,270):
                    if not valid(r,x,y,th,side):continue
                    c=cost(r,x,y,th,side,pp)
                    if best is None or c<best[0]:best=(c,x,y,th,side)
    return best
# ---------------------------------------------------------------- greedy insertion (priority order), then local search
def prio(r):
    w=MP[r]['w']
    return (-w,int(re.sub(r'\D','',r)))
order=sorted(VARS,key=prio)
fail=[]
for r in order:
    b=best_pose(r)
    if b is None: b=best_pose(r,None,True)
    if b is None: b=scan_pose(r)
    if b is None and MP[r]['twin']:
        tw=MP[r]['twin'];MP[r]['twin']=None;MP[tw].pop('derived',None);DERIVED.pop(tw,None);VARS.append(tw);order.append(tw)
        print('untwinned',r,tw)
        b=best_pose(r)
        if b is None: b=best_pose(r,None,True)
        if b is None: b=scan_pose(r)
    if b is None:
        fail.append(r);continue
    put(r,b[1],b[2],b[3],b[4])
    if os.environ.get('DBGIC') and r.startswith('U'):print('placed',r,b[1:])
print('greedy placed',len(POS),'fail',fail)
def total():
    pp=passive_pad_positions();return sum(cost(r,*POS[r],pp) for r in VARS if r in POS)
print('cost after greedy %.1f'%total())
def sample_pose(r,cur,T):
    """random candidate pose near targets/current; returns best valid of a random subset"""
    pts=candidates(r,cur);random.shuffle(pts);pts=pts[:260]
    pp=passive_pad_positions();best=None
    for side in sides_for(r):
        for (x,y) in pts:
            th=random.choice((0,90,180,270))
            if not valid(r,x,y,th,side):continue
            c=cost(r,x,y,th,side,pp)
            if best is None or c<best[0]:best=(c,x,y,th,side)
    return best
for ps in range(PASSES):
    T=max(0.02,1.2*(1-ps/max(1,PASSES-3)))
    imp=0;random.shuffle(order)
    for r in order:
        if r not in POS:
            b=best_pose(r) or best_pose(r,None,True) or scan_pose(r)
            if b:put(r,b[1],b[2],b[3],b[4]);imp+=1
            continue
        cur=lift(r);pp=passive_pad_positions();c0=cost(r,*cur,pp)
        b=best_pose(r,cur)
        if b and b[0]<c0-1e-6:
            put(r,b[1],b[2],b[3],b[4]);imp+=1
        elif T>0.05:
            b2=sample_pose(r,cur,T)
            if b2 and (b2[0]-c0)<random.expovariate(1.0/T) and (abs(b2[1]-cur[0])+abs(b2[2]-cur[1])>0.01):
                put(r,b2[1],b2[2],b2[3],b2[4]);imp+=1
            else:put(r,*cur)
        else:
            put(r,*cur)
    print('pass',ps,'T=%.2f'%T,'moves',imp,'cost %.1f'%total())
# ---------------------------------------------------------------- write back
def flipblk(b,to):
    m0=re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)',b);head=b[:m0.end()];rest=b[m0.end():]
    a,c=('F','B') if to=='B' else ('B','F')
    for k in('Cu','Mask','Paste','SilkS','Fab','CrtYd','Adhes'):
        head=head.replace('"%s.%s"'%(a,k),'"%s.%s"'%(c,k));rest=rest.replace('"%s.%s"'%(a,k),'"%s.%s"'%(c,k))
    rest=re.sub(r'\((at|start|end|mid|center|xy) ([-\d.]+) ([-\d.]+)((?: [-\d.]+)?)\)',lambda m:'(%s %s %s%s)'%(m.group(1),m.group(2),('%g'%(-float(m.group(3)))),m.group(4)),rest)
    return head+rest
fpat=re.compile(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)')
def retarget(b,x,y,th):
    m0=fpat.search(b);old=float(m0.group(3) or 0)
    head=b[:m0.start()]+'\n\t\t(at %.3f %.3f %g)'%(x,y,th);rest=b[m0.end():]
    def sh(m):
        a=float(m.group(3) or 0);n=((a-old+th+180)%360)-180
        if n==-180:n=180
        return '(at %s %s %g)'%(m.group(1),m.group(2),n)
    return head+re.sub(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)',sh,rest)
t=B.t;edits=[]
for r,(x,y,th,side) in POS.items():
    f=fps[r];b=retarget(f['b'],0,0,0)
    if f['layer'][0]!=side:b=flipblk(b,side)
    edits.append((f['s'],f['e'],retarget(b,x+CX,y+CY,th)))
for s,e,nb in sorted(edits,reverse=True):t=t[:s]+nb+t[e:]
open(OUT,'w',encoding='utf8').write(t)
json.dump({r:list(v) for r,v in POS.items()},open(os.environ['TEMP']+'/opt_pos.json','w'))
print('wrote',OUT,'parts',len(POS),'unplaced',[r for r in MOV if r not in POS])
