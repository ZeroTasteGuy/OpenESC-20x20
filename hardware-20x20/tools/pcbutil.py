import re
def toplevel(t):
    """yield (start,end,head) of depth-1 items"""
    d=0;i=0;n=len(t);ins=False;st=None
    while i<n:
        c=t[i]
        if ins:
            if c==chr(92):i+=1
            elif c=='"':ins=False
        elif c=='"':ins=True
        elif c=='(':
            d+=1
            if d==2:st=i
        elif c==')':
            if d==2:
                yield st,i+1,re.match(r'\((\w+)',t[st:st+30]).group(1)
            d-=1
        i+=1
