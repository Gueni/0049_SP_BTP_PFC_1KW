# Hardware in the loop on the RT Box 1

The power stage runs in real time on a PLECS RT Box 1; the control algorithm runs on its own board (STM32 or other), wired to the RT Box as it would be to the real converter.

```
controller board                                RT Box 1  (plant: grid, PFC stage, DC link, load, sensors)
   4 PWM outputs   ───────────────────────────►  digital inputs 0..3   (PWM capture)  ──► gates HS1, LS1, HS2, LS2
   3 ADC inputs    ◄───────────────────────────  analog outputs 0..2   (0 ... 3.3 V)  ◄── sensor voltages Vac, Vdc, Iin
```

`main.py` writes the model for this, `Model/PFC_rtbox.plecs`, from `Model/PFC.plecs` ([lib/rtbox.py](../lib/rtbox.py)).

## The RT Box copy (`Model/PFC_rtbox.plecs`)

| Block | Content | Role |
|---|---|---|
| `Plant` | everything of `PFC.plecs` except the controller, the scopes and the data export, plus one `PWM Capture` and three `Analog Out` blocks | code generation enabled, target `PLECS RT Box 1`, step `RTBox.Ts`. This is what runs on the RT Box. |
| `MCU` | the controller of `PFC.plecs`, unchanged | closes the loop in the offline simulation. On the bench its place is taken by the controller board. |
| `Scopes`, `Data Export` | unchanged, their probes point into `Plant` | offline only, not in the generated code |

The copy is standalone: no links to the user libraries, and every parameter written as a value in the initialization commands (see [simulation.md](simulation.md)). The links to the PLECS power modules and to the RT Box blocks are kept, because those blocks must stay linked to their package.

The file is regenerated on every run of `main.py` while `RTBOX_MODEL` is on, so do not edit it by hand. It is set to sweep point `STD_POINT`, always in the `rtbox` mode, whatever `MODE` is.

## The `rtbox` mode

Real-time code cannot use the switch models of the other modes: on the RT Box 1 the plant runs on the CPU with a step of a few microseconds, which is only 3 to 5 steps per PWM period.

| Part | `rtbox` mode | Why |
|---|---|---|
| PFC legs | `Power/PFC` configuration 4, `1PH TPB PFC 2 Leg Avg`: each leg is a PLECS Half Bridge power module in sub-cycle average mode | the PWM capture gives the on-time of each gate during a step (0 ... 1), and the leg applies it as an averaged voltage. Dead time and diode conduction are handled by the module. |
| Load | `Passives/Load` configuration 3, `R`: controlled current source i = v / R | PLECS Coder does not accept the variable resistor with series inductor of `RL` |
| EMI filter, capacitors, choke | as in `ideal` (filter bypassed, ideal parts) | no fast resonances that the step cannot follow |

With the controller of the model driving 0 / 1 gates, the averaged legs give the same result as the ideal switches (100 kHz, 1 kW, after 0.1 s: same Vout range and input power, THD 1.48 % against 1.47 %). `MODE = 'rtbox'` can therefore also be used for ordinary sweeps.

There is no switch loss, junction temperature or switch current in this mode: those result columns are 0.

## Parameters (struct `RTBox` in `vars.py`)

| Key | Default | Meaning |
|---|---|---|
| `Ts_min` | 2.2 µs | smallest step the RT Box can run the plant at. Raise it if the RT Box reports overruns. |
| `Ts` | derived | step of the plant: the PWM period divided by a whole number, not below `Ts_min` (2.5 µs at 100 kHz, 2.22 µs at 150 kHz). Set by `Derived.update`. |
| `DI_gate` | `[0, 1, 2, 3]` | digital inputs of HS1, LS1, HS2, LS2 |
| `AO_sns` | `[0, 1, 2]` | analog outputs of the Vac, Vdc and Iin sensor voltages |
| `AO_max` | 3.3 V | upper limit of the analog outputs (lower limit 0 V), to protect the ADC pins |
| `gate_width` | 6 | width of the gate bus of the plant; the signals after the captured ones are 0 |

The analog outputs carry the sensor voltages of [measurement.md](measurement.md), so the board sees what the real sensors would give:

| Output | Signal | Scale |
|---|---|---|
| AO 0 | Vac sensor | 3.75 mV/V around 1.65 V |
| AO 1 | Vdc sensor | 6 mV/V, 20 mV offset |
| AO 2 | Iin sensor | 50 mV/A around 1.65 V |

The analog output range of the RT Box must be 0 ... 5 V (the default of the target).

## Building and running

| Flag in `main.py` | Effect |
|---|---|
| `RTBOX_MODEL` | write `Model/PFC_rtbox.plecs` |
| `CODEGEN` | build the plant (`PFC_rtbox/Plant`) with PLECS Coder into `CODEGEN_DIR` |
| `RTBOX` | upload the build to the RT Box at `RTBOX_URL`, start it, write `RTBOX_SET`, read `RTBOX_CAPTURE` |

The build needs the full PLECS RT Box target support package. A PLECS installation that only has the preview of the package stops with "The required target 'PLECS RT Box 1' is only installed as a preview version". Download the package from Plexim and set its folder in the PLECS preferences (Coder > Target support packages).

The plant can also be built from PLECS: open `PFC_rtbox.plecs`, Coder > Coder options, select `Plant`, Build.

## What to expect on the bench

Offline run of the copy as generated (1 kW, 230 V, 150 kHz, plant step 2.22 µs, 0.4 s): Vout 388.5 ... 411.8 V, input power 1000.6 W.

> [!IMPORTANT]
> The grid current has a DC component of about -0.7 A in this run (-0.85 A at 100 kHz with a 2.5 µs step), which the ordinary model does not have. It comes from the latency of the loop: a gate edge reaches the plant up to one step late and averaged over a step, so the inductor current ripple is shifted against the PWM carrier, and the ADC no longer samples it at its average. Shifting the sampling instant of the controller by about one plant step moves this DC component through zero (checked offline: -0.34 A at 0.7 steps, +0.70 A at 1.5 steps). On the bench, delay the ADC trigger of the board by about one plant step, or run the plant with a smaller step.

The delay of the analog outputs of the RT Box is not in the offline run and adds to this latency.

## Limits

- The controller is not ready for code generation: its PWM carrier and dead-time blocks need a much smaller step than the control algorithm. To generate the algorithm with PLECS Coder, `PFC CTRL` must first be split into the algorithm (sampled once per PWM period) and the modulator (the PWM timer of the board).
- The generic C code of the plant was generated without errors (PLECS Coder, target Generic, I/O blocks replaced). The RT Box build itself and the run on the hardware have not been done yet.
- `MODE = 'rtbox'` in `PFC.plecs` needs the updated `Power` and `Passives` libraries. PLECS keeps libraries in memory: restart PLECS after the libraries change.

## In another project

```python
from lib.rtbox import RTBoxModel
RTBoxModel.write('model.plecs', ModelVars, ['path/to/libraries'], controller='MCU', offline=('Scopes',), gate_width=6)
```

The controller must be one subsystem on the top level of the model, connected to the rest through From blocks (the signals it reads) and one Goto block (the gate bus). Copy `rtbox.py`, `standalone.py` and `breaklink.py` together.
