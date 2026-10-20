# EMI filter

![EMI filter, 1PH configuration](../asset/EMI_Filter.png)

Block `EMI FILTER` (library `Power/EMI FILTER`), struct `AC_Filter`. Configurations: `1 = 1PH` (used), `2 = 3PH`, `3 = Pass`.

It is a two-stage differential-mode (DM) filter with a common-mode choke:

```
CMC → Cx, Cy1/Cy2 to PE → L1/L5 (Ll) → DMC → Cx1 ∥ (Rd + Cd) → PFC
```

## Parts

| Part | Value | Part type |
|---|---|---|
| CMC | 4.7 mH per winding, k = 0.995, 30 mΩ | nanocrystalline, 10 A; its 23.5 µH leakage per winding is the stage-1 DM inductance |
| DMC | 120 µH per winding, uncoupled, 25 mΩ | powder core, 10 A |
| L1, L5 (`Ll`) | 2 µH | wiring between the stages |
| Cx (grid side), Cx1 (PFC side) | 1 µF each, 10 mΩ / 10 nH | X2 film, 310 VAC |
| Rd + Cd across Cx1 | 10 Ω + 4 µF | parallel RC damper of stage 2: n = Cd / Cx1 = 4, Rd ≈ 0.6·√(L / Cx1) |
| Cy1, Cy2 | 2.2 nF each, 0.2 Ω / 5 nH | Y1 ceramic, leakage 0.18 mA at 265 V |

## Design figures

| Figure | Value |
|---|---|
| Stage 1 (47 µH, Cx) | ≈ 23 kHz |
| Stage 2 (244 µH, Cx1) | ≈ 10 kHz, characteristic impedance 15.6 Ω, damped by Rd + Cd |
| DM attenuation at 2·fsw = 160 kHz | ≈ 80 dB |

## Capacitor model

Cx, Cx1, Cy1 and Cy2 are separate `Passives/C` structs, each with its own `Config`:

| Config | Model |
|---|---|
| 1 | C + ESR + ESL (current setting) |
| 2 | Ideal C (faster simulation; damping then comes only from Rd + Cd) |
| 3 | Pass (capacitor removed) |

`Resr_s` and `Lesl_s` are only used with config 1.

## Chokes

The CMC and the DMC use the coupled-inductor block, see [pfc_stage.md](pfc_stage.md#coupled-inductors).
