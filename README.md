# 1 kW Totem-Pole Bridgeless PFC

> [!IMPORTANT]
> The component libraries used by the PLECS model are not included in this repository. Get them from [Gueni/0000_libraries](https://github.com/Gueni/0000_libraries) before opening or running the simulations.

Design and simulation of a single-phase, **non-interleaved** totem-pole bridgeless PFC (TPB PFC) rated at 1 kW / 400 V DC. One fast leg switches at PWM frequency (HS1/LS1, SiC), and one slow leg switches at line frequency (HS2/LS2) and replaces the diode bridge. The model is built in PLECS and driven from Python: a parameter sweep, an HTML report with waveforms and harmonics, logs, and optional code generation for a PLECS RT Box.

![Single phase bridgeless totem-pole PFC: top level](asset/schematic.png)

The top level chains **grid → EMI filter → PFC stage → DC link (CDC) → load**. The PFC controller (`PFC CTRL`) drives the gates through `g_PFC`. The switches' thermal port goes to ambient through `Rth H-A`. `Scopes` and `Data Export` (the To File block that writes the result CSV) hold the measurements.

## Specifications

| Parameter | Value |
|---|---|
| Output power | 1 kW (load step at t = 0.55 s) |
| Output voltage | 400 V DC |
| Input voltage | 85–265 Vrms, 50 Hz (nominal 230 Vrms) |
| Switching frequency | 80 kHz (fast leg), 50 Hz (slow leg) |
| Boost inductance | 248 µH effective |
| Inductor ripple | 5.0 A p-p max, 30 % of the 16.6 A line peak at 85 Vrms |
| DC-link capacitance | 480 µF (470 µF electrolytic + 10 µF HF) |
| DC-link ripple | ≈ 16.6 V p-p at 100 Hz (4.1 %) |
| Hold-up | ≈ 16.8 ms from 400 V down to 300 V at 1 kW |

## Power stage

### Grid

![Grid model](asset/grid.png)

The grid is an ideal sine source, `√2 · Vin · sin(2π · f · t)`, with a series resistance in line and neutral. L2/L3 are only used by the three-phase configuration.

| Parameter | Value |
|---|---|
| `Grid.Vin` | 230 Vrms |
| `Grid.f` | 50 Hz |
| `Grid.R` | 10 mΩ per conductor |

### EMI filter

![EMI filter, 1PH configuration](asset/EMI_Filter.png)

A two-stage single-phase filter, library block `Power/EMI FILTER`. It has three configurations: `1 = 1PH` (used), `2 = 3PH` and `3 = Pass`. The signal path is CMC → Cx, with Cy1/Cy2 to PE → series inductors L1/L5 → DMC → Cx1.

| Part | Value | Part type |
|---|---|---|
| CMC | 4.7 mH per winding, k = 0.995 (23.5 µH leakage), 30 mΩ | nanocrystalline, 10 A |
| DMC | 100 µH per winding, uncoupled, 25 mΩ | powder core, 10 A |
| L1, L5 (`Ll`) | 10 µH | line / neutral series inductance |
| Cx, Cx1 | 470 nF, ESR 15 mΩ | X2 film, 310 VAC |
| Cy1, Cy2 | 2.2 nF, ESR 0.2 Ω | Y1 ceramic (leakage 0.18 mA at 265 V) |

| Figure | Value |
|---|---|
| DM resonance (≈ 267 µH, Cx1) | ≈ 14 kHz, ≈ 30 dB attenuation at 80 kHz from this stage alone |
| CM resonance (4.7 mH, Cy1 + Cy2) | ≈ 35 kHz |
| X-capacitor reactive current | 78 mA at 265 V |

> [!NOTE]
> The filter is lightly damped in simulation (Q ≈ 190, no core losses). If the input current rings near the zero crossings, add an R–C damping branch across Cx1 (≈ 24 Ω with 1–2 µF).

### Coupled inductors (CMC, DMC, boost choke)

![Coupled inductor model](asset/EMI_CMC_DMC.png)

The CMC, the DMC and the PFC boost choke all use the same `Magnatic Components/Choke` block. It is a two-winding mutual inductance with self inductances L1/L2, mutual inductance Lm, winding resistances R1/R2 and mutual resistance Rm. Each winding sees a leakage inductance of `L − Lm`. For the boost choke the current loop sees `L_boost = L1 + L2 − 2·Lm`.

### PFC stage

![Totem-pole PFC stage](asset/PFC_stage.png)

The boost choke sits between the AC input and the switch node of the fast leg (HS1/LS1). The slow leg (HS2/LS2) connects the other AC line to the DC rails according to the line polarity. `Cout` is the high-frequency decoupling capacitor on the DC bus. Gate signals for HS3/LS3 exist for other configurations and stay off in the `TPB PFC` configuration.

| Parameter | Value |
|---|---|
| Boost choke | L1 = 240 µH, L2 = 10 µH, Lm = 1 µH → **L_boost = 248 µH**, 10 mΩ per winding |
| `PFC.Cout` | 10 µF |
| Dead time | 300 ns |

### Switches

![MOSFET model with body diode, Coss and thermal chain](asset/MOSFET_Model.png)

Each switch is a MOSFET with a body diode and an optional Coss, plus a Cauer/Foster thermal chain to the heatsink. Losses come from the thermal description files.

| Parameter | Value |
|---|---|
| Device (thermal model) | Wolfspeed C3M0021120K, 1200 V SiC |
| R_DS(on) | 65 mΩ |
| Body diode | Vf = 4.5 V, 5 mΩ |
| Gate resistance | 2.5 Ω on / off |
| Coss | 180 pF (configuration 5 = bypassed) |
| Thermal | R_th j-c = 0.1 K/W, c-h = 0.1 K/W, h-a = 0.09 K/W, T_amb = 25 °C |

### DC link

![DC-link capacitor model](asset/DCLINK%20cap%20model.png)

The capacitor model is C + ESR + ESL (`Passives/C`). Its configurations are 1 Ideal, 2 ESR, 3 ESL, 4 ESR + ESL, 5 Pass and 6 Short. The DC link uses configuration 4.

| Parameter | Value |
|---|---|
| `DCLink.Cap_s` | 470 µF |
| ESR / ESL | 50 mΩ / 1 pH |
| Initial voltage | √2 · Vin (pre-charged, inrush bypass assumed) |

### Load

![Load model](asset/load%20model.png)

The load is a switchable resistive / RL load (RL1, RL2, RL3) with a freewheeling path (RF, DF). It takes a load step at `Load.t_switch`.

| Parameter | Value |
|---|---|
| `Load.Pout` | 1 kW → R = 160 Ω at 400 V |
| Load step | t = tSim − load_tflip = 0.55 s |

## Control

The controller uses average current mode control in the `PFC CTRL` → `TPB PFC` configuration:

- **Voltage loop:** PI on `Vref − Vdc`. The error passes through a 20 Hz low-pass filter that attenuates the 100 Hz ripple. The output is the power command `P*`, limited to `[0, 1.5 kW]`.
- **Current reference:** `Iref = |Vac| · P* / Vrms²`, limited to `Ipk_max = 25 A`, the peak current at 1.5 kW and 85 Vrms.
- **Current loop:** PI on `Iref − |iL|` with input-voltage / Vdc duty feed-forward. The duty is limited to `Dmax = 0.98`.
- **Zero crossing:** all gates are blanked while `|Vac| < 20 V`. The slow leg follows the line polarity.
- **Soft start:** Vref ramps from √2 · Vin to 400 V over 0.2 s.

| Loop | Crossover | Kp | Ki |
|---|---|---|---|
| Current | fc_i = fsw / 10 = 8 kHz | 2π · fc_i · L_boost = 12.47 V/A | (2π · fc_i)² / 10 · L_boost = 62.7 kV/(A·s) |
| Voltage | fc_v = 10 Hz | 2π · fc_v · C_out · Vref = 12.06 W/V | (2π · fc_v)² / 2 · C_out · Vref = 379 W/(V·s) |

The gains are recomputed by `Derived.update()` in `derived.py` whenever a sweep changes L, C, fsw or Vref.

## Simulation

| Setting | Value |
|---|---|
| Simulation time | 0.6 s |
| Saved window | 0.4 s → 0.6 s (`ToFile.tsave`) |
| Solver | variable step, max step 1 ms, rel. tol. 1e-7, zero-crossing limit 1000 |

## Running a sweep

```bash
python Lib/sweep.py
```

`sweep.py` simulates every combination of the values in `SWEEP`. `SWEEP_PATHS` sets where each swept value is written in `ModelVars`, and one swept value can drive several parameters. The flags at the top choose what runs:

| Flag | Effect |
|---|---|
| `SWEEP_EN` | Run the simulation sweep |
| `PARASIM` / `PARANUM` | Run sweep points in parallel. `PARANUM = None` sizes the batches from the CPU threads, keeping one free and spreading the points evenly over the batches. |
| `SCOPES` | Scopes to clear/hold/save. `None` = every scope found in the model, including only the active configuration of configurable subsystems and skipping commented-out blocks. `[]` = none. |
| `CODEGEN` | Generate code with PLECS Coder (`CODEGEN_TARGET` = subsystem with code generation enabled) |
| `RTBOX` | Upload and run the generated code on the RT Box at `RTBOX_URL` |

A sweep writes these outputs to `data/` (git-ignored):

```
data/
  timeseries/            Results_<run>_<n>.csv     waveforms of each sweep point (columns: time + Waveforms in parameters.py)
  mat/                   RMS_<run>.csv             one row per sweep point, one column per waveform
                         Average_<run>.csv
                         PeakToPeak_<run>.csv
                         Max_<run>.csv
                         Min_<run>.csv
                         Peak_<run>.csv            largest absolute value
                         FFT_<run>.csv             one row per sweep point and waveform: f0_Hz, H1 … H50
  html/                  Html_<run>.html           single report: for each waveform its time-domain figure then its
                                                   harmonic bar plot (every point overlaid), then the calculated
                                                   results table and the parameter table
  log/                   Log_<run>.log             base parameters, then the parameters changed by each iteration
  traces/                                          saved scope traces
```

The calculated results are computed once per time-series file, with one batch function per type in `pmath.py` (`rms`, `average`, `peak_to_peak`, `maximum`, `minimum`, `peak`, `harmonics`):

- **Window:** all types use the same steady-state window, the last `ANALYSIS_CYCLES` (5) whole cycles of the grid fundamental. Without a fundamental, they use the whole saved window.
- **RMS and average:** time-weighted, so they are correct on PLECS' variable-step samples.
- **Harmonics:** the x-axis is the harmonic order, and each title shows the fundamental used: `Grid.f` = 50 Hz by default, `CTRL.fsw` = 80 kHz for the fast-leg signals (`F0_OVERRIDES`).
- **Parameter table:** units, comments and values; a swept value is shown as `a / b / c`.

## Repository layout

```
asset/                 Schematics used in this README and the HTML report
doc/literature/        Reference papers and app notes
Model/
  PFC.plecs            PLECS model (power stage + control)
  tpbpfc_init.m        Stand-alone MATLAB/Octave first-cut design script (sizing from the specs)
Lib/
  sweep.py             Sweep definition and run flags (sweep / code generation / RT Box)   [system specific]
  parameters.py        Model paths, component parameters, waveforms                       [system specific]
  derived.py           Derived parameters, recomputed on every sweep point                 [system specific]
  pplecs.py            PLECS XML-RPC interface, scope detection, result folders, sweep points, batch sizing
  pplots.py            HTML report: waveforms, harmonic bar plots, parameter table
  plog.py              Sweep log
  pmath.py             Signal math: batch RMS, average, peak-to-peak, max, min, peak, harmonics; envelope
  rtbox.py             PLECS Coder code generation and RT Box run
data/                  Sweep outputs (git-ignored)
```

Only `parameters.py`, `derived.py` and `sweep.py` are specific to this converter. To simulate another system (LLC, OBC, DC-DC …), copy those files and edit them; the library modules stay unchanged. The header of `parameters.py` lists what it must define.

## Parameter structs (`ModelVars`)

| Struct | Contents |
|---|---|
| `Sim_param` | Simulation time, load step time, solver settings |
| `ToFile` | Saved window and output file paths (filled in per run) |
| `Grid` | Grid source: Vin, f, phase, line resistance |
| `AC_Filter` | EMI filter: CMC, DMC, Ll, Cx, Cy1, Cy2 |
| `PFC` | Boost choke, Cout, switches (electrical + thermal) |
| `DCLink` | DC-link capacitor |
| `CTRL` | Control loops, gains, limits, zero-crossing and soft-start settings |
| `Load` | Load power, R/L, load step |
| `Thermals` | Ambient temperature, heatsink-to-ambient thermal resistance |
