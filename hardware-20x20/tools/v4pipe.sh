#!/bin/bash
cd /c/Users/Admin/Claude/KiCad/OpenESC-30x30/hardware-v2
cp ../hardware-alt/4in1.kicad_pcb t0.kicad_pcb
python $TEMP/v2_step1b.py t0.kicad_pcb | tail -1
python $TEMP/v2c_place.py t0.kicad_pcb | head -1
python $TEMP/ic_place.py t0.kicad_pcb t1.kicad_pcb | grep -E "no spot|wrote t1"
SRC=t1.kicad_pcb DST=t2.kicad_pcb EDGE=0.6 NMAX=${NMAX:-30} python $TEMP/place_bulk3.py | tail -2 | head -1
NONCRIT_F=${NONCRIT_F:-1} ONLYB=1 TWINS=1 PASSES=${PASSES:-14} python $TEMP/opt_layout2.py t2.kicad_pcb base_v4.kicad_pcb | grep -E "untwinned|cost after|wrote" | tr '\n' ' '
echo
