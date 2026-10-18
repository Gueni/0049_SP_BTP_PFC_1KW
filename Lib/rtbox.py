#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?              ____  ______   ____
#?             / __ \/_  __/  / __ )____  _  __
#?            / /_/ / / /    / __  / __ \| |/_/
#?           / _, _/ / /    / /_/ / /_/ />  <
#?          /_/ |_| /_/    /_____/\____/_/|_|
#?
#?
#? Name:        rtbox.py
#? Purpose:     PLECS Coder code generation and PLECS RT Box workflow (upload, start, set values, capture data, stop).
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     10/18/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import glob
import os
import time
import xmlrpc.client
#?----------------------------------------------------------------------------------------------------------------------------------------
class RTBox:
    """
    Code generation goes through PLECS (plecs_server = the simpy connection), the hardware calls go to the RT Box's
    own XML-RPC server (rtbox_url, e.g. http://192.168.0.10:9998/RPC2), which is only contacted by connect().
    codegen_target is the subsystem with 'Enable code generation' checked (Target I/O blocks must sit on its top level).
    """

    def __init__(self,plecs_server,modelname,codegen_target,output_dir,rtbox_url=''):
        self.plecs                  =   plecs_server
        self.modelname              =   modelname
        self.codegen_target         =   codegen_target
        self.output_dir             =   str(output_dir)
        self.rtbox_url              =   rtbox_url
        self.server                 =   None
        self.elf                    =   None

    def generate_code(self,modelvars):
        """Run PLECS Coder on modelname/codegen_target with the given ModelVars, return the generated .elf path (None for non-RT Box targets)."""
        if not self.codegen_target:
            raise ValueError("CODEGEN_TARGET is empty: set it to the subsystem that has 'Enable code generation' checked.")
        os.makedirs(self.output_dir, exist_ok=True)
        target                      =   f"{self.modelname}/{self.codegen_target}"
        t0                          =   time.time()
        print(f"Generating code for {target} -> {self.output_dir}")
        self.plecs.plecs.codegen(target, {'ModelVars': modelvars}, self.output_dir)
        # The .elf base name depends on the model's Coder options, so take the one written by this build
        elfs                        =   [f for f in glob.glob(os.path.join(self.output_dir, '*.elf')) if os.path.getmtime(f) >= t0 - 1]
        self.elf                    =   max(elfs, key=os.path.getmtime) if elfs else None
        print(f"Code generated in {time.time() - t0:.1f} s" + (f": {self.elf}" if self.elf else " (no .elf produced)"))
        return self.elf

    def connect(self):
        if not self.rtbox_url:
            raise ValueError("RTBOX_URL is empty: set it to http://<rtbox-ip>:9998/RPC2.")
        self.server                 =   xmlrpc.client.ServerProxy(self.rtbox_url)

    def upload(self,elf=None):
        elf                         =   elf or self.elf
        if not elf or not os.path.isfile(elf):
            raise FileNotFoundError(f"No executable to upload: {elf}")
        print(f"Uploading {elf}")
        with open(elf, 'rb') as f:
            self.server.rtbox.load(xmlrpc.client.Binary(f.read()))

    def start(self):
        self.server.rtbox.start()
        print("RT Box running.")

    def stop(self):
        self.server.rtbox.stop()
        print("RT Box stopped.")

    def reboot(self):
        self.server.rtbox.reboot()

    def query(self):
        return self.server.rtbox.querySimulation()

    def log(self):
        return self.server.rtbox.getApplicationLog()

    def list_blocks(self):
        """(Programmable Value block names, Data Capture block names) of the running model."""
        return self.server.rtbox.getProgrammableValueBlocks(), self.server.rtbox.getDataCaptureBlocks()

    def set_value(self,block,values):
        self.server.rtbox.setProgrammableValue(block, [float(v) for v in values])

    def get_capture(self,blocks,poll_interval=1.0,timeout=None):
        """Wait for a trigger on the first Data Capture block, then read all of them: {block: data}."""
        t0                          =   time.time()
        while self.server.rtbox.getCaptureTriggerCount(blocks[0]) == 0:
            if timeout is not None and time.time() - t0 >= timeout:
                raise TimeoutError(f"No trigger on {blocks[0]} after {timeout} s.")
            time.sleep(poll_interval)
        return {block: self.server.rtbox.getCaptureData(block) for block in blocks}

    def run(self,set_values=None,capture_blocks=None,poll_interval=1.0,timeout=None):
        """Upload the generated .elf, start it, write set_values {block: [values]}, read capture_blocks, always stop."""
        self.connect()
        self.upload()
        captured                    =   {}
        self.start()
        try:
            inputs, outputs         =   self.list_blocks()
            print(f"Programmable Value blocks: {inputs}\nData Capture blocks      : {outputs}")
            for block, values in (set_values or {}).items():
                self.set_value(block, values)
            if capture_blocks:
                captured            =   self.get_capture(capture_blocks, poll_interval, timeout)
        except Exception:
            try:
                print(f"RT Box application log: {self.log()}")
            except Exception:
                pass
            raise
        finally:
            self.stop()
        return captured

#?----------------------------------------------------------------------------------------------------------------------------------------
