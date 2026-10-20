# PFC stage

![Totem-pole PFC stage](../asset/PFC_stage.png)

Block `PFC` (library `Power/PFC`), struct `PFC`. Configurations: `1 TPB` (used), `2 PFC`, `3 PFC D`, `4 Pass`.

The boost choke sits between the AC input and the switch node of the **fast leg** (HS1/LS1, PWM at fsw). The **slow leg** (HS2/LS2) switches at line frequency and connects the other AC line to the DC rails according to the line polarity, replacing the diode bridge. `Cout` is the high-frequency decoupling capacitor on the DC bus.

Gate signals for HS3/LS3 exist for other configurations and stay off in `TPB`.

| Key | Value | Meaning |
|---|---|---|
| `Config` | 1 | TPB (also selects the `PFC CTRL` configuration) |
| `Choke` | see below | boost choke |
| `Cout` | 10 µF | DC-bus HF decoupling |
| `SW` | copy of `Switches[PFC_SWITCH]` | the six switches, see [switches.md](switches.md) |

The dead time (300 ns, `CTRL.T_dt`) is applied by the controller.

## Boost choke

![PFC choke](../asset/PFC_Choke.png)

| Key | Value |
|---|---|
| `L1` / `L2` | 240 µH / 10 µH |
| `Lm` | 1 µH |
| `R1`, `R2` / `Rm` | 10 mΩ / 1 mΩ |

The current loop sees `L_boost = L1 + L2 − 2·Lm` = **248 µH**. That gives a 5.0 A p-p ripple at 85 Vrms and 80 kHz: 30 % of the 16.6 A line peak.

`L_boost` is recomputed by `derived.py`, so sweeping `L1` retunes the current loop ([control.md](control.md#tuning)).

## Coupled inductors

![Coupled inductor model](../asset/EMI_CMC_DMC.png)

The CMC, the DMC and the boost choke all use the `Magnatic Components/Choke` block. It is a two-winding mutual inductance with:
- self inductances `L1`/`L2`;
- mutual inductance `Lm`;
- winding resistances `R1`/`R2` and mutual resistance `Rm`;
- initial currents `i1`/`i2`.

Each winding sees a leakage inductance of `L − Lm`.
