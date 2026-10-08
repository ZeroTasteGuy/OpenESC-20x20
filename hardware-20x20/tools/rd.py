import sys,os,time,collections;sys.path.insert(0,os.environ['TEMP'])
from rsolve import *
path=sys.argv[1];esc=sys.argv[2];t0=time.time()
B=Board(path);t=B.t;f=B.fps
bp=[(r,p) for r,fp in f.items() for p in fp['pads'] if r=='U3' and p['net']=='+BATT' and p['w']*p['h']>12]
gp=[(r,p) for r,fp in f.items() for p in fp['pads'] if p['net']=='GND' and p['w']*p['h']>12 and r=='U3']
print('battery pads',[(r,p['n'],round(p['x'],1),round(p['y'],1)) for r,p in bp],'gnd big',[(r,p['n']) for r,p in gp][:6])
bat_ref=set(r for r,p in bp);gnd_ref=set(r for r,p in gp)
NB=Net(B,t,'+BATT');NG=Net(B,t,'GND');print('nets built %.0fs'%(time.time()-t0))
bm=padmask(B,pred=lambda r,p:r in bat_ref and p['net']=='+BATT' and p['w']*p['h']>12)
gm=padmask(B,pred=lambda r,p:r in gnd_ref and p['net']=='GND' and p['w']*p['h']>12)
# phases
q={}
for r in f:
    if not r.startswith('Q'):continue
    pn={}
    for p in f[r]['pads']:pn.setdefault(p['n'],p['net'])
    if pn.get('3')=='+BATT' and pn['1'].startswith('/'+esc+'/'):q.setdefault(pn['1'],{})['hs']=r
    elif pn.get('1')=='GND' and pn['3'].startswith('/'+esc+'/'):q.setdefault(pn['3'],{})['ls']=r
res={}
for mot in sorted(q):
    hs=q[mot]['hs'];ls=q[mot]['ls']
    NM=Net(B,t,mot)
    mp=padmask(B,pred=lambda r,p:r=='U3' and p['net']==mot)
    hs_src=padmask(B,pred=lambda r,p:r==hs and p['net']==mot)
    hs_tab=padmask(B,pred=lambda r,p:r==hs and p['net']=='+BATT' and p['w']>2 and p['h']>2)
    ls_drn=padmask(B,pred=lambda r,p:r==ls and p['net']==mot)
    ls_src=padmask(B,pred=lambda r,p:r==ls and p['net']=='GND' and p['n']=='1')
    out={}
    out['batt->HS tab']=solve(NB,bm,hs_tab)[0]
    out['HS src->motor pad']=solve(NM,hs_src,mp)[0]
    out['motor pad->LS drain']=solve(NM,ls_drn,mp)[0]
    out['LS src->batt-']=solve(NG,ls_src,gm)[0]
    res[mot]=out;print(mot,hs,ls,{k:(None if v is None else round(v,3)) for k,v in out.items()},'%.0fs'%(time.time()-t0),flush=True)
print('--- mOhm per phase half-path; loop = batt->HS(a)+HS->pad(a)+pad(b)->LS(b)+LS->batt-(b)')
ph=sorted(res)
for a in ph:
    for b in ph:
        if a==b:continue
        R=res[a]['batt->HS tab']+res[a]['HS src->motor pad']+res[b]['motor pad->LS drain']+res[b]['LS src->batt-']
        print(a[-1],'->',b[-1],'loop copper R %.3f mOhm'%R,' P@40A %.2f W  P@60A %.2f W'%(1600*R*1e-3,3600*R*1e-3))
