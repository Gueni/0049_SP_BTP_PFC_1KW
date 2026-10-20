# Switches

![MOSFET model with body diode, Coss and thermal chain](../asset/MOSFET_Model.png)

Each of the six PFC switches is a `Switches/FET` block. The switch thermal ports go to ambient through `Rth H-A` (`Thermals.rth_Amb`, `Thermals.T_amb`).

`Switches` in [parameters.py](../lib/parameters.py) is a small device library. `PFC_SWITCH` picks the device, and `PFC['SW']` is a copy of it. The FET configuration is set by `Configs['PFC_SW']`.

## FET configurations (`Config`)

| Config | Model | Uses |
|---|---|---|
| 1 | Real SW: MOSFET with thermal description, Foster chain, Coss, body diode | `therm_mosfet`, `Coss` (`Passives/C`), `therm_body_diode` (`Switches/D`) |
| 2 | Ideal SW | – |
| 3 | Physical equivalent circuit (see below) | `Drv`, `Pkg`, `Rg_int`, `Ch`, `Cap`, `Leak`, `Aval`, `Th`, `therm_body_diode` |

## Body diode (`therm_body_diode`, library `Switches/D`)

The same struct serves both diode configurations. `Config` is 2 (physical) when the FET is physical (`PFC_SW = 3`), otherwise 1.

| Config | Model | Fields |
|---|---|---|
| 1 | Diode Thermal: ideal diode + thermal description | `therm_diode`, `vf_diode`, `ron_diode`, `t_init`, `num_par_diode`, `Case_Cth`, `Case_Tinit`, `Case_Amb_rth` |
| 2 | Physical Discrete: forward curve vs. temperature, charge-control reverse recovery, Cj(V), forward recovery, avalanche, package, Cauer chain | `nPara`, `VI`, `Ron`, `RR`, `Cj`, `Roff`, `Aval`, `FR`, `Pkg`, `Th` |

As a body diode, the physical diode has no package of its own (`Pkg.La = Pkg.Lk = 0`, the FET package is in series). It is thermally tied to the FET junction (`Th.Rth` = 1 mK/W).

## Physical equivalent circuit (FET config 3)

| Part | Model | Parameters |
|---|---|---|
| Gate driver | separate on/off current sources with Rgon / Rgoff, switched by the core | `Drv.Von`, `Drv.Voff`, `Drv.Rgon`, `Drv.Rgoff` |
| Package | Lg, Ld, Ls, Lcs (common source), Lk (Kelvin), each damped by Rp | `Pkg` |
| Internal gate resistance | resistor | `Rg_int` |
| Capacitances | nonlinear Cgs, Cgd (Miller plateau, oxide plateau for Vdg < 0), Cds from Ciss/Coss/Crss tables | `Cap` |
| Channel | subthreshold, square law with soft saturation, JFET/drift quasi-saturation, third quadrant; temperature dependent | `Ch` |
| Leakage, avalanche | Rgs_leak, Rds_leak; soft avalanche in the channel | `Leak`, `Aval` |
| Thermal | channel power v·i into the junction, Cauer chain to the thermal port | `Th` |

The `FET core` C-Script computes the channel current, the three capacitances, the channel power and the driver commands from Vgs, Vds and Tj. Its signals reach the circuit through Goto/From tags with schematic scope:
- inputs: `G`, `Vgs`, `Vds`, `Tj`;
- outputs: `Ich`, `Cgs`, `Cgd`, `Cds`, `P_ch`, `S_on`, `S_off`.

The physical diode uses the same pattern (`Ij`, `Cj`, `P_d`, `Tj`, `Qs`, `Mode`).

Use a stiff variable-step solver (RADAU) with this configuration.

## Device: Wolfspeed C3M0021120K (selected)

1200 V / 100 A SiC MOSFET. Datasheet: [Wolfspeed_C3M0021120K_data_sheet.pdf](Wolfspeed_C3M0021120K_data_sheet.pdf).

| Key | Value | Meaning |
|---|---|---|
| `therm_mosfet` | `file:C3M0021120K` | thermal description (config 1) |
| `ron_mosfet` | 21 mΩ | R_DS(on) at 25 °C (config 1) |
| `Rgon` / `Rgoff` | 2.5 Ω | external gate resistance |
| `rth_sw` / `rth_ch` | 0.1 / 0.1 K/W | junction → case / case → heatsink |
| `foster_rth` / `foster_cth` | [0.0472, 0.0688] K/W / [0.95, 2.4] J/K | Foster thermal network (config 1) |
| `T_init`, `Tamb`, `t_init` | 25 °C | initial / ambient temperatures (swept with `Tamb`) |
| `Coss` | 180 pF, ESR 0.5 Ω, ESL 2 nH, `Config` 1 (1 ESR + ESL, 2 Ideal, 3 Pass) | output capacitance (config 1) |

## Simulation speed

| Setting | Effect |
|---|---|
| Any Coss (`Coss.Config` 1 or 2) | ≈ 15× slower. The solver follows the nanosecond charge/discharge at every edge. Example: 0.2 s took 816 s with Coss config 1. |
| `Coss.Config = 3` (Pass) | fast; use it for long runs and sweeps |
| `Case_Cth > 0` | adds a thermal state and was ≈ 4× slower; 0 is accepted |
| FET config 3 (physical) | resolves every switching transient (ns); meant for short switching studies, not 0.4 s line-cycle runs |
