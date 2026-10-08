#!/bin/bash
# usage: drc.sh   (runs on 4in1.kicad_pcb in cwd)
"/c/Users/Admin/AppData/Local/Programs/KiCad/10.0/bin/kicad-cli.exe" pcb drc --refill-zones --save-board --format json --severity-all -o drc.json 4in1.kicad_pcb >/dev/null 2>&1
python - <<'P'
import json,collections
d=json.load(open('drc.json'))
c=collections.Counter(v['type'] for v in d['violations'])
print(dict(c),'unconn',len(d['unconnected_items']))
n=0
for v in d['violations']:
    if v['type'] not in('annular_width','lib_footprint_mismatch'):
        n+=1
        if n<=25:print(v['type'],[i['description'] for i in v['items']],v['items'][0]['pos'])
P
