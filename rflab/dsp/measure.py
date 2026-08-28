"""Measurements taken from the actual samples.

Nothing in here reads the configuration.  Everything is estimated from the
waveform the way a receiver would have to, which is what lets the lab compare
"what you asked for" against "what is actually in the signal".
"""
import numpy as np
from scipy import signal as sps_sig

from .pulse import rrc_taps


# --------------------------------------------------------------------------
# Receiver front-end
# --------------------------------------------------------------------------

def matched_filter(x, sig):
    """Apply the receive matched filter for linear modulations.

    RRC at the transmitter times RRC at the receiver gives a raised cosine,
    which is zero at every symbol instant but its own -- that is what makes
    the sampled constellation ISI-free.
    """
    if sig.tx_taps is None:
        return x, 0
    h = sig.tx_taps
    y = np.convolve(x, h, mode="full")
    gd = (len(h) - 1) // 2
    return y[gd:gd + len(x)], gd


def best_timing_phase(y, sps):
    """Pick the decimation phase with the largest sampled-symbol energy
    variance -- i.e. the phase where the eye is most open."""
    best, best_metric = 0, -np.inf
    n = len(y)
    for p in range(sps):
        s = y[p::sps]
        if len(s) < 8:
            continue
        # Maximum-energy criterion: at the optimal instant the pulse peaks.
        metric = np.mean(np.abs(s) ** 2)
        if metric > best_metric:
            best_metric, best = metric, p
    return best


def symbol_samples(x, sig, apply_mf=True, timing_phase=None, trim=None):
    """Return (samples, phase) at one sample per symbol.

    OQPSK is sampled with a staggered grid: the Q branch is half a symbol
    late by construction, so sampling both rails at the same instant would
    manufacture an error that is not there.
    """
    if sig.sps <= 1:
        return x.copy(), 0
    y, _ = matched_filter(x, sig) if apply_mf else (x, 0)
    if timing_phase is not None:
        p = timing_phase
    elif sig.info.get("offset_qpsk"):
        # The two rails peak half a symbol apart, so the combined magnitude is
        # nearly flat and the usual max-energy rule picks an arbitrary phase.
        # Lock to the I rail instead; Q is then sampled sps/2 later.
        p = int(np.argmax([np.mean(y.real[k::sig.sps] ** 2) for k in range(sig.sps)]))
    else:
        p = best_timing_phase(y, sig.sps)
    if sig.info.get("offset_qpsk"):
        half = sig.sps // 2
        i = y.real[p::sig.sps]
        q = y.imag[p + half::sig.sps]
        n = min(len(i), len(q))
        s = i[:n] + 1j * q[:n]
    else:
        s = y[p::sig.sps]
    if trim:
        s = s[trim:-trim] if len(s) > 2 * trim + 8 else s
    return s, p


def align_symbol_lag(rx, tx, max_lag=6, block=8):
    """Find the integer symbol lag that lines the received symbols up with the
    transmitted ones, tolerating a rotating carrier.

    A plain |<tx, rx>| correlation is invariant to a *constant* phase but not to
    a rotating one: with a few turns of CFO across the frame the contributions
    cancel and the correct lag scores no better than noise.  Correlating in
    short blocks and summing the magnitudes keeps each block close to coherent,
    which is the same reason real acquisition correlates over a preamble rather
    than a whole packet.
    """
    n = min(len(rx), len(tx))
    if n < 16:
        return 0
    best, best_lag = -np.inf, 0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            a, b = rx[lag:], tx[:n - lag]
        else:
            a, b = rx[:n + lag], tx[-lag:n]
        m = min(len(a), len(b))
        if m < 16:
            continue
        a, b = a[:m], b[:m]
        nb = max(1, m // block)
        av = a[:nb * block].reshape(nb, block)
        bv = b[:nb * block].reshape(nb, block)
        num = np.abs(np.sum(av * np.conj(bv), axis=1)).sum()
        den = (np.linalg.norm(a) * np.linalg.norm(b) + 1e-18)
        score = num / den
        if score > best:
            best, best_lag = score, lag
    return best_lag


def apply_symbol_lag(rx, tx, lag):
    n = min(len(rx), len(tx))
    if lag >= 0:
        a, b = rx[lag:], tx[:n - lag]
    else:
        a, b = rx[:n + lag], tx[-lag:n]
    m = min(len(a), len(b))
    return a[:m], b[:m]


def align_gain(rx_syms, ideal_syms):
    """Least-squares complex gain that maps ideal -> received.

    Returns (gain, residual_rms / ideal_rms) which is exactly EVM.
    """
    n = min(len(rx_syms), len(ideal_syms))
    a, b = ideal_syms[:n], rx_syms[:n]
    denom = np.vdot(a, a)
    g = np.vdot(a, b) / denom if abs(denom) > 0 else 1.0
    err = b - g * a
    ref = np.sqrt(np.mean(np.abs(g * a) ** 2))
    evm = np.sqrt(np.mean(np.abs(err) ** 2)) / ref if ref > 0 else np.nan
    return g, evm


# --------------------------------------------------------------------------
# Instantaneous quantities
# --------------------------------------------------------------------------

def inst_amplitude(x):
    return np.abs(x)


def inst_phase(x, unwrap=True):
    p = np.angle(x)
    return np.unwrap(p) if unwrap else p


def inst_freq(x, fs, smooth=1):
    """Instantaneous frequency in Hz from the phase derivative.

    Uses the conjugate-product form, which is immune to unwrapping errors:
    angle(x[n] * conj(x[n-1])) is already in (-pi, pi].
    """
    d = np.angle(x[1:] * np.conj(x[:-1]))
    f = d * fs / (2 * np.pi)
    if smooth > 1:
        k = np.ones(smooth) / smooth
        f = np.convolve(f, k, mode="same")
    return np.concatenate([[f[0]], f]) if len(f) else np.zeros_like(np.abs(x))


# --------------------------------------------------------------------------
# Spectral
# --------------------------------------------------------------------------

def fft_mag_db(x, fs, nfft=None, window="hann", max_points=None):
    """Windowed magnitude spectrum in dB.

    `nfft` smaller than len(x) would make numpy *truncate* the input rather
    than reduce the output resolution -- and truncating a Hann-windowed signal
    keeps only the window's rising edge, which produces a badly skewed spectrum
    that looks like a real feature.  So the transform always runs at full
    length and the output is decimated afterwards if fewer points are wanted.
    """
    n = len(x)
    size = int(2 ** np.ceil(np.log2(max(n, nfft or 0))))
    w = sps_sig.get_window(window, n)
    X = np.fft.fftshift(np.fft.fft(x * w, size))
    mag = 20 * np.log10(np.abs(X) / (np.sum(w) / 2) + 1e-15)
    f = np.fft.fftshift(np.fft.fftfreq(size, 1 / fs))
    keep = max_points or nfft
    if keep and len(mag) > keep:
        # Decimate by taking the peak of each group, so narrow lines (a DC
        # spike, an interferer) survive rather than being averaged away.
        g = int(np.ceil(len(mag) / keep))
        trim = (len(mag) // g) * g
        mag = mag[:trim].reshape(-1, g).max(axis=1)
        f = f[:trim].reshape(-1, g).mean(axis=1)
    return f, mag


def welch_psd(x, fs, nperseg=256, noverlap=None):
    nperseg = min(nperseg, len(x))
    f, p = sps_sig.welch(x, fs=fs, nperseg=nperseg,
                         noverlap=noverlap if noverlap is not None else nperseg // 2,
                         return_onesided=False, detrend=False,
                         scaling="density")
    idx = np.argsort(f)
    return f[idx], 10 * np.log10(p[idx] + 1e-18)


def spectrogram(x, fs, nperseg=128, noverlap=None, nfft=None):
    """Short-time Fourier transform.

    `nfft` larger than `nperseg` zero-pads each segment.  That does not create
    real resolution -- the true resolution is still fs/nperseg, set by how long
    each segment is -- but it interpolates the spectrum so the picture is smooth
    rather than a coarse mosaic.  The readout quotes the true resolution, not
    the padded one, so the display cannot mislead about what was measured.
    """
    nperseg = int(min(nperseg, max(16, len(x))))
    nov = noverlap if noverlap is not None else int(nperseg * 0.75)
    nov = int(min(nov, nperseg - 1))
    nfft = int(max(nfft or nperseg, nperseg))
    f, t, S = sps_sig.spectrogram(x, fs=fs, nperseg=nperseg, noverlap=nov, nfft=nfft,
                                  return_onesided=False, mode="magnitude",
                                  detrend=False)
    idx = np.argsort(f)
    S = 20 * np.log10(S[idx] + 1e-15)
    return f[idx], t, S


def occupied_bandwidth(f, psd_db, fraction=0.99):
    """Bandwidth containing `fraction` of total power, and the power centroid."""
    p = 10 ** (psd_db / 10.0)
    total = np.sum(p)
    if total <= 0:
        return 0.0, 0.0
    centroid = float(np.sum(f * p) / total)
    order = np.argsort(np.abs(f - centroid))
    cum = np.cumsum(p[order]) / total
    k = int(np.searchsorted(cum, fraction))
    k = min(k, len(order) - 1)
    bw = 2 * float(np.abs(f[order[k]] - centroid))
    return bw, centroid


def noise_floor_db(psd_db, pct=20):
    return float(np.percentile(psd_db, pct))


# --------------------------------------------------------------------------
# Blind parameter estimators (what a receiver would have to do)
# --------------------------------------------------------------------------

def estimate_cfo_mth_power(x, fs, m=4):
    """Classic blind M-th power CFO estimate for M-PSK.

    Raising an M-PSK signal to the M-th power collapses the data-dependent
    phases onto multiples of 2*pi, leaving a tone at M*delta_f.
    """
    y = x ** m
    n = int(2 ** np.ceil(np.log2(len(y)))) * 4
    Y = np.abs(np.fft.fftshift(np.fft.fft(y, n)))
    f = np.fft.fftshift(np.fft.fftfreq(n, 1 / fs))
    k = int(np.argmax(Y))
    # Parabolic interpolation around the peak for sub-bin accuracy.
    if 0 < k < len(Y) - 1:
        a, b, c = Y[k - 1], Y[k], Y[k + 1]
        d = 0.5 * (a - c) / (a - 2 * b + c + 1e-30)
    else:
        d = 0.0
    df = f[1] - f[0]
    peak_f = f[k] + d * df
    sharpness = float(Y[k] / (np.median(Y) + 1e-15))
    return peak_f / m, sharpness


def estimate_cfo_phase_slope(x, sig):
    """CFO from the drift of the symbol-instant phase after removing the
    modulation by an M-th power.  More robust than a single FFT peak for
    small offsets."""
    m = {"psk": sig.info.get("order", 4)}.get(sig.family, None)
    if m is None or m > 16:
        return None
    s, _ = symbol_samples(x, sig)
    if len(s) < 16:
        return None
    y = s ** m
    ph = np.unwrap(np.angle(y))
    t = np.arange(len(ph)) / (sig.fs / sig.sps)
    slope = np.polyfit(t, ph, 1)[0]
    return slope / (2 * np.pi * m)


def estimate_cfo_cyclic_prefix(x, n_fft, cp_len, fs):
    """Van de Beek style CFO estimate for OFDM, using the cyclic prefix.

    The CP is a literal copy of the tail of the same symbol, so y[n] and
    y[n + n_fft] are the same sample seen n_fft/fs seconds apart.  Any carrier
    offset shows up as a fixed phase between them, and the angle of their
    correlation reads it off directly.  This is why OFDM systems can
    synchronise with no preamble at all -- and it caps unambiguously at
    +/- half a subcarrier spacing, because beyond that the phase wraps.
    """
    L = n_fft + cp_len
    ns = len(x) // L
    if ns < 1 or cp_len < 2:
        return None, 0.0, None
    acc = 0j
    for s_ in range(ns):
        a = x[s_ * L: s_ * L + cp_len]
        b = x[s_ * L + n_fft: s_ * L + n_fft + cp_len]
        if len(b) == len(a):
            acc += np.vdot(a, b)
    est = float(np.angle(acc) / (2 * np.pi * n_fft / fs))
    unamb = fs / (2 * n_fft)
    return est, float(np.abs(acc)), unamb


def estimate_cfo_spectral_centroid(x, fs):
    """Frequency offset as the power centroid of the spectrum.

    Works for anything with a symmetric spectrum about its own carrier --
    FSK, AM, FM -- where the M-th power trick has no modulation symmetry to
    exploit.  Coarse, but it does not care what the modulation is.
    """
    f, psd = welch_psd(x, fs, 512)
    p = 10 ** (psd / 10.0)
    thr = np.percentile(p, 60)
    p = np.where(p > thr, p - thr, 0.0)
    tot = np.sum(p)
    if tot <= 0:
        return 0.0, 0.0
    c = float(np.sum(f * p) / tot)
    spread = float(np.sqrt(np.sum(p * (f - c) ** 2) / tot))
    return c, spread


def estimate_cfo_fsk(x, fs, symbol_rate, tone_spacing_hz, n_symbols):
    """CFO for FSK as the mean instantaneous frequency.

    The symbol deviations are symmetric about the carrier, so they average to
    zero -- eventually.  Over a finite frame the transmitted symbols are not
    perfectly balanced, and that imbalance biases the mean by roughly
    (tone spacing / 2) / sqrt(n_symbols).  For a short frame that uncertainty
    can be larger than the offset being measured, which is a real limit of the
    method and not something more averaging of the same frame can fix.
    """
    f = inst_freq(x, fs)
    # The mean is biased by whatever symbol imbalance the frame happens to have.
    # The midpoint between the extreme frequency states is not: the tones sit
    # symmetrically about the carrier, so their midpoint *is* the carrier however
    # unevenly the symbols were drawn.
    mean_est = float(np.mean(f))
    lo, hi = np.percentile(f, [2.0, 98.0])
    mid_est = float((lo + hi) / 2.0)
    unc_mean = float((tone_spacing_hz / 2.0) / np.sqrt(max(n_symbols, 1)))
    return mid_est, unc_mean, mean_est


def estimate_dc(x):
    dc = complex(np.mean(x))
    rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
    return dc, (abs(dc) / rms if rms > 0 else 0.0)


def estimate_iq_imbalance(x):
    """Estimate gain/phase imbalance from the improper second moment.

    A balanced complex signal with a rotationally symmetric constellation has
    E[x^2] = 0.  Imbalance mixes in a conjugate (image) copy, so E[x^2] goes
    non-zero.  Writing the output as y = a.x + b.conj(x), the measurable ratio
    is

        rho = |E[y^2]| / E[|y|^2] = 2|a||b| / (|a|^2 + |b|^2)

    which inverts to |b|/|a| = (1 - sqrt(1 - rho^2)) / rho.  Reading the image
    rejection straight off as -20log10(rho) is wrong by about 6 dB -- that
    factor of two in the numerator is easy to drop and hard to notice.

    Returns (gain_db, phase_deg, irr_db, floor_db) where floor_db is the
    measurement ceiling set by finite-sample error at this frame length:
    an estimate at or above the floor means "no imbalance detectable", not
    "imbalance equal to the floor".
    """
    xz = x - np.mean(x)
    n = len(xz)
    p = float(np.mean(np.abs(xz) ** 2))
    if p <= 0:
        return 0.0, 0.0, np.inf, np.inf
    rho = float(np.abs(np.mean(xz ** 2)) / p)
    rho = min(rho, 0.999999)
    ratio = (1 - np.sqrt(1 - rho ** 2)) / rho if rho > 1e-12 else 0.0
    irr_db = float(-20 * np.log10(ratio)) if ratio > 0 else np.inf
    # Finite-sample floor: |E[x^2]| of a truly circular signal is ~1/sqrt(N).
    rho_floor = 1.0 / np.sqrt(n)
    r_floor = (1 - np.sqrt(1 - rho_floor ** 2)) / rho_floor
    floor_db = float(-20 * np.log10(r_floor))
    # Equivalent single-cause gain or phase imbalance producing this ratio.
    gain_db = float(20 * np.log10((1 + ratio) / (1 - ratio))) if ratio < 1 else np.inf
    phase_deg = float(np.degrees(2 * np.arctan(ratio)))
    return gain_db, phase_deg, irr_db, floor_db


def es_n0_db(snr_db, sps):
    """Convert wideband sample SNR to per-symbol Es/N0.

    The matched filter only passes noise inside the symbol bandwidth, so it
    throws away most of the noise that sits in the oversampled band.  The gain
    is 10log10(sps).  Quoting a raw sample SNR as if it were Es/N0 understates
    a receiver's real margin by exactly this amount -- for sps = 8 that is
    9 dB, which is the difference between "hopeless" and "fine".
    """
    return float(snr_db + 10 * np.log10(sps))


def estimate_snr_m2m4(x, kurtosis_signal=1.0):
    """M2/M4 moment-based SNR estimate for constant-modulus-ish signals."""
    m2 = np.mean(np.abs(x) ** 2)
    m4 = np.mean(np.abs(x) ** 4)
    arg = 2 * m2 ** 2 - m4
    if arg <= 0:
        return -np.inf
    s = np.sqrt(arg)
    n = m2 - s
    if n <= 0:
        return np.inf
    return float(10 * np.log10(s / n))


def _spectral_line(sig_real, fs, f_min):
    """Find the strongest narrow spectral *line*, then step down to the lowest
    harmonic of it that is also present.

    Two traps this avoids.  Random data puts a broad low-frequency pedestal
    under the line, so a raw argmax often lands on that pedestal -- we score
    peaks by their *ratio* to a median-filtered baseline, which is flat for a
    pedestal and large only for something genuinely narrow.  And a sharp-edged
    symbol transition puts energy on every harmonic of Rs, so the strongest
    line may be at 3Rs -- we check the sub-harmonics and take the lowest one
    that still stands up.
    """
    from scipy.ndimage import median_filter
    n = int(2 ** np.ceil(np.log2(len(sig_real))))
    E = np.abs(np.fft.rfft(sig_real - np.mean(sig_real), n))
    f = np.fft.rfftfreq(n, 1 / fs)
    lo = np.searchsorted(f, f_min)
    if lo >= len(E) - 8:
        return None, 0.0
    win = max(21, (len(E) // 64) | 1)
    baseline = median_filter(E, size=win, mode="nearest")
    R = E / (baseline + 1e-15)
    R[:lo] = 0.0
    k = int(np.argmax(R))
    w = max(2, len(E) // 4000)
    for div in (5, 4, 3, 2):
        kk = int(round(k / div))
        if kk < lo:
            continue
        a, b = max(lo, kk - w), min(len(R), kk + w + 1)
        if b > a and R[a:b].max() > 0.25 * R[k]:
            k = a + int(np.argmax(R[a:b]))
            break
    return float(f[k]), float(R[k])


def estimate_symbol_rate(x, fs, f_min=None):
    """Blind symbol-rate estimate.

    Amplitude-varying signals put a spectral line at the symbol rate in their
    squared envelope.  Constant-envelope signals (PSK-after-hard-limiting,
    FSK, GMSK) have a flat envelope by definition, so the envelope carries no
    line at all -- for those the line lives in the instantaneous frequency,
    which steps once per symbol.  Trying only the envelope is a classic way
    to get a confidently wrong answer on FSK.
    """
    f_min = f_min if f_min is not None else fs / 128.0
    env = np.abs(x) ** 2
    env_var = float(np.var(env) / (np.mean(env) ** 2 + 1e-18))
    if env_var < 1e-3:
        f_inst = inst_freq(x, fs)
        r_f, s_f = _spectral_line(np.abs(np.diff(f_inst, prepend=f_inst[0])), fs, f_min)
        return r_f, s_f, "instantaneous-frequency line (constant envelope)"
    r_env, s_env = _spectral_line(env, fs, f_min)
    if s_env is not None and s_env >= 8.0:
        return r_env, s_env, "squared-envelope line"
    # OQPSK and heavily filtered waveforms deliberately smooth the envelope,
    # so the envelope line can vanish.  The cyclic autocorrelation still
    # carries the symbol-rate periodicity because it uses phase as well.
    prof = cyclic_profile(x, fs, fs / 4.0, span=1.0,
                          max_lag_samples=int(fs / f_min), lag_step=2)
    from scipy.ndimage import median_filter
    a, pr = prof["alphas"], prof["profile"]
    keep = a > f_min
    if not keep.any():
        return r_env, s_env, "squared-envelope line (weak)"
    # Same trick as the envelope route: score narrowness, not height, so the
    # broad residual pedestal near alpha=0 cannot win.
    base = median_filter(pr, size=max(21, (len(pr) // 40) | 1), mode="nearest")
    ratio = np.where(keep, pr / (base + 1e-12), 0.0)
    k = int(np.argmax(ratio))
    return float(a[k]), float(ratio[k]), "cyclic autocorrelation (envelope line too weak)"


def papr_db(x):
    p = np.abs(x) ** 2
    return float(10 * np.log10(np.max(p) / np.mean(p))) if np.mean(p) > 0 else 0.0


# --------------------------------------------------------------------------
# Higher-order statistics
# --------------------------------------------------------------------------

def cumulants(x):
    """Normalised higher-order cumulants, the classical AMC feature set.

    Normalising by C21^(n/2) removes the dependence on signal power, which is
    what makes these usable as scale-invariant class signatures.
    """
    z = x - np.mean(x)
    p = np.mean(np.abs(z) ** 2)
    if p <= 0:
        return {}
    z = z / np.sqrt(p)

    def M(p_, q_):
        return np.mean(z ** (p_ - q_) * np.conj(z) ** q_)

    m20, m21, m40, m41, m42 = M(2, 0), M(2, 1), M(4, 0), M(4, 1), M(4, 2)
    m60, m63 = M(6, 0), M(6, 3)
    c20 = m20
    c21 = m21
    c40 = m40 - 3 * m20 ** 2
    c41 = m41 - 3 * m20 * m21
    c42 = m42 - abs(m20) ** 2 - 2 * m21 ** 2
    c60 = m60 - 15 * m20 * m40 + 30 * m20 ** 3
    c63 = m63 - 6 * m20 * m41 - 9 * m21 * m42 + 18 * m20 ** 2 * m21 + 12 * m21 ** 3
    out = {"C20": c20, "C21": c21, "C40": c40, "C41": c41,
           "C42": c42, "C60": c60, "C63": c63}
    return {k: (float(abs(v)) if k != "C21" else float(v.real)) for k, v in out.items()}


IDEAL_CUMULANTS = {
    # |C40| and |C42| for unit-power constellations -- the classical table.
    "bpsk":   {"C40": 2.00, "C42": 2.00},
    "qpsk":   {"C40": 1.00, "C42": 1.00},
    "8psk":   {"C40": 0.00, "C42": 1.00},
    "16psk":  {"C40": 0.00, "C42": 1.00},
    "16qam":  {"C40": 0.68, "C42": 0.68},
    "64qam":  {"C40": 0.62, "C42": 0.62},
    "256qam": {"C40": 0.60, "C42": 0.60},
    "pam4":   {"C40": 1.36, "C42": 1.36},
    "2fsk":   {"C40": 0.00, "C42": 1.00},
    "gmsk":   {"C40": 0.00, "C42": 1.00},
    "ofdm":   {"C40": 0.00, "C42": 0.00},
}


# --------------------------------------------------------------------------
# Cyclostationarity
# --------------------------------------------------------------------------

def cyclic_autocorrelation(x, fs, alphas, lag_samples=0):
    """Magnitude of the cyclic autocorrelation R_x^alpha(tau) at each alpha.

    R^a(tau) = < x[n+tau] conj(x[n]) e^{-j2 pi a n / fs} >
    A digitally modulated signal has non-zero cyclic features at multiples of
    its symbol rate; noise and most interference do not.  That is why cyclic
    features survive where energy detection fails.
    """
    n = np.arange(len(x) - abs(lag_samples))
    if lag_samples >= 0:
        prod = x[lag_samples:] * np.conj(x[:len(x) - lag_samples])
    else:
        prod = x[:lag_samples] * np.conj(x[-lag_samples:])
    out = []
    for a in alphas:
        e = np.exp(-2j * np.pi * a * n / fs)
        out.append(float(np.abs(np.mean(prod * e))))
    return np.array(out)


def conjugate_cyclic(x, fs, alphas, lag_samples=0):
    """Conjugate cyclic autocorrelation < x[n+tau] x[n] e^{-j2 pi a n/fs} >.
    Non-zero for BPSK/PAM-type (real-valued) constellations at alpha = 0 and
    at twice the carrier -- a genuine BPSK-vs-QPSK discriminator."""
    if lag_samples >= 0:
        prod = x[lag_samples:] * x[:len(x) - lag_samples]
    else:
        prod = x[:lag_samples] * x[-lag_samples:]
    n = np.arange(len(prod))
    return np.array([float(np.abs(np.mean(prod * np.exp(-2j * np.pi * a * n / fs))))
                     for a in alphas])


def autocorrelation(x, max_lag):
    z = x - np.mean(x)
    n = len(z)
    max_lag = int(min(max_lag, n - 1))
    f = np.fft.fft(z, 2 * n)
    r = np.fft.ifft(f * np.conj(f))[:max_lag + 1]
    r0 = r[0].real
    return (np.abs(r) / r0) if r0 > 0 else np.abs(r)


# --------------------------------------------------------------------------
# Eye diagram
# --------------------------------------------------------------------------

def eye_traces(x, sps, n_traces=120, span=2, apply_mf=None, phase=0):
    """Fold the waveform into overlapping symbol-period segments.

    Segment starts are locked to the symbol grid so that the centre column of
    every trace falls exactly on a decision instant.  Start them at arbitrary
    offsets and the traces still overlay into an eye-shaped picture, but the
    centre column is no longer the sampling instant, so any opening measured
    from it is meaningless.
    """
    y = apply_mf if apply_mf is not None else x
    seg = int(span * sps)
    half = seg // 2
    first = (phase - half) % sps
    starts = np.arange(first, len(y) - seg, sps)
    if len(starts) == 0:
        return np.zeros((0, seg)), np.zeros((0, seg))
    if len(starts) > n_traces:
        starts = starts[np.linspace(0, len(starts) - 1, n_traces).astype(int)]
    I = np.stack([y.real[s:s + seg] for s in starts])
    Q = np.stack([y.imag[s:s + seg] for s in starts])
    return I, Q


def eye_opening(I, sps, span=2):
    """Vertical eye opening at the centre instant, as a fraction of the
    full trace excursion.  1.0 = perfectly open, 0 = fully closed."""
    if I.size == 0:
        return 0.0, 0.0
    centre = I.shape[1] // 2
    col = I[:, centre]
    scale = float(np.max(np.abs(I))) or 1.0
    pos, neg = col[col > 0], col[col < 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.0, float(np.std(col) / scale)
    opening = float(np.min(pos) - np.max(neg)) / (2 * scale)
    return max(opening, 0.0), float(np.std(col) / scale)


def spectral_coherence_profile(x, fs, alphas, nperseg=256, noverlap=None):
    """Time-smoothed cyclic periodogram, normalised to spectral coherence.

    For each cycle frequency alpha we form two copies of the signal shifted
    by -alpha/2 and +alpha/2, take their STFTs, and average the cross-product
    over time:

        S_x^alpha(f) = < X_t(f + a/2) . conj(X_t(f - a/2)) >_t

    Dividing by sqrt(S(f+a/2) S(f-a/2)) turns power into *coherence*, a number
    in [0, 1].  This matters: the raw cyclic autocorrelation decays smoothly
    with alpha, so a symbol-rate feature hides under the alpha=0 pedestal.
    Coherence flattens that pedestal and the symbol-rate line stands clear.

    Returns (profile, peak_freq) where profile[i] = max over f of the
    coherence at alphas[i].
    """
    n = len(x)
    nperseg = int(min(nperseg, max(32, n // 8)))
    nov = noverlap if noverlap is not None else nperseg // 2
    step = nperseg - nov
    starts = np.arange(0, n - nperseg + 1, step)
    if len(starts) < 4:
        return np.zeros(len(alphas)), np.zeros(len(alphas))
    w = np.hanning(nperseg)
    idx = starts[:, None] + np.arange(nperseg)[None, :]
    t = np.arange(n)

    prof = np.zeros(len(alphas))
    pk = np.zeros(len(alphas))
    freqs = np.fft.fftshift(np.fft.fftfreq(nperseg, 1 / fs))
    for i, a in enumerate(alphas):
        rot = np.exp(-1j * np.pi * a * t / fs)
        u = x * rot                    # spectrum shifted by -a/2
        v = x * np.conj(rot)           # spectrum shifted by +a/2
        U = np.fft.fftshift(np.fft.fft(u[idx] * w, axis=1), axes=1)
        V = np.fft.fftshift(np.fft.fft(v[idx] * w, axis=1), axes=1)
        Sxy = np.mean(U * np.conj(V), axis=0)
        Sxx = np.mean(np.abs(U) ** 2, axis=0)
        Syy = np.mean(np.abs(V) ** 2, axis=0)
        coh = np.abs(Sxy) / (np.sqrt(Sxx * Syy) + 1e-18)
        # Only trust bins where there is actually signal power in both copies.
        strong = (Sxx > 0.05 * Sxx.max()) & (Syy > 0.05 * Syy.max())
        if not strong.any():
            continue
        c = np.where(strong, coh, 0.0)
        k = int(np.argmax(c))
        prof[i] = float(c[k])
        pk[i] = float(freqs[k])
    return prof, pk


def cyclic_profile(x, fs, symbol_rate, span=2.6, max_lag_symbols=2, sps=8,
                   max_lag_samples=None, lag_step=1):
    """Degree of cyclostationarity vs cycle frequency alpha.

    Rather than sweeping alpha one value at a time (which misses the lines --
    a cyclic feature is only about 1/T_observation wide, so a coarse alpha
    grid steps straight over it), we form the lag product

        p_tau[n] = x[n + tau] . conj(x[n])

    and take one FFT over n.  That yields R_x^alpha(tau) for every alpha on a
    dense grid in a single transform.  The profile reported is
    max over tau of |R^alpha(tau)|, normalised by the signal power, so alpha=0
    reads 1.0 and everything else is measured against it.

    The conjugate version < x[n+tau] . x[n] e^{-j2 pi alpha n} > is returned
    alongside: it is non-zero for real-valued constellations (BPSK, PAM, ASK)
    and zero for rotationally symmetric ones (QPSK and up, QAM), which makes
    it a genuine BPSK-vs-QPSK discriminator that survives noise well.
    """
    n = len(x)
    z = x - np.mean(x)
    power = float(np.mean(np.abs(z) ** 2)) + 1e-18
    nfft = int(2 ** np.ceil(np.log2(n)))
    df = fs / nfft
    n_keep = int(min(nfft // 2, np.ceil(span * symbol_rate / df)))
    L = max_lag_samples if max_lag_samples is not None else max_lag_symbols * sps
    lags = np.arange(-L, L + 1, lag_step)

    best = np.zeros(n_keep)
    best_c = np.zeros(n_keep)
    best_lag = np.zeros(n_keep, dtype=int)
    for tau in lags:
        if tau >= 0:
            a, b = z[tau:], z[:n - tau]
        else:
            a, b = z[:n + tau], z[-tau:]
        m = len(a)
        w = np.hanning(m)
        cg = np.sum(w)
        prod = a * np.conj(b) * w
        cprod = a * b * w
        # Subtract the alpha=0 component before transforming.  Without this the
        # ordinary (alpha=0) autocorrelation leaks a wide skirt across the whole
        # cyclic axis and buries genuine lines; the Hann window then keeps that
        # removal from ringing.  alpha=0 is the ordinary autocorrelation and is
        # reported separately, so nothing informative is lost.
        prod = prod - w * (np.sum(prod) / cg)
        R = np.abs(np.fft.fft(prod, nfft)) / cg
        Rc = np.abs(np.fft.fft(cprod, nfft)) / cg
        upd = R[:n_keep] > best
        best = np.where(upd, R[:n_keep], best)
        best_lag = np.where(upd, tau, best_lag)
        best_c = np.maximum(best_c, Rc[:n_keep])

    alphas = np.arange(n_keep) * df
    return {"alphas": alphas,
            "profile": best / power,
            "conj_profile": best_c / power,
            "best_lag": best_lag,
            "alpha_resolution_hz": float(fs / n)}


def cyclic_line_strength(prof, symbol_rate, k=1, guard_frac=0.25):
    """Height of the alpha = k x Rs line above the local floor around it."""
    a, p = prof["alphas"], prof["profile"]
    target = k * symbol_rate
    if target > a[-1]:
        return None
    df = a[1] - a[0]
    w = max(2, int(round(0.02 * symbol_rate / df)))
    i = int(round(target / df))
    lo, hi = max(0, i - w), min(len(p), i + w + 1)
    peak = float(p[lo:hi].max())
    g = int(round(guard_frac * symbol_rate / df))
    left = p[max(0, i - g):max(0, i - 3 * w)]
    right = p[min(len(p), i + 3 * w):min(len(p), i + g)]
    near = np.concatenate([left, right])
    floor = float(np.median(near)) if near.size else 0.0
    return {"alpha_hz": target, "peak": peak, "floor": floor,
            "contrast_db": float(20 * np.log10((peak + 1e-12) / (floor + 1e-12)))}


def cyclic_features(x, fs, symbol_rate, n_alpha=241, span=2.6):
    """Cyclic-domain profile out to `span` x the symbol rate, plus the
    strength of the symbol-rate line relative to its local neighbourhood."""
    alphas = np.linspace(0.0, span * symbol_rate, n_alpha)
    prof, pk = spectral_coherence_profile(x, fs, alphas)
    out = {"alphas": alphas, "profile": prof, "peak_freq": pk}
    for k, name in ((1, "alpha_Rs"), (2, "alpha_2Rs")):
        target = k * symbol_rate
        if target > alphas[-1]:
            continue
        i = int(np.argmin(np.abs(alphas - target)))
        w = max(3, n_alpha // 40)
        lo, hi = max(0, i - 6 * w), min(len(alphas), i + 6 * w)
        near = np.concatenate([prof[lo:max(lo, i - w)], prof[min(hi, i + w):hi]])
        base = float(np.median(near)) if len(near) else 0.0
        local = float(prof[max(0, i - w):i + w + 1].max())
        out[name] = {"value": local, "baseline": base,
                     "contrast_db": float(20 * np.log10((local + 1e-9) / (base + 1e-9)))}
    return out


def constellation_diagnostics(sym, ideal, gain=None, tx=None):
    """Describe the shape of the received clusters, measured not assumed.

    The key number is the ratio of tangential to radial cluster spread.  AWGN
    is isotropic, so it produces round clouds -- ratio near 1.  Phase noise and
    residual CFO displace samples along the arc only, so they stretch clouds
    tangentially -- ratio well above 1.  Amplifier compression and timing error
    act on magnitude, so they stretch radially -- ratio below 1.  Three
    different causes that all read as "blur" to the eye are separated by this
    one measurement.

    When the transmitted symbols are known (they are, in a lab) each received
    sample is compared against its own true symbol.  Assigning samples to the
    nearest ideal point instead would silently mislabel everything under a bulk
    rotation and report the rotation as cluster spread.
    """
    if ideal is None or len(sym) < 8:
        return None
    n = len(sym)
    if tx is not None and len(tx) >= n:
        tx = np.asarray(tx[:n])
        g = np.vdot(tx, sym) / np.vdot(tx, tx)      # complex: scale and rotation
        ref_pt = g * tx
        rot = float(np.degrees(np.angle(g)))
        scale = float(abs(g))
        ideal_scaled = ideal * abs(g)
        # Group by which ideal point each sample was actually sent as.
        di = np.abs(tx[:, None] - ideal[None, :])
        lab = np.argmin(di, axis=1)
    else:
        scale = gain if gain is not None else float(
            np.sqrt(np.mean(np.abs(sym) ** 2) / np.mean(np.abs(ideal) ** 2)))
        ideal_scaled = ideal * scale
        d = np.abs(sym[:, None] - ideal_scaled[None, :])
        lab = np.argmin(d, axis=1)
        ref_pt = ideal_scaled[lab]
        rot = float(np.degrees(np.angle(np.mean(sym * np.conj(ref_pt)))))

    # How well does "clusters near scaled ideal points" describe this at all?
    # Under a large accumulated rotation the samples are spread over every
    # angle, the single-gain fit collapses, and every cluster statistic derived
    # from it becomes meaningless.  Better to say so than to report a number.
    coh = float(np.abs(np.vdot(ref_pt, sym)) /
                (np.linalg.norm(ref_pt) * np.linalg.norm(sym) + 1e-18))

    err = sym - ref_pt
    u = ref_pt / (np.abs(ref_pt) + 1e-12)
    radial = (err * np.conj(u)).real
    tangential = (err * np.conj(u)).imag
    rad_s, tan_s = float(np.std(radial)), float(np.std(tangential))

    per_cluster = []
    rad_in, tan_in = [], []
    for k in range(len(ideal_scaled)):
        m_ = lab == k
        if m_.sum() < 5:
            continue
        pts = sym[m_]
        c = complex(np.mean(pts))
        # Spread measured *within* each cluster, about that cluster's own centre.
        # Measuring every point against the global ideal grid instead would count
        # a DC offset -- which displaces every cluster by the same vector and
        # smears nothing -- as though it had blurred them.
        rk = float(np.std(radial[m_] - np.mean(radial[m_])))
        tk = float(np.std(tangential[m_] - np.mean(tangential[m_])))
        rad_in.append(rk); tan_in.append(tk)
        per_cluster.append({"ideal_i": float(ideal_scaled[k].real),
                            "ideal_q": float(ideal_scaled[k].imag),
                            "centroid_i": float(c.real), "centroid_q": float(c.imag),
                            "n": int(m_.sum()),
                            "radial_std": rk, "tangential_std": tk})
    if rad_in:
        rad_s, tan_s = float(np.mean(rad_in)), float(np.mean(tan_in))

    # Deterministic displacement: how far each cluster's centre has moved from
    # where it should be, as distinct from how much the samples scatter about
    # that centre.  Noise moves centres barely at all and scatters a lot;
    # I/Q imbalance, DC offset and amplifier compression do the opposite.  Two
    # very different failures that both read as "the constellation looks wrong".
    if per_cluster:
        cen_err = np.array([complex(c["centroid_i"] - c["ideal_i"],
                                    c["centroid_q"] - c["ideal_q"]) for c in per_cluster])
        centroid_rms = float(np.sqrt(np.mean(np.abs(cen_err) ** 2)))
        # Remove the common translation to isolate shear/compression from a
        # pure DC shift.
        shear_rms = float(np.sqrt(np.mean(np.abs(cen_err - cen_err.mean()) ** 2)))
    else:
        centroid_rms = shear_rms = 0.0

    dd = np.abs(ideal_scaled[:, None] - ideal_scaled[None, :])
    np.fill_diagonal(dd, np.inf)
    d_min = float(dd.min())
    cloud = float(np.sqrt(rad_s ** 2 + tan_s ** 2))
    centroid = complex(np.mean(sym))

    a = np.angle(sym)
    h, _ = np.histogram(a, bins=72, range=(-np.pi, np.pi))
    p_ = h / max(h.sum(), 1)
    ent = float(-np.sum(p_[p_ > 0] * np.log(p_[p_ > 0])) / np.log(72))
    amp = np.abs(sym)
    return {
        "n_points": int(n),
        "coherence": coh,
        "model_valid": bool(coh > 0.5),
        "centroid_offset": float(abs(centroid) / max(scale, 1e-12)),
        "centroid_i": float(centroid.real / max(scale, 1e-12)),
        "centroid_q": float(centroid.imag / max(scale, 1e-12)),
        "radial_std": rad_s / max(scale, 1e-12),
        "tangential_std": tan_s / max(scale, 1e-12),
        "tangential_over_radial": float(tan_s / max(rad_s, 1e-12)),
        "mean_cluster_std": cloud / max(scale, 1e-12),
        "d_min_scaled": d_min / max(scale, 1e-12),
        "separation_sigma": float((d_min / 2) / max(cloud, 1e-12)),
        "mean_error": float(np.mean(np.abs(err)) / max(scale, 1e-12)),
        "centroid_rms_error": centroid_rms / max(scale, 1e-12),
        "shear_rms_error": shear_rms / max(scale, 1e-12),
        "deterministic_over_random": float(shear_rms / max(cloud, 1e-12)),
        "net_rotation_deg": rot,
        "gain": scale,
        "angular_uniformity": ent,
        "amplitude_cv": float(np.std(amp) / max(np.mean(amp), 1e-12)),
        "clusters_populated": int(len(per_cluster)),
        "clusters_expected": int(len(ideal_scaled)),
        "per_cluster": per_cluster[:64],
    }
