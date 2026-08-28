"""Baseband modulators.

Every modulator returns a `Signal` describing one frame of complex baseband
at sample rate fs, normalised to unit average power.  Where the scheme has a
constellation, the ideal points and the sample index of the first symbol
centre are carried along so the constellation view can overlay ground truth
instead of guessing at it.
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from . import constellations as C
from .pulse import rrc_taps, rect_taps, gaussian_freq_pulse, upsample


@dataclass
class Signal:
    x: np.ndarray                     # complex baseband, unit average power
    fs: float                         # sample rate, Hz
    sps: int                          # samples per symbol
    mod: str                          # modulation key
    family: str                       # psk | qam | pam | apsk | fsk | analog | ofdm
    ideal: Optional[np.ndarray] = None    # ideal constellation, unit avg power
    symbols: Optional[np.ndarray] = None  # transmitted symbol sequence
    sym_offset: int = 0               # sample index of first symbol centre
    tx_taps: Optional[np.ndarray] = None  # pulse-shaping taps (for matched filter)
    linear: bool = False              # True if built by symbol-map + pulse-shape
    info: dict = field(default_factory=dict)

    @property
    def symbol_rate(self) -> float:
        return self.fs / self.sps

    @property
    def duration(self) -> float:
        return len(self.x) / self.fs


def _unit_power(x: np.ndarray) -> np.ndarray:
    p = np.mean(np.abs(x) ** 2)
    return x / np.sqrt(p) if p > 0 else x


# --------------------------------------------------------------------------
# Linear (symbol-mapped, pulse-shaped) modulations
# --------------------------------------------------------------------------

_LINEAR = {
    "bpsk":    (lambda: C.psk(2),        "psk",  1),
    "qpsk":    (lambda: C.psk(4),        "psk",  2),
    "8psk":    (lambda: C.psk(8),        "psk",  3),
    "16psk":   (lambda: C.psk(16),       "psk",  4),
    "16qam":   (lambda: C.qam_square(16),  "qam",  4),
    "64qam":   (lambda: C.qam_square(64),  "qam",  6),
    "256qam":  (lambda: C.qam_square(256), "qam",  8),
    "pam4":    (lambda: C.pam(4),        "pam",  2),
    "ook":     (lambda: C.ask(2),        "pam",  1),
    "4ask":    (lambda: C.ask(4),        "pam",  2),
    "16apsk":  (lambda: C.apsk(16),      "apsk", 4),
    "32apsk":  (lambda: C.apsk(32),      "apsk", 5),
}

_DIFFERENTIAL = {"dbpsk": 2, "dqpsk": 4, "pi4dqpsk": 4}


def _linear_waveform(symbols, sps, beta, span, n_out):
    taps = rrc_taps(beta, sps, span)
    up = upsample(symbols, sps)
    y = np.convolve(up, taps, mode="full")
    gd = (len(taps) - 1) // 2
    # First symbol centre lands at index gd in the full convolution.
    start = gd
    x = y[start:start + n_out]
    if len(x) < n_out:                       # pad if we ran short
        x = np.concatenate([x, np.zeros(n_out - len(x), dtype=complex)])
    return x, taps


def make_linear(mod, n_samples, sps, beta, rng, span=12):
    ideal, family, bps = _LINEAR[mod][0](), _LINEAR[mod][1], _LINEAR[mod][2]
    m = len(ideal)
    n_sym = int(np.ceil(n_samples / sps)) + span + 2
    idx = rng.integers(0, m, n_sym)
    symbols = ideal[idx]
    x, taps = _linear_waveform(symbols, sps, beta, span, n_samples)
    scale = 1.0 / np.sqrt(np.mean(np.abs(x) ** 2))
    return Signal(x=x * scale, fs=None, sps=sps, mod=mod, family=family,
                  ideal=ideal, symbols=symbols, sym_offset=0, tx_taps=taps,
                  linear=True,
                  info={"order": m, "bits_per_symbol": bps, "rolloff": beta,
                        "d_min": C.min_distance(ideal),
                        "papr_constellation": C.peak_to_avg(ideal)})


def make_differential(mod, n_samples, sps, beta, rng, span=12):
    m = _DIFFERENTIAL[mod]
    n_sym = int(np.ceil(n_samples / sps)) + span + 2
    idx = rng.integers(0, m, n_sym)
    if mod == "pi4dqpsk":
        # Differential phase from {+/-pi/4, +/-3pi/4}: the constellation
        # alternates between two QPSK sets rotated by pi/4, so the trajectory
        # never passes through the origin.
        dphi = (2 * idx + 1) * np.pi / 4
        ideal = C.psk(8)
    else:
        dphi = 2 * np.pi * idx / m
        ideal = C.psk(m)
    phase = np.cumsum(dphi)
    if mod == "dbpsk":
        phase = phase          # 0 / pi
    symbols = np.exp(1j * phase)
    x, taps = _linear_waveform(symbols, sps, beta, span, n_samples)
    scale = 1.0 / np.sqrt(np.mean(np.abs(x) ** 2))
    return Signal(x=x * scale, fs=None, sps=sps, mod=mod, family="psk",
                  ideal=ideal, symbols=symbols, sym_offset=0, tx_taps=taps,
                  linear=True,
                  info={"order": m, "bits_per_symbol": int(np.log2(m)),
                        "rolloff": beta, "differential": True,
                        "d_min": C.min_distance(ideal),
                        "papr_constellation": C.peak_to_avg(ideal)})


def make_oqpsk(n_samples, sps, beta, rng, span=12):
    """Offset QPSK: the Q branch is delayed by half a symbol, which removes
    the 180-degree transitions that make QPSK's trajectory cross the origin."""
    ideal = C.psk(4)
    n_sym = int(np.ceil(n_samples / sps)) + span + 4
    idx = rng.integers(0, 4, n_sym)
    symbols = ideal[idx]
    taps = rrc_taps(beta, sps, span)
    up_i = upsample(symbols.real.astype(complex), sps)
    up_q = upsample(symbols.imag.astype(complex), sps)
    half = sps // 2
    up_q = np.concatenate([np.zeros(half, dtype=complex), up_q])[:len(up_i)]
    yi = np.convolve(up_i, taps, mode="full")
    yq = np.convolve(up_q, taps, mode="full")
    gd = (len(taps) - 1) // 2
    x = (yi + 1j * yq)[gd:gd + n_samples]
    if len(x) < n_samples:
        x = np.concatenate([x, np.zeros(n_samples - len(x), dtype=complex)])
    scale = 1.0 / np.sqrt(np.mean(np.abs(x) ** 2))
    return Signal(x=x * scale, fs=None, sps=sps, mod="oqpsk", family="psk",
                  ideal=ideal, symbols=symbols, sym_offset=0, tx_taps=taps,
                  linear=True,
                  info={"order": 4, "bits_per_symbol": 2, "rolloff": beta,
                        "offset_qpsk": True, "d_min": C.min_distance(ideal),
                        "papr_constellation": 1.0})


# --------------------------------------------------------------------------
# Continuous-phase frequency modulations
# --------------------------------------------------------------------------

_FSK = {
    # key      : (levels, default h, pulse, default BT)
    "2fsk":     (2, 1.0, "rect", None),
    "4fsk":     (4, 1.0, "rect", None),
    "cpfsk":    (2, 0.5, "rect", None),
    "msk":      (2, 0.5, "rect", None),
    "gfsk":     (2, 0.5, "gauss", 0.5),
    "gmsk":     (2, 0.5, "gauss", 0.3),
}


def make_fsk(mod, n_samples, sps, rng, h=None, bt=None):
    levels, h_def, pulse, bt_def = _FSK[mod]
    h = h_def if h is None else h
    bt = bt_def if bt is None else bt
    n_sym = int(np.ceil(n_samples / sps)) + 8
    idx = rng.integers(0, levels, n_sym)
    a = 2 * idx - (levels - 1)                     # {-1,+1} or {-3,-1,1,3}

    # Frequency pulse with unit area per symbol -> phase step of pi*h*a_k.
    if pulse == "gauss":
        g = gaussian_freq_pulse(bt, sps, span_symbols=4)
    else:
        g = np.ones(sps) / sps

    up = np.zeros(n_sym * sps)
    up[::sps] = a
    f_shape = np.convolve(up, g, mode="full")      # units: symbols^-1
    # phase[n] = pi*h * cumulative frequency pulse
    phase = np.pi * h * np.cumsum(f_shape)
    gd = (len(g) - 1) // 2
    x = np.exp(1j * phase[gd:gd + n_samples])
    if len(x) < n_samples:
        x = np.concatenate([x, np.zeros(n_samples - len(x), dtype=complex)])
    sym_rate = 1.0
    return Signal(x=_unit_power(x), fs=None, sps=sps, mod=mod, family="fsk",
                  ideal=None, symbols=a[:n_sym], sym_offset=0, tx_taps=None,
                  linear=False,
                  info={"levels": levels, "bits_per_symbol": int(np.log2(levels)),
                        "mod_index_h": h, "bt": bt, "pulse": pulse,
                        "tone_spacing_symbol_rates": h,
                        "peak_dev_symbol_rates": h * (levels - 1) / 2.0})


# --------------------------------------------------------------------------
# Analog modulations
# --------------------------------------------------------------------------

def _message(n, fs, bw, rng, kind="tones"):
    """Band-limited real message, peak-normalised to +/-1."""
    t = np.arange(n) / fs
    if kind == "tones":
        f = np.array([0.17, 0.41, 0.83]) * bw
        amp = np.array([1.0, 0.55, 0.3])
        ph = rng.uniform(0, 2 * np.pi, 3)
        m = sum(a * np.cos(2 * np.pi * fi * t + p) for a, fi, p in zip(amp, f, ph))
    else:
        from scipy.signal import butter, filtfilt
        w = rng.standard_normal(n)
        b, a = butter(6, min(bw / (fs / 2), 0.99))
        m = filtfilt(b, a, w)
    peak = np.max(np.abs(m))
    return m / peak if peak > 0 else m


def make_analog(mod, n_samples, fs, rng, msg_bw, depth=0.8, fdev=None, msg="tones"):
    m = _message(n_samples, fs, msg_bw, rng, msg)
    if mod == "am_dsb_wc":
        x = (1.0 + depth * m).astype(complex)
        info = {"depth": depth, "carrier": "present"}
    elif mod == "am_dsb_sc":
        x = m.astype(complex)
        info = {"depth": depth, "carrier": "suppressed"}
    elif mod == "am_ssb":
        from scipy.signal import hilbert
        x = hilbert(m)                              # upper sideband analytic signal
        info = {"sideband": "upper"}
    elif mod in ("fm", "wbfm"):
        fdev = fdev if fdev is not None else (5.0 * msg_bw if mod == "wbfm" else 1.0 * msg_bw)
        phase = 2 * np.pi * fdev * np.cumsum(m) / fs
        x = np.exp(1j * phase)
        beta_fm = fdev / msg_bw
        info = {"freq_dev_hz": fdev, "modulation_index_beta": beta_fm,
                "carson_bw_hz": 2 * (fdev + msg_bw)}
    else:
        raise ValueError(mod)
    info.update({"msg_bw_hz": msg_bw, "msg_kind": msg})
    return Signal(x=_unit_power(np.asarray(x, dtype=complex)), fs=fs, sps=1,
                  mod=mod, family="analog", ideal=None, symbols=None,
                  tx_taps=None, linear=False, info=info)


# --------------------------------------------------------------------------
# OFDM
# --------------------------------------------------------------------------

def make_ofdm(n_samples, rng, n_fft=64, n_used=52, cp_len=16, sub_mod="16qam"):
    ideal = _LINEAR[sub_mod][0]()
    sym_len = n_fft + cp_len
    n_ofdm = int(np.ceil(n_samples / sym_len)) + 1

    used = np.concatenate([np.arange(1, n_used // 2 + 1),
                           np.arange(n_fft - n_used // 2, n_fft)])
    out = []
    grid = np.zeros((n_ofdm, n_fft), dtype=complex)
    for s in range(n_ofdm):
        f = np.zeros(n_fft, dtype=complex)
        d = ideal[rng.integers(0, len(ideal), len(used))]
        f[used] = d
        grid[s] = f
        td = np.fft.ifft(f) * np.sqrt(n_fft)
        out.append(np.concatenate([td[-cp_len:], td]))
    x = np.concatenate(out)[:n_samples]
    return Signal(x=_unit_power(x), fs=None, sps=sym_len, mod="ofdm",
                  family="ofdm", ideal=ideal, symbols=None, tx_taps=None,
                  linear=False,
                  info={"n_fft": n_fft, "n_used": n_used, "cp_len": cp_len,
                        "sub_mod": sub_mod, "symbol_len": sym_len,
                        "n_ofdm_symbols": n_ofdm,
                        "cp_fraction": cp_len / sym_len,
                        "grid_shape": list(grid.shape)})


# --------------------------------------------------------------------------
# Registry / dispatch
# --------------------------------------------------------------------------

ALL_MODS = (list(_LINEAR) + list(_DIFFERENTIAL) + ["oqpsk"] + list(_FSK)
            + ["am_dsb_wc", "am_dsb_sc", "am_ssb", "fm", "wbfm", "ofdm"])


def generate(mod, n_samples=4096, fs=1_000_000.0, sps=8, beta=0.35, seed=0, **kw):
    rng = np.random.default_rng(seed)
    if mod in _LINEAR:
        s = make_linear(mod, n_samples, sps, beta, rng)
    elif mod in _DIFFERENTIAL:
        s = make_differential(mod, n_samples, sps, beta, rng)
    elif mod == "oqpsk":
        s = make_oqpsk(n_samples, sps, beta, rng)
    elif mod in _FSK:
        s = make_fsk(mod, n_samples, sps, rng,
                     h=kw.get("mod_index"), bt=kw.get("bt"))
    elif mod in ("am_dsb_wc", "am_dsb_sc", "am_ssb", "fm", "wbfm"):
        s = make_analog(mod, n_samples, fs, rng,
                        msg_bw=kw.get("msg_bw", fs / 40.0),
                        depth=kw.get("am_depth", 0.8),
                        fdev=kw.get("freq_dev"),
                        msg=kw.get("msg_kind", "tones"))
    elif mod == "ofdm":
        s = make_ofdm(n_samples, rng, n_fft=kw.get("n_fft", 64),
                      n_used=kw.get("n_used", 52), cp_len=kw.get("cp_len", 16),
                      sub_mod=kw.get("sub_mod", "16qam"))
    else:
        raise ValueError(f"unknown modulation {mod!r}")
    s.fs = fs
    return s
