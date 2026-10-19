#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?
#?             ______      _____  ___  ____
#?            / ___/ | /| / / _ \/ _ \/ __ \
#?           (__  )| |/ |/ /  __/  __/ /_/ /
#?          /____/ |__/|__/\___/\___/ .___/
#?                                 /_/
#?
#?
#? Name:        sweep.py
#? Purpose:     Sweep the operating point / design parameters and run the simulation for each point
#?              (every combination of the SWEEP values), optionally several points in parallel, then optionally
#?              generate code and run it on the RT Box. The system itself is defined in parameters.py; for another
#?              system only SWEEP / SWEEP_PATHS and the settings below change.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/15/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import time

import pplecs           as      plc
import parameters       as      prm
from   derived          import  Derived
from   pplots           import  PPlots
from   plog             import  PLog
from   rtbox            import  RTBox
#?----------------------------------------------------------------------------------------------------------------------------------------
#? Sweep definition: every combination of the values below is simulated (keep a single value to hold a parameter fixed).
SWEEP                                  = {
                                          'Vin'   : [230],
                                          'Pout'  : [500, 1000],
                                          'fsw'   : [70e3, 80e3, 100e3],
                                          'L1'    : [240e-6],
                                          'Cdc'   : [470e-6],
                                          'Tamb'  : [25],
                                         }
#? Where each swept value is written in ModelVars (one sweep value can drive several parameters).
SWEEP_PATHS                            = {
                                          'Vin'   : [('Grid', 'Vin')],
                                          'Pout'  : [('Load', 'Pout'), ('CTRL', 'Pout')],
                                          'fsw'   : [('CTRL', 'fsw')],
                                          'L1'    : [('PFC', 'Choke', 'L1')],
                                          'Cdc'   : [('DCLink', 'Cap_s')],
                                          'Tamb'  : [('Thermals', 'T_amb'), ('PFC', 'SW', 'Tamb'), ('PFC', 'SW', 'T_init')],
                                         }
#? What to run (in this order): the sweep, then code generation, then the RT Box (RTBOX implies CODEGEN).
SWEEP_EN                               = True                                                  # run the simulation sweep
CODEGEN                                = False                                                 # generate code (PLECS Coder) with the base ModelVars
RTBOX                                  = False                                                 # upload + run the generated code on the RT Box
SCOPES                                 = None                                                    # scope names to clear/hold/save: None = all scopes in the model, [] = none
HOLD_TRACES                            = True                                                  # hold traces after each simulation point, to save them all at the end
SAVE_TRACES                            = False                                                 # save all traces at the end of the sweep        
PARASIM                                = True                                                  # run several sweep points in parallel
PARANUM                                = None                                                  # max sweep points per parallel batch (None = auto from the CPU threads)

ANALYSIS_NAME                          = ''                                                    # PLECS analysis name, for plcsim.launch_analysis

modelname                              = prm.MODEL_NAME
port                                   = "1080"
url                                    = f"http://localhost:{port}/RPC2"
model_directory                        = prm.MODEL_PATH.as_posix()
paths                                  = plc.ResultPaths(prm.DATA_DIR)

#? Code generation / RT Box settings (only used when CODEGEN or RTBOX is True)
CODEGEN_TARGET                         = ""                                                    # subsystem with 'Enable code generation' checked, e.g. "PFC CTRL"
CODEGEN_DIR                            = prm.DATA_DIR / "codegen"                               # where PLECS Coder writes the generated code / .elf
RTBOX_URL                              = "http://192.168.0.10:9998/RPC2"                       # RT Box XML-RPC server (its IP, port 9998)
RTBOX_SET                              = {}                                                    # Programmable Value blocks to write after start: {'Vref': [400]}
RTBOX_CAPTURE                          = []                                                    # Data Capture blocks to read before stop: ['Capture1']
RTBOX_TIMEOUT                          = 30                                                    # [s] max wait for a capture trigger (None = forever)
#?----------------------------------------------------------------------------------------------------------------------------------------
plcsim                                 = plc.simpy(
                                                    url             =   url                 ,
                                                    port            =   port                ,
                                                    path            =   model_directory     ,
                                                    modelvar        =   prm.ModelVars       ,
                                                    analysisvars    =   prm.ModelVars       ,
                                                    analysisName    =   ANALYSIS_NAME       ,
                                                    parasim         =   PARASIM             ,
                                                    paranum         =   PARANUM or 1
                                                    )
plcsim.rpc_connect()
plcsim.load_model()

if SWEEP_EN:
        plcsim.clear_data_folders(paths.folders)
        scopes                         = plcsim.get_scopes(modelname, only=SCOPES)
        scopes                         = plcsim.ClearAllTraces(scopes)
        run_id                         = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        points                         = plc.Sweep.build_points(prm.ModelVars, SWEEP, SWEEP_PATHS, run_id, paths,update_derived=Derived.update)
        batch_size                     = plc.Sweep.auto_batch_size(len(points), PARANUM) if PARASIM else 1
        plcsim.paranum                 = batch_size
        mode                           = f"parallel x{batch_size}" if PARASIM else "sequential"
        print(f"Sweep {run_id}: {len(points)} points, {mode}. Log: {PLog.write_sweep_log(points, prm.ModelVars, run_id)}")

        for start in range(0, len(points), batch_size):
                batch                  = points[start:start + batch_size]
                for label, mv in batch:
                        print(f"  [{mv[plc.OUTPUT_KEY]['sim_idx']}/{len(points)}] {label}")
                plcsim.Set_sim_param([mv for _, mv in batch] if PARASIM else batch[0][1])
                t0                     = time.time()
                plcsim.launch_sim(modelname=modelname)
                print(f"     done in {time.time() - t0:.1f} s")
                if HOLD_TRACES: plcsim.HoldAllTraces(scopes)

        if SAVE_TRACES: plcsim.saveAllTraces(scopes, paths.traces.as_posix(), run_id)
        PPlots.gen_sweep_plots(
                                points                                                              ,
                                waveforms       =   prm.Waveforms                                   ,
                                f0_path         =   getattr(prm, 'F0_PATH', None)                   ,
                                f0_overrides    =   getattr(prm, 'F0_OVERRIDES', None)              ,
                                model_name      =   modelname                                       ,
                                img_path        =   getattr(prm, 'MODEL_IMG_PATH', None)            ,
                                params_file     =   prm.__file__                                    ,
                                OPEN            =   False
                                )

if CODEGEN or RTBOX:
        rtb                            = RTBox(
                                                plcsim.server                       ,
                                                modelname       =   modelname       ,
                                                codegen_target  =   CODEGEN_TARGET  ,
                                                output_dir      =   CODEGEN_DIR     ,
                                                rtbox_url       =   RTBOX_URL
                                                )
        rtb.generate_code(prm.ModelVars)
        if RTBOX:
                captured               = rtb.run(set_values=RTBOX_SET, capture_blocks=RTBOX_CAPTURE, timeout=RTBOX_TIMEOUT)
                print(f"RT Box captured: {list(captured)}")
#?----------------------------------------------------------------------------------------------------------------------------------------
