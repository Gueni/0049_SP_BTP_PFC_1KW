#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?                  __          _                __
#?             ____/ /__  _____(_)   _____  ____/ /
#?            / __  / _ \/ ___/ / | / / _ \/ __  /
#?           / /_/ /  __/ /  / /| |/ /  __/ /_/ /
#?           \__,_/\___/_/  /_/ |___/\___/\__,_/
#?
#?
#? Name:        derived.py
#? Purpose:     Parameters of the simulated system (here the 1 kW TPB PFC) computed from other parameters.
#?              Derived.update(mv) is called on every sweep point after the swept values are written, so the
#?              derived values follow the sweep. System specific, like parameters.py and sweep.py; optional
#?              (a system without derived parameters has no derived.py).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     10/19/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import   numpy       as       np
#?----------------------------------------------------------------------------------------------------------------------------------------
class Derived:
    """Parameters computed from other ones; update() is called on every sweep point after the swept values are set."""

    @staticmethod
    def update(mdlvar):
        """Recompute the parameters derived from other ones (same formulas as in parameters.py), after a sweep changed the base values."""
        Choke, DC, Ctrl, Ld        = mdlvar['PFC']['Choke'], mdlvar['DCLink'], mdlvar['CTRL'], mdlvar['Load']
        DC['Vinit']                = -2**0.5 * mdlvar['Grid']['Vin']
        Ctrl['L_boost']            = Choke['L1'] + Choke['L2'] - 2 * Choke['Lm']
        Ctrl['C_out']              = mdlvar['PFC']['Cout'] + DC['Cap_s'] * DC['Npara'] / DC['Nseri']
        Ctrl['fc_i']               = Ctrl['fsw'] / 10
        Ctrl['Kp_i']               = 2 * np.pi * Ctrl['fc_i'] * Ctrl['L_boost']
        Ctrl['Ki_i']               = (2 * np.pi * Ctrl['fc_i'])**2 / 10 * Ctrl['L_boost']
        Ctrl['Kp_v']               = 2 * np.pi * Ctrl['fc_v'] * Ctrl['C_out'] * Ctrl['Vref']
        Ctrl['Ki_v']               = (2 * np.pi * Ctrl['fc_v'])**2 / 2 * Ctrl['C_out'] * Ctrl['Vref']
        Ld['R']                    = Ctrl['Vref']**2 / Ld['Pout']
        Ctrl['t_car']              = 15 / 16 / Ctrl['fsw']                                  # carrier delay: ADC samples Ts/16 after the valley
        if 'MCU' in mdlvar:
            mdlvar['MCU']['ADC']['Ts']  = 1 / Ctrl['fsw']                                     # ADC samples once per PWM period
        return mdlvar
#?----------------------------------------------------------------------------------------------------------------------------------------
