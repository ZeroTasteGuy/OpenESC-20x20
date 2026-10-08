import json,re,sys
pcb,drc=sys.argv[1],sys.argv[2]
d=json.load(open(drc,encoding='utf8'));t=open(pcb,encoding='utf8').read()
n=0
for v in d['violations']:
    if v['type']=='via_dangling':
        uid=v['items'][0]['uuid']
        m=re.search(r'\n\t\(via\b(?:(?!\n\t\()[\s\S])*?\(uuid "%s"\)[\s\S]*?\n\t\)'%re.escape(uid),t)
        if m:t=t[:m.start()]+t[m.end():];n+=1
open(pcb,'w',encoding='utf8').write(t);print('pruned dangling vias:',n)
