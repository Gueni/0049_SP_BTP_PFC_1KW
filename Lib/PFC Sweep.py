#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?              ____  ____________   _____
#?             / __ \/ ____/ ____/  / ___/      _____  ___  ____
#?            / /_/ / /_  / /       \__ \ | /| / / _ \/ _ \/ __ \
#?           / ____/ __/ / /___    ___/ / |/ |/ /  __/  __/ /_/ /
#?          /_/   /_/    \____/   /____/|__/|__/\___/\___/ .___/
#?                                                      /_/
#?
#? Name:        PFC Sweep.py
#? Purpose:     Sweep the operating point / design parameters and run the PFC simulation for each point
#?              (every combination of the SWEEP values), optionally several points in parallel.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/15/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import plecs as plc
import Model_Parameters as mdl
from pmath import PMath
import time
#?----------------------------------------------------------------------------------------------------------------------------------------
#? Sweep definition: every combination of the values below is simulated (keep a single value to hold a parameter fixed).
SWEEP                                  = {
                                          'Vin'   : [90, 115, 230, 265],                       # [Vrms] grid input voltage
                                          'Pout'  : [500, 1000],                               # [W]    load power
                                          'fsw'   : [80e3],                                    # [Hz]   fast-leg switching frequency
                                          'Vref'  : [400],                                     # [V]    DC-link voltage reference
                                          'L1'    : [240e-6],                                  # [H]    boost choke inductance
                                          'Cdc'   : [470e-6],                                  # [F]    DC-link capacitance
                                          'Tamb'  : [25],                                      # [C]    ambient temperature
                                         }
#? Where each swept value is written in ModelVars (one sweep value can drive several parameters).
SWEEP_PATHS                            = {
                                          'Vin'   : [('Grid', 'Vin')],
                                          'Pout'  : [('Load', 'Pout'), ('CTRL', 'Pout')],
                                          'fsw'   : [('CTRL', 'fsw')],
                                          'Vref'  : [('CTRL', 'Vref'), ('Load', 'Vout1'), ('Load', 'Vout2')],
                                          'L1'    : [('PFC', 'Choke', 'L1')],
                                          'Cdc'   : [('DCLink', 'Cap_s')],
                                          'Tamb'  : [('Thermals', 'T_amb'), ('PFC', 'SW', 'Tamb'), ('PFC', 'SW', 'T_init')],
                                         }
PARASIM                                = True                                                  # run several sweep points in parallel
PARANUM                                = 4                                                     # sweep points per parallel batch

modelname                              = mdl.MODEL_NAME
port                                   = "1080"
url                                    = f"http://localhost:{port}/RPC2"
model_directory                        = mdl.MODEL_PATH.as_posix()
#?----------------------------------------------------------------------------------------------------------------------------------------
plcsim                                 = plc.simpy(
                                                    url             =   url                 ,
                                                    port            =   port                ,
                                                    path            =   model_directory     ,
                                                    modelvar        =   mdl.ModelVars       ,
                                                    analysisvars    =   mdl.ModelVars       ,
                                                    analysisName    =   'PFC'               ,
                                                    parasim         =   PARASIM             ,
                                                    paranum         =   PARANUM
                                                    )
plcsim.rpc_connect()
plcsim.load_model()
plcsim.clear_data_folders(mdl.RES_FOLDERS)
scopes                                 = mdl.set_scopes(modelname)
plcsim.ClearAllTraces(scopes)

run_id                                 = time.strftime("%Y%m%d%H%M%S", time.gmtime())
points                                 = plc.build_points(mdl.ModelVars, SWEEP, SWEEP_PATHS, run_id)
batch_size                             = PARANUM if PARASIM else 1
mode                                   = f"parallel x{batch_size}" if PARASIM else "sequential"
print(f"Sweep {run_id}: {len(points)} points, {mode}. Index: {plc.write_sweep_table(points, SWEEP, run_id)}")

for start in range(0, len(points), batch_size):
        batch                          = points[start:start + batch_size]
        for label, mv in batch:
                print(f"  [{mv['ToFile']['sim_idx']}/{len(points)}] {label}")
                plcsim.logParams(mv['ToFile']['logfile'], mv)
        plcsim.Set_sim_param([mv for _, mv in batch] if PARASIM else batch[0][1])
        t0                             = time.time()
        plcsim.launch_sim(modelname=modelname)
        print(f"     done in {time.time() - t0:.1f} s")
        plcsim.HoldAllTraces(scopes)
        for _, mv in batch:
                PMath.gen_plots(resFile=mv['ToFile']['ToFile_path'], html_file=mv['ToFile']['output_html'], OPEN=False, mdlvar=mv)

plcsim.saveAllTraces(scopes, mdl.Traces_path.as_posix(), run_id)
#?----------------------------------------------------------------------------------------------------------------------------------------
