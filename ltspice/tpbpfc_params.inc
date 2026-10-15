* =========================================================================
* 1 kW Totem-Pole Bridgeless PFC (single leg, non-interleaved)
* LTspice parameters -- mirror of plecs/tpbpfc_init.m
* Use in a schematic with:  .include tpbpfc_params.inc
* Keep in sync with the PLECS init script.
* =========================================================================

* ---- Specifications ----
.param Po=1000 Vo=400
.param Vin_min=85 Vin_nom=230 Vin_max=265 f_line=50
.param eta=0.97 ripple_iL=0.30 dVo_pp={0.05*Vo}
.param t_hold=10m Vo_hold=300

* ---- AC source ----
.param Vin={Vin_nom} Rsrc=0.1

* ---- EMI filter ----
.param Rf=10m Cx=1u Cy=2.2n Rbleed=470k Lcm=5m Llk=20u

* ---- Power stage ----
.param fsw=65k Tsw={1/fsw} t_dead=100n
.param Iin_pk={sqrt(2)*Po/(eta*Vin_min)}
.param dIL={ripple_iL*Iin_pk}
.param L={Vo/(4*fsw*dIL)} RL=50m
.param Co_ripple={Po/(2*pi*f_line*Vo*dVo_pp)}
.param Co_hold={2*Po*t_hold/(Vo**2-Vo_hold**2)}
.param Co={max(Co_ripple,Co_hold)} Co_esr=50m
.param Rload={Vo**2/Po}
