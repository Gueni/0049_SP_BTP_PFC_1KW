# Load

![Load model](../asset/load%20model.png)

Block `Load` (library `Passives/Load`), struct `Load`. The resistance is driven as a signal: the top level computes `Load.Vout1² / Load.Pout` and sends it to the load through the `Load` Goto tag.

| Config | Model |
|---|---|
| 1 | Resistive Simple (used) |
| 2 | Parallel Resistive |
| 3 | RL Var Parallel |
| 4 | RL Var Series |
| 5 | Var R |

The library block `Passives/Load` itself has three configurations: `1` RL, `2` RL Parallel and `3` R. Configuration 3 is a variable resistor without inductor (controlled current source i = v / R); it is used by the `rtbox` mode because PLECS Coder does not accept the variable resistor with series inductor ([rtbox.md](rtbox.md)).
| 6 | Var I |
| 7 | Short |
| 8 | Open |

| Key | Value | Meaning |
|---|---|---|
| `Pout` | 1 kW | load power (swept as `Pout`) |
| `Vout1` / `Vout2` | 400 V | load voltage before / after the step |
| `R` | Vref² / Pout = 160 Ω | load resistance (recomputed by `Derived.update()` in `calc.py`) |
| `L` | 10 µH | load inductance |
| `CL` | 0 | load capacitance |
| `t_switch` | tSim − load_tflip | load step time (0.2 s with TSIM = 0.4 s) |
| `t_dead` | t_switch / 2 | dead time of the load switching |

> [!NOTE]
> Keep `L > 0` with configs 3/4: with `L = 0` the RL loads make PLECS stop with "inductance/capacitance matrix appears to be singular".
