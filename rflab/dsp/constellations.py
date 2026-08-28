"""Ideal constellation point sets, all normalised to unit average power.

Unit average power is the convention used throughout the lab: it makes SNR
mean the same thing for every modulation, and it makes the minimum distance
d_min directly comparable across schemes.  That comparability is the whole
reason 64-QAM collapses under noise that QPSK shrugs off.
"""
import numpy as np


def _norm(points: np.ndarray) -> np.ndarray:
    p = np.asarray(points, dtype=complex)
    return p / np.sqrt(np.mean(np.abs(p) ** 2))


def psk(m: int) -> np.ndarray:
    k = np.arange(m)
    # Offset by pi/M for even M so that QPSK sits on the diagonals (the usual
    # textbook / RadioML orientation) and BPSK stays on the real axis.
    off = np.pi / m if m > 2 else 0.0
    return _norm(np.exp(1j * (2 * np.pi * k / m + off)))


def qam_square(m: int) -> np.ndarray:
    side = int(round(np.sqrt(m)))
    if side * side != m:
        raise ValueError(f"{m}-QAM is not a perfect square")
    levels = np.arange(-(side - 1), side, 2)
    i, q = np.meshgrid(levels, levels)
    return _norm((i + 1j * q).ravel())


def pam(m: int) -> np.ndarray:
    levels = np.arange(-(m - 1), m, 2)
    return _norm(levels.astype(complex))


def ask(m: int) -> np.ndarray:
    """Unipolar ASK: amplitude levels 0..M-1 on the real axis. M=2 is OOK."""
    return _norm(np.arange(m).astype(complex))


def apsk(m: int) -> np.ndarray:
    """DVB-S2 style amplitude-and-phase shift keying on concentric rings."""
    if m == 16:
        rings = [(4, 1.0, np.pi / 4), (12, 2.85, 0.0)]
    elif m == 32:
        rings = [(4, 1.0, np.pi / 4), (12, 2.84, 0.0), (16, 5.27, np.pi / 16)]
    elif m == 64:
        rings = [(4, 1.0, np.pi / 4), (12, 2.73, 0.0),
                 (20, 4.52, np.pi / 20), (28, 6.31, 0.0)]
    else:
        raise ValueError(f"unsupported APSK order {m}")
    pts = []
    for n, r, ph in rings:
        pts.extend(r * np.exp(1j * (2 * np.pi * np.arange(n) / n + ph)))
    return _norm(np.array(pts))


def min_distance(points: np.ndarray) -> float:
    """Smallest Euclidean gap between any two constellation points."""
    p = np.asarray(points)
    if len(p) < 2:
        return float("inf")
    d = np.abs(p[:, None] - p[None, :])
    np.fill_diagonal(d, np.inf)
    return float(d.min())


def peak_to_avg(points: np.ndarray) -> float:
    p = np.asarray(points)
    return float(np.max(np.abs(p) ** 2) / np.mean(np.abs(p) ** 2))
