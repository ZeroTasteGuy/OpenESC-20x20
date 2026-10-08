import sys,os
sys.path.insert(0,os.environ['TEMP'])
from engine import *
def build_occ(B,margin=0.085,skip=()):
    inside,pts=outline_mask(B.t)
    occ={k:dilate(~inside,0.3)|~inside for k in 'FB'}
    xs=np.arange(X0,X1,RES)+RES/2;ys=np.arange(Y0,Y1,RES)+RES/2
    XX,YY=np.meshgrid(xs,ys)
    for hx in(-10,10):
        for hy in(-10,10):
            c=(XX-hx)**2+(YY-hy)**2<=3.4**2
            for k in 'FB':occ[k]|=c
    for f in B.fps.values():
        if f['x']>25 or f['ref'] in skip:continue
        for p in f['pads']:
            for sd in p['sides']: rect_mark(occ[sd],p['x'],p['y'],p['w'],p['h'],margin)
    return occ,inside
def svg_free(occ,side,out,sc=14):
    g=~occ[side]
    x0,y0,x1,y1=-19,-21,19,24
    i0,j0=gi(x0,y0);i1,j1=gi(x1,y1)
    rects=[]
    for j in range(j0,j1):
        row=g[j,i0:i1];i=0
        while i<len(row):
            if row[i]:
                k=i
                while k<len(row) and row[k]:k+=1
                rects.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>'%(i*RES*sc,(j-j0)*RES*sc,(k-i)*RES*sc,RES*sc))
                i=k
            else:i+=1
    W=int((x1-x0)*sc);H=int((y1-y0)*sc)
    grid=''.join('<line x1="%d" y1="0" x2="%d" y2="%d" stroke="#555" stroke-width=".5"/>'%(i*5*sc,i*5*sc,H) for i in range(0,8))+''.join('<line x1="0" y1="%d" x2="%d" y2="%d" stroke="#555" stroke-width=".5"/>'%(i*5*sc,W,i*5*sc) for i in range(0,10))
    open(out,'w').write('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d"><rect width="100%%" height="100%%" fill="#222"/><g fill="#3c3">%s</g>%s<text x="6" y="14" fill="#fff" font-size="12">%s free (x -19..19, y -21..24; grid 5mm)</text></svg>'%(W,H,''.join(rects),grid,side))
if __name__=='__main__':
    B=Board('4in1.kicad_pcb');occ,_=build_occ(B)
    svg_free(occ,'B','../free_bot.svg');svg_free(occ,'F','../free_top.svg')
