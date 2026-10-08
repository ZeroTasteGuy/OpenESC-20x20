import sys,os;sys.path.insert(0,os.environ['TEMP'])
from rsolve import *
path,mot,hs,kind=sys.argv[1:5];I=40.0
B=Board(path);t=B.t
N=Net(B,t,mot)
mp=padmask(B,pred=lambda r,p:r=='U3' and p['net']==mot)
if kind=='hs':s=padmask(B,pred=lambda r,p:r==hs and p['net']==mot)
R,fld=solve(N,s,mp,want_field=True)
V,xh,gx,gy,gl=fld
ks=peakK(V,gx,gy,gl,I,R);Itot=1000.0/R
print(mot,kind,'R %.3f mOhm'%R)
for l in range(6):
    k=ks[l]*1000/RES*(I/Itot)   # A/mm
    nz=k[k>0]
    if len(nz)==0:continue
    print(LAY[l],'max %.1f A/mm  p99.9 %.1f  p99 %.1f  (at %dA)'%(k.max(),np.percentile(nz,99.9),np.percentile(nz,99),I))
    j,i=np.unravel_index(k.argmax(),k.shape);print('   max at board xy (%.1f,%.1f)'%(GX0+(i+.5)*RES,GY0+(j+.5)*RES))
