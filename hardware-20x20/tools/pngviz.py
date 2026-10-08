import sys,os,re,math,zlib,struct,colorsys,hashlib
sys.path.insert(0,os.environ['TEMP'])
import numpy as np
from engine import Board,CX,CY
from pcbutil import toplevel
def hexrgb(h):return tuple(int(h[i:i+2],16) for i in (1,3,5))
def netcolor(n):
    if n=='GND':return (58,123,213)
    if n=='+BATT':return (217,83,79)
    if n=='+10V':return (240,173,78)
    if n=='+3V3':return (92,184,92)
    h=int(hashlib.md5(n.encode()).hexdigest()[:4],16)/65535.0
    r,g,b=colorsys.hsv_to_rgb(h,0.75 if '/Motor' in n else 0.4,0.95 if '/Motor' in n else 0.85)
    return (int(r*255),int(g*255),int(b*255))
def write_png(path,img):
    h,w,_=img.shape
    raw=b''.join(b'\x00'+img[y].tobytes() for y in range(h))
    def chunk(t,d):
        c=struct.pack('>I',len(d))+t+d;return c+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    open(path,'wb').write(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b''))
class Canvas:
    def __init__(s,x0,y0,w,h,sc,mirror=False,bg=(20,24,28)):
        s.x0,s.y0,s.w,s.h,s.sc,s.mirror=x0,y0,w,h,sc,mirror
        s.W=int(w*sc);s.H=int(h*sc);s.img=np.empty((s.H,s.W,3),np.uint8);s.img[:]=bg
    def P(s,x,y):
        X=(x-s.x0)*s.sc
        if s.mirror:X=(s.w-(x-s.x0))*s.sc
        return X,(y-s.y0)*s.sc
    def poly(s,pts,col,alpha=0.8):
        P=np.array([s.P(x,y) for x,y in pts]);n=len(P)
        if n<3:return
        ymin=max(0,int(P[:,1].min()));ymax=min(s.H-1,int(P[:,1].max())+1)
        x1=P[:,0];y1=P[:,1];x2=np.roll(x1,-1);y2=np.roll(y1,-1)
        for row in range(ymin,ymax+1):
            yc=row+0.5
            m=((y1<=yc)&(y2>yc))|((y2<=yc)&(y1>yc))
            if not m.any():continue
            xi=x1[m]+(yc-y1[m])*(x2[m]-x1[m])/(y2[m]-y1[m]);xi.sort()
            for a in range(0,len(xi)-1,2):
                xa=max(0,int(round(xi[a])));xb=min(s.W,int(round(xi[a+1])))
                if xb>xa:
                    seg=s.img[row,xa:xb].astype(np.float32);s.img[row,xa:xb]=(seg*(1-alpha)+np.array(col)*alpha).astype(np.uint8)
    def rect(s,x,y,w,h,col,alpha=1.0,outline=True):
        X,Y=s.P(x,y);W_=w*s.sc;H_=h*s.sc
        x0=int(max(0,X-W_/2));x1=int(min(s.W,X+W_/2+1));y0=int(max(0,Y-H_/2));y1=int(min(s.H,Y+H_/2+1))
        if x1<=x0 or y1<=y0:return
        seg=s.img[y0:y1,x0:x1].astype(np.float32);s.img[y0:y1,x0:x1]=(seg*(1-alpha)+np.array(col)*alpha).astype(np.uint8)
        if outline:
            s.img[y0,x0:x1]=(240,240,240);s.img[y1-1,x0:x1]=(240,240,240);s.img[y0:y1,x0]=(240,240,240);s.img[y0:y1,x1-1]=(240,240,240)
    def circle(s,x,y,r,col):
        X,Y=s.P(x,y);R=r*s.sc
        x0=int(max(0,X-R-1));x1=int(min(s.W,X+R+2));y0=int(max(0,Y-R-1));y1=int(min(s.H,Y+R+2))
        if x1<=x0 or y1<=y0:return
        yy,xx=np.mgrid[y0:y1,x0:x1];m=(xx+0.5-X)**2+(yy+0.5-Y)**2<=R*R
        s.img[y0:y1,x0:x1][m]=col
    def seg(s,xa,ya,xb,yb,w,col):
        Xa,Ya=s.P(xa,ya);Xb,Yb=s.P(xb,yb);R=w*s.sc/2
        x0=int(max(0,min(Xa,Xb)-R-1));x1=int(min(s.W,max(Xa,Xb)+R+2));y0=int(max(0,min(Ya,Yb)-R-1));y1=int(min(s.H,max(Ya,Yb)+R+2))
        if x1<=x0 or y1<=y0:return
        yy,xx=np.mgrid[y0:y1,x0:x1];px=xx+0.5;py=yy+0.5;dx=Xb-Xa;dy=Yb-Ya
        t=np.clip(((px-Xa)*dx+(py-Ya)*dy)/(dx*dx+dy*dy+1e-9),0,1)
        m=(px-Xa-t*dx)**2+(py-Ya-t*dy)**2<=max(R,0.8)**2
        s.img[y0:y1,x0:x1][m]=col
def render(path,layer,out,sc=24,x0=-19,y0=-21,w=38,h=46,mirror=False,showpads=True,showvias=True,showfills=True,showtracks=True):
    B=Board(path);t=B.t;c=Canvas(x0,y0,w,h,sc,mirror)
    if showfills:
        for s_,e,hh in toplevel(t):
            if hh!='zone':continue
            b=t[s_:e];net=re.search(r'\(net "([^"]*)"\)',b);net=net.group(1) if net else ''
            for m in re.finditer(r'\(filled_polygon\s*\(layer "([^"]+)"\)\s*\(pts([\s\S]*?)\)\s*\)',b):
                if m.group(1)!=layer:continue
                pts=[(float(a)-CX,float(q)-CY) for a,q in re.findall(r'\(xy ([-\d.]+) ([-\d.]+)\)',m.group(2))]
                c.poly(pts,netcolor(net),0.75)
    if showtracks:
        for s_,e,hh in toplevel(t):
            if hh=='segment':
                b=t[s_:e];a=re.search(r'\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\)',b);n=re.search(r'\(net "([^"]*)"',b)
                if a and a.group(6)==layer:c.seg(float(a.group(1))-CX,float(a.group(2))-CY,float(a.group(3))-CX,float(a.group(4))-CY,float(a.group(5)),netcolor(n.group(1) if n else ''))
    if showpads:
        for r,f in B.fps.items():
            if abs(f['x'])>25:continue
            for p in f['pads']:
                on=p['th'] or (layer=='F.Cu' and 'F' in p['sides']) or (layer=='B.Cu' and 'B' in p['sides'])
                if on:c.rect(p['x'],p['y'],p['w'],p['h'],netcolor(p['net']) if p['net'] else (130,130,130),0.95)
    if showvias:
        for s_,e,hh in toplevel(t):
            if hh=='via':
                b=t[s_:e];a=re.search(r'\(at ([-\d.]+) ([-\d.]+)\)',b);sz=float(re.search(r'\(size ([\d.]+)\)',b).group(1));dr=float(re.search(r'\(drill ([\d.]+)\)',b).group(1));n=re.search(r'\(net "([^"]*)"',b)
                x=float(a.group(1))-CX;y=float(a.group(2))-CY
                c.circle(x,y,sz/2,(235,235,235));c.circle(x,y,sz/2*0.78,netcolor(n.group(1) if n else ''));c.circle(x,y,dr/2,(10,10,10))
    for s_,e,hh in toplevel(t):
        if hh in('gr_line','gr_arc') and 'Edge.Cuts' in t[s_:e]:
            b=t[s_:e];g=lambda k:list(map(float,re.search(r'\(%s ([-\d.]+) ([-\d.]+)\)'%k,b).groups()))
            if hh=='gr_line':
                a=g('start');z=g('end');c.seg(a[0]-CX,a[1]-CY,z[0]-CX,z[1]-CY,0.08,(255,216,0))
            else:
                a=g('start');m=g('mid');z=g('end')
                for k in range(0,9):
                    t0=k/9;t1=(k+1)/9
                    def q(tt):return ((1-tt)**2*a[0]+2*tt*(1-tt)*(2*m[0]-(a[0]+z[0])/2)+tt*tt*z[0]-CX,(1-tt)**2*a[1]+2*tt*(1-tt)*(2*m[1]-(a[1]+z[1])/2)+tt*tt*z[1]-CY)
                    p0=q(t0);p1=q(t1);c.seg(p0[0],p0[1],p1[0],p1[1],0.08,(255,216,0))
    write_png(out,c.img)
if __name__=='__main__':
    path=sys.argv[1];layer=sys.argv[2];out=sys.argv[3];mir=len(sys.argv)>4 and sys.argv[4]=='m'
    render(path,layer,out,mirror=mir)
