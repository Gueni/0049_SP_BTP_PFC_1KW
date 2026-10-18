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
#? Name:        Model_Parameters.py
#? Purpose:     Model paths, simulation settings and component parameters of the PFC model.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/15/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
from     pathlib     import   Path
import   numpy       as       np
#!----------------------------------------------------------------------------------------------------------------------------------------
#! All paths are resolved from this file's location, so the scripts work from any working directory.
LIB_DIR                    = Path(__file__).resolve().parent                    # <repo>/Lib
ROOT_DIR                   = LIB_DIR.parent                                     # <repo>
MODEL_NAME                 = "PFC"
MODEL_PATH                 = ROOT_DIR / "Model" / f"{MODEL_NAME}.plecs"
MODEL_IMG_PATH             = ROOT_DIR / "doc" / "schematic.png"
RES_DIR                    = ROOT_DIR / "RES"
Traces_path                = RES_DIR / "Traces"
ToFile_path                = RES_DIR / "CSV"
logfile_path               = RES_DIR / "Log"
output_html_path           = RES_DIR / "html"
RES_FOLDERS                = [ToFile_path, output_html_path, logfile_path, Traces_path]
for _folder in RES_FOLDERS : _folder.mkdir(parents=True, exist_ok=True)
#!----------------------------------------------------------------------------------------------------------------------------------------
Sim_param 	= {                                                                                            
                  'tSim'	    	   : 1.0,                                                                                                               #? [s]     - Total simulation time
                  'load_tflip'	   : 1.0/2,                                                                                                             #? [s]     - Time at which the load changes state 
                  'maxStep'		   : 1e-3,                                                                                                              #? [s]     - Maximum simulation time step
                  'ZeroCross'       : 1000,                                                                                                              #? [/]     - Zero-crossing detection limit
                  'rel_tol'		   : 1e-7                                                                                                               #? [/]     - Relative tolerance for the numerical solver
               }
Configs     = {
                  'Grid'            : 1,                                                                                                                 #? [/]      - Config of the Grid.
                  'AC_Filter'       : 1,                                                                                                                 #? [/]      - Config of the AC filter.
                  'PFC'             : 1,                                                                                                                 #? [/]      - Config of the PFC.
                  'DCLink'          : 2,                                                                                                                 #? [/]      - Config of the DCLink (2 = capacitor with ESR).
                  'Load'            : 1                                                                                                                  #? [/]      - Config of the Load.

               }
ToFile      = {                     
                  'Ts'              : 0,                                                                                                                 #? [s]     - Sampling time for saving data
                  'tsave' 	    	   : Sim_param['tSim']-0.2                                                                                              #? [s]     - Time point at which the data is saved
               }
Grid        = {                                                                                                                                          # EVSE / grid source
                  'Config'          : Configs['Grid'],                                                                                                   #? [/]     - Configuration setting for the grid
                  'Vin'             : 230,                                                                                                               #? [V]     - Input voltage of the grid
                  'Ts'              : 1/80e3,                                                                                                            #? [s]     - Sampling time for grid operations
                  'f'               : 50,                                                                                                                #? [Hz]    - Grid frequency
                  'phase'           : 0,                                                                                                                 #? [rad]   - Grid voltage phase angle
                  'R'               : 0.01                                                                                                               #? [Ohm]   - Grid resistance
               }
AC_Filter   = {
                  'Config'          : Configs['AC_Filter'],                                                                                              #? [/]      - Configuration setting for the AC filter
                  'Cin'             : 1e-6,                                                                                                              #? [F]      - Input capacitance
                  'L_CMC'           : 1.5e-3,                                                                                                            #? [H]      - Common-mode choke inductance
                  'L_DMC'           : 900e-6,                                                                                                            #? [H]      - Differential-mode choke inductance
                  'Cx'              : 0.1e-6,                                                                                                            #? [F]      - X-capacitor value
                  'Cy1'             : 4.7e-12,                                                                                                           #? [F]      - Y-capacitor value (first)
                  'Cy2'             : 4.7e-12,                                                                                                           #? [F]      - Y-capacitor value (second)
                  'Ll'              : 10e-6                                                                                                              #? [H]      - Filter inductor leakage inductance
               }
PFC         = {
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
                  'SW'              : {
                        'Config'       : 1,                                                                                                              #? [/]      - Switch configuration
                        'therm_mosfet' : 'file:C3M0021120K',                                                                                             #? [/]      - MOSFET thermal model file path
                        'Rgon'         : 2.5,                                                                                                            #? [Ohm]    - Gate resistance for turn-on
                        'Rgoff'        : 2.5,                                                                                                            #? [Ohm]    - Gate resistance for turn-off
                        'ron_mosfet'   : 65e-3,                                                                                                          #? [Ohm]    - MOSFET on-state resistance
                        'Iinit'        : 0,                                                                                                              #? [A]      - Initial current through the MOSFET
                        'Coss'         : {
                              'Config' : 5,                                                                                                              #? [/]      - Capacitance configuration
                              'Cap_s'  : 180e-12,                                                                                                        #? [F]      - Capacitance value
                              'Resr_s' : 1e-12,                                                                                                          #? [Ohm]    - Equivalent series resistance of the capacitance
                              'Lesl_s' : 1e-12,                                                                                                          #? [H]      - Equivalent series inductance of the capacitance
                              'Npara'  : 1,                                                                                                              #? [/]      - Number of parallel capacitors
                              'Nseri'  : 1,                                                                                                              #? [/]      - Number of series capacitors
                              'Vinit'  : 0,                                                                                                              #? [V]      - Initial voltage across the capacitance
                              'Iinit'  : 0                                                                                                               #? [A]      - Initial current through the capacitance
                        },
                        'therm_body_diode'   : 'file:C3M0021120K_bodydiode',                                                                             #? [/]      - Body diode thermal model file path
                        'ron_body_diode'     : 5e-3,                                                                                                     #? [Ohm]    - Body diode on-state resistance
                        'Rdb_off'            : 0,                                                                                                        #? [Ohm]    - Resistance when the body diode is off
                        'vf_body_diode'      : 4.5,                                                                                                      #? [V]      - Body diode forward voltage
                        'nPara'              : 1,                                                                                                        #? [/]      - Number of parallel MOSFETs
                        'T_init'             : 25,                                                                                                       #? [°C]     - Initial temperature of the MOSFET
                        'Tamb'               : 25,                                                                                                       #? [°C]     - Ambient temperature
                        't_init'             : 25,                                                                                                       #? [s]      - Initial time for thermal calculations
                        'rth_sw'             : 0.1,                                                                                                      #? [K/W]    - Thermal resistance between the switch junction and case
                        'rth_ch'             : 0.1,                                                                                                      #? [K/W]    - Thermal resistance between the case and heatsink
                        'Rth'                : 0.1                                                                                                       #? [K/W]    - Total thermal resistance
                     }
               }
DCLink      = {                                                                                             
                      'Config'		   : Configs['DCLink'],                                                                                              #? [/]      - Capacitance configuration
                      'Cap_s'    		: 470e-6,                                                                                                         #? [F]      - Capacitance value 
                      'Resr_s'		   : 50e-3,                                                                                                          #? [Ohm]    - Equivalent series resistance of the capacitance
                      'Lesl_s'		   : 1e-12,                                                                                                          #? [H]      - Equivalent series inductance of the capacitance
                      'Npara'		      : 1,                                                                                                              #? [/]      - Number of parallel capacitors
                      'Nseri'		      : 1,                                                                                                              #? [/]      - Number of series capacitors
                      'Vinit'		      : -2**0.5 * Grid['Vin'],                                                                                          #? [V]      - Initial voltage: line peak, inrush bypass assumed (negative: CDC is placed flipped)
                      'Iinit'		      : 0                                                                                                               #? [A]      - Initial current through the capacitance   
                     }
CTRL        = {
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
Load        = {
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
                     't_dead'                : (Sim_param['tSim'] - Sim_param['load_tflip']) / 2                                                         #? [s]      - Dead time for load switching
                  }
Thermals    = {
                     'T_amb'                 : 25.0,                                                                                                     #? [°C]     - Ambient temperature
                     'rth_Amb'               : 0.09                                                                                                      #? [K/W]    - Thermal resistance from junction to ambient
                  }
#!----------------------------------------------------------------------------------------------------------------------------------------
ModelVars   = {                                                                                             
                  'Sim_param'             :  Sim_param               ,      
                  'ToFile'                :  ToFile                  ,
                  'Grid'                  :  Grid                    ,                                                                   
                  'AC_Filter'             :  AC_Filter               ,                                                           
                  'PFC'                   :  PFC                     ,                                                                 
                  'DCLink'                :  DCLink                  ,                                                              
                  'CTRL'                  :  CTRL                    ,                                                            
                  'Load'                  :  Load                    ,                                                                
                  'Thermals'              :  Thermals    
               }	
SolverOpts  = {
                  'Sim_param'             :  ModelVars['Sim_param'] 
               }
AnalysisOpts= {
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
#!----------------------------------------------------------------------------------------------------------------------------------------
def set_output_files(mdlvar, utc_numeric, sim_idx):
   mdlvar['ToFile']['sim_idx']      = sim_idx
   mdlvar['ToFile']['utc_numeric']  = utc_numeric
   mdlvar['ToFile']['ToFile_path']  = (ToFile_path      / f"Results_{utc_numeric}_{sim_idx}.csv").as_posix()
   mdlvar['ToFile']['logfile']      = (logfile_path     / f"Log_{utc_numeric}.log").as_posix()
   mdlvar['ToFile']['output_html']  = (output_html_path / f"Html_{utc_numeric}.html").as_posix()
   mdlvar['ToFile']['Traces']       = Traces_path.as_posix()
   return mdlvar

def update_derived(mdlvar):
   """Recompute the parameters derived from other ones (same formulas as above), after a sweep changed the base values."""
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
   return mdlvar

Waveforms   =  [                                                                                            
                  'Grid Voltage',                  
                  'Grid Current',
                  #!-------------------------
                  'EMI Filter Current',
                  'EMI Filter Voltage',
                  #!-------------------------
                  'PFC Input Voltage',
                  'PFC Input Current',
                  'PFC output voltage',
                  'PFC output Current',
                  #!-------------------------
                  'PFC gates signal HS1',
                  'PFC gates signal LS1',
                  'PFC gates signal HS2',
                  'PFC gates signal LS2',
                  'PFC gates signal HS3',
                  'PFC gates signal LS3',
                  #!-------------------------
                  'PFC Input choke Winding 1 Current',
                  'PFC Input choke Winding 1 Voltage',
                  'PFC Input choke Winding 3 Current',
                  'PFC Input choke Winding 2 Voltage',
                  #!-------------------------
                  'PFC HS1 voltage',
                  'PFC LS1 voltage',
                  'PFC HS2 voltage',
                  'PFC LS2 voltage',
                  'PFC HS3 voltage',
                  'PFC LS3 voltage',
                  #!-------------------------
                  'PFC HS1 Current',
                  'PFC LS1 Current',
                  'PFC HS2 Current',
                  'PFC LS2 Current',
                  'PFC HS3 Current',
                  'PFC LS3 Current',
                  #!-------------------------
                  'PFC HS1 junction Temperature',
                  'PFC LS1 junction Temperature',
                  'PFC HS2 junction Temperature',
                  'PFC LS2 junction Temperature',
                  'PFC HS3 junction Temperature',
                  'PFC LS3 junction Temperature',
                  #!-------------------------
                  'PFC HS1 switching losses',
                  'PFC LS1 switching losses',
                  'PFC HS2 switching losses',
                  'PFC LS2 switching losses',
                  'PFC HS3 switching losses',
                  'PFC LS3 switching losses',
                  #!-------------------------
                  'PFC HS1 conduction losses',
                  'PFC LS1 conduction losses',
                  'PFC HS2 conduction losses',
                  'PFC LS2 conduction losses',
                  'PFC HS3 conduction losses',
                  'PFC LS3 conduction losses',
                  #!-------------------------
                  'PFC output capacitor voltage',
                  'PFC output capacitor current',
                  #!-------------------------
                  'DCLink capacitor voltage',
                  'DCLink capacitor current',
                  #!-------------------------
                  'Load voltage',
                  'Load current'
               ]		

def generate_units(waveforms):
    keyword_to_unit = {
        'Voltage'       : '[ V ]',
        'Current'       : '[ A ]',
        'Temperature'   : '[ C ]',
        'losses'        : '[ W ]',
        'signal'        : '[ V ]'
    }
    units = []
    for waveform in waveforms:
        unit_found = False
        for keyword, unit in keyword_to_unit.items():
            if keyword.lower() in waveform.lower():
                units.append(unit)
                unit_found = True
                break
        if not unit_found:
            units.append('[ Unknown ]')
    return units

Units       = generate_units(Waveforms)




