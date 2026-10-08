# tools

Python and shell scripts used to generate and check the 20x20 placement
(outline and pads, MOSFET sites, IC and bulk-cap placement, small-part
optimiser, DRC wrapper, an experimental grid router and a copper-path resistance
solver).

Provenance only. They were developed on Windows against `kicad-cli` from KiCad
10 and expect local working copies and intermediate boards that are not in this
repository (for example `../hardware-alt/4in1.kicad_pcb` as the source layout).
Each script rewrites KiCad board text, so run them on copies, never on files in
`hardware/` or `hardware-20x20/`. Upstream rules apply: close KiCad before
writing any KiCad file.
