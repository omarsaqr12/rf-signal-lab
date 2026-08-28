"""Pulse-shaping filters.

Root-raised-cosine is the workhorse for linear modulations (PSK/QAM/PAM/APSK).
Gaussian frequency pulses are used by GFSK/GMSK.
"""
import numpy as np


def rrc_taps(beta: float, sps: int, span_symbols: int = 12) -> np.ndarray:
    """Root-raised-cosine impulse response, unit-energy.

    beta : roll-off (0 = brick wall, 1 = widest)
    sps  : samples per symbol
    span_symbols : filter length in symbol periods (even number preferred)
    """
    n_taps = int(span_symbols * sps)
    if n_taps % 2 == 0:
        n_taps += 1
    t = (np.arange(n_taps) - (n_taps - 1) / 2.0) / float(sps)
    h = np.zeros_like(t)

    # Handle the three analytic cases separately to avoid 0/0.
    eps = 1e-8
    b = max(beta, 0.0)

    # t == 0
    i0 = np.abs(t) < eps
    h[i0] = 1.0 - b + 4.0 * b / np.pi

    if b > eps:
        # t == +/- 1/(4 beta)
        ic = np.abs(np.abs(t) - 1.0 / (4.0 * b)) < eps
        h[ic] = (b / np.sqrt(2.0)) * (
            (1 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * b))
            + (1 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * b))
        )
    else:
        ic = np.zeros_like(t, dtype=bool)

    rest = ~(i0 | ic)
    tr = t[rest]
    num = np.sin(np.pi * tr * (1 - b)) + 4.0 * b * tr * np.cos(np.pi * tr * (1 + b))
    den = np.pi * tr * (1.0 - (4.0 * b * tr) ** 2)
    h[rest] = num / den

    h = h / np.sqrt(np.sum(h ** 2))
    return h


def rect_taps(sps: int) -> np.ndarray:
    h = np.ones(sps)
    return h / np.sqrt(np.sum(h ** 2))


def gaussian_freq_pulse(bt: float, sps: int, span_symbols: int = 4) -> np.ndarray:
    """Gaussian frequency pulse g[n] used by GFSK / GMSK.

    Normalised so that sum(g) = 1, i.e. each symbol contributes exactly one
    unit of frequency-pulse area (so the modulation index is preserved).
    """
    n_taps = int(span_symbols * sps)
    if n_taps % 2 == 0:
        n_taps += 1
    t = (np.arange(n_taps) - (n_taps - 1) / 2.0) / float(sps)
    alpha = np.sqrt(np.log(2.0) / 2.0) / max(bt, 1e-3)
    g = (1.0 / (np.sqrt(2 * np.pi) * alpha)) * np.exp(-(t ** 2) / (2 * alpha ** 2))
    s = np.sum(g)
    return g / s if s > 0 else g


def upsample(symbols: np.ndarray, sps: int) -> np.ndarray:
    up = np.zeros(len(symbols) * sps, dtype=complex)
    up[::sps] = symbols
    return up


def pulse_shape(symbols: np.ndarray, sps: int, beta: float,
                span_symbols: int = 12, shape: str = "rrc"):
    """Upsample + pulse shape. Returns (waveform, taps, group_delay_samples)."""
    if shape == "rect":
        taps = rect_taps(sps)
    else:
        taps = rrc_taps(beta, sps, span_symbols)
    up = upsample(symbols, sps)
    y = np.convolve(up, taps, mode="full")
    gd = (len(taps) - 1) // 2
    return y, taps, gd
