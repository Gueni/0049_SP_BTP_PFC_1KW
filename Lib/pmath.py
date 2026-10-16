#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?                                     __  __
#?              ____  ____ ___  ____ _/ /_/ /_
#?             / __ \/ __ `__ \/ __ `/ __/ __ \
#?            / /_/ / / / / / / /_/ / /_/ / / /
#?           / .___/_/ /_/ /_/\__,_/\__/_/ /_/
#?          /_/
#?
#?
#? Name:        pmath.py
#? Purpose:     Compute rms, average, FFT ... and plot simulation results to HTML reports.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/15/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import  os
import  webbrowser
import  io
import  base64
import  screeninfo

import  numpy                       as      np
import  pandas                      as      pd
import  plotly.graph_objects        as      go
import  Model_Parameters            as      mdl

from    scipy.fft                   import  rfft, rfftfreq
from    plotly.subplots             import  make_subplots
from    PIL                         import  Image
#?----------------------------------------------------------------------------------------------------------------------------------------
class PMath:
    """Signal math and HTML report helpers for the PFC simulation results."""

    TOFILE_KEYS = ('sim_idx', 'utc_numeric', 'ToFile_path', 'logfile', 'output_html', 'Traces')

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Signal math
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def compute_fft(signal, fs):
        """Single-sided FFT of a signal sampled at fs. Returns (amplitude, phase [deg], frequency [Hz])."""
        signal              = np.asarray(signal, dtype=float)
        N                   = signal.size
        spectrum            = rfft(signal)[:N // 2]
        f                   = rfftfreq(N, 1 / fs)[:N // 2]
        amplitude           = np.abs(spectrum) * (2.0 / N)
        amplitude[0]       /= 2                                                        # DC is not doubled
        phase               = np.angle(spectrum, deg=True)
        return amplitude, phase, f

    @staticmethod
    def resample_signal(time, signal):
        """Linearly resample a signal onto uniformly spaced time points. Returns (new_time, new_signal)."""
        time                = np.asarray(time, dtype=float)
        new_time            = np.linspace(time[0], time[-1], len(signal))
        return new_time, np.interp(new_time, time, signal)

    @staticmethod
    def _time_mean(values, time_values):
        """Time-weighted mean of values over time_values (trapezoidal integration)."""
        time_values         = np.asarray(time_values, dtype=float)
        delta_T             = time_values[-1] - time_values[0]
        if delta_T == 0:
            raise ValueError("Time interval cannot be zero.")
        return np.trapezoid(values, x=time_values) / delta_T

    @staticmethod
    def compute_average(signal, time_values):
        """Average value of a signal over time_values."""
        return PMath._time_mean(np.asarray(signal, dtype=float), time_values)

    @staticmethod
    def compute_rms(signal, time_values):
        """RMS value of a signal over time_values."""
        return np.sqrt(PMath._time_mean(np.square(signal, dtype=float), time_values))

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Report helpers
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def png_to_hex_base64():
        """Model image resized to the screen and encoded as base64 PNG ('' if unavailable)."""
        img_path            = mdl.MODEL_IMG_PATH
        if not img_path.is_file():
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
                items.update(PMath.flatten_dict(v, new_key, sep))
            else:
                items[new_key] = v
        return items

    @staticmethod
    def extract_comments(filename):
        """Split each trailing '#?' comment (after code) into its 8-char unit field and the rest. Returns (units, comments)."""
        units, comments     = [], []
        with open(filename, 'r', encoding='utf-8') as file:
            for line in file:
                code, sep, comment = line.partition('#?')
                if sep and code.strip():
                    units.append(comment[:8])
                    comments.append(comment[8:].strip())
        return units, comments

    @staticmethod
    def _params_table(columns):
        """Plotly table with one header per key of columns and its values as cells."""
        return go.Figure(data=[go.Table(
            header          = dict(values=list(columns), fill_color='paleturquoise', align='left'),
            cells           = dict(values=list(columns.values()), fill_color='lavender', align='left'),
        )])

    @staticmethod
    def _write_html(html_file, title, figures, img_b64='', OPEN=False):
        """Write figures (first one loads plotly.js) to an HTML page, with an optional base64 PNG on top."""
        img                 = (f'<div class="center"><img src="data:image/png;base64,{img_b64}" alt="{mdl.MODEL_NAME}.png"></div>'
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
    #? Reports
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def gen_plots(resFile, html_file, OPEN=False, mdlvar=None):
        """Plot every waveform of the result CSV with a model parameter table into an HTML report.
        mdlvar: the ModelVars of this run (defaults to mdl.ModelVars), shown in the parameter table."""
        mdlvar              = mdl.ModelVars if mdlvar is None else mdlvar
        if not os.path.isfile(resFile):
            print(f"WARNING: result CSV not found, skipping HTML report: {resFile}\n"
                  f"         The model has no 'To File' block writing to ToFile.ToFile_path.")
            return
        df                  = pd.read_csv(resFile)
        n                   = len(mdl.Waveforms)
        fig                 = make_subplots(rows=n, cols=1, subplot_titles=tuple(mdl.Waveforms))
        for i, col in enumerate(df.columns[1:n + 1], start=1):
            fig.add_trace(go.Scatter(x=df.iloc[:, 0], y=df[col], mode='lines', name=mdl.Waveforms[i - 1]), row=i, col=1)
            fig.update_xaxes(title_text="Time [s]", row=i, col=1)
            fig.update_yaxes(title_text=mdl.Units[i - 1], row=i, col=1)
        fig.update_layout(
            plot_bgcolor    = '#e9f5f9',
            title           = dict(text="PFC WAVEFORMS", font=dict(family="Arial", size=30)),
            showlegend      = False,
            height          = 300 * n,
        )
        tofile              = mdlvar['ToFile']
        shown               = {k: (v if k != 'ToFile' else {kk: vv for kk, vv in v.items() if kk not in PMath.TOFILE_KEYS})
                               for k, v in mdlvar.items()}
        params              = PMath.flatten_dict(shown)
        units, comments     = PMath.extract_comments(mdl.__file__)
        table_fig           = PMath._params_table({"PARAMETERS": list(params.keys()), "VALUES": list(params.values()),
                                                   "UNITS": units, "COMMENTS": comments})
        title               = f"{mdl.MODEL_NAME}_{tofile['utc_numeric']}_{tofile['sim_idx']}_MOHAMED_GUENI"
        PMath._write_html(html_file, title, [fig, table_fig], PMath.png_to_hex_base64(), OPEN)

    @staticmethod
    def plot_ac_analysis_sweep(results_list, html_file, OPEN=False):
        """Plot magnitude (Gr) and phase (Gi) of each AC sweep result in results_list on log-frequency axes."""
        fig                 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.20,
                                            subplot_titles=('Magnitude (Gr)', 'Phase (Gi)'))
        for idx, data in enumerate(results_list, start=1):
            fig.add_trace(go.Scatter(x=data['F'], y=data['Gr'][0], mode='lines', name=f'Magnitude (Gr) Iteration {idx}'), row=1, col=1)
            fig.add_trace(go.Scatter(x=data['F'], y=data['Gi'][0], mode='lines', name=f'Phase (Gi) Iteration {idx}'), row=2, col=1)
        fig.update_layout(
            autosize        = True,
            title_text      = 'AC Sweep Analysis',
            yaxis_title     = 'Magnitude (dB)',
            yaxis2_title    = 'Phase (deg)',
            margin          = dict(l=50, r=50, t=100, b=50),
            height          = 600,
        )
        fig.update_xaxes(type='log', title_text='Frequency (Hz)')
        params              = PMath.flatten_dict(mdl.AnalysisOpts)
        table_fig           = PMath._params_table({"PARAMETERS": list(params.keys()), "VALUES": list(params.values())})
        tofile              = mdl.ModelVars['ToFile']
        title               = f"AC Sweep Analysis_{tofile['utc_numeric']}_{tofile['sim_idx']}_MOHAMED_GUENI"
        PMath._write_html(html_file, title, [fig, table_fig], OPEN=OPEN)
#?----------------------------------------------------------------------------------------------------------------------------------------
