#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?                          __      __
#?            ____  ____  / /___  / /______
#?           / __ \/ __ \/ / __ \/ __/ ___/
#?          / /_/ / /_/ / / /_/ / /_(__  )
#?         / .___/ .___/_/\____/\__/____/
#?        /_/   /_/
#?
#?
#? Name:        pplots.py
#? Purpose:     Plot simulation results to HTML reports (time-domain waveforms, harmonic spectra, parameter tables).
#?              System independent: waveform names, fundamental, model name/image are passed in by the caller.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     10/18/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import  os
import  re
import  webbrowser
import  io
import  base64
import  screeninfo

import  numpy                       as      np
import  pandas                      as      pd
import  plotly.graph_objects        as      go
import  plotly.colors               as      pc

from    pathlib                     import  Path
from    plotly.subplots             import  make_subplots
from    PIL                         import  Image
from    pmath                       import  PMath
from    pplecs                      import  OUTPUT_KEY, OUTPUT_FIELDS, get_nested
#?----------------------------------------------------------------------------------------------------------------------------------------
class PPlots:
    """HTML reports of simulation results."""

    PLOT_BUCKETS        = 2500                                                         # time-domain min/max bins per trace
    N_HARMONICS         = 50                                                           # harmonic orders shown in the harmonic bar plots
    HARMONIC_CYCLES     = 5                                                            # last fundamental cycles used for the harmonic analysis
    UNIT_KEYWORDS       = {                                                            # waveform name keyword -> unit (first match wins)
                            'voltage'       : '[ V ]',
                            'current'       : '[ A ]',
                            'temperature'   : '[ C ]',
                            'losses'        : '[ W ]',
                            'power'         : '[ W ]',
                            'signal'        : '[ V ]',
                          }

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Helpers
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def units_from_names(waveforms):
        """Unit of each waveform guessed from a keyword of its name ('[ Unknown ]' if none matches)."""
        return [next((u for kw, u in PPlots.UNIT_KEYWORDS.items() if kw in w.lower()), '[ Unknown ]') for w in waveforms]

    @staticmethod
    def png_to_hex_base64(img_path):
        """Image resized to the screen and encoded as base64 PNG ('' if unavailable)."""
        if not img_path or not Path(img_path).is_file():
            print(f"Model image not found: {img_path}")
            return ''
        screen              = screeninfo.get_monitors()[0]
        size                = (int(screen.width * 0.5), int(screen.height * 0.4))
        try:
            with Image.open(img_path) as img:
                buffer      = io.BytesIO()
                img.resize(size, resample=Image.LANCZOS).save(buffer, format="PNG")
        except OSError:
            print("Unable to resize image")
            return ''
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def flatten_dict(d, parent_key='', sep='.'):
        """Flatten a nested dict into {'a.b.c': value}."""
        items               = {}
        for k, v in d.items():
            new_key         = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(PPlots.flatten_dict(v, new_key, sep))
            else:
                items[new_key] = v
        return items

    @staticmethod
    def extract_comments(filename):
        """Unit and comment of each parameter of a parameters file, keyed by its dotted path ('Grid.Vin', 'PFC.Choke.L1').
        The path follows the dict nesting of the file: a top-level 'Grid = {' is 'Grid', an entry "'Choke' : {" inside it
        is 'PFC.Choke' (so top-level dict names must be the ModelVars keys). The trailing '#?' comment of an entry is split
        into its 8-char unit field and the rest. Returns {path: (unit, comment)}."""
        found               = {}
        stack               = []
        with open(filename, 'r', encoding='utf-8') as file:
            for line in file:
                code, sep, comment = line.partition('#?')
                code        = code.split('#')[0].strip()
                top         = re.match(r"^(\w+)\s*=\s*\{", code)
                entry       = re.match(r"^'([^']+)'\s*:\s*(.*)$", code)
                if top:
                    stack   = [top.group(1)]
                elif entry and stack:
                    if entry.group(2).startswith('{'):
                        stack.append(entry.group(1))
                    elif sep:
                        found['.'.join(stack + [entry.group(1)])] = (comment[:8].strip(), comment[8:].strip())
                if code.startswith('}') and stack:
                    stack.pop()
        return found

    @staticmethod
    def _params_table(columns):
        """Plotly table with one header per key of columns and its values as cells."""
        return go.Figure(data=[go.Table(
            header          = dict(values=list(columns), fill_color='paleturquoise', align='left'),
            cells           = dict(values=list(columns.values()), fill_color='lavender', align='left'),
        )])

    @staticmethod
    def write_html(html_file, title, figures, img_b64='', OPEN=False):
        """Write figures (first one loads plotly.js) to an HTML page, with an optional base64 PNG on top."""
        img                 = (f'<div class="center"><img src="data:image/png;base64,{img_b64}" alt="{title}"></div>'
                               if img_b64 else '')
        plots               = ''.join(fig.to_html(full_html=False, include_plotlyjs='cdn' if i == 0 else False)
                                      for i, fig in enumerate(figures))
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>.center {{display: flex; justify-content: center;}}</style>
</head>
<body>
{img}
{plots}
</body>
</html>
""")
        if OPEN:
            webbrowser.open(html_file)

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Sweep report
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def format_hz(f):
        """50 -> '50 Hz', 80000 -> '80 kHz'."""
        for scale, prefix in ((1e9, 'G'), (1e6, 'M'), (1e3, 'k')):
            if abs(f) >= scale:
                return f"{f / scale:g} {prefix}Hz"
        return f"{f:g} Hz"

    @staticmethod
    def waveform_f0_paths(waveforms, f0_path=None, f0_overrides=None):
        """Key path of the fundamental of each waveform: the first f0_overrides keyword found in its name, else f0_path."""
        overrides           = f0_overrides or {}
        return [next((p for kw, p in overrides.items() if kw.lower() in w.lower()), f0_path) for w in waveforms]

    @staticmethod
    def _load_run(resFile, n, f0s=None):
        """Time-domain envelopes and harmonic amplitudes of the n waveforms of one result CSV (None if missing).
        f0s: fundamental of each waveform (None = no harmonics for it). The analysis window is the last whole cycles
        of the lowest fundamental, so every fundamental of the run is analysed over the same span."""
        if not os.path.isfile(resFile):
            print(f"WARNING: result CSV not found, skipped in the HTML report: {resFile}. "
                  f"The model has no 'To File' block writing to {OUTPUT_KEY}.ToFile_path.")
            return None
        data                = pd.read_csv(resFile, header=None, usecols=range(n + 1), dtype=float).to_numpy()
        t, Y                = data[:, 0], data[:, 1:]
        t_env, Y_env        = PMath.envelope(t, Y, PPlots.PLOT_BUCKETS)
        f0s                 = f0s or [None] * n
        harmonics           = [None] * n
        f_base              = min((f for f in f0s if f), default=None)
        window              = PMath.harmonic_window(t, f_base, PPlots.HARMONIC_CYCLES) if f_base else None
        if f_base and window is None:
            print(f"WARNING: less than one {PPlots.format_hz(f_base)} cycle saved in {resFile}, no harmonic plots for it.")
        if window:
            harmonics       = [PMath.compute_harmonics(t, Y[:, k], f0, PPlots.N_HARMONICS, window) if f0 else None
                               for k, f0 in enumerate(f0s)]
        return t_env, Y_env, harmonics

    @staticmethod
    def _run_name(label, mv, varied):
        """Legend name of a sweep point: '#idx k1=v1, k2=v2' over the varied sweep parameters."""
        fmt                 = lambda v: f"{v:g}" if isinstance(v, (int, float)) else str(v)
        return f"#{mv[OUTPUT_KEY]['sim_idx']} " + ", ".join(f"{k}={fmt(label[k])}" for k in varied)

    @staticmethod
    def gen_sweep_plots(points, waveforms, units=None, f0_path=None, f0_overrides=None, model_name='', img_path=None, params_file=None, OPEN=False):
        """One HTML report for the whole sweep, written to ModelVars[OUTPUT_KEY]['output_html']: for each waveform a
        time-domain figure then its harmonic bar plot, every sweep point overlaid (one colour + legend entry per point),
        then a parameter table (one column per point).

        *Args:
            points      : list of (label, ModelVars) as built by pplecs.build_points.
            waveforms   : names of the result CSV columns after time, in order.
            units       : unit of each waveform; None = guessed from the names (units_from_names).
            f0_path     : key path of the fundamental frequency in ModelVars, e.g. ('Grid', 'f'); None = no harmonic plots.
            f0_overrides: {waveform name keyword: key path} for waveforms with their own fundamental, e.g. {'HS1': ('CTRL', 'fsw')}.
            model_name  : used in the page title.
            img_path    : image shown on top of the report (optional).
            params_file : file whose '#?' comments give the unit/comment columns of the parameter table (optional).
        """
        n                   = len(waveforms)
        units               = units or PPlots.units_from_names(waveforms)
        labels              = [label for label, _ in points]
        varied              = [k for k in labels[0] if len({str(l[k]) for l in labels}) > 1] or list(labels[0])
        colors              = pc.qualitative.Dark24
        f0_paths            = PPlots.waveform_f0_paths(waveforms, f0_path, f0_overrides)
        f0s                 = [[get_nested(mv, p) if p else None for p in f0_paths] for _, mv in points]   # [run][waveform]
        runs                = []
        for i, ((label, mv), run_f0s) in enumerate(zip(points, f0s)):
            res             = PPlots._load_run(mv[OUTPUT_KEY]['ToFile_path'], n, run_f0s)
            if res is not None:
                runs.append((PPlots._run_name(label, mv, varied), colors[i % len(colors)], res))
        if not runs:
            print("WARNING: no result CSV found, HTML report not written.")
            return
        figures             = []
        for k, (wave, unit) in enumerate(zip(waveforms, units)):
            fig_t           = go.Figure()
            fig_h           = go.Figure()
            for name, color, (t, Y, harmonics) in runs:
                fig_t.add_trace(go.Scatter(x=t, y=Y[:, k], mode='lines', name=name, line=dict(color=color, width=1)))
                if harmonics[k] is not None:
                    orders, H = harmonics[k]
                    fig_h.add_trace(go.Bar(x=orders, y=H, name=name, marker_color=color))
            f0_text         = " / ".join(PPlots.format_hz(f) for f in sorted({run_f0s[k] for run_f0s in f0s if run_f0s[k]}))
            f0_name         = f"{'.'.join(map(str, f0_paths[k]))} = {f0_text}" if f0_paths[k] else ''
            fig_t.update_layout(title=wave, xaxis_title="Time [s]", yaxis_title=unit)
            fig_h.update_layout(title=f"{wave} - Harmonics (f0: {f0_name})", xaxis_title="Harmonic order",
                                yaxis_title=f"Amplitude {unit}", barmode='group', bargap=0.15)
            fig_h.update_xaxes(tickmode='linear', tick0=1, dtick=1)
            wave_figs       = [fig_t] + ([fig_h] if fig_h.data else [])
            for fig in wave_figs:
                fig.update_layout(plot_bgcolor='#e9f5f9', height=450, showlegend=True)
            figures        += wave_figs
        shown               = lambda mv: {k: (v if k != OUTPUT_KEY else {kk: vv for kk, vv in v.items() if kk not in OUTPUT_FIELDS})
                                          for k, v in mv.items()}
        params              = [PPlots.flatten_dict(shown(mv)) for _, mv in points]
        names               = list(params[0].keys())
        fmt                 = lambda v: f"{v:g}" if isinstance(v, float) else str(v)
        values              = [" / ".join(dict.fromkeys(fmt(p[name]) for p in params)) for name in names]   # swept: 'a / b / c'
        columns             = {"PARAMETERS": names}
        if params_file:
            notes           = PPlots.extract_comments(params_file)
            columns.update({"UNITS": [notes.get(name, ('', ''))[0] for name in names],
                            "COMMENTS": [notes.get(name, ('', ''))[1] for name in names]})
        columns["VALUE"]    = values
        table_fig           = PPlots._params_table(columns)
        table_fig.update_layout(height=900)
        out                 = points[0][1][OUTPUT_KEY]
        title               = f"{model_name}_{out['utc_numeric']}_SWEEP_MOHAMED_GUENI"
        PPlots.write_html(out['output_html'], title, figures + [table_fig], PPlots.png_to_hex_base64(img_path), OPEN)

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? AC analysis report
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def plot_ac_analysis_sweep(results_list, html_file, analysis_opts, title='AC Sweep Analysis', OPEN=False):
        """Plot magnitude (Gr) and phase (Gi) of each AC sweep result in results_list on log-frequency axes,
        with the analysis options as a table."""
        fig                 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.20,
                                            subplot_titles=('Magnitude (Gr)', 'Phase (Gi)'))
        for idx, data in enumerate(results_list, start=1):
            fig.add_trace(go.Scatter(x=data['F'], y=data['Gr'][0], mode='lines', name=f'Magnitude (Gr) Iteration {idx}'), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['F'], y=data['Gi'][0], mode='lines', name=f'Phase (Gi) Iteration {idx}'), row=2, col=1)
        fig.update_layout(
            autosize        = True,
            title_text      = title,
            yaxis_title     = 'Magnitude (dB)',
            yaxis2_title    = 'Phase (deg)',
            margin          = dict(l=50, r=50, t=100, b=50),
            height          = 600,
        )
        fig.update_xaxes(type='log', title_text='Frequency (Hz)')
        params              = PPlots.flatten_dict(analysis_opts)
        table_fig           = PPlots._params_table({"PARAMETERS": list(params.keys()), "VALUES": list(params.values())})
        PPlots.write_html(html_file, f"{title}_MOHAMED_GUENI", [fig, table_fig], OPEN=OPEN)
#?----------------------------------------------------------------------------------------------------------------------------------------
