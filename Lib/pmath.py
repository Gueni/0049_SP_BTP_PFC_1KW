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
import  plotly.colors               as      pc
import  Model_Parameters            as      mdl

from    scipy.fft                   import  rfft, rfftfreq
from    plotly.subplots             import  make_subplots
from    PIL                         import  Image
#?----------------------------------------------------------------------------------------------------------------------------------------
class PMath:
    """Signal math and HTML report helpers for the PFC simulation results."""

    TOFILE_KEYS         = ('sim_idx', 'utc_numeric', 'ToFile_path', 'logfile', 'output_html', 'Traces')
    PLOT_BUCKETS        = 2500                                                         # time-domain min/max bins per trace
    N_HARMONICS         = 50                                                           # harmonic orders shown in the harmonic bar plots
    HARMONIC_CYCLES     = 5                                                            # last fundamental cycles used for the harmonic analysis

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
    def compute_harmonics(t, Y, f0, n_harmonics, n_cycles):
        """Amplitudes of harmonic orders 1..n_harmonics of each column of Y, from the last whole fundamental cycles
        (up to n_cycles) resampled uniformly, so that harmonic k falls exactly on an FFT bin. Returns (orders, H) or None."""
        cycles              = min(n_cycles, int((t[-1] - t[0]) * f0 + 1e-9))
        if cycles < 1:
            return None
        window              = cycles / f0
        N                   = max(int(np.sum(t >= t[-1] - window)), 4 * n_harmonics * cycles)
        t_u                 = t[-1] - window + np.arange(N) * (window / N)             # endpoint excluded: one exact period set
        Y_u                 = np.column_stack([np.interp(t_u, t, Y[:, k]) for k in range(Y.shape[1])])
        spectrum            = np.abs(rfft(Y_u, axis=0)) * (2.0 / N)
        orders              = np.arange(1, n_harmonics + 1)
        return orders, spectrum[orders * cycles]

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
    def _envelope(x, Y, n_buckets, log=False):
        """Min/max envelope of the columns of Y over n_buckets equal-width (or log-width) bins of the sorted x.
        Keeps switching ripple / spectral peaks visible with ~2*n_buckets points. Returns (x_env, Y_env)."""
        if len(x) <= 2 * n_buckets:
            return x, Y
        edges               = (np.geomspace(x[0], x[-1], n_buckets + 1) if log else np.linspace(x[0], x[-1], n_buckets + 1))[:-1]
        idx                 = np.unique(np.searchsorted(x, edges))
        Y_env               = np.empty((2 * len(idx), Y.shape[1]))
        Y_env[0::2]         = np.minimum.reduceat(Y, idx, axis=0)
        Y_env[1::2]         = np.maximum.reduceat(Y, idx, axis=0)
        return np.repeat(x[idx], 2), Y_env

    @staticmethod
    def _load_run(resFile, n, f0):
        """Time-domain envelopes and harmonic amplitudes (fundamental f0) of the n waveforms of one result CSV (None if missing)."""
        if not os.path.isfile(resFile):
            print(f"WARNING: result CSV not found, skipped in the HTML report: {resFile}. "f"The model has no 'To File' block writing to ToFile.ToFile_path.")
            return None
        data                = pd.read_csv(resFile, header=None, usecols=range(n + 1), dtype=float).to_numpy()
        t, Y                = data[:, 0], data[:, 1:]
        t_env, Y_env        = PMath._envelope(t, Y, PMath.PLOT_BUCKETS)
        harmonics           = PMath.compute_harmonics(t, Y, f0, PMath.N_HARMONICS, PMath.HARMONIC_CYCLES)
        if harmonics is None:
            print(f"WARNING: less than one {f0:g} Hz cycle saved in {resFile}, no harmonic plot for it.")
        return t_env, Y_env, harmonics

    @staticmethod
    def _run_name(label, mv, varied):
        """Legend name of a sweep point: '#idx k1=v1, k2=v2' over the varied sweep parameters."""
        fmt                 = lambda v: f"{v:g}" if isinstance(v, (int, float)) else str(v)
        return f"#{mv['ToFile']['sim_idx']} " + ", ".join(f"{k}={fmt(label[k])}" for k in varied)

    @staticmethod
    def gen_sweep_plots(points, html_file, OPEN=False):
        """One HTML report for the whole sweep: for each waveform a time-domain figure then its harmonic bar plot,
        every sweep point overlaid (one colour + legend entry per point), then a parameter table (one column per point).
        points: list of (label, ModelVars) as built by plecs.build_points."""
        n                   = len(mdl.Waveforms)
        labels              = [label for label, _ in points]
        varied              = [k for k in labels[0] if len({str(l[k]) for l in labels}) > 1] or list(labels[0])
        colors              = pc.qualitative.Dark24
        runs                = []
        for i, (label, mv) in enumerate(points):
            res             = PMath._load_run(mv['ToFile']['ToFile_path'], n, mv['Grid']['f'])
            if res is not None:
                runs.append((PMath._run_name(label, mv, varied), colors[i % len(colors)], res))
        f0_text             = " / ".join(f"{f:g}" for f in sorted({mv['Grid']['f'] for _, mv in points}))
        if not runs:
            print("WARNING: no result CSV found, HTML report not written.")
            return
        figures             = []
        for k, (wave, unit) in enumerate(zip(mdl.Waveforms, mdl.Units)):
            fig_t, fig_f    = go.Figure(), go.Figure()
            for name, color, (t, Y, harmonics) in runs:
                fig_t.add_trace(go.Scatter(x=t, y=Y[:, k], mode='lines', name=name, line=dict(color=color, width=1)))
                if harmonics is not None:
                    orders, H = harmonics
                    fig_f.add_trace(go.Bar(x=orders, y=H[:, k], name=name, marker_color=color))
            fig_t.update_layout(title=wave, xaxis_title="Time [s]", yaxis_title=unit)
            fig_f.update_layout(title=f"{wave} - Harmonics (f0 = {f0_text} Hz)", xaxis_title="Harmonic order",
                                yaxis_title=f"Amplitude {unit}", barmode='group', bargap=0.15)
            fig_f.update_xaxes(tickmode='linear', tick0=1, dtick=1)
            for fig in (fig_t, fig_f):
                fig.update_layout(plot_bgcolor='#e9f5f9', height=450, showlegend=True)
            figures        += [fig_t, fig_f]
        shown               = lambda mv: {k: (v if k != 'ToFile' else {kk: vv for kk, vv in v.items() if kk not in PMath.TOFILE_KEYS})
                                          for k, v in mv.items()}
        params              = [PMath.flatten_dict(shown(mv)) for _, mv in points]
        units, comments     = PMath.extract_comments(mdl.__file__)
        columns             = {"PARAMETERS": list(params[0].keys()), "UNITS": units, "COMMENTS": comments}
        columns.update({f"#{mv['ToFile']['sim_idx']}": list(p.values()) for p, (_, mv) in zip(params, points)})
        table_fig           = PMath._params_table(columns)
        table_fig.update_layout(height=900)
        tofile              = points[0][1]['ToFile']
        title               = f"{mdl.MODEL_NAME}_{tofile['utc_numeric']}_SWEEP_MOHAMED_GUENI"
        PMath._write_html(html_file, title, figures + [table_fig], PMath.png_to_hex_base64(), OPEN)

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
