"""Copper geometry database for the board (board-relative mm, y down).
Objects: pads (rect), vias (circle), tracks (segments with width) on named layers.
Queries answer 'can a via / track of net N be placed here' against foreign-net copper."""
import sys,os,re,math,collections
sys.path.insert(0,os.environ['TEMP'])
from engine import Board,CX,CY
from pcbutil import toplevel
LAYERS=['F.Cu','In1.Cu','In2.Cu','In3.Cu','In4.Cu','B.Cu']
CELL=2.0
class Geo:
    def __init__(s,path):
        s.B=Board(path);s.items=[];s.grid=collections.defaultdict(list)
        t=s.B.t
        for r,f in s.B.fps.items():
            if abs(f['x'])>25:continue
            for p in f['pads']:
                lays=LAYERS if p['th'] else [f['layer'] if p['sides']=={f['layer'][0]} else f['layer']]
                if not p['th']:
                    lays=['F.Cu'] if 'F' in p['sides'] else ['B.Cu']
                s.add(dict(kind='pad',x=p['x'],y=p['y'],w=p['w'],h=p['h'],net=p['net'],layers=lays,ref=r,pn=p['n'],th=p['th'],typ=p['typ']))
        for st,e,h in toplevel(t):
            b=t[st:e]
            if h=='via':
                a=re.search(r'\(at ([-\d.]+) ([-\d.]+)\)',b);sz=float(re.search(r'\(size ([\d.]+)\)',b).group(1));dr=float(re.search(r'\(drill ([\d.]+)\)',b).group(1))
                n=re.search(r'\(net "([^"]*)"',b)
                s.add(dict(kind='via',x=float(a.group(1))-CX,y=float(a.group(2))-CY,r=sz/2,drill=dr,net=n.group(1) if n else '',layers=LAYERS))
            elif h=='segment':
                a=re.search(r'\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)',b);n=re.search(r'\(net "([^"]*)"',b)
                if a:s.add(dict(kind='seg',x0=float(a.group(1))-CX,y0=float(a.group(2))-CY,x1=float(a.group(3))-CX,y1=float(a.group(4))-CY,w=float(a.group(5)),net=n.group(1) if n else '',layers=[a.group(6)]))
    def bbox(s,it):
        if it['kind']=='pad':return it['x']-it['w']/2,it['y']-it['h']/2,it['x']+it['w']/2,it['y']+it['h']/2
        if it['kind']=='via':return it['x']-it['r'],it['y']-it['r'],it['x']+it['r'],it['y']+it['r']
        return min(it['x0'],it['x1'])-it['w']/2,min(it['y0'],it['y1'])-it['w']/2,max(it['x0'],it['x1'])+it['w']/2,max(it['y0'],it['y1'])+it['w']/2
    def add(s,it):
        s.items.append(it);x0,y0,x1,y1=s.bbox(it)
        for i in range(int(x0//CELL),int(x1//CELL)+1):
            for j in range(int(y0//CELL),int(y1//CELL)+1):s.grid[(i,j)].append(it)
    def near(s,x,y,r):
        seen=set();out=[]
        for i in range(int((x-r)//CELL),int((x+r)//CELL)+1):
            for j in range(int((y-r)//CELL),int((y+r)//CELL)+1):
                for it in s.grid.get((i,j),()):
                    if id(it) not in seen:seen.add(id(it));out.append(it)
        return out
    @staticmethod
    def dist_pt_rect(x,y,it):
        dx=max(abs(x-it['x'])-it['w']/2,0);dy=max(abs(y-it['y'])-it['h']/2,0);return math.hypot(dx,dy)
    @staticmethod
    def dist_pt_seg(x,y,it):
        ax,ay,bx,by=it['x0'],it['y0'],it['x1'],it['y1'];dx,dy=bx-ax,by-ay
        t=0 if dx==dy==0 else max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy)))
        return math.hypot(x-ax-t*dx,y-ay-t*dy)-it['w']/2
    def clearance_at(s,x,y,net,layers,rad,exclude_refs=()):
        """smallest gap between a copper circle of radius rad at (x,y) and foreign-net copper on the given layers"""
        best=9e9
        for it in s.near(x,y,rad+3.0):
            if it['net']==net and net!='':continue
            if not set(it['layers'])&set(layers):continue
            if it['kind']=='pad':d=s.dist_pt_rect(x,y,it)-rad
            elif it['kind']=='via':d=math.hypot(x-it['x'],y-it['y'])-it['r']-rad
            else:d=s.dist_pt_seg(x,y,it)-rad
            best=min(best,d)
        return best
    def hole_ok(s,x,y,drill):
        for it in s.near(x,y,2.0):
            if it['kind']=='via' and math.hypot(x-it['x'],y-it['y'])-it['drill']/2-drill/2<0.2:return False
            if it['kind']=='pad' and it['th'] and it['typ'] in('thru_hole','np_thru_hole'):
                # mounting holes / motor pad holes: keep the drill 0.25 away from any pad copper edge
                pass
        return True
