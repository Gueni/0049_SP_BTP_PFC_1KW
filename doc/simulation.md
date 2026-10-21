# Simulation, sweep and results

## Settings (`vars.py`)

| Setting | Value |
|---|---|
| `TSIM` | 0.4 s. The converter is settled after about 75 ms (1 ms enable + 50 ms soft start). |
| Load step | at `tSim − load_tflip` = 0.2 s |
| Saved window | from `TSAVE = TSIM − 0.05` to the end (`ToFile.tsave`) |
| Solver | variable step, max step 1 ms, rel. tol. 1e-3, zero-crossing limit 1000 |

The run time depends mostly on the switch model ([switches.md](switches.md#simulation-speed)).

## Running a sweep

PLECS must be running with its XML-RPC server enabled on port 1080. Restart PLECS after editing a library, because it caches libraries.

```bash
python main.py
```

`main.py` simulates every combination of the values in `SWEEP`. Values in `SWEEP` override the defaults in `vars.py`, so check them before a run.

Each `SWEEP` key is the name of a parameter in `vars.py` (`'Vin'`), or the end of its path when the name is used several times (`'Choke.L1'`, `'DCLink.Cap_s'`). The sweep finds the parameter in `ModelVars` by itself and prints where each key goes. A key that matches no parameter, or several, stops the run with the possible names. Parameters that follow another one are set in `Derived.update()` (in `calc.py`): `CTRL.Pout` follows `Load.Pout`, and the switch `Tamb` / `T_init` follow `Thermals.T_amb`. After the swept values are written, `Derived.update()` also recomputes the dependent parameters (loop gains, load R, ADC rate…).

### Model mode

All block configurations are in `Configs` in [vars.py](../lib/vars.py), and `CONFIG_PATHS` says where each one is written in `ModelVars`. `MODE` at the top of `main.py` switches the model depth in one variable:

| `MODE` | Capacitors (EMI filter, DC link, Coss) | Switches | Body diode |
|---|---|---|---|
| `'ideal'` | ideal | ideal | – |
| `'real'` | ESR + ESL (Y capacitors ideal) | thermal model with Coss | thermal |
| `'physical'` | ESR + ESL (Y capacitors ideal) | physical equivalent circuit | physical |
| `None` | as in `Configs` | as in `Configs` | as in `Configs` |

The presets are the `MODES` dict in `vars.py`; edit it to change what a mode means. The Y capacitors stay ideal: their ESL closes a common-mode loop with no damping path, and the slow-leg commutation at the line zero crossing then makes PLECS stop with "State discontinuity after switching". Grid, EMI filter topology, PFC topology and load keep their `Configs` value in every mode.

### Flags

| Flag | Effect |
|---|---|
| `SWEEP_EN` | run the simulation sweep |
| `PARASIM` / `PARANUM` | run sweep points in parallel; `PARANUM = None` sizes the batches from the CPU threads |
| `SCOPES` | scopes to clear/hold/save: `None` = every scope of the active configurations, `[]` = none |
| `HOLD_TRACES` / `SAVE_TRACES` | keep and save the scope traces of every point |
| `CODEGEN` | generate code with PLECS Coder (`CODEGEN_TARGET` = subsystem with code generation enabled) |
| `RTBOX` | upload and run the generated code on the RT Box at `RTBOX_URL` |

## Outputs (`data/`, git-ignored)

```
data/
  timeseries/   Results_<run>_<n>.csv   waveforms of each point (time + the probe signals, named in the header)
  mat/          RMS / Average / PeakToPeak / Max / Min / Peak _<run>.csv   one row per point, one column per waveform
                FFT_<run>.csv                                             f0_Hz, H1 … H50 per point and waveform
  html/         Html_<run>.html         single report: waveform + harmonic plot of every point, results table, parameter table
  log/          Log_<run>.log           base parameters, then what each iteration changed
  traces/                               saved scope traces
```

### Signal names

The result columns are not listed by hand. The `To File` block in `Data Export` writes the signal names in the CSV header, as `component:probe signal`, and `:k` for each element of a vector probe. `plecs.ProbeNames` turns them into report names and units:

- **Vector elements:** named after the mask probe of the referenced library block (in `PLECS_LIB_DIR`) for its active configuration, e.g. `PFC:SW Voltages:1` becomes `PFC SW Voltages HS1`.
- **Placeholder constants:** they count with their width, e.g. `SW PH 1`, `SW PH 2` for the switches the 2-leg configuration does not have.
- **Units:** taken from the probe and signal names (voltage → V, current → A, temperature → °C, loss → W, gate → /).
- **Vectors no library block names:** e.g. the gate vector entering the PFC block. Their element names come from `SIGNAL_LABELS` in `vars.py`.

Adding or removing a probe in `Data Export` needs no change in Python.

How the results are computed (`calc.py`, `process.py`):

| Item | Detail |
|---|---|
| Window | all metrics use the last `ANALYSIS_CYCLES` (5) whole cycles of the grid fundamental; without a fundamental, the whole saved window |
| RMS and average | time-weighted, so they are correct on PLECS' variable-step samples |
| Harmonics | x-axis is the harmonic order. The fundamental is `Grid.f` (50 Hz), or `CTRL.fsw` for the fast-leg signals (`F0_OVERRIDES`). |
| Parameter table | units, comments and values; a swept value is shown as `a / b / c` |

## Device tests

The switch models (`Switches/D`, `Switches/FET`) are tested on their own in the standalone component test project `0000_libraries/Plecs/component_tests`: a double pulse in each mode (ideal, real, physical), run with `python lib/ctest.py` there. See its README.

## Parameter structs (`ModelVars`)

| Struct | Contents | Doc |
|---|---|---|
| `Sim_param` | simulation time, load step, solver | this page |
| `ToFile` | saved window, output paths (filled per run) | this page |
| `Grid` | grid source | [grid.md](grid.md) |
| `AC_Filter` | EMI filter | [emi_filter.md](emi_filter.md) |
| `PFC` | boost choke, Cout, switches | [pfc_stage.md](pfc_stage.md), [switches.md](switches.md) |
| `DCLink` | DC-link capacitor bank | [dc_link.md](dc_link.md) |
| `CTRL` | control loops, limits, timing | [control.md](control.md) |
| `Load` | load | [load.md](load.md) |
| `Thermals` | ambient temperature, heatsink-to-ambient Rth | [switches.md](switches.md) |
| `Sensors`, `MCU` | measurement chain, ADC, firmware calibration | [measurement.md](measurement.md) |

Every parameter in `vars.py` carries a `#? [unit] - comment`, which the HTML report shows.
