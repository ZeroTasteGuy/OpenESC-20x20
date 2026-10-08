import re,sys,os,math
sys.path.insert(0,os.environ['TEMP'])
from engine import Board,CX,CY
p=sys.argv[1]
ROWY=float(os.environ.get('ROWY','3.5'))
t=open(p,encoding='utf8').read()
# ---- hole rings -> plain unplated holes
def ring(m):
    return '(pad "11" np_thru_hole circle\n\t\t\t(at %s %s %s)\n\t\t\t(size 4 4)\n\t\t\t(drill 4)\n\t\t\t(layers "*.Cu" "*.Mask")\n\t\t\t(uuid "%s")\n\t\t)'%(m.group(1),m.group(2),m.group(3),m.group(4))
t,n=re.subn(r'\(pad "11" thru_hole circle\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)[\s\S]*?\(uuid "([^"]+)"\)\s*\)',ring,t)
print('hole rings removed',n)
NL='\n\t(footprint'
i=t.index('(property "Reference" "U3"');j=t.rfind(NL,0,i);k=t.index(NL,i)
blk=t[j:k].replace('(size 2.5 3.1)','(size 2.5 2.6)');t=t[:j]+blk+t[k:]
fpat=re.compile(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)')
def retarget(b,x,y,th):
    m0=fpat.search(b);old=float(m0.group(3) or 0)
    head=b[:m0.start()]+'\n\t\t(at %.3f %.3f %g)'%(x,y,th);rest=b[m0.end():]
    def sh(m):
        a=float(m.group(3) or 0);n=((a-old+th+180)%360)-180
        if n==-180:n=180
        return '(at %s %s %g)'%(m.group(1),m.group(2),n)
    return head+re.sub(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)',sh,rest)
def flipb(b):
    m0=fpat.search(b);head=b[:m0.end()];rest=b[m0.end():]
    for kk in('Cu','Mask','Paste','SilkS','Fab','CrtYd','Adhes'):
        head=head.replace('"F.%s"'%kk,'"B.%s"'%kk);rest=rest.replace('"F.%s"'%kk,'"B.%s"'%kk)
    rest=re.sub(r'\((at|start|end|mid|center|xy) ([-\d.]+) ([-\d.]+)((?: [-\d.]+)?)\)',lambda m:'(%s %s %s%s)'%(m.group(1),m.group(2),('%g'%(-float(m.group(3)))),m.group(4)),rest)
    return head+rest
S={}
def pair(hs,ls,x,y,th):S[hs]=(x,y,th);S[ls]=(x,y,th)
TH=eval(os.environ.get('TH','{"B":(0,180),"C":(0,180)}'))
for (hs,ls,sx,sy,ph) in [('Q6','Q11',1,1,'B'),('Q8','Q12',1,-1,'B'),('Q9','Q14',-1,1,'B'),('Q10','Q15',-1,-1,'B'),
                         ('Q16','Q21',1,1,'C'),('Q17','Q22',1,-1,'C'),('Q18','Q23',-1,1,'C'),('Q20','Q24',-1,-1,'C')]:
    x=float(os.environ.get('XB','14.4')) if ph=='B' else float(os.environ.get('XC','8.6'))
    th=TH[ph][0 if sy>0 else 1]
    pair(hs,ls,sx*x,sy*ROWY,th)
open(p,'w',encoding='utf8').write(t)
B=Board(p);edits=[]
LSB=('Q11','Q12','Q14','Q15','Q21','Q22','Q23','Q24')
for ref,(x,y,th) in S.items():
    f=B.fps[ref];b=retarget(f['b'],0,0,0)
    if ref in LSB and f['layer']!='B.Cu':b=flipb(b)
    edits.append((f['s'],f['e'],retarget(b,x+CX,y+CY,th)))
t=open(p,encoding='utf8').read()
for s,e,nb in sorted(edits,reverse=True):t=t[:s]+nb+t[e:]
open(p,'w',encoding='utf8').write(t)
B=Board(p)
for ref in sorted(S,key=lambda r:int(r[1:])):
    f=B.fps[ref];src=[q for q in f['pads'] if q['n']=='1']
    print(ref,f['layer'],'pos %.2f %.2f'%(f['x'],f['y']),'pins dy %.2f'%(sum(q['y'] for q in src)/len(src)-f['y']))
