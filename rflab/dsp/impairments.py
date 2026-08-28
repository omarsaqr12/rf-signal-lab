"""Channel and hardware impairments.

Applied in the order a real signal actually meets them, because the order
changes the result.  Amplifier compression happens at the transmitter, before
the channel; DC offset and I/Q imbalance are receiver analog defects, so they
land after the channel and after thermal noise; quantisation is last because
it happens at the ADC.  Apply I/Q imbalance before the channel and you get a
physically impossible signal that no real radio could produce.

    TX  ->  PA nonlinearity
        ->  multipath / fading channel
        ->  interference added over the air
        ->  carrier frequency offset, phase offset, phase noise   (RX LO)
        ->  sample clock offset                                   (RX clock)
        ->  AWGN                                                  (thermal)
        ->  I/Q imbalance, DC offset                              (RX analog)
        ->  AGC, clipping, quantisation                           (ADC)
    ->  RX

Every function returns (signal, report) where `report` records what the
impairment physically did, measured on the samples rather than assumed.
"""
import numpy as np

CHAIN_ORDER = [
    "pa", "multipath", "fading", "interference",
    "cfo", "phase_offset", "phase_noise", "clock_offset",
    "awgn", "iq_imbalance", "dc_offset", "clipping", "quantization",
]

CHAIN_STAGE = {
    "pa": "transmitter", "multipath": "channel", "fading": "channel",
    "interference": "over the air", "cfo": "receiver LO",
    "phase_offset": "receiver LO", "phase_noise": "receiver LO",
    "clock_offset": "receiver sample clock", "awgn": "receiver thermal noise",
    "iq_imbalance": "receiver analog", "dc_offset": "receiver analog",
    "clipping": "ADC front end", "quantization": "ADC",
}


# --------------------------------------------------------------------------
# Fractional-delay / arbitrary-time resampler (shared by several impairments)
# --------------------------------------------------------------------------

def sinc_resample(x, t_new, n_taps=16):
    """Evaluate x at arbitrary (fractional) sample positions t_new.

    Windowed-sinc interpolation.  Linear interpolation would be much cheaper
    but it is itself a low-pass filter, so it would quietly add its own
    distortion on top of the impairment we are trying to study.
    """
    n = len(x)
    t = np.asarray(t_new, dtype=float)
    base = np.floor(t).astype(int)
    half = n_taps // 2
    offs = np.arange(-half + 1, half + 1)
    idx = base[:, None] + offs[None, :]
    frac = (t[:, None] - idx)
    w = np.sinc(frac) * np.kaiser(n_taps, 8.0)[None, :]
    w = w / (np.sum(w, axis=1, keepdims=True) + 1e-15)
    idx_c = np.clip(idx, 0, n - 1)
    vals = x[idx_c]
    vals = np.where((idx >= 0) & (idx < n), vals, 0.0)
    return np.sum(vals * w, axis=1)


def _power(x):
    return float(np.mean(np.abs(x) ** 2))


# --------------------------------------------------------------------------
# 1. Power amplifier nonlinearity  (transmitter)
# --------------------------------------------------------------------------

def pa_nonlinearity(x, ibo_db=6.0, model="rapp", rapp_p=2.0,
                    saleh=(2.0, 1.0, np.pi / 3, 1.0)):
    """Amplifier compression.

    IBO (input back-off) is the headroom between the average input power and
    the amplifier's saturation point.  Large IBO = operating well below
    saturation = nearly linear but power-inefficient.  Small IBO = efficient
    but compressing.  That trade is why APSK exists for satellite links and
    why 256-QAM needs a very linear transmitter.
    """
    p_in = _power(x)
    a_sat = np.sqrt(p_in * 10 ** (ibo_db / 10.0))
    r = np.abs(x)
    ph = np.angle(x)
    if model == "rapp":
        g = 1.0 / (1.0 + (r / (a_sat + 1e-18)) ** (2 * rapp_p)) ** (1.0 / (2 * rapp_p))
        r_out = r * g
        ph_out = ph
        am_pm_deg = 0.0
    else:  # saleh (travelling-wave tube)
        aa, ba, ap, bp = saleh
        rn = r / (a_sat + 1e-18)
        r_out = a_sat * aa * rn / (1.0 + ba * rn ** 2)
        dphi = ap * rn ** 2 / (1.0 + bp * rn ** 2)
        ph_out = ph + dphi
        am_pm_deg = float(np.degrees(np.max(np.abs(dphi))))
    y = r_out * np.exp(1j * ph_out)

    peak_in = float(np.max(r))
    k = int(np.argmax(r))
    compression_db = float(20 * np.log10((r_out[k] + 1e-18) / (peak_in + 1e-18)))
    frac_compressed = float(np.mean(r > 0.7 * a_sat))
    return y, {
        "model": model, "ibo_db": ibo_db,
        "a_sat_over_rms": float(a_sat / np.sqrt(p_in)),
        "peak_compression_db": compression_db,
        "max_am_pm_deg": am_pm_deg,
        "fraction_samples_near_saturation": frac_compressed,
        "papr_before_db": float(10 * np.log10(peak_in ** 2 / p_in)),
        "papr_after_db": float(10 * np.log10(np.max(r_out) ** 2 / (_power(y) + 1e-18))),
    }


# --------------------------------------------------------------------------
# 2. Multipath  (channel)
# --------------------------------------------------------------------------

def multipath(x, fs, delays_s, gains_db, phases_deg=None):
    """Sum of delayed, attenuated, phase-shifted copies.

    Whether this is benign or destructive is decided by the delay spread
    relative to the symbol period, not by the number of paths.
    """
    delays_s = np.asarray(delays_s, dtype=float)
    gains = 10 ** (np.asarray(gains_db, dtype=float) / 20.0)
    if phases_deg is None:
        phases = np.zeros(len(gains))
    else:
        phases = np.radians(np.asarray(phases_deg, dtype=float))
    n = len(x)
    t = np.arange(n, dtype=float)
    y = np.zeros(n, dtype=complex)
    for d, g, p in zip(delays_s, gains, phases):
        shift = d * fs
        y += g * np.exp(1j * p) * sinc_resample(x, t - shift)

    pw = gains ** 2
    tot = np.sum(pw)
    mean_delay = float(np.sum(pw * delays_s) / tot) if tot > 0 else 0.0
    rms_ds = float(np.sqrt(np.sum(pw * (delays_s - mean_delay) ** 2) / tot)) if tot > 0 else 0.0
    coh_bw = (1.0 / (5.0 * rms_ds)) if rms_ds > 0 else None
    return y, {
        "n_paths": len(gains), "delays_s": delays_s.tolist(),
        "gains_db": np.asarray(gains_db, dtype=float).tolist(),
        "mean_excess_delay_s": mean_delay, "rms_delay_spread_s": rms_ds,
        "coherence_bandwidth_hz": float(coh_bw) if coh_bw is not None else None,
        "coherence_bandwidth_note": (None if coh_bw is not None else
                                     "zero delay spread: the channel is flat, so coherence "
                                     "bandwidth is unbounded"),
        "max_excess_delay_s": float(delays_s.max() - delays_s.min()) if len(delays_s) else 0.0,
    }


# --------------------------------------------------------------------------
# 3. Rayleigh / Rician fading  (channel)
# --------------------------------------------------------------------------

def _jakes_process(n, fs, f_d, rng):
    """Complex Gaussian process with a Jakes (classical) Doppler spectrum.

    Built by shaping white noise in the frequency domain, which is the
    standard cheap way to get the right temporal correlation.
    """
    if f_d <= 0:
        g = (rng.standard_normal() + 1j * rng.standard_normal()) / np.sqrt(2)
        return np.full(n, g, dtype=complex)
    nfft = int(2 ** np.ceil(np.log2(max(n * 2, 1024))))
    f = np.fft.fftfreq(nfft, 1 / fs)
    s = np.zeros(nfft)
    inb = np.abs(f) < f_d
    s[inb] = 1.0 / (np.pi * f_d * np.sqrt(1 - (f[inb] / f_d) ** 2) + 1e-12)
    s[np.abs(f) >= f_d] = 0.0
    w = (rng.standard_normal(nfft) + 1j * rng.standard_normal(nfft)) / np.sqrt(2)
    g = np.fft.ifft(np.fft.fft(w) * np.sqrt(s))
    g = g[:n]
    p = np.sqrt(np.mean(np.abs(g) ** 2))
    return g / p if p > 0 else g


def fading(x, fs, kind="rayleigh", k_factor_db=6.0, f_doppler=0.0,
           n_taps=1, tap_spacing_s=0.0, seed=0):
    """Flat or frequency-selective fading with a Jakes Doppler spectrum.

    Rayleigh = no line of sight, every path is a scatterer.  Rician adds a
    deterministic line-of-sight component whose power ratio to the scattered
    part is the K factor: K -> infinity is a clean AWGN-like channel,
    K = 0 dB means the direct path carries no more power than the scatter.
    """
    rng = np.random.default_rng(seed)
    n = len(x)
    y = np.zeros(n, dtype=complex)
    t = np.arange(n, dtype=float)
    taps = []
    # Exponential power-delay profile across taps.
    tap_pow = np.exp(-np.arange(n_taps) * 0.7)
    tap_pow = tap_pow / np.sum(tap_pow)
    for i in range(n_taps):
        g = _jakes_process(n, fs, f_doppler, rng)
        if kind == "rician" and i == 0:
            k = 10 ** (k_factor_db / 10.0)
            los = np.sqrt(k / (k + 1.0))
            g = los + np.sqrt(1.0 / (k + 1.0)) * g
        g = g * np.sqrt(tap_pow[i])
        d = i * tap_spacing_s * fs
        y += g * (sinc_resample(x, t - d) if d > 0 else x)
        taps.append(g)

    env = np.abs(np.sum([taps[i] for i in range(n_taps)], axis=0))
    env_db = 20 * np.log10(env + 1e-12)
    coh_time = (0.423 / f_doppler) if f_doppler > 0 else None
    delays = np.arange(n_taps) * tap_spacing_s
    mean_d = float(np.sum(tap_pow * delays))
    rms_ds = float(np.sqrt(np.sum(tap_pow * (delays - mean_d) ** 2)))
    return y, {
        "kind": kind, "k_factor_db": k_factor_db if kind == "rician" else None,
        "f_doppler_hz": f_doppler, "n_taps": n_taps,
        "coherence_time_s": float(coh_time) if coh_time is not None else None,
        "coherence_time_note": (None if coh_time is not None else
                                "zero Doppler: the channel is frozen for the whole frame, so "
                                "coherence time is unbounded"),
        "rms_delay_spread_s": rms_ds,
        "coherence_bandwidth_hz": (float(1.0 / (5 * rms_ds)) if rms_ds > 0 else None),
        "coherence_bandwidth_note": (None if rms_ds > 0 else
                                     "a single tap has zero delay spread, so the channel is flat "
                                     "across all frequencies and coherence bandwidth is unbounded"),
        "fade_depth_db": float(np.median(env_db) - np.percentile(env_db, 1)),
        "envelope_range_db": float(env_db.max() - env_db.min()),
        "gain_envelope": env,
    }


# --------------------------------------------------------------------------
# 4. Interference  (over the air)
# --------------------------------------------------------------------------

def interference(x, fs, sir_db=10.0, kind="cw", freq_offset_hz=0.0,
                 bandwidth_hz=None, seed=0):
    """Another transmitter in or near the band."""
    rng = np.random.default_rng(seed + 991)
    n = len(x)
    t = np.arange(n) / fs
    p_sig = _power(x)
    p_int = p_sig / (10 ** (sir_db / 10.0))
    if kind == "cw":
        i_sig = np.exp(1j * (2 * np.pi * freq_offset_hz * t + rng.uniform(0, 2 * np.pi)))
    elif kind == "chirp":
        bw = bandwidth_hz or fs / 8
        i_sig = np.exp(1j * 2 * np.pi * (freq_offset_hz * t + 0.5 * bw * t ** 2 / (n / fs)))
    else:  # modulated adjacent-channel signal
        bw = bandwidth_hz or fs / 8
        sps_i = max(2, int(round(fs / bw)))
        nsym = n // sps_i + 8
        sym = (rng.integers(0, 2, nsym) * 2 - 1) + 1j * (rng.integers(0, 2, nsym) * 2 - 1)
        up = np.zeros(nsym * sps_i, dtype=complex)
        up[::sps_i] = sym
        from .pulse import rrc_taps
        h = rrc_taps(0.35, sps_i, 8)
        i_sig = np.convolve(up, h, mode="full")[:n]
        i_sig = i_sig * np.exp(2j * np.pi * freq_offset_hz * t)
    i_sig = i_sig / (np.sqrt(_power(i_sig)) + 1e-18) * np.sqrt(p_int)
    return x + i_sig, {
        "kind": kind, "sir_db": sir_db, "freq_offset_hz": freq_offset_hz,
        "bandwidth_hz": bandwidth_hz,
        "interferer_power_rel_db": float(10 * np.log10(_power(i_sig) / p_sig)),
    }


# --------------------------------------------------------------------------
# 5. Oscillator: CFO, phase offset, phase noise  (receiver LO)
# --------------------------------------------------------------------------

def cfo(x, fs, cfo_hz):
    n = np.arange(len(x))
    y = x * np.exp(2j * np.pi * cfo_hz * n / fs)
    total = 2 * np.pi * cfo_hz * len(x) / fs
    return y, {
        "cfo_hz": cfo_hz,
        "phase_per_sample_rad": float(2 * np.pi * cfo_hz / fs),
        "total_phase_rad": float(total),
        "total_rotations": float(total / (2 * np.pi)),
    }


def phase_offset(x, deg):
    return x * np.exp(1j * np.radians(deg)), {"phase_offset_deg": deg}


def phase_noise(x, fs, linewidth_hz=0.0, rms_deg=0.0, seed=0):
    """Two mechanisms, deliberately kept separate.

    A free-running oscillator random-walks: the phase variance grows with
    time, which is what a Lorentzian linewidth describes.  A locked
    oscillator instead has bounded residual jitter about a stable mean.  They
    look different on a phase-vs-time plot -- one wanders off, the other
    fuzzes around a line -- and lumping them together hides that.
    """
    rng = np.random.default_rng(seed + 7717)
    n = len(x)
    ph = np.zeros(n)
    if linewidth_hz > 0:
        step_var = 2 * np.pi * linewidth_hz / fs
        ph = ph + np.cumsum(rng.standard_normal(n) * np.sqrt(step_var))
    if rms_deg > 0:
        ph = ph + rng.standard_normal(n) * np.radians(rms_deg)
    y = x * np.exp(1j * ph)
    return y, {
        "linewidth_hz": linewidth_hz, "stationary_rms_deg": rms_deg,
        "realised_rms_deg": float(np.degrees(np.std(ph))),
        "realised_drift_deg": float(np.degrees(ph[-1] - ph[0])) if n else 0.0,
        "phase_track": ph,
    }


# --------------------------------------------------------------------------
# 6. Sample clock offset and timing offset  (receiver clock)
# --------------------------------------------------------------------------

def clock_offset(x, ppm=0.0, timing_offset_symbols=0.0, sps=8):
    """Receiver sampling clock running fast or slow, plus a static timing
    error.  The drift accumulates: the damage at the end of a long frame is
    far worse than at the start, which is why frame length and clock accuracy
    have to be considered together."""
    n = len(x)
    eps = ppm * 1e-6
    t = np.arange(n, dtype=float) * (1.0 + eps) + timing_offset_symbols * sps
    y = sinc_resample(x, t)
    drift_samples = eps * n
    return y, {
        "ppm": ppm,
        "static_timing_offset_symbols": timing_offset_symbols,
        "drift_samples_over_frame": float(drift_samples),
        "drift_symbols_over_frame": float(drift_samples / sps),
    }


# --------------------------------------------------------------------------
# 7. AWGN  (thermal)
# --------------------------------------------------------------------------

def awgn(x, snr_db, seed=0):
    rng = np.random.default_rng(seed + 4242)
    p_sig = _power(x)
    p_n = p_sig / (10 ** (snr_db / 10.0))
    n = np.sqrt(p_n / 2) * (rng.standard_normal(len(x)) + 1j * rng.standard_normal(len(x)))
    return x + n, {
        "snr_db": snr_db, "signal_power": p_sig, "noise_power": float(p_n),
        "noise_sigma_per_axis": float(np.sqrt(p_n / 2)),
        "realised_snr_db": float(10 * np.log10(p_sig / (_power(n) + 1e-18))),
    }


# --------------------------------------------------------------------------
# 8. Receiver analog defects
# --------------------------------------------------------------------------

def iq_imbalance(x, gain_db=0.0, phase_deg=0.0):
    """Separate I and Q analog paths that do not quite match.

    The clean way to see what this does: the output is a mix of the signal
    and its own conjugate.  The conjugate term is a mirror image about DC, so
    a single tone at +f grows a spurious twin at -f, and the constellation
    turns from square into a parallelogram.
    """
    g = 10 ** (gain_db / 20.0)
    ph = np.radians(phase_deg)
    i = x.real * g
    q = x.imag * np.cos(ph) + x.real * np.sin(ph)
    y = i + 1j * q
    # Image rejection for the standard small-imbalance model.
    a = (1 + g * np.exp(-1j * ph)) / 2.0
    b = (1 - g * np.exp(1j * ph)) / 2.0
    irr = float(-20 * np.log10(np.abs(b) / np.abs(a))) if abs(a) > 0 else np.inf
    return y, {
        "gain_imbalance_db": gain_db, "phase_imbalance_deg": phase_deg,
        "image_rejection_db": irr,
    }


def dc_offset(x, i_off=0.0, q_off=0.0):
    """Direct-conversion LO leakage: a constant added to every sample."""
    rms = np.sqrt(_power(x))
    off = (i_off + 1j * q_off) * rms
    return x + off, {
        "i_offset_rel": i_off, "q_offset_rel": q_off,
        "magnitude_rel_rms": float(np.abs(i_off + 1j * q_off)),
        "offset_complex": complex(off),
    }


# --------------------------------------------------------------------------
# 9. ADC: clipping and quantisation
# --------------------------------------------------------------------------

def clipping(x, headroom_db=6.0):
    """Hard limiting when the signal exceeds the converter's full scale.

    Headroom is the gap between full scale and the signal RMS.  A high-PAPR
    waveform (OFDM, high-order QAM) needs more headroom than a
    constant-envelope one, which is the whole reason PAPR is worth tracking.
    """
    rms = np.sqrt(_power(x))
    limit = rms * 10 ** (headroom_db / 20.0)
    r = np.abs(x)
    over = r > limit
    y = np.where(over, limit * np.exp(1j * np.angle(x)), x)
    return y, {
        "headroom_db": headroom_db, "clip_level_rel_rms": float(limit / rms),
        "fraction_clipped": float(np.mean(over)),
        "n_clipped": int(np.sum(over)),
        "papr_before_db": float(10 * np.log10(np.max(r) ** 2 / (rms ** 2))),
        "papr_after_db": float(10 * np.log10(np.max(np.abs(y)) ** 2 / (_power(y) + 1e-18))),
    }


def quantization(x, bits=8, headroom_db=6.0):
    """Finite ADC resolution.

    Two things fight here.  Set the gain too low and the signal uses only a
    few codes, so quantisation noise dominates.  Set it too high and the
    peaks clip.  The theoretical best case is about 6.02 bits + 1.76 dB of
    SNR, minus whatever headroom the peaks demand.
    """
    rms = np.sqrt(_power(x))
    full_scale = rms * 10 ** (headroom_db / 20.0)
    levels = 2 ** (bits - 1)
    step = full_scale / levels
    qi = np.clip(np.round(x.real / step), -levels, levels - 1) * step
    qq = np.clip(np.round(x.imag / step), -levels, levels - 1) * step
    y = qi + 1j * qq
    err = y - x
    sqnr = 10 * np.log10(_power(x) / (_power(err) + 1e-30))
    used = len(np.unique(np.round(x.real / step)))
    return y, {
        "bits": bits, "headroom_db": headroom_db,
        "step_size_rel_rms": float(step / rms),
        "theoretical_sqnr_db": float(6.02 * bits + 1.76 - headroom_db),
        "measured_sqnr_db": float(sqnr),
        "codes_used_i": int(used), "codes_available": int(2 ** bits),
        "clipped_fraction": float(np.mean(np.abs(x.real) > full_scale)),
    }
