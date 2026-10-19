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
#? Purpose:     Signal math: rms, average, FFT, harmonics, min/max envelope. System independent.
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     09/15/2024
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import  numpy                       as      np

from    scipy.fft                   import  rfft, rfftfreq
#?----------------------------------------------------------------------------------------------------------------------------------------
class PMath:
    """Signal math on simulation results."""

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
    def harmonic_window(t, f_base, n_cycles):
        """Length [s] of the last whole f_base cycles of t (up to n_cycles), None if less than one cycle is saved."""
        cycles              = min(n_cycles, int((t[-1] - t[0]) * f_base + 1e-9))
        return cycles / f_base if cycles >= 1 else None

    @staticmethod
    def compute_harmonics(t, y, f0, n_harmonics, window):
        """Amplitudes of harmonic orders 1..n_harmonics of f0 in the signal y(t), over its last `window` seconds
        resampled uniformly (fine enough for the highest order). Harmonic k is read at bin k*f0*window, exact when the
        window holds a whole number of f0 periods (e.g. 80 kHz over whole 50 Hz cycles). Returns (orders, H)."""
        N                   = max(int(np.sum(t >= t[-1] - window)), int(4 * n_harmonics * f0 * window))
        t_u                 = t[-1] - window + np.arange(N) * (window / N)             # endpoint excluded: one exact period set
        spectrum            = np.abs(rfft(np.interp(t_u, t, y))) * (2.0 / N)
        orders              = np.arange(1, n_harmonics + 1)
        return orders, spectrum[np.rint(orders * f0 * window).astype(int)]

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

    @staticmethod
    def envelope(x, Y, n_buckets, log=False):
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
#?----------------------------------------------------------------------------------------------------------------------------------------
