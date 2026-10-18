#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?              ____  __    _________________    ________  ___   ________
#?             / __ \/ /   / ____/ ____/ ___/   / ____/ / / / | / / ____/
#?            / /_/ / /   / __/ / /    \__ \   / /_  / / / /  |/ / /
#?           / ____/ /___/ /___/ /___ ___/ /  / __/ / /_/ / /|  / /___
#?          /_/   /_____/_____/\____//____/  /_/    \____/_/ |_/\____/
#?
#?
#? Name:        plecs.py
#? Purpose:     PLECS XML-RPC interface (launch PLECS, set parameters, run simulations).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/15/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import copy
import itertools
import math
import xmlrpc.client
import subprocess
import shutil
import os

import Model_Parameters     as  mdl
#?----------------------------------------------------------------------------------------------------------------------------------------
class simpy:
    
    def __init__(self,url,port,path,modelvar,analysisvars='',analysisName='',parasim = False,paranum = 1):
        self.url                    =   url
        self.port                   =   port
        self.path                   =   path
        self.modelvar               =   modelvar
        self.analysisvars           =   analysisvars
        self.analysisName           =   analysisName
        self.opts                   =   []
        self.parasim                =   parasim 
        self.paranum                =   paranum

    def is_running(self,process_name):
        try:
            tasks = os.popen('tasklist').read().strip().split('\n')
            for task in tasks:
                if process_name.lower() in task.lower():
                    return True
            return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False
        
    def return_opts(self,parasim = False , paranum = 1):
        # Single run: one opts dict. Parallel run: a list of opts dicts, PLECS simulates them in parallel.
        # In parallel mode self.modelvar is either a list of ModelVars (one per run) or one dict copied paranum times.
        if not parasim :
            self.opts  = { 'ModelVars': self.modelvar}  #, 'SolverOpts': self.slv0pts, 'AnalysisOpts': self.an10pts}
        else :
            modelvars  = self.modelvar if isinstance(self.modelvar, list) else [copy.deepcopy(self.modelvar) for _ in range(paranum)]
            self.opts  = [{'ModelVars' : mv} for mv in modelvars]
        return self.opts

    def find_executable(self,exe_name):
        # PLECS_EXE env var > PATH > standard install folders > ~/Documents
        env_path = os.environ.get("PLECS_EXE")
        if env_path and os.path.isfile(env_path):
            return env_path
        on_path = shutil.which(exe_name)
        if on_path:
            return on_path
        search_roots = [os.path.join(os.environ.get(var, ""), "Plexim") for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
        search_roots.append(os.path.expanduser("~/Documents"))
        for search_root in search_roots:
            if not os.path.isdir(search_root):
                continue
            for root, dirs, files in os.walk(search_root):
                if exe_name in files:
                    return os.path.join(root, exe_name)
        return None

    def launch_if_not_running(self):
        exe_name = "PLECS.exe"
        exe_path = self.find_executable(exe_name)
        if not exe_path:
            print(f"Could not find {exe_name} on your system.")
            return
        
        if not self.is_running(exe_name):
            subprocess.Popen(exe_path)
            print(f"{exe_name} has been launched from {exe_path}.")
        else:
            print(f"{exe_name} is already running.")

    def rpc_connect(self):
        self.launch_if_not_running()
        self.server =   xmlrpc.client.ServerProxy(self.url)

    def load_model(self):
        self.server.plecs.load(self.path)
    
    def get_scopes(self,modelname,only=None):
        """
        Full PLECS paths ('PFC/Scopes/grid_scope', ...) of every Scope block in the model, found by walking the
        nested Component/Schematic blocks of the .plecs file, so scopes added/renamed in the model are picked up automatically.
        only : optional list of scope names to keep (None = all scopes, [] = none).
        Scopes inside library references are not stored in the model file and are not found.
        """
        stack, scopes          = [], []                                         # stack: one [is_component, Type, Name] per open block
        with open(self.path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                s              = line.strip()
                if s.endswith('{') and s[:-1].strip().isidentifier():
                    stack.append([s[:-1].strip() == 'Component', None, None])
                elif s == '}' and stack:
                    is_comp, kind, name = stack.pop()
                    if is_comp and kind == 'Scope':
                        parents = [b[2] for b in stack if b[0] and b[2]]
                        scopes.append('/'.join([modelname] + [n.replace('/', '//') for n in parents + [name]]))
                elif stack and stack[-1][0] and (s.startswith('Type ') or s.startswith('Name ')):
                    key, value = s.split(None, 1)
                    stack[-1][1 if key == 'Type' else 2] = value.strip().strip('"')
        if only is not None:
            scopes             = [p for p in scopes if p.split('/')[-1] in only]
        return scopes

    def ClearAllTraces(self,scopelist):
        for val in scopelist:
            self.server.plecs.scope(val,'ClearTraces')

    def Set_sim_param(self,mdlvars):
        self.modelvar = mdlvars
        self.opts     = self.return_opts(self.parasim , self.paranum)
    
    def set_analysis_param(self,analysisvars):
        self.analysisvars = analysisvars
        self.analysisopts =  {'ModelVars' :  self.analysisvars }

    def launch_analysis(self,modelname):
        results = self.server.plecs.analyze(modelname, self.analysisName, self.analysisopts)
        return results
    
    def launch_sim(self,modelname):
        return self.server.plecs.simulate(modelname, self.opts)

    def HoldAllTraces(self,scopelist):
        for val in scopelist:
            self.server.plecs.scope(val,'HoldTrace')

    def saveAllTraces(self,scopelist,path,tag):
        for val in scopelist:
            trace_file = os.path.join(path, f"{val.split('/')[-1]}_{tag}.trace").replace("\\", "/")
            self.server.plecs.scope(val, 'SaveTraces', trace_file)

    def close_cnx(self,modelname):
        self.server.plecs.close(modelname) 

    def logParams(self,file_path, nested_dict):
        with open(file_path, 'a') as file:
            self.log_parameters(file, nested_dict, parent_keys=[])

    def log_parameters(self,file, nested_dict, parent_keys):
        for key, value in nested_dict.items():
            current_keys = parent_keys + [key]
            if isinstance(value, dict):
                self.log_parameters(file, value, current_keys)
                file.write("---------------------------------------------------------------------------------------------------\n")
            else:
                parent_path = "[" + "][".join(current_keys) + "]"
                file.write("{:<40}= {}\n".format(parent_path, value))

    def clear_data_folders(self,folder_paths):
        # Delete the files (not sub-folders) of each result folder
        for folder_path in folder_paths:
            if not os.path.isdir(folder_path):
                print(f"Error: {folder_path} is not a directory.")
                continue
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)

#?----------------------------------------------------------------------------------------------------------------------------------------
def set_nested(d, path, value):
    for key in path[:-1]:
        d                      = d[key]
    d[path[-1]]                = value

def build_points(base, sweep, sweep_paths, run_id):
    """One deep-copied ModelVars per combination of the sweep values, with derived parameters and output files updated."""
    points                     = []
    for sim_idx, values in enumerate(itertools.product(*sweep.values()), start=1):
        label                  = dict(zip(sweep, values))
        mv                     = copy.deepcopy(base)
        for name, value in label.items():
            for path in sweep_paths[name]:
                set_nested(mv, path, value)
        mdl.update_derived(mv)
        mdl.set_output_files(mv, run_id, sim_idx)
        points.append((label, mv))
    return points

def _flat(d, keys=()):
    for key, value in d.items():
        if isinstance(value, dict):
            yield from _flat(value, keys + (key,))
        else:
            yield keys + (key,), value

def _differs(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return not math.isclose(a, b, rel_tol=1e-9)
    return a != b

def write_sweep_log(points, base, run_id):
    """One log file per sweep: the base parameters once, then one section per iteration with only the parameters
    that differ from the base (swept values and the derived parameters they change)."""
    log_file                   = points[0][1]['ToFile']['logfile']
    base_flat                  = dict(_flat(base))
    fmt                        = lambda keys: "[" + "][".join(keys) + "]"
    lines                      = [f"Sweep {run_id}: {len(points)} iterations", "=" * 99, "BASE PARAMETERS", "-" * 99]
    lines                     += ["{:<40}= {}".format(fmt(k), v) for k, v in base_flat.items() if k[0] != 'ToFile']
    for label, mv in points:
        swept                  = ", ".join(f"{k}={v:g}" if isinstance(v, (int, float)) else f"{k}={v}" for k, v in label.items())
        lines                 += ["=" * 99, f"ITERATION {mv['ToFile']['sim_idx']}/{len(points)} : {swept}",
                                  f"results : {mv['ToFile']['ToFile_path']}", "-" * 99]
        lines                 += ["{:<40}= {:<24} (base: {})".format(fmt(k), str(v), base_flat.get(k))
                                  for k, v in _flat(mv) if k[0] != 'ToFile' and _differs(v, base_flat.get(k))]
    with open(log_file, 'w') as f:
        f.write("\n".join(lines) + "\n")
    return log_file

#?----------------------------------------------------------------------------------------------------------------------------------------