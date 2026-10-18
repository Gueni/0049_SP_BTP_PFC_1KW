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
from rtbox import RTBox
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
#? What to run (in this order): the sweep, then code generation, then the RT Box (RTBOX implies CODEGEN).
SWEEP_EN                               = True                                                  # run the simulation sweep
CODEGEN                                = False                                                 # generate code (PLECS Coder) with the base ModelVars
RTBOX                                  = False                                                 # upload + run the generated code on the RT Box
SCOPES                                 = None                                                  # scope names to clear/hold/save: None = all scopes in the model, [] = none
PARASIM                                = True                                                  # run several sweep points in parallel
PARANUM                                = 4                                                     # sweep points per parallel batch

modelname                              = mdl.MODEL_NAME
port                                   = "1080"
url                                    = f"http://localhost:{port}/RPC2"
model_directory                        = mdl.MODEL_PATH.as_posix()

#? Code generation / RT Box settings (only used when CODEGEN or RTBOX is True)
CODEGEN_TARGET                         = ""                                                    # subsystem with 'Enable code generation' checked, e.g. "PFC CTRL"
CODEGEN_DIR                            = mdl.RES_DIR / "Codegen"                               # where PLECS Coder writes the generated code / .elf
RTBOX_URL                              = "http://192.168.0.10:9998/RPC2"                       # RT Box XML-RPC server (its IP, port 9998)
RTBOX_SET                              = {}                                                    # Programmable Value blocks to write after start: {'Vref': [400]}
RTBOX_CAPTURE                          = []                                                    # Data Capture blocks to read before stop: ['Capture1']
RTBOX_TIMEOUT                          = 30                                                    # [s] max wait for a capture trigger (None = forever)
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

if SWEEP_EN:
        plcsim.clear_data_folders(mdl.RES_FOLDERS)
        scopes                         = plcsim.get_scopes(modelname, only=SCOPES)
        print(f"{len(scopes)} scopes: {scopes}")
        plcsim.ClearAllTraces(scopes)

        run_id                         = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        points                         = plc.build_points(mdl.ModelVars, SWEEP, SWEEP_PATHS, run_id)
        batch_size                     = PARANUM if PARASIM else 1
        mode                           = f"parallel x{batch_size}" if PARASIM else "sequential"
        print(f"Sweep {run_id}: {len(points)} points, {mode}. Log: {plc.write_sweep_log(points, mdl.ModelVars, run_id)}")

        for start in range(0, len(points), batch_size):
                batch                  = points[start:start + batch_size]
                for label, mv in batch:
                        print(f"  [{mv['ToFile']['sim_idx']}/{len(points)}] {label}")
                plcsim.Set_sim_param([mv for _, mv in batch] if PARASIM else batch[0][1])
                t0                     = time.time()
                plcsim.launch_sim(modelname=modelname)
                print(f"     done in {time.time() - t0:.1f} s")
                plcsim.HoldAllTraces(scopes)

        plcsim.saveAllTraces(scopes, mdl.Traces_path.as_posix(), run_id)
        PMath.gen_sweep_plots(points, html_file=points[0][1]['ToFile']['output_html'], OPEN=False)

if CODEGEN or RTBOX:
        rtb                            = RTBox(
                                                plcsim.server                       ,
                                                modelname       =   modelname       ,
                                                codegen_target  =   CODEGEN_TARGET  ,
                                                output_dir      =   CODEGEN_DIR     ,
                                                rtbox_url       =   RTBOX_URL
                                                )
        rtb.generate_code(mdl.ModelVars)
        if RTBOX:
                captured               = rtb.run(set_values=RTBOX_SET, capture_blocks=RTBOX_CAPTURE, timeout=RTBOX_TIMEOUT)
                print(f"RT Box captured: {list(captured)}")
#?----------------------------------------------------------------------------------------------------------------------------------------
