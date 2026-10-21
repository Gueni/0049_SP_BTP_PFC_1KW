# Control

![PFC controller](../asset/ctrl.png)

The controller is the `PFC CTRL` configurable subsystem inside the `MCU` block. It is selected with the same index as the power stage (`PFC.Config`), so configuration 1 runs the **TPB PFC** controller: **average current mode control** of a non-interleaved totem-pole PFC.

There is a second configuration, `Interleaved`, which this design does not use.

## Inputs and output

| Port | Signal | Unit |
|---|---|---|
| `Vac` | AC voltage at the PFC terminals, as the firmware sees it (ADC → scaling) | V |
| `Vdc` | DC-link voltage, as the firmware sees it | V |
| `Iin` | Inductor (input) current, as the firmware sees it | A |
| `g_PFC` | Gate vector `[HS1, LS1, HS2, LS2, HS3, LS3]` to the power stage | 0/1 |

All three inputs come from the measurement chain ([measurement.md](measurement.md)), so sensor bandwidth, ADC sampling and quantization, and calibration errors are all inside the loops.

## Signal flow

```
                    soft start                     voltage loop
 t ──► Vref* = min(√2·Vin + ramp·t, Vref) ──►(+)──► LPF 20 Hz ──► PI_v ──► P* ∈ (−∞, Pmax]
                                     Vdc ───►(−)                              │
                                                                              ▼
 vac ──► |vac| ─────────────────────────────────────────────────► Iref = P*·|vac| / Vrms²  ≤ Ipk_max
 vac ──► RMS (fs = Grid.f) ──► Vrms ────────────────────────────►          │
                                                                           ▼  (× enable)
 Iin ──► × sign(vac) ──► |iL| ──────────────────────────────────────────►(−)(+)
                                                                           │
                                                                     current loop
                                                                           ▼
                                                     PI_i ──► uL* ∈ [−uL_max, uL_max]
                                                                           │
 Vdc (≥ Vdc_min), |vac| ──────────────► D = (Vdc − |vac| + uL*) / Vdc ∈ [0, Dmax]
                                                                           │
 sign(vac) ──────────────────────────► D_HS1 = 0.5 + sign·(0.5 − D) ──► PWM vs carrier
                                                                           │
                       zero-crossing blanking, enable, polarity, 300 ns dead time
                                                                           ▼
                                                                         g_PFC
```

## 1. Enable

The controller is held off for the first `CTRL.t_en` (1 ms) while the sensor filters and the first ADC samples settle:

- `Enable = t > t_en`;
- every gate is ANDed with `Enable`;
- the current reference is multiplied by `Enable`, so `Iref = 0` before it.

## 2. Soft start

The DC link is pre-charged to the line peak (`DCLink.Vinit = √2·Vin`). The voltage reference starts there and ramps to the target:

```
Vref* = clamp( √2·Grid.Vin + (CTRL.Vref − √2·Grid.Vin) / CTRL.t_ss · t , 0 , CTRL.Vref )
```

With `t_ss` = 50 ms, the output reaches 400 V about 51 ms after start and is settled after about 75 ms.

## 3. Voltage loop (outer)

| Step | Block | Detail |
|---|---|---|
| Error | `Sum Ev` | `ev = Vref* − Vdc` |
| Ripple filter | `Ev LPF` | first-order low pass at `f_lpf_v` = 20 Hz; attenuates the 100 Hz (2·f_line) ripple, so the power command, and with it the current reference, stays undistorted |
| PI | `Kp_v`, `Ki_v`, `Int_v` | integrator starts at `P0` = 0 and is clamped to `Pmax` (anti-windup) |
| Limit | `P*` | power command, upper limit `Pmax` = 1.5 kW |

The output `P*` is a **power** command in W, not a current amplitude, so the loop gain does not depend on the line voltage.

## 4. Current reference

```
Iref = P* · |vac| / Vrms²        (Function block "Iref", limited to Ipk_max)
```

- `Vrms` comes from a `RMS Value` block at the line frequency, initialised to `Grid.Vin`.
- `P*/Vrms²` is the input conductance, so `Iref` is a rectified sine in phase with the line. Its RMS value is `P*/Vrms`.
- `Ipk_max = 2·Pmax / (√2·85 V)` ≈ 25 A, the peak current at 1.5 kW and the minimum line voltage.

## 5. Current loop (inner)

| Step | Block | Detail |
|---|---|---|
| Rectified current | `Sign`, `Irect` | `sign(vac) = vac / (|vac| + eps_s)` (smooth sign, `eps_s` = 0.1 V); `|iL| = Iin · sign(vac)` |
| Error | `Sum Ei` | `ei = Iref − |iL|` |
| PI | `Kp_i`, `Ki_i`, `Int_i` | output is the inductor-voltage command `uL*`; integrator clamped to ±`uL_max` |
| Limit | `uL*` | ±`uL_max` = ±400 V |

## 6. Duty feed-forward

The boost relation `vL = |vac| − (1 − D)·Vdc`, solved for the duty of the active switch, gives:

```
D = (Vdc − |vac| + uL*) / Vdc        Vdc clamped to ≥ Vdc_min (50 V), D clamped to [0, Dmax = 0.98]
```

The feed-forward term `1 − |vac|/Vdc` already provides nearly the whole duty. The PI only supplies the inductor voltage `uL*`. This keeps the zero-crossing distortion low and the loop gain constant over the line cycle.

## 7. PWM and leg mapping

| Item | Detail |
|---|---|
| Carrier | triangle 0…1 at `fsw` = 80 kHz, delayed by `t_car` = 15/16·Ts. With `MCU.ADC.Toffs = 0` the ADC then samples Ts/16 after the valley, which compensates the delay of the current sensor, so the sample is close to the average inductor current. |
| Fast leg | `D_HS1 = 0.5 + sign(vac)·(0.5 − D)`. In one half-cycle LS1 is the boost switch (HS1 = 1 − D, synchronous rectifier). In the other half-cycle the roles swap (HS1 = D). LS1 is the complement of HS1. |
| Slow leg | HS2 / LS2 follow the line polarity (`Pos`: vac > 0, `Neg`: vac < 0); each conducts for one half-cycle at 50 Hz. |
| Zero crossing | `ZC ok = |vac| > Vzc` (20 V); all four gates are blanked below it, so no switch shoots through while the polarity changes. |
| Dead time | a 300 ns (`T_dt`) turn-on delay on every gate. |
| HS3 / LS3 | held at 0 (used only by other power-stage configurations). |

## Tuning

The gains are computed in [vars.py](../lib/vars.py) and recomputed by `Derived.update()` in [calc.py](../lib/calc.py) on every sweep point, so they follow swept values of L, C, fsw and Vref.

| Loop | Plant | Crossover | Kp | Ki (PI zero) |
|---|---|---|---|---|
| Current | `1 / (s·L_boost)` | `fc_i = fsw / 10` = 8 kHz | `2π·fc_i·L_boost` = 12.47 V/A | `(2π·fc_i)²/10 · L_boost` = 62.7 kV/(A·s), zero at fc_i/10 |
| Voltage | `1 / (s·C_out·Vref)` (power → voltage) | `fc_v` = 10 Hz | `2π·fc_v·C_out·Vref` = 12.06 W/V | `(2π·fc_v)²/2 · C_out·Vref` = 379 W/(V·s), zero at fc_v/2 |

with:
- `L_boost = L1 + L2 − 2·Lm` = 248 µH (boost choke, see [pfc_stage.md](pfc_stage.md));
- `C_out = PFC.Cout + DCLink.Cap_s · Npara / Nseri` = 480 µF.

Rules of thumb:
- **Current loop:** keep `fc_i` ≤ fsw/10. The ADC samples once per period, and the sampling and PWM delay eat phase margin quickly above that.
- **Voltage loop:** keep `fc_v` well below 2·f_line (100 Hz), or the 100 Hz ripple enters the current reference as third-harmonic distortion. The 20 Hz LPF adds phase lag: if you raise `fc_v`, raise `f_lpf_v` with it.
- **Derived values:** `Derived.update()` also sets `t_car = 15/16/fsw` and `MCU.ADC.Ts = 1/fsw` when fsw changes.

## Parameters (`CTRL`)

| Key | Value | Meaning |
|---|---|---|
| `Vref` | 400 V | DC-link voltage reference |
| `fsw` | 80 kHz | fast-leg PWM frequency |
| `T_dt` | 300 ns | dead time |
| `fc_i`, `Kp_i`, `Ki_i` | derived | current PI |
| `uL_max` | 400 V | current PI output limit |
| `fc_v`, `Kp_v`, `Ki_v` | derived | voltage PI |
| `f_lpf_v` | 20 Hz | voltage-error low pass |
| `Pmax` | 1.5 kW | power command limit |
| `Ipk_max` | 25 A | current reference limit |
| `Vdc_min` | 50 V | lower clamp of Vdc in the feed-forward |
| `Dmax` | 0.98 | maximum duty |
| `Vzc` | 20 V | zero-crossing blanking threshold |
| `eps_s` | 0.1 V | smoothing of sign(vac) |
| `t_ss` | 50 ms | soft-start ramp |
| `t_en` | 1 ms | controller enable delay |
| `P0` | 0 W | initial voltage-integrator state |
| `t_car` | 11.7 µs | carrier delay |

The older entries at the top of `CTRL` (`Vmax`, `Imax`, `Rmax`, `f_Vloop`, `BW_Vloop`, `IBW_Vloop`, `f_Iloop`, `BW_Iloop`, `IBW_Iloop`, `Ra`, `Rsa`, `Ga`, `Gsa`, `fs`, `Ri_*`, `Rv_*`, `Pout`) are not referenced by the model.
