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
import xmlrpc.client
import subprocess
import shutil
import os
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
    
    def ClearAllTraces(self,scopelist):
        for val in scopelist:
            self.server.plecs.scope(val,'ClearTraces')

    def Set_sim_param(self,mdlvars):
        self.modelvar = mdlvars
        # self.opts =  {'ModelVars' :  self.modelvar} 
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