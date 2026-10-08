# OpenESC 20x20 layout (derivative of OpenESC-30x30)

An alternative PCB layout of the OpenESC-30x30 4-in-1 sensorless BLDC ESC for the
**20 x 20 mm** FPV stack hole pattern. The circuit is the upstream circuit; only
the board is new.

> **Status: placement only.** All parts are placed, but there is **no copper and
> no routing**. The board has not been routed, fabricated or tested. Do not order
> it. See [Known issues](#known-issues).

Derived from [OpenDrone-hw/OpenESC-30x30](https://github.com/OpenDrone-hw/OpenESC-30x30)
(CERN-OHL-S-2.0). This is not an official OpenDrone or Incutec release and is not
covered by the upstream OSHWA certification.

![Top](images/20x20-top.png)
![Bottom](images/20x20-bottom.png)

3D views: [top](images/20x20-3d-top.png), [bottom](images/20x20-3d-bottom.png).

## What is the same as the 30x30

Schematics (`4in1.kicad_sch`, `ESC.kicad_sch`), symbols, nets, parts and the
design rules file are **byte-identical** to `../hardware/`. Nothing in the circuit
changed: four AT32F421 + NSG2065Q channels, 24 SP40N01GHNK MOSFETs, board-level
INA186 current sense, LMR54406 buck and TLV76733 LDO, 8-pin Betaflight connector.
See the [root README](../README.md) and [AGENTS.md](../AGENTS.md) for the
architecture, key parts and I/O pinout.

## What is different

| | 30x30 (upstream) | 20x20 (this layout) |
|---|---|---|
| Mounting holes | 30.5 mm pattern | 20 x 20 mm, 4 mm unplated, no copper ring |
| Board size | See upstream | about 35 x 42 mm with battery tab |
| Layers / copper | 6 layers, 1.6 mm, 2 oz outer / 1 oz inner | same (rules in `4in1.kicad_pro`, `4in1.kicad_dru`) |
| Motor pads | per upstream | corner groups, 3 pads per motor, no notches mid-edge |
| MOSFETs | 24 | 24, as 12 stacked pairs (high side top, low side bottom) |
| Bulk ceramic 1206 | 52 | **28** on top, near the MOSFETs |
| Battery pads | per upstream | two castellated pads on a tab, 4 mm wide x 1.5 mm deep |
| MCU, drivers, critical passives | per upstream | bottom side |
| Programming pads | per upstream | 2.54 mm pitch with hand-rework clearance |

Fewer bulk capacitors than the 30x30 means less local ripple filtering; plan to
add the 470 uF electrolytic on the battery leads as the upstream README says.
Per-phase current capacity of the 20x20 layout has **not** been validated: four
channels at 60 A through a board this size is not realistic. See
[docs/DESIGN-NOTES.md](docs/DESIGN-NOTES.md).

## Files

| Path | Content |
|---|---|
| `4in1.kicad_pro`, `.kicad_pcb`, `.kicad_sch`, `ESC.kicad_sch` | KiCad 10 project (name kept from upstream) |
| `4in1.kicad_dru` | Fab design rules |
| `components.kicad_sym` | Local symbols (same as upstream) |
| `fp-lib-table`, `sym-lib-table` | Point at `../hardware/` for the footprint library and the `KiCad-Library` submodule, so nothing is duplicated |
| `fabrication-toolkit-options.json` | Fab export config (archive name still the 30x30 one, change before any export) |
| `images/` | Renders used above |
| `docs/DESIGN-NOTES.md` | Layout decisions, rules followed, findings |
| `docs/drc-v15-placement.json` | Last DRC run on this board |
| `tools/` | Scripts used to generate the placement (provenance only, see [tools/README.md](tools/README.md)) |

## Open the project

```sh
git clone --recurse-submodules <your fork url>
# open hardware-20x20/4in1.kicad_pro in KiCad 10
```

The `OpenDrone` libraries resolve through `../hardware/KiCad-Library`, so the
submodule must be checked out.

## Checks

```sh
kicad-cli sch erc hardware-20x20/4in1.kicad_sch
kicad-cli pcb drc --schematic-parity --refill-zones hardware-20x20/4in1.kicad_pcb
```

Last DRC (`docs/drc-v15-placement.json`): 0 clearance errors; 20 `annular_width`
(the castellated battery and motor pad half-holes, expected for castellation),
29 `lib_footprint_mismatch` (library table path differs from where the footprints
were copied from, to be re-saved from KiCad), and 472 unconnected items because
nothing is routed. ERC was not re-run for this layout; the schematic is unchanged
from upstream.

## Known issues

- No copper, planes, vias or tracks. Routing, power-plane design and a current
  and thermal check are all still to do.
- The 20 castellation `annular_width` findings need the fab to accept
  half-plated holes of this size.
- Some small parts sit in tight clusters (0.2 to 0.3 mm gaps). An earlier
  routing attempt on a related layout failed mostly on boxed-in pads, so expect
  to spread parts or route by hand.
- Silkscreen and `fabrication-toolkit-options.json` still carry upstream naming.

## Licence and credit

CERN-OHL-S-2.0, same as upstream (see [../LICENSE](../LICENSE)). Original design
by the OpenDrone / Incutec team, maintainer @Just4Stan. The 20x20 layout in this
folder is a modified version; changes are limited to PCB placement and outline
as described above.
