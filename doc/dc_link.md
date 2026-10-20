# DC link

![DC-link capacitor model](../asset/DCLINK%20cap%20model.png)

Block `CDC` (library `Passives/C`), struct `DCLink`.

| Config | Model |
|---|---|
| 1 | C + ESR + ESL (used) |
| 2 | Ideal C |
| 3 | Pass |

| Key | Value | Meaning |
|---|---|---|
| `Cap_s` | 47 µF | one capacitor (swept as `Cdc`) |
| `Npara` / `Nseri` | 10 / 1 | bank: 10 in parallel → 470 µF |
| `Resr_s` | 50 mΩ | ESR of one capacitor |
| `Lesl_s` | 20 nH | ESL of one capacitor |
| `Vinit` | −√2·Vin | pre-charged to the line peak (inrush bypass assumed). The sign is negative because CDC is placed flipped. |

Together with `PFC.Cout` (10 µF), the voltage loop sees `C_out` = 480 µF ([control.md](control.md#tuning)).

| Figure | Value |
|---|---|
| 100 Hz ripple at 1 kW | ≈ 16.6 V p-p (4.1 %) |
| Hold-up from 400 V to 300 V at 1 kW | ≈ 16.8 ms |
