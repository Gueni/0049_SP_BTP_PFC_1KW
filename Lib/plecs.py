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
#? Name:        pplecs.py
#? Purpose:     PLECS XML-RPC interface (launch PLECS, set parameters, run simulations), result folders and sweep points.
#?              System independent: everything system specific comes from parameters.py / sweep.py.
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
from   pathlib              import  Path

#?----------------------------------------------------------------------------------------------------------------------------------------
#? Convention with the PLECS model: ModelVars[OUTPUT_KEY] holds the output files of a run; the model's To File block writes
#? its CSV to ToFile.ToFile_path. OUTPUT_FIELDS are filled in per run by Sweep.set_output_files (not real model parameters).
OUTPUT_KEY                     = 'ToFile'
OUTPUT_FIELDS                  = ('sim_idx', 'utc_numeric', 'ToFile_path', 'logfile', 'output_html', 'Traces', 'Mat')
#?----------------------------------------------------------------------------------------------------------------------------------------
class ResultPaths:
    """Result folders of a project under data_dir (created if missing):
    timeseries (simulation CSVs), mat (one <type>_<run>.csv matrix per result type of PMath.RESULT_TYPES), log, html, traces."""

    def __init__(self,data_dir):
        self.root                   =   Path(data_dir)
        self.timeseries             =   self.root / "timeseries"
        self.mat                    =   self.root / "mat"
        self.log                    =   self.root / "log"
        self.html                   =   self.root / "html"
        self.traces                 =   self.root / "traces"
        self.folders                =   [self.timeseries, self.mat, self.html, self.log, self.traces]
        for folder in self.folders:
            folder.mkdir(parents=True, exist_ok=True)
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
    
    @staticmethod
    def _parse_blocks(lines):
        """Tree of the 'Tag { ... }' blocks of a .plecs file: {'tag', 'props' [(key, value) in order], 'children'}."""
        root                        =   {'tag': None, 'props': [], 'children': []}
        stack                       =   [root]
        for line in lines:
            s                       =   line.strip()
            if s.endswith('{') and s[:-1].strip().isidentifier():
                node                =   {'tag': s[:-1].strip(), 'props': [], 'children': []}
                stack[-1]['children'].append(node)
                stack.append(node)
            elif s == '}' and len(stack) > 1:
                stack.pop()
            elif s and not s.startswith('"'):
                key, _, value       =   s.partition(' ')
                stack[-1]['props'].append((key, value.strip().strip('"')))
        return root

    @staticmethod
    def _prop(node, key):
        return next((v for k, v in node['props'] if k == key), None)

    def get_scopes(self,modelname,only=None):
        """
        Full PLECS paths ('PFC/Scopes/grid_scope', ...) of the Scope blocks of the model, found by walking the
        nested Component/Schematic blocks of the .plecs file, so scopes added/renamed in the model are picked up automatically.
        Commented-out blocks are skipped, and of a Configurable Subsystem only the active configuration is walked.
        only : optional list of scope names to keep (None = all scopes, [] = none).
        Scopes inside library references are not stored in the model file and are not found.
        """
        with open(self.path, encoding='utf-8', errors='ignore') as f:
            root                    =   self._parse_blocks(f.readlines())
        scopes                      =   []
        esc                         =   lambda name: name.replace('/', '//')

        def walk(node, parents):
            for child in node['children']:
                if child['tag'] != 'Component':
                    walk(child, parents)
                    continue
                if self._prop(child, 'CommentOut'):
                    continue
                kind, name          =   self._prop(child, 'Type'), self._prop(child, 'Name')
                if kind == 'Scope':
                    scopes.append('/'.join([modelname] + parents + [esc(name)]))
                elif kind == 'ConfigurableSubsystem':
                    configs         =   next((c for c in child['children'] if c['tag'] == 'Configurations'), None)
                    if configs is None:
                        continue
                    names           =   [v for k, v in configs['props'] if k == 'Name']
                    schematics      =   [c for c in configs['children'] if c['tag'] == 'Schematic']
                    active          =   next((self._prop(c, 'Value') for c in child['children']
                                              if c['tag'] == 'Parameter' and self._prop(c, 'Variable') == 'Configuration'), None)
                    if active is not None and active.isdigit() and 1 <= int(active) <= len(schematics):
                        selected    =   [schematics[int(active) - 1]]
                    elif active in names:
                        selected    =   [schematics[names.index(active)]]
                    else:                                                       # set by an expression: cannot tell offline
                        selected    =   schematics
                    for schematic in selected:
                        walk(schematic, parents + [esc(name)])
                else:
                    walk(child, parents + [esc(name)])

        walk(root, [])
        if only is not None:
            scopes                  =   [p for p in scopes if p.split('/')[-1] in only]
        return scopes

    def ClearAllTraces(self,scopelist):
        """Clear the traces of the scopes; scopes PLECS cannot find are skipped. Returns the scopes that exist."""
        found                       =   []
        for val in scopelist:
            try:
                self.server.plecs.scope(val,'ClearTraces')
                found.append(val)
            except xmlrpc.client.Fault as fault:
                print(f"WARNING: scope skipped: {fault.faultString}")
        return found

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
class Sweep:
    """Sweep points: nested ModelVars access, parallel batch sizing, output files of a run, sweep point generation."""

    @staticmethod
    def set_nested(d, path, value):
        for key in path[:-1]:
            d                      = d[key]
        d[path[-1]]                = value

    @staticmethod
    def get_nested(d, path):
        for key in path:
            d                      = d[key]
        return d

    @staticmethod
    def apply_configs(mdlvar, configs, config_paths):
        """Write block configurations {name: value} (e.g. a mode preset) to every ModelVars path of config_paths[name]."""
        for name, value in configs.items():
            for path in config_paths[name]:
                Sweep.set_nested(mdlvar, path, value)
        return mdlvar

    @staticmethod
    def auto_batch_size(n_points, max_parallel=None, reserve=1):
        """Sweep points per parallel batch, from the CPU threads available to this process (minus `reserve` left for the
        OS / PLECS GUI), capped by max_parallel, then balanced so the batches are as even as possible
        (e.g. 20 points on 15 threads -> 2 batches of 10 instead of 15 + 5)."""
        threads                    = (os.process_cpu_count() if hasattr(os, 'process_cpu_count') else os.cpu_count()) or 1
        workers                    = max(1, min(threads - reserve, max_parallel or threads, n_points))
        n_batches                  = math.ceil(n_points / workers)
        return math.ceil(n_points / n_batches)

    @staticmethod
    def set_output_files(mdlvar, paths, run_id, sim_idx):
        """Output files of one run of the sweep run_id, written in mdlvar[OUTPUT_KEY]."""
        out                        = mdlvar[OUTPUT_KEY]
        out['sim_idx']             = sim_idx
        out['utc_numeric']         = run_id
        out['ToFile_path']         = (paths.timeseries / f"Results_{run_id}_{sim_idx}.csv").as_posix()
        out['logfile']             = (paths.log  / f"Log_{run_id}.log").as_posix()
        out['output_html']         = (paths.html / f"Html_{run_id}.html").as_posix()
        out['Traces']              = paths.traces.as_posix()
        out['Mat']                 = paths.mat.as_posix()
        return mdlvar

    @staticmethod
    def build_points(base, sweep, sweep_paths, run_id, paths, update_derived=None):
        """One deep-copied ModelVars per combination of the sweep values, with derived parameters (update_derived(mv),
        optional, e.g. parameters.Derived.update) and output files updated. Returns a list of (label {sweep name: value}, ModelVars)."""
        points                     = []
        for sim_idx, values in enumerate(itertools.product(*sweep.values()), start=1):
            label                  = dict(zip(sweep, values))
            mv                     = copy.deepcopy(base)
            for name, value in label.items():
                for path in sweep_paths[name]:
                    Sweep.set_nested(mv, path, value)
            if update_derived:
                update_derived(mv)
            Sweep.set_output_files(mv, paths, run_id, sim_idx)
            points.append((label, mv))
        return points

#?----------------------------------------------------------------------------------------------------------------------------------------
