# 1 kW Totem-Pole Bridgeless PFC

> [!IMPORTANT]
> The component libraries used by the PLECS and LTspice models are not included in this repository. Get them from [Gueni/0000_libraries](https://github.com/Gueni/0000_libraries) before opening or running the simulations.

Design and simulation of a single-phase, **non-interleaved** totem-pole bridgeless PFC (TPB PFC) rated at 1 kW: one fast leg switching at PWM frequency (HS1/LS1, GaN or SiC) and one slow leg switching at line frequency (HS2/LS2, Si).

The power stage and control are developed in PLECS first, then ported to LTspice.

## Target specifications

| Parameter | Value |
|---|---|
| Output power | 1 kW |
| Output voltage | 400 V DC |
| Input voltage | 85–265 Vrms, 50/60 Hz |
| Switching frequency | 65 kHz (fast leg) |
| Inductor current ripple | 30 % of peak at 85 Vrms |
| Output voltage ripple | 5 % p-p (2·f_line) |
| Hold-up | 10 ms down to 300 V |

These are starting values. Edit them in [plecs/tpbpfc_init.m](plecs/tpbpfc_init.m); the inductor, output capacitor and first-cut PI gains are derived from them.

## Repository layout

```
doc/
  literature/          Reference papers and app notes
  design/              Design notes, calculations, loss estimates
plecs/
  tpbpfc.plecs         PLECS model (power stage + control)
  tpbpfc_init.m        Model initialization: specs, filter, power stage, control
  results/             Exported waveforms / scope data (git-ignored)
ltspice/
  tpbpfc.asc           LTspice schematic
  tpbpfc_params.inc    Parameters, mirror of tpbpfc_init.m
  models/              Vendor device models (.lib, .asy)
  results/             Simulation outputs (git-ignored)
```

## Workflow

1. **PLECS power stage** – source, EMI filter, totem-pole bridge, Cout, load. Run the init script from *Simulation > Simulation Parameters > Initialization*.
2. **PLECS control** – average current mode control: outer voltage PI, inner current PI, input voltage feedforward, slow-leg polarity detection, and zero-crossing soft-start for the fast leg.
3. **LTspice** – rebuild the verified design with real device models (put them in `ltspice/models/`) and include `tpbpfc_params.inc`.

## Parameter structs

| Struct | Contents |
|---|---|
| `Spec` | Ratings and design targets |
| `Source` | AC source (`Source.Vin`, `Source.f`) |
| `Filter` | EMI filter (Cx, Cy, CMC, bleeders) |
| `PS` | Power stage (L, Co, switches, load) |
| `Ctrl` | Control loops, sample time, thresholds |
| `Sim` | Simulation time and initial conditions |
