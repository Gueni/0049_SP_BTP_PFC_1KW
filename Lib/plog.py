#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?                  __
#?           ____  / /___  ____ _
#?          / __ \/ / __ \/ __ `/
#?         / /_/ / / /_/ / /_/ /
#?        / .___/_/\____/\__, /
#?       /_/            /____/
#?
#?
#? Name:        plog.py
#? Purpose:     Text logs of the simulation parameters (one log file per sweep). System independent.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     10/18/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import math

from   pplecs               import  OUTPUT_KEY
#?----------------------------------------------------------------------------------------------------------------------------------------
class PLog:
    """Parameter logs. ModelVars are nested dicts; a parameter is written as [key][subkey]... = value."""

    WIDTH               = 99                                                           # length of the section separators

    @staticmethod
    def flat(d, keys=()):
        """Yield (key path tuple, value) for every leaf of a nested dict."""
        for key, value in d.items():
            if isinstance(value, dict):
                yield from PLog.flat(value, keys + (key,))
            else:
                yield keys + (key,), value

    @staticmethod
    def _differs(a, b):
        """a != b, with a relative tolerance on numbers so rounding noise of derived parameters is not a change."""
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return not math.isclose(a, b, rel_tol=1e-9)
        return a != b

    @staticmethod
    def _key(keys):
        return "[" + "][".join(str(k) for k in keys) + "]"

    @staticmethod
    def _fmt(value):
        return f"{value:g}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)

    @staticmethod
    def params_lines(params):
        """All parameters of a nested dict (output files excluded), one '[a][b] = value' line each."""
        return ["{:<40}= {}".format(PLog._key(k), v) for k, v in PLog.flat(params) if k[0] != OUTPUT_KEY]

    @staticmethod
    def write_params(file_path, params, title="PARAMETERS"):
        """Write all parameters of a nested dict (e.g. the ModelVars of a single run) to file_path."""
        with open(file_path, 'w') as f:
            f.write("\n".join([title, "-" * PLog.WIDTH] + PLog.params_lines(params)) + "\n")
        return file_path

    @staticmethod
    def write_sweep_log(points, base, run_id):
        """One log file per sweep: the base parameters once, then one section per iteration with only the parameters
        that differ from the base (swept values and the derived parameters they change).
        points: list of (label, ModelVars) as built by pplecs.Sweep.build_points; the file is ModelVars[OUTPUT_KEY]['logfile']."""
        log_file            = points[0][1][OUTPUT_KEY]['logfile']
        base_flat           = dict(PLog.flat(base))
        lines               = [f"Sweep {run_id}: {len(points)} iterations", "=" * PLog.WIDTH, "BASE PARAMETERS", "-" * PLog.WIDTH]
        lines              += PLog.params_lines(base)
        for label, mv in points:
            swept           = ", ".join(f"{k}={PLog._fmt(v)}" for k, v in label.items())
            lines          += ["=" * PLog.WIDTH, f"ITERATION {mv[OUTPUT_KEY]['sim_idx']}/{len(points)} : {swept}",
                               f"results : {mv[OUTPUT_KEY]['ToFile_path']}", "-" * PLog.WIDTH]
            lines          += ["{:<40}= {:<24} (base: {})".format(PLog._key(k), str(v), base_flat.get(k))
                               for k, v in PLog.flat(mv) if k[0] != OUTPUT_KEY and PLog._differs(v, base_flat.get(k))]
        with open(log_file, 'w') as f:
            f.write("\n".join(lines) + "\n")
        return log_file
#?----------------------------------------------------------------------------------------------------------------------------------------
