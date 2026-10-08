import re,sys,uuid,os
p=sys.argv[1];t=open(p,encoding='utf8').read()
MAP=eval(os.environ.get('MAP','{11.0:15.55,7.05:11.95,3.05:8.35}'))
CY=47.35
# --- pads of U3 (12..23)
def fix(m):
    n=m.group(1)
    if not 12<=int(n)<=23:return m.group(0)
    x=m.group(2);y=float(m.group(3));rel=y-0.15+0.0
    mag=min(MAP,key=lambda k:abs(k-abs(rel)))
    new=(1 if rel>0 else -1)*MAP[mag]+0.15
    return m.group(0).replace('(at %s %s)'%(x,m.group(3)),'(at %s %.4f)'%(x,new))
t2=re.sub(r'\(pad "(\d+)" thru_hole roundrect\s*\(at ([-\d.]+) ([-\d.]+)\)',fix,t)
print('pads changed',sum(1 for a,b in zip(re.findall(r'\(pad "(1[2-9]|2[0-3])" thru_hole roundrect\s*\(at [-\d.]+ ([-\d.]+)\)',t),re.findall(r'\(pad "(1[2-9]|2[0-3])" thru_hole roundrect\s*\(at [-\d.]+ ([-\d.]+)\)',t2)) if a!=b))
t=t2
# --- outline: drop side edge items and slot, rebuild straight edges with new castellation arcs
items=list(re.finditer(r'\n\t\((gr_line|gr_arc)\s*\(start ([-\d.]+) ([-\d.]+)\)\s*(?:\(mid ([-\d.]+) ([-\d.]+)\)\s*)?\(end ([-\d.]+) ([-\d.]+)\)[^\n]*?\(layer "Edge.Cuts"\)[^\n]*\)',t))
print('edge items',len(items))
kill=[]
for m in items:
    k,sx,sy,mx,my,ex,ey=m.groups();sx,sy,ex,ey=map(float,(sx,sy,ex,ey))
    for X in (58.1,93.1):
        if abs(sx-X)<1e-3 and abs(ex-X)<1e-3 and 30.75<=min(sy,ey) and max(sy,ey)<=63.85+1e-3:kill.append(m)
    # slot pieces
    if k=='gr_line' and sy in(46.9,48.1) and ey==sy and (abs(sx-58.1)<1e-3 or abs(ex-58.1)<1e-3 or abs(sx-93.1)<1e-3 or abs(ex-93.1)<1e-3):kill.append(m)
    if k=='gr_arc' and mx and abs(float(mx)-90.1)<1e-3 or (k=='gr_arc' and mx and abs(float(mx)-61.1)<1e-3):kill.append(m)
kill=list({m.start():m for m in kill}.values());print('removing',len(kill))
new=''
ys=[CY+s*v for v in MAP.values() for s in (-1,1)];ys.sort()
for X,inw in ((58.1,0.9),(93.1,-0.9)):
    prev=30.75
    for y in ys:
        if y-0.9-prev>0.01: new+='\n\t(gr_line (start %.4f %.4f) (end %.4f %.4f) (stroke (width 0.05) (type default)) (layer "Edge.Cuts") (uuid "%s"))'%(X,prev,X,y-0.9,uuid.uuid4())
        new+='\n\t(gr_arc (start %.4f %.4f) (mid %.4f %.4f) (end %.4f %.4f) (stroke (width 0.05) (type default)) (layer "Edge.Cuts") (uuid "%s"))'%(X,y-0.9,X+inw,y,X,y+0.9,uuid.uuid4())
        prev=y+0.9
    if 63.85-prev>0.01: new+='\n\t(gr_line (start %.4f %.4f) (end %.4f %.4f) (stroke (width 0.05) (type default)) (layer "Edge.Cuts") (uuid "%s"))'%(X,prev,X,63.85,uuid.uuid4())
for m in sorted(kill,key=lambda m:-m.start()):t=t[:m.start()]+t[m.end():]
i=t.rindex('\n)');t=t[:i]+new+t[i:]
open(p,'w',encoding='utf8').write(t)
