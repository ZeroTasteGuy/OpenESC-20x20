"""Place MCU / gate-driver ICs of each ESC.  usage: ic_place.py in.kicad_pcb out.kicad_pcb"""
import os,sys,re,math,runpy,itertools
sys.path.insert(0,os.environ['TEMP'])
SRC,DST=sys.argv[1:3]
from engine import Board,CX,CY
# 1) probe board with ICs moved far away so they do not block the masks
B0=Board(SRC);t=B0.t
ICS=[r for r,f in B0.fps.items() if re.search('QFN-2',f['lib'])]
BULK=[r for r,f in B0.fps.items() if '1206' in f['lib']]
GLOB=['U13','U15']
fpat=re.compile(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)')
def moved(t,B,ref,x,y,th=None):
    f=B.fps[ref];m=fpat.search(f['b'])
    old=float(m.group(3) or 0);th=old if th is None else th
    def sh(mm):
        a=float(mm.group(3) or 0);n=((a-old+th+180)%360)-180
        if n==-180:n=180
        return '(at %s %s %g)'%(mm.group(1),mm.group(2),n)
    nb=f['b'][:m.start()]+'\n\t\t(at %.3f %.3f %g)'%(x,y,th)+re.sub(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)',sh,f['b'][m.end():])
    return nb
edits=[]
for r in ICS+BULK+GLOB:
    f=B0.fps[r];edits.append((f['s'],f['e'],moved(t,B0,r,CX+60,CY)))
tp=t
for s,e,nb in sorted(edits,reverse=True):tp=tp[:s]+nb+tp[e:]
open('icprobe.kicad_pcb','w',encoding='utf8').write(tp)
os.environ.update(dict(ONLYB='1',PASSES='0'));os.environ.pop('MOVIC',None);os.environ.pop('TWINS',None)
sys.argv=['x','icprobe.kicad_pcb','icprobe_out.kicad_pcb']
g=runpy.run_path(os.environ['TEMP']+'/opt_layout2.py')
DY=g['DY'];DY['B'][:]=0;DY['F'][:]=0
g['POS'].clear()
fps=g['fps'];MP=g['MP'];valid=g['valid'];geom=g['geom'];put=g['put']
for r in ICS+GLOB:
    MP[r]=dict(ref=r,tg=[],w=1.0,side0='B',twin=None)
chan=g['chan'];MCU=g['MCU'];GD=g['GD']
# gate targets of a gate driver: GHx / GLx -> resistor -> FET gate pad
netpads=g['netpads']
def fet_gate_target(net):
    for r2,p2 in netpads.get(net,[]):
        if r2.startswith('R'):
            for p3 in fps[r2]['pads']:
                if p3['net']!=net and p3['net'].startswith('Net-(Q'):
                    for r4,p4 in netpads[p3['net']]:
                        if r4.startswith('Q') and p4['n']=='2':return (p4['x'],p4['y'])
    return None
def pads_at(ref,x,y,th):
    gs=geom(ref,x,y,th,'B');out={}
    for k,(px,py,w,h) in enumerate(gs):
        out.setdefault(fps[ref]['lp'][k]['net'],[]).append((px,py))
    return out
def d(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
res={}
ORDER=['ESC1','ESC2','ESC3','ESC4']
HOMEGD=(4.0,9.4);HOMEMCU=(2.2,4.8)
gt={}
for ch in ORDER:
    gt[ch]={n:fet_gate_target(n) for n in {p['net'] for p in fps[GD[ch]]['pads']} if re.search(r'/G[HL][ABC]$',n)}
for ch in ORDER:
    sx,sy=chan[ch]
    # driver first
    best=None
    hx,hy=sx*HOMEGD[0],sy*HOMEGD[1]
    for dx in [i*0.25 for i in range(-3,4)]:
        for dy in [i*0.25 for i in range(-3,4)]:
            x,y=hx+dx,hy+dy
            if sx*x<2.0 or sy*y<8.0:continue
            for th in (0,90,180,270):
                if not valid(GD[ch],x,y,th,'B'):continue
                pp=pads_at(GD[ch],x,y,th)
                c=sum(d(pp[n][0],tg) for n,tg in gt[ch].items() if tg and n in pp)+0.8*d((x,y),(hx,hy))
                if best is None or c<best[0]:best=(c,x,y,th)
    if best is None:print('no spot for',GD[ch]);continue
    put(GD[ch],best[1],best[2],best[3],'B');res[GD[ch]]=best[1:]
    gp=pads_at(GD[ch],*best[1:],)if False else pads_at(GD[ch],best[1],best[2],best[3])
    # MCU: close to driver for the six control nets
    best2=None
    shared=[n for n in gp if re.search(r'/[ABC][HL]$',n)]
    hx,hy=sx*HOMEMCU[0],sy*HOMEMCU[1]
    for dx in [i*0.25 for i in range(-3,4)]:
        for dy in [i*0.25 for i in range(-3,4)]:
            x,y=hx+dx,hy+dy
            if sx*x<1.3 or sy*y<3.0:continue
            for th in (0,90,180,270):
                if not valid(MCU[ch],x,y,th,'B'):continue
                pp=pads_at(MCU[ch],x,y,th)
                c=sum(d(pp[n][0],gp[n][0]) for n in shared if n in pp)+0.5*d((x,y),(hx,hy))
                if best2 is None or c<best2[0]:best2=(c,x,y,th)
    if best2 is None:
        print('no spot for',MCU[ch])
        for (x,y) in ((sx*1.5,sy*4.8),(sx*1.8,sy*4.8)):
            for (px,py,w,h) in geom(MCU[ch],x,y,0,'B')[:40:6]:
                j0,j1,i0,i1=g['rect_idx'](px,py,w,h,g['M'])
                print('  at',(x,y),'pad',round(px,1),round(py,1),'edgeband',g['edgeband'][j0:j1+1,i0:i1+1].any(),'kp',g['kp'][j0:j1+1,i0:i1+1].any(),'gum',g['gum'][j0:j1+1,i0:i1+1].any(),'ST',g['ST']['B'][j0:j1+1,i0:i1+1].any(),'DY',(DY['B'][j0:j1+1,i0:i1+1]>0).any())
        continue
    put(MCU[ch],best2[1],best2[2],best2[3],'B');res[MCU[ch]]=best2[1:]
    print(ch,'GD',[round(v,2) for v in best[1:]],'MCU',[round(v,2) for v in best2[1:]],'ctrl cost %.1f'%best2[0])
for ref,home in (('U13',(-1.2,14.0)),('U15',(1.2,12.0))):
    best=None
    for dx in [i*0.25 for i in range(-8,9)]:
        for dy in [i*0.25 for i in range(-16,17)]:
            x,y=home[0]+dx,home[1]+dy
            if abs(x)>2.0:continue
            for th in (0,90,180,270):
                if not valid(ref,x,y,th,'B'):continue
                c=math.hypot(dx,dy)
                if best is None or c<best[0]:best=(c,x,y,th)
    if best:
        put(ref,best[1],best[2],best[3],'B');res[ref]=best[1:];print(ref,[round(v,2) for v in best[1:]])
    else:print('no spot for',ref)

# enforce exact 180-degree twins: ESC1->ESC4, ESC2->ESC3
for a,b in (('ESC1','ESC4'),('ESC2','ESC3')):
    for kind in (GD,MCU):
        if kind[a] in res:
            x,y,th=res[kind[a]];res[kind[b]]=(-x,-y,(th+180)%360)
# 2) write chosen poses into the real board
B1=Board(SRC);t=B1.t;edits=[]
for r,(x,y,th) in res.items():
    f=B1.fps[r];edits.append((f['s'],f['e'],moved(t,B1,r,x+CX,y+CY,th)))
for s,e,nb in sorted(edits,reverse=True):t=t[:s]+nb+t[e:]
open(DST,'w',encoding='utf8').write(t)
print('wrote',DST,len(res))
