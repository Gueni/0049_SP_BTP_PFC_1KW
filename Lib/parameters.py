#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?              __  ___          __     __   ____
#?             /  |/  /___  ____/ /__  / /  / __ \____ __________ _____ ___  _____
#?            / /|_/ / __ \/ __  / _ \/ /  / /_/ / __ `/ ___/ __ `/ __ `__ \/ ___/
#?           / /  / / /_/ / /_/ /  __/ /  / ____/ /_/ / /  / /_/ / / / / / (__  )
#?          /_/  /_/\____/\__,_/\___/_/  /_/    \__,_/_/   \__,_/_/ /_/ /_/____/
#?
#?
#? Name:        parameters.py
#? Purpose:     Everything specific to the simulated system (here the 1 kW TPB PFC): model paths, parameters,
#?              derived parameters, result waveforms. For another system (LLC, OBC, DC-DC ...) copy this file and
#?              edit it; the library files (pplecs, pplots, plog, pmath, rtbox) do not change.
#?
#?              Required : MODEL_NAME, MODEL_PATH, DATA_DIR, ModelVars (with a 'ToFile' struct read by the model's
#?                         To File block), Waveforms ({name: unit} of the result CSV columns after time, in order).
#?              Optional : MODEL_IMG_PATH (image on top of the HTML report), F0_PATH (key path of the fundamental
#?                         frequency in ModelVars, None = no harmonic plots), F0_OVERRIDES (waveform name keyword ->
#?                         key path of that waveform's own fundamental, e.g. the switching frequency),
#?                         parameters after the sweep changed base values), SolverOpts, AnalysisOpts.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/15/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import   copy
from     pathlib     import   Path
import   numpy       as       np
#!----------------------------------------------------------------------------------------------------------------------------------------
#! All paths are resolved from this file's location, so the scripts work from any working directory.
LIB_DIR        =  Path(__file__).resolve().parent                    # <repo>/Lib
ROOT_DIR       =  LIB_DIR.parent                                     # <repo>
MODEL_NAME     =  "PFC"                                              # pfc model name (without .plecs extension) 
MODEL_PATH     =  ROOT_DIR / "Model" / f"{MODEL_NAME}.plecs"         
MODEL_IMG_PATH =  ROOT_DIR / "asset" / "schematic.png"
DATA_DIR       =  ROOT_DIR / "data"                                  # results: data/timeseries, data/mat, data/html, data/log, data/traces
F0_PATH        =  ('Grid', 'f')                                      # fundamental of the harmonic plots (None = no harmonic plots)
F0_OVERRIDES   =  {                                                  # waveform name keyword -> its own fundamental (first match wins)
                              'HS1'   : ('CTRL', 'fsw'),                        # fast leg switches at fsw
                              'LS1'   : ('CTRL', 'fsw'),
                             }
TSIM           = 1                                                  # simulation time [s]
TSAVE          = TSIM - 0.02                                               # time point at which the data is saved [s]
#!----------------------------------------------------------------------------------------------------------------------------------------
Sim_param 	   =  {                                                                                            
                  'tSim'	    	   : TSIM,                                                                                                               #? [s]     - Total simulation time
                  'load_tflip'	   : TSIM/2,                                                                                                             #? [s]     - Time at which the load changes state 
                  'maxStep'		   : 1e-3,                                                                                                              #? [s]     - Maximum simulation time step
                  'ZeroCross'       : 1000,                                                                                                              #? [/]     - Zero-crossing detection limit
                  'rel_tol'		   : 1e-3                                                                                                               #? [/]     - Relative tolerance for the numerical solver (PLECS default; 1e-7 was ~4x slower for < 0.02 % difference)
               }
Configs        =  {
                  'Grid'            : 1,                                                                                                                 #? [/]      - Config of the Grid.
                  'AC_Filter'       : 1,                                                                                                                 #? [/]      - Config of the AC filter (1 = 1PH, 2 = 3PH, 3 = Pass).
                  'PFC'             : 1,                                                                                                                 #? [/]      - Config of the PFC (1 TPB, 2 PFC, 3 PFC D, 4 Pass).
                  'DCLink'          : 2,                                                                                                                 #? [/]      - Config of the DCLink (2 = capacitor with ESR; 4 adds the ESL, a stiff 1 pH pole that slows the solver).
                  'Load'            : 1,                                                                                                                 #? [/]      - Config of the Load.
                  'Loadgen'         : 1                                                                                                                  #? [/]      - Config of the Load generator.

               }
ToFile         =  {                     
                  'Ts'              : 0,                                                                                                                 #? [s]     - Sampling time for saving data
                  'tsave' 	    	   : TSAVE,                                                                                                              #? [s]     - Time point at which the data is saved
               }
Grid           =  {                                                                                                                                          # EVSE / grid source
                  'Config'          : Configs['Grid'],                                                                                                   #? [/]     - Configuration setting for the grid
                  'Vin'             : 230,                                                                                                               #? [V]     - Input voltage of the grid
                  'Ts'              : 1/80e3,                                                                                                            #? [s]     - Sampling time for grid operations
                  'f'               : 50,                                                                                                                #? [Hz]    - Grid frequency
                  'phase'           : 0,                                                                                                                 #? [rad]   - Grid voltage phase angle
                  'R'               : 0.01                                                                                                               #? [Ohm]   - Grid resistance
               }
AC_Filter      =  {                                                                                                                                   # Power/EMI FILTER, 1PH: CMC -> Cx, Cy1/Cy2 -> L1/L5 (Ll) -> DMC -> Cx1 // (Rd + Cd) -> PFC
                                                                                                                                                     # two-stage DM filter: stage 1 = CMC leakage + Cx (~23 kHz), stage 2 = DMC + Ll + Cx1 (~10 kHz),
                                                                                                                                                     # ~80 dB DM attenuation at 2*fsw = 160 kHz; Rd + Cd = optimum parallel damping of stage 2 (n = Cd/Cx1 = 4)
                  'Config'        : Configs['AC_Filter'],                                                                                             #? [/]      - Configuration of the EMI filter (1 = 1PH, 2 = 3PH, 3 = Pass)
                  'Ll'            : 2e-6,                                                                                                             #? [H]      - Line / neutral series inductance L1, L5 (wiring between the two stages)
                  'CMC'           : {                                                                                                                 # common-mode choke, 2 coupled windings (nanocrystalline, 10 A)
                     'L1'         : 4.7e-3,                                                                                                           #? [H]      - Self inductance of winding 1 (CMC 4.7 mH; leakage 23.5 uH per winding = stage-1 DM inductance)
                     'L2'         : 4.7e-3,                                                                                                           #? [H]      - Self inductance of winding 2 (CMC 4.7 mH; leakage 23.5 uH per winding = stage-1 DM inductance)
                     'R1'         : 30e-3,                                                                                                            #? [Ohm]    - DC resistance of winding 1
                     'R2'         : 30e-3,                                                                                                            #? [Ohm]    - DC resistance of winding 2
                     'Lm'         : 0.995 * 4.7e-3,                                                                                                   #? [H]      - Mutual inductance (coupling k = 0.995; leakage L - Lm per winding)
                     'Rm'         : 0,                                                                                                                #? [Ohm]    - Mutual resistance
                     'i1'         : 0,                                                                                                                #? [A]      - Initial current in winding 1
                     'i2'         : 0                                                                                                                 #? [A]      - Initial current in winding 2
                  },
                  'DMC'           : {                                                                                                                 # differential-mode choke, 2 uncoupled windings (powder core, 10 A)
                     'L1'         : 120e-6,                                                                                                           #? [H]      - Self inductance of winding 1 (DM choke 120 uH)
                     'L2'         : 120e-6,                                                                                                           #? [H]      - Self inductance of winding 2 (DM choke 120 uH)
                     'R1'         : 25e-3,                                                                                                            #? [Ohm]    - DC resistance of winding 1
                     'R2'         : 25e-3,                                                                                                            #? [Ohm]    - DC resistance of winding 2
                     'Lm'         : 0,                                                                                                                #? [H]      - Mutual inductance (coupling k = 0; leakage L - Lm per winding)
                     'Rm'         : 0,                                                                                                                #? [Ohm]    - Mutual resistance
                     'i1'         : 0,                                                                                                                #? [A]      - Initial current in winding 1
                     'i2'         : 0                                                                                                                 #? [A]      - Initial current in winding 2
                  },
                  'Cx'            : {                                                                                                                 # X2 capacitor, grid side (Passives/C)
                     'Config'     : 1,                                                                                                                #? [/]      - 1 Ideal, 2 ESR, 3 ESL, 4 ESR+ESL, 5 Pass, 6 Short (ideal: damping is explicit, faster simulation)
                     'Cap_s'      : 1e-6,                                                                                                             #? [F]      - X2 film capacitance, 1 uF / 310 VAC
                     'Resr_s'     : 10e-3,                                                                                                            #? [Ohm]    - Equivalent series resistance (used with Config 2/4)
                     'Lesl_s'     : 10e-9,                                                                                                            #? [H]      - Equivalent series inductance (used with Config 3/4)
                     'Npara'      : 1,                                                                                                                #? [/]      - Number of parallel capacitors
                     'Nseri'      : 1,                                                                                                                #? [/]      - Number of series capacitors
                     'Vinit'      : 0,                                                                                                                #? [V]      - Initial voltage
                     'Iinit'      : 0                                                                                                                 #? [A]      - Initial current
                  },
                  'Cx1'           : {                                                                                                                 # X2 capacitor, PFC side (Passives/C)
                     'Config'     : 1,                                                                                                                #? [/]      - 1 Ideal, 2 ESR, 3 ESL, 4 ESR+ESL, 5 Pass, 6 Short (ideal: damping is explicit, faster simulation)
                     'Cap_s'      : 1e-6,                                                                                                             #? [F]      - X2 film capacitance, 1 uF / 310 VAC
                     'Resr_s'     : 10e-3,                                                                                                            #? [Ohm]    - Equivalent series resistance (used with Config 2/4)
                     'Lesl_s'     : 10e-9,                                                                                                            #? [H]      - Equivalent series inductance (used with Config 3/4)
                     'Npara'      : 1,                                                                                                                #? [/]      - Number of parallel capacitors
                     'Nseri'      : 1,                                                                                                                #? [/]      - Number of series capacitors
                     'Vinit'      : 0,                                                                                                                #? [V]      - Initial voltage
                     'Iinit'      : 0                                                                                                                 #? [A]      - Initial current
                  },
                  'Rd'            : 10,                                                                                                               #? [Ohm]    - Damping resistor in series with Cd across Cx1 (~0.6 * sqrt(L_stage2 / Cx1))
                  'Cd'            : 4e-6,                                                                                                             #? [F]      - Damping capacitor (n = Cd / Cx1 = 4), X2 film 4 uF
                  'Cy1'           : {                                                                                                                 # Y capacitor line -> PE (Passives/C)
                     'Config'     : 1,                                                                                                                #? [/]      - 1 Ideal, 2 ESR, 3 ESL, 4 ESR+ESL, 5 Pass, 6 Short (ideal: damping is explicit, faster simulation)
                     'Cap_s'      : 2.2e-9,                                                                                                           #? [F]      - Y1 ceramic capacitance, 2.2 nF (leakage < 0.2 mA at 265 V)
                     'Resr_s'     : 0.2,                                                                                                              #? [Ohm]    - Equivalent series resistance (used with Config 2/4)
                     'Lesl_s'     : 5e-9,                                                                                                             #? [H]      - Equivalent series inductance (used with Config 3/4)
                     'Npara'      : 1,                                                                                                                #? [/]      - Number of parallel capacitors
                     'Nseri'      : 1,                                                                                                                #? [/]      - Number of series capacitors
                     'Vinit'      : 0,                                                                                                                #? [V]      - Initial voltage
                     'Iinit'      : 0                                                                                                                 #? [A]      - Initial current
                  },
                  'Cy2'           : {                                                                                                                 # Y capacitor neutral -> PE (Passives/C)
                     'Config'     : 1,                                                                                                                #? [/]      - 1 Ideal, 2 ESR, 3 ESL, 4 ESR+ESL, 5 Pass, 6 Short (ideal: damping is explicit, faster simulation)
                     'Cap_s'      : 2.2e-9,                                                                                                           #? [F]      - Y1 ceramic capacitance, 2.2 nF (leakage < 0.2 mA at 265 V)
                     'Resr_s'     : 0.2,                                                                                                              #? [Ohm]    - Equivalent series resistance (used with Config 2/4)
                     'Lesl_s'     : 5e-9,                                                                                                             #? [H]      - Equivalent series inductance (used with Config 3/4)
                     'Npara'      : 1,                                                                                                                #? [/]      - Number of parallel capacitors
                     'Nseri'      : 1,                                                                                                                #? [/]      - Number of series capacitors
                     'Vinit'      : 0,                                                                                                                #? [V]      - Initial voltage
                     'Iinit'      : 0                                                                                                                 #? [A]      - Initial current
                  }
               }
#! Switch library: one entry per device of the PLECS Thermal Lib (/0000_libraries/Plecs/Thermal Lib).
#! PFC['SW'] takes a copy of the device selected by PFC_SWITCH.
Switches       =  {
                  'C3M0021120K'    : {                                                                                                                # Wolfspeed C3M0021120K, 1200 V / 100 A / 21 mOhm SiC MOSFET (selected)
                     'Config'         : 2,                                                                                                            #? [/]      - FET config: 1 Real SW, 2 Real SW + separate body diode, 3 Ideal, 4 Pass, 5 Short
                     'therm_mosfet'   : 'file:C3M0021120K',                                                                                           #? [/]      - Thermal description of the switch (Thermal Lib)
                     'Rgon'           : 2.5,                                                                                                          #? [Ohm]    - External turn-on gate resistance
                     'Rgoff'          : 2.5,                                                                                                          #? [Ohm]    - External turn-off gate resistance
                     'ron_mosfet'     : 21e-3,                                                                                                        #? [Ohm]    - R_DS(on) at 25 °C (C3M0021120K: 21 mOhm typ, 1200 V / 100 A)
                     'Iinit'          : 0,                                                                                                            #? [A]      - Initial current through the switch
                     'Coss'           : {                                                                                                             # output capacitance (Passives/C)
                        'Config'  : 5,                                                                                                                #? [/]      - 1 Ideal, 2 ESR, 3 ESL, 4 ESR+ESL, 5 Pass (Coss off), 6 Short
                        'Cap_s'   : 180e-12,                                                                                                          #? [F]      - Coss at 800 V (C3M0021120K: 180 pF)
                        'Resr_s'  : 1e-12,                                                                                                            #? [Ohm]    - Equivalent series resistance
                        'Lesl_s'  : 1e-12,                                                                                                            #? [H]      - Equivalent series inductance
                        'Npara'   : 1,                                                                                                                #? [/]      - Number of parallel capacitors
                        'Nseri'   : 1,                                                                                                                #? [/]      - Number of series capacitors
                        'Vinit'   : 0,                                                                                                                #? [V]      - Initial voltage
                        'Iinit'   : 0                                                                                                                 #? [A]      - Initial current
                     },
                     'therm_body_diode': 'file:C3M0021120K_bodydiode',                                                                                #? [/]      - Thermal description of the body diode (Config 2)
                     'ron_body_diode' : 5e-3,                                                                                                         #? [Ohm]    - Body diode on-state resistance (Config 2)
                     'Rdb_off'        : 0,                                                                                                            #? [Ohm]    - Body diode off-state resistance
                     'vf_body_diode'  : 4.5,                                                                                                          #? [V]      - Body diode forward voltage
                     'nPara'          : 1,                                                                                                            #? [/]      - Number of parallel switches
                     'T_init'         : 25,                                                                                                           #? [°C]     - Initial junction temperature
                     'Tamb'           : 25,                                                                                                           #? [°C]     - Ambient temperature
                     't_init'         : 25,                                                                                                           #? [°C]     - Initial temperature of the thermal chain
                     'rth_sw'         : 0.1,                                                                                                          #? [K/W]    - Thermal resistance junction -> case
                     'rth_ch'         : 0.1,                                                                                                          #? [K/W]    - Thermal resistance case -> heatsink (TIM)
                     'Rth'            : 0.2                                                                                                           #? [K/W]    - Total thermal resistance junction -> heatsink
                  },
           
                  'C3M0015065K'    : {                                                                                                                # Wolfspeed C3M0015065K, 650 V / 120 A / 15 mOhm SiC MOSFET (650 V option)
                     'Config'         : 2,                                                                                                            #? [/]      - FET config: 1 Real SW, 2 Real SW + separate body diode, 3 Ideal, 4 Pass, 5 Short
                     'therm_mosfet'   : 'file:C3M0015065K',                                                                                           #? [/]      - Thermal description of the switch (Thermal Lib)
                     'Rgon'           : 2.5,                                                                                                          #? [Ohm]    - External turn-on gate resistance
                     'Rgoff'          : 2.5,                                                                                                          #? [Ohm]    - External turn-off gate resistance
                     'ron_mosfet'     : 15e-3,                                                                                                        #? [Ohm]    - R_DS(on) at 25 °C (C3M0015065K: 15 mOhm typ, 650 V / 120 A)
                     'Iinit'          : 0,                                                                                                            #? [A]      - Initial current through the switch
                     'Coss'           : {                                                                                                             # output capacitance (Passives/C)
                        'Config'  : 5,                                                                                                                #? [/]      - 1 Ideal, 2 ESR, 3 ESL, 4 ESR+ESL, 5 Pass (Coss off), 6 Short
                        'Cap_s'   : 289e-12,                                                                                                          #? [F]      - Coss at 400 V (C3M0015065K: 289 pF)
                        'Resr_s'  : 1e-12,                                                                                                            #? [Ohm]    - Equivalent series resistance
                        'Lesl_s'  : 1e-12,                                                                                                            #? [H]      - Equivalent series inductance
                        'Npara'   : 1,                                                                                                                #? [/]      - Number of parallel capacitors
                        'Nseri'   : 1,                                                                                                                #? [/]      - Number of series capacitors
                        'Vinit'   : 0,                                                                                                                #? [V]      - Initial voltage
                        'Iinit'   : 0                                                                                                                 #? [A]      - Initial current
                     },
                     'therm_body_diode': 'file:C3M0015065K_bodydiode',                                                                                #? [/]      - Thermal description of the body diode (Config 2)
                     'ron_body_diode' : 5e-3,                                                                                                         #? [Ohm]    - Body diode on-state resistance (Config 2)
                     'Rdb_off'        : 0,                                                                                                            #? [Ohm]    - Body diode off-state resistance
                     'vf_body_diode'  : 4.5,                                                                                                          #? [V]      - Body diode forward voltage
                     'nPara'          : 1,                                                                                                            #? [/]      - Number of parallel switches
                     'T_init'         : 25,                                                                                                           #? [°C]     - Initial junction temperature
                     'Tamb'           : 25,                                                                                                           #? [°C]     - Ambient temperature
                     't_init'         : 25,                                                                                                           #? [°C]     - Initial temperature of the thermal chain
                     'rth_sw'         : 0.1,                                                                                                          #? [K/W]    - Thermal resistance junction -> case
                     'rth_ch'         : 0.1,                                                                                                          #? [K/W]    - Thermal resistance case -> heatsink (TIM)
                     'Rth'            : 0.2                                                                                                           #? [K/W]    - Total thermal resistance junction -> heatsink
                  }
               }
PFC_SWITCH     = 'C3M0021120K'                                                                                                                           # device of Switches used by the PFC stage
PFC            =  {
                  'Config'          : Configs['PFC'],                                                                                                    #? [/]      - Diode thermal description
                  'Choke'           : {
                     'Config'       : 1,                                                                                                                 #? [/]      - Diode thermal description
                     'L1'           : 240e-6,                                                                                                            #? [H]      - Inductance of the first choke winding (boost inductor; L_boost = 248 uH -> ~30 % p-p ripple at 85 Vrms, 80 kHz)
                     'L2'           : 10e-6,                                                                                                             #? [H]      - Inductance of the second choke winding
                     'R1'           : 0.01,                                                                                                              #? [Ohm]    - Resistance of the first choke winding
                     'R2'           : 0.01,                                                                                                              #? [Ohm]    - Resistance of the second choke winding
                     'Lm'           : 1e-6,                                                                                                              #? [H]      - Mutual inductance of the choke
                     'Rm'           : 0.001,                                                                                                             #? [Ohm]    - Resistance of the mutual inductance
                     'i1'           : 0,                                                                                                                 #? [A]      - Initial current in the first choke winding
                     'i2'           : 0                                                                                                                  #? [A]      - Initial current in the second choke winding
                  },
                  'Cout'            : 10e-6,                                                                                                             #? [F]      - PFC output (HF decoupling) capacitance
                  'SW'              : copy.deepcopy(Switches[PFC_SWITCH])                                                                             # selected switch (see Switches / PFC_SWITCH)
               }
DCLink         =  {                                                                                             
                      'Config'		   : Configs['DCLink'],                                                                                              #? [/]      - Capacitance configuration
                      'Cap_s'    		: 47e-6,                                                                                                         #? [F]      - Capacitance value 
                      'Resr_s'		   : 50e-3,                                                                                                          #? [Ohm]    - Equivalent series resistance of the capacitance
                      'Lesl_s'		   : 1e-12,                                                                                                          #? [H]      - Equivalent series inductance of the capacitance
                      'Npara'		      : 10,                                                                                                              #? [/]      - Number of parallel capacitors
                      'Nseri'		      : 1,                                                                                                              #? [/]      - Number of series capacitors
                      'Vinit'		      : -2**0.5 * Grid['Vin'],                                                                                          #? [V]      - Initial voltage: line peak, inrush bypass assumed (negative: CDC is placed flipped)
                      'Iinit'		      : 0                                                                                                               #? [A]      - Initial current through the capacitance   
                     }
CTRL           =  {
                     'Vmax'                  : 440.0,                                                                                                    #? [V]     - Maximum voltage
                     'Imax'                  : 12.54,                                                                                                    #? [A]     - Maximum current
                     'Rmax'                  : 440.0 / 12.54,                                                                                            #? [Ohm]   - Maximum load impedance (Rmax = Vmax / Imax)
                     'f_Vloop'               : 2e3,                                                                                                      #? [Hz]    - Voltage control loop frequency
                     'BW_Vloop'              : 20,                                                                                                       #? [Hz]    - Voltage loop bandwidth
                     'IBW_Vloop'             : 12.5,                                                                                                     #? [Hz]    - Integral bandwidth for voltage loop
                     'f_Iloop'               : 50e3,                                                                                                     #? [Hz]    - Current control loop frequency
                     'BW_Iloop'              : 4e3,                                                                                                      #? [Hz]    - Current loop bandwidth
                     'IBW_Iloop'             : 1e3,                                                                                                      #? [Hz]    - Integral bandwidth for current loop
                     'Ra'                    : 2 * np.pi * 700e-6 * 4e3,                                                                                 #? [Ohm]   - Current compensator resistance (Ra = 2*pi*L*BW_Iloop)
                     'Rsa'                   : 2 * np.pi * (2 * np.pi * 700e-6 * 4e3) * 1e3,                                                             #? [Ohm]   - Current compensator series resistance (Rsa = 2*pi*Ra*IBW_Iloop)
                     'Ga'                    : 2 * np.pi * 360e-6 * 20,                                                                                  #? [S]     - Voltage compensator gain (Ga = 2*pi*C*BW_Vloop)
                     'Gsa'                   : 2 * np.pi * (2 * np.pi * 360e-6 * 20) * 12.5,                                                             #? [S]     - Voltage compensator series gain (Gsa = 2*pi*Ga*IBW_Vloop)
                     
                     'Vref'                  : 400,                                                                                                      #? [V]      - Reference voltage
                     'Pout'                  : 1e3,                                                                                                      #? [W]      - Rated output power
                     'T_dt'                  : 300e-9,                                                                                                   #? [s]      - Dead time
                     'fs'                    : 100e-3,                                                                                                   #? [Hz]     - Switching frequency
                     'Ri_Kp'                 : 0.1,                                                                                                      #? [/]      - Proportional gain for current control
                     'Ri_Ki'                 : 600,                                                                                                      #? [/]      - Integral gain for current control
                     'Rv_Kp'                 : 5,                                                                                                        #? [/]      - Proportional gain for voltage control
                     'Rv_Ki'                 : 800,                                                                                                      #? [/]      - Integral gain for voltage control
                   
                     #! TPB PFC controller (PFC CTRL configuration 'TPB PFC')
                     'fsw'                   : 80e3,                                                                                                     #? [Hz]    - Fast-leg PWM (carrier) frequency
                     'L_boost'               : PFC['Choke']['L1'] + PFC['Choke']['L2'] - 2 * PFC['Choke']['Lm'],                                         #? [H]     - Effective boost inductance seen by the current loop
                     'C_out'                 : PFC['Cout'] + DCLink['Cap_s'] * DCLink['Npara'] / DCLink['Nseri'],                                        #? [F]     - Total DC-link capacitance seen by the voltage loop
                     'fc_i'                  : 80e3/10,                                                                                                  #? [Hz]    - Current loop crossover frequency
                     'Kp_i'                  : 2 * np.pi * 80e3/10 * (PFC['Choke']['L1'] + PFC['Choke']['L2'] - 2 * PFC['Choke']['Lm']),                 #? [V/A]   - Current PI proportional gain (2*pi*fc_i*L_boost)
                     'Ki_i'                  : (2 * np.pi * 80e3/10)**2 / 10 * (PFC['Choke']['L1'] + PFC['Choke']['L2'] - 2 * PFC['Choke']['Lm']),       #? [V/As]  - Current PI integral gain (zero at fc_i/10)
                     'uL_max'                : 400,                                                                                                      #? [V]     - Current PI output (inductor voltage) limit
                     'fc_v'                  : 10,                                                                                                       #? [Hz]    - Voltage loop crossover frequency
                     'Kp_v'                  : 2 * np.pi * 10 * (PFC['Cout'] + DCLink['Cap_s'] * DCLink['Npara'] / DCLink['Nseri']) * 400,               #? [W/V]   - Voltage PI proportional gain (2*pi*fc_v*C_out*Vref)
                     'Ki_v'                  : (2 * np.pi * 10)**2 / 2 * (PFC['Cout'] + DCLink['Cap_s'] * DCLink['Npara'] / DCLink['Nseri']) * 400,      #? [W/Vs]  - Voltage PI integral gain (zero at fc_v/2)
                     'f_lpf_v'               : 20,                                                                                                       #? [Hz]    - Cut-off of the voltage-error low-pass filter (attenuates 2*f_line ripple)
                     'Pmax'                  : 1.5e3,                                                                                                    #? [W]     - Power command limit (voltage PI output)
                     'Ipk_max'               : 2 * 1.5e3 / (2**0.5 * 85),                                                                                #? [A]     - Peak current reference limit (Pmax at 85 Vrms)
                     'Vdc_min'               : 50,                                                                                                       #? [V]     - Lower clamp of Vdc used in the duty feedforward
                     'Dmax'                  : 0.98,                                                                                                     #? [/]     - Maximum duty of the active fast-leg switch
                     'Vzc'                   : 20,                                                                                                       #? [V]     - |Vac| below which all gates are blanked (zero crossing)
                     'eps_s'                 : 0.1,                                                                                                      #? [V]     - Offset in sign(vac) = vac/(|vac|+eps_s)
                     't_ss'                  : 0.2                                                                                                       #? [s]     - Soft-start ramp time of Vref from sqrt(2)*Vin to Vref
                  }
Load           =  {
                     'Config'                : Configs['Load'],                                                                                          #? [/]      - Configuration type for the load setup
                     'Pout'                  : 1e3,                                                                                                      #? [W]      - Load power
                     'Vout1'                 : 400,                                                                                                      #? [V]      - Load voltage (first step)
                     'Vout2'                 : 400,                                                                                                      #? [V]      - Load voltage (second step)
                     'CL'                    : 0,                                                                                                        #? [F]      - Load capacitance value
                     'R'                     : 400**2 / 1e3,                                                                                             #? [Ohm]    - Load resistance value
                     'L'                     : 0,                                                                                                        #? [H]      - Load inductance value
                     'Vinit'                 : 0,                                                                                                        #? [V]      - Initial voltage across the load
                     'Iinit'                 : 0,                                                                                                        #? [A]      - Initial current through the load
                     't_switch'              : Sim_param['tSim'] - Sim_param['load_tflip'],                                                              #? [s]      - Time when the load switching occurs
                     't_dead'                : (Sim_param['tSim'] - Sim_param['load_tflip']) / 2 ,                                                       #? [s]      - Dead time for load switching
                     'Loadgen'               : {
                                                'Config' : Configs['Loadgen'],                                                                                                  #? [/]      - Load generator configuration
                                                }
                        
               }
Thermals       =  {
                     'T_amb'                 : 25.0,                                                                                                     #? [°C]     - Ambient temperature
                     'rth_Amb'               : 0.09                                                                                                      #? [K/W]    - Thermal resistance from junction to ambient
                  }
Sensors        =  {                                                                                                                                   # measurement chain on the board (Sensors library): v_out = clamp(Vofs + err_ofs + G*(1+err_g)*x, Vmin, Vmax)
                  'Iin'           : {                                                                                                                 # input (inductor) current: 5 mOhm shunt + AMC1301 (x8.2) + level shift, +-25 A -> 1.65 +- 1.25 V
                     'G'       : 0.05,                                                                                                                #? [V/A]    - Sensitivity
                     'Vofs'    : 1.65,                                                                                                                #? [V]      - Output at 0 A (mid-rail)
                     'BW'      : 200e3,                                                                                                               #? [Hz]     - Bandwidth (isolated amplifier)
                     'err_g'   : 0,                                                                                                                   #? [/]      - Gain error (e.g. 0.005 = +0.5 %)
                     'err_ofs' : 0,                                                                                                                   #? [V]      - Offset error
                     'Vmin'    : 0,                                                                                                                   #? [V]      - Output clamp low (ADC rail)
                     'Vmax'    : 3.3,                                                                                                                 #? [V]      - Output clamp high (ADC rail)
                  },
                  'Vac'           : {                                                                                                                 # AC input voltage: resistive divider + RC + AMC1311, +-400 V -> 1.65 +- 1.5 V
                     'G'       : 1.5/400,                                                                                                             #? [V/V]    - Divider + amplifier gain
                     'Vofs'    : 1.65,                                                                                                                #? [V]      - Output at 0 V (mid-rail)
                     'BW'      : 10e3,                                                                                                                #? [Hz]     - RC anti-alias filter corner
                     'BW2'     : 275e3,                                                                                                               #? [Hz]     - Isolated amplifier bandwidth
                     'err_g'   : 0,                                                                                                                   #? [/]      - Gain error
                     'err_ofs' : 0,                                                                                                                   #? [V]      - Offset error
                     'Vmin'    : 0,                                                                                                                   #? [V]      - Output clamp low
                     'Vmax'    : 3.3,                                                                                                                 #? [V]      - Output clamp high
                  },
                  'Vdc'           : {                                                                                                                 # DC-link voltage: resistive divider + RC + AMC1311, 0..500 V -> 0..3 V
                     'G'       : 3/500,                                                                                                               #? [V/V]    - Divider + amplifier gain
                     'Vofs'    : 0,                                                                                                                   #? [V]      - Output at 0 V
                     'BW'      : 5e3,                                                                                                                 #? [Hz]     - RC anti-alias filter corner
                     'BW2'     : 275e3,                                                                                                               #? [Hz]     - Isolated amplifier bandwidth
                     'err_g'   : 0,                                                                                                                   #? [/]      - Gain error
                     'err_ofs' : 0,                                                                                                                   #? [V]      - Offset error
                     'Vmin'    : 0,                                                                                                                   #? [V]      - Output clamp low
                     'Vmax'    : 3.3,                                                                                                                 #? [V]      - Output clamp high
                  }
               }
MCU            =  {                                                                                                                                   # microcontroller: ADC + firmware calibration (nominal sensor gain / offset, without the errors)
                  'ADC'           : {                                                                                                                 # ADC used for all three channels (Sensors/ADC)
                     'N'       : 12,                                                                                                                  #? [bit]    - Resolution
                     'Vref'    : 3.3,                                                                                                                 #? [V]      - Full scale
                     'Ts'      : 1/CTRL['fsw'],                                                                                                       #? [s]      - Sampling period (once per PWM period)
                     'Toffs'   : 0,                                                                                                                   #? [s]      - Sampling instant in the period (0 = carrier valley -> average inductor current)
                     'err_g'   : 0,                                                                                                                   #? [/]      - ADC gain error
                     'err_ofs' : 0,                                                                                                                   #? [V]      - ADC offset error
                  },
                  'Cal'           : {                                                                                                                 # calibration the firmware uses to convert counts back to V / A
                     'Iin'     : {                                                                                                                    # Iin channel
                        'G'    : Sensors['Iin']['G'],                                                                                                 #? [V/unit] - Nominal sensor gain
                        'ofs'  : Sensors['Iin']['Vofs']                                                                                               #? [V]      - Nominal sensor offset
                     },
                     'Vac'     : {                                                                                                                    # Vac channel
                        'G'    : Sensors['Vac']['G'],                                                                                                 #? [V/unit] - Nominal sensor gain
                        'ofs'  : Sensors['Vac']['Vofs']                                                                                               #? [V]      - Nominal sensor offset
                     },
                     'Vdc'     : {                                                                                                                    # Vdc channel
                        'G'    : Sensors['Vdc']['G'],                                                                                                 #? [V/unit] - Nominal sensor gain
                        'ofs'  : Sensors['Vdc']['Vofs']                                                                                               #? [V]      - Nominal sensor offset
                     }
                  }
               }
#!----------------------------------------------------------------------------------------------------------------------------------------
ModelVars      =  {                                                                                             
                  'Sim_param'             :  Sim_param               ,      
                  'ToFile'                :  ToFile                  ,
                  'Grid'                  :  Grid                    ,                                                                   
                  'AC_Filter'             :  AC_Filter               ,                                                           
                  'PFC'                   :  PFC                     ,                                                                 
                  'DCLink'                :  DCLink                  ,                                                              
                  'CTRL'                  :  CTRL                    ,                                                            
                  'Load'                  :  Load                    ,                                                                
                  'Thermals'              :  Thermals                ,
                  'Sensors'               :  Sensors                 ,
                  'MCU'                   :  MCU
               }	
SolverOpts     =  {
                  'Sim_param'             :  ModelVars['Sim_param'] 
               }
AnalysisOpts   =  {
                  'system_period'         :  1/Grid['f']             ,      
                  'freq_range_min'        :  1                       ,
                  'freq_range_max'        :  1e7                     ,
                  'amplitude'             :  1e-1                    ,                                                                   
                  'sim_Tstart'            :  0                       ,                                                           
                  'NB_pts'                :  10000                   ,                                                                 
                  'additional_freq'       :  []                      ,                                                              
                  'NB_init_cycles'        :  0                       ,                                                                 
                  'Termination_tol'       :  1e-3                    ,                                                            
                  'max_iter_NB'           :  50                      ,   
                  'Jacobian_rel_tol'      :  1e-6        
                                                                           
              }
Waveforms      =  {                                                                                            # result CSV columns after time, in order: name -> unit
                  'Grid Voltage'                          : '[ V ]',
                  'Grid Current'                          : '[ A ]',
                  #!-------------------------
                  'EMI Filter Current'                    : '[ A ]',
                  'EMI Filter Voltage'                    : '[ V ]',
                  #!-------------------------
                  'PFC Input Voltage'                     : '[ V ]',
                  'PFC Input Current'                     : '[ A ]',
                  'PFC output voltage'                    : '[ V ]',
                  'PFC output Current'                    : '[ A ]',
                  #!-------------------------
                  'PFC gates signal HS1'                  : '[ / ]',
                  'PFC gates signal LS1'                  : '[ / ]',
                  'PFC gates signal HS2'                  : '[ / ]',
                  'PFC gates signal LS2'                  : '[ / ]',
                  'PFC gates signal HS3'                  : '[ / ]',
                  'PFC gates signal LS3'                  : '[ / ]',
                  #!-------------------------
                  'PFC Input choke Winding 1 Current'     : '[ A ]',
                  'PFC Input choke Winding 1 Voltage'     : '[ V ]',
                  'PFC Input choke Winding 3 Current'     : '[ A ]',
                  'PFC Input choke Winding 2 Voltage'     : '[ V ]',
                  #!-------------------------
                  'PFC HS1 voltage'                       : '[ V ]',
                  'PFC LS1 voltage'                       : '[ V ]',
                  'PFC HS2 voltage'                       : '[ V ]',
                  'PFC LS2 voltage'                       : '[ V ]',
                  'PFC HS3 voltage'                       : '[ V ]',
                  'PFC LS3 voltage'                       : '[ V ]',
                  #!-------------------------
                  'PFC HS1 Current'                       : '[ A ]',
                  'PFC LS1 Current'                       : '[ A ]',
                  'PFC HS2 Current'                       : '[ A ]',
                  'PFC LS2 Current'                       : '[ A ]',
                  'PFC HS3 Current'                       : '[ A ]',
                  'PFC LS3 Current'                       : '[ A ]',
                  #!-------------------------
                  'PFC HS1 junction Temperature'          : '[ °C ]',
                  'PFC LS1 junction Temperature'          : '[ °C ]',
                  'PFC HS2 junction Temperature'          : '[ °C ]',
                  'PFC LS2 junction Temperature'          : '[ °C ]',
                  'PFC HS3 junction Temperature'          : '[ °C ]',
                  'PFC LS3 junction Temperature'          : '[ °C ]',
                  #!-------------------------
                  'PFC HS1 switching losses'              : '[ W ]',
                  'PFC LS1 switching losses'              : '[ W ]',
                  'PFC HS2 switching losses'              : '[ W ]',
                  'PFC LS2 switching losses'              : '[ W ]',
                  'PFC HS3 switching losses'              : '[ W ]',
                  'PFC LS3 switching losses'              : '[ W ]',
                  #!-------------------------
                  'PFC HS1 conduction losses'             : '[ W ]',
                  'PFC LS1 conduction losses'             : '[ W ]',
                  'PFC HS2 conduction losses'             : '[ W ]',
                  'PFC LS2 conduction losses'             : '[ W ]',
                  'PFC HS3 conduction losses'             : '[ W ]',
                  'PFC LS3 conduction losses'             : '[ W ]',
                  #!-------------------------
                  'PFC output capacitor voltage'          : '[ V ]',
                  'PFC output capacitor current'          : '[ A ]',
                  #!-------------------------
                  'DCLink capacitor voltage'              : '[ V ]',
                  'DCLink capacitor current'              : '[ A ]',
                  #!-------------------------
                  'Load voltage'                          : '[ V ]',
                  'Load current'                          : '[ A ]'
               }
#!----------------------------------------------------------------------------------------------------------------------------------------