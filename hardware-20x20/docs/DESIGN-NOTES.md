# 20x20 layout: design notes

Why the board looks the way it does, and what is known and unknown. Revision
history of the layout lives in git; this file is the intent.

## Goals

- Fit the existing OpenESC circuit on a 20 x 20 mm stack pattern, about 35 x 42 mm.
- Layout in the style of common 20x20 4-in-1 ESCs: motor pads in corner groups
  (3 per motor), no notch in the middle of the long edges, stacked MOSFET pairs.
- Keep the circuit the same except where the layout forced a change (see below).

## Placement

- **Holes:** 4 mm unplated at (+-10, +-10) mm. A 6 mm rubber-grommet zone around
  each hole keeps small parts out.
- **MOSFETs:** 12 sites, each a stacked pair on the same x/y (high side on top,
  low side on the bottom): 4 corner pairs (phase A) and 8 strip pairs (phases B
  and C, inner and edge columns). Upper-half sites are rotated 0 degrees, lower
  half 180 degrees.
- **Bottom side:** MCUs, gate drivers, buck, LDO and critical passives (gate
  resistors, bootstrap and supply decoupling).
- **Top side:** MOSFETs, 28 bulk 1206 capacitors, test points and a few
  non-critical parts.
- **Symmetry:** the two half-boards are 180 degree twins.
- **Battery tab:** two castellated pads 4 mm wide and 1.5 mm deep with rounded
  tab corners; a bulk-cap row sits directly above it.
- **Keep-outs used:** small ICs and passives at least 3 mm from motor and battery
  pads and 2 mm from the board edge. MOSFETs, the JST connector and 1206 caps may
  sit closer. Bulk-cap pad gaps are at least 0.2 mm for fab safety.
- **No current sensing at all.** The board-level INA186 (U12), its two shunts
  (Rsense1, Rsense2) and the input network (R89, R90, C40, C41, C42, plus C94 and
  R73) are not on the PCB, and per-phase shunts were not wanted either. They
  were removed from the schematic so it matches the board.
- **Schematic matched to the board:** castellated strip J2 added (pins +BATT,
  GND, CURR, unused, M1 to M4); the U3 board block lost the pins that no longer
  have pads (3 to 11) and was redrawn with the real board outline (chamfered
  top strip, bottom battery tab, four mounting holes); the battery pad (U3 pin 1)
  joins `+BATT` directly where the shunts used to sit.

## Findings

- **Bottom free area is the bottleneck.** About 391 mm2 of 1345 mm2 is free for
  small parts after MOSFETs, pad keep-outs, grommet zones and the edge band.
- **Copper-only path resistance** (estimated on an earlier placement with power
  copper, ESC1, source-to-pad / pad-to-drain, mOhm): phase A 0.18 / 0.14,
  B 0.06 / 0.03, C 0.61 / 0.48. Worst point: low-side ground path of phase B
  (about 2 mOhm, no ground vias yet) and the narrow phase-C lane between hole and
  MOSFET row. This was **not** repeated on the final placement.
- **Current capacity:** lane necks reached about 45 A/mm at 40 A in an earlier
  trial; about 8 to 10 A/mm is comfortable for 2 oz outer copper. Do not expect
  four channels at 60 A.
- **Signal routing:** an automatic grid router completed about a third of the
  links on the related layout, and most failures were pads boxed in by
  neighbours. Spacing, not copper weight, is the limit.

## To do before this can be a real board

0. Add a PWR_FLAG on `+BATT` and `GND`, set J2's value and BOM flag to match the
   board, then re-run ERC and DRC with schematic parity.
1. Power copper: planes, phase copper, via sets, ground vias at low-side sources.
2. Signal routing, mostly by hand.
3. Re-run DRC with schematic parity and ERC, resolve `lib_footprint_mismatch`.
4. Resistance and thermal check on the routed board.
5. Confirm castellation capability with the intended fab.
6. Rename the archive in `fabrication-toolkit-options.json`, review silkscreen.
7. Bring-up with a current-limited supply before any motor.

## Regenerating

`tools/` holds the scripts that produced the placement. They were run against
local working copies that are not in this repository, so treat them as
documentation of the method rather than a reproducible build. See
`tools/README.md`.
