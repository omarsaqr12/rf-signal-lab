"""Run one experiment: generate, impair, measure, verify, and package for the UI.

The important design choice here is that the clean signal is kept alongside the
impaired one all the way through.  That makes two things possible that a normal
SDR pipeline cannot do: an exact error vector (rather than an estimate), and a
stage-by-stage record of what each impairment did on its own.
"""
import numpy as np

from .dsp.modulators import generate, ALL_MODS
from .dsp import impairments as imp
from .dsp import measure as M
from .tutor import severity as sev

MAX_CONST_PTS = 2500
MAX_TRACE_PTS = 1600
SPEC_MAX = 112


def _f(a, nd=5):
    """Round for transport; JSON of raw float64 is mostly wasted bytes."""
    a = np.asarray(a, dtype=float)
    a = np.where(np.isfinite(a), a, 0.0)
    return np.round(a, nd).tolist()


def _dec(a, n):
    a = np.asarray(a)
    if len(a) <= n:
        return a, np.arange(len(a))
    idx = np.linspace(0, len(a) - 1, n).astype(int)
    return a[idx], idx


DEFAULTS = {
    "mod": "qpsk", "n_samples": 4096, "fs": 1e6, "sps": 8, "rolloff": 0.35,
    "seed": 0, "rx_timing_recovery": True, "rx_matched_filter": True,
    "stft_symbols": 4, "stft_span_symbols": 48,
    "mod_index": None, "bt": None, "msg_bw": None, "am_depth": 0.8,
    "freq_dev": None, "n_fft": 64, "n_used": 52, "cp_len": 16, "sub_mod": "16qam",
    "impairments": {},
}


def _cfg(user):
    c = dict(DEFAULTS)
    c.update({k: v for k, v in (user or {}).items() if k != "impairments"})
    c["impairments"] = dict((user or {}).get("impairments") or {})
    return c


def apply_chain(sig, cfg):
    """Walk the physical chain, snapshotting after every enabled stage."""
    x = sig.x.copy()
    fs, seed = sig.fs, cfg["seed"]
    imps = cfg["impairments"]
    reports, stages = {}, []
    for key in imp.CHAIN_ORDER:
        p = imps.get(key)
        if not p or not p.get("enabled"):
            continue
        before = x
        if key == "pa":
            x, r = imp.pa_nonlinearity(x, p.get("ibo_db", 6.0), p.get("model", "rapp"),
                                       p.get("rapp_p", 2.0))
        elif key == "multipath":
            d = np.asarray(p.get("delays_us", [0.0, 2.0]), float) * 1e-6
            x, r = imp.multipath(x, fs, d, p.get("gains_db", [0.0, -3.0]),
                                 p.get("phases_deg"))
        elif key == "fading":
            x, r = imp.fading(x, fs, p.get("kind", "rayleigh"),
                              p.get("k_factor_db", 6.0), p.get("doppler_hz", 0.0),
                              int(p.get("n_taps", 1)),
                              p.get("tap_spacing_us", 1.0) * 1e-6, seed)
        elif key == "interference":
            x, r = imp.interference(x, fs, p.get("sir_db", 10.0), p.get("kind", "cw"),
                                    p.get("freq_offset_hz", 150e3),
                                    p.get("bandwidth_hz"), seed)
        elif key == "cfo":
            x, r = imp.cfo(x, fs, p.get("cfo_hz", 1000.0))
        elif key == "phase_offset":
            x, r = imp.phase_offset(x, p.get("deg", 30.0))
        elif key == "phase_noise":
            x, r = imp.phase_noise(x, fs, p.get("linewidth_hz", 0.0),
                                   p.get("rms_deg", 0.0), seed)
        elif key == "clock_offset":
            x, r = imp.clock_offset(x, p.get("ppm", 0.0),
                                    p.get("timing_offset_symbols", 0.0), sig.sps)
        elif key == "awgn":
            x, r = imp.awgn(x, p.get("snr_db", 20.0), seed)
        elif key == "iq_imbalance":
            x, r = imp.iq_imbalance(x, p.get("gain_db", 0.5), p.get("phase_deg", 3.0))
        elif key == "dc_offset":
            x, r = imp.dc_offset(x, p.get("i", 0.1), p.get("q", 0.0))
        elif key == "clipping":
            x, r = imp.clipping(x, p.get("headroom_db", 4.0))
        elif key == "quantization":
            x, r = imp.quantization(x, int(p.get("bits", 8)), p.get("headroom_db", 6.0))
        else:
            continue
        reports[key] = r
        stages.append({"key": key, "stage": imp.CHAIN_STAGE[key],
                       "delta_evm_pct": float(_evm(before, x) * 100),
                       "snapshot": x.copy()})
    return x, reports, stages


def _ideal_sync(ref, y):
    """Remove the constant gain and linear phase ramp an ideal synchroniser
    would remove, and return the corrected signal."""
    z = y * np.conj(ref)
    mag = np.abs(ref) ** 2
    keep = mag > 0.05 * np.mean(mag)
    if keep.sum() < 16:
        return y
    n = np.arange(len(z))
    ph = np.unwrap(np.angle(z[keep]))
    slope, icept = np.polyfit(n[keep], ph, 1)
    corrected = y * np.exp(-1j * (slope * n + icept))
    return corrected if _evm(ref, corrected) < _evm(ref, y) else y


def _evm_after_sync(ref, y):
    """Error remaining after a *perfect* synchroniser has done its best.

    We fit and remove a constant gain and a linear phase ramp -- exactly what
    ideal gain control plus ideal carrier-frequency and phase correction would
    remove.  Whatever survives is the part of the damage no amount of
    front-end synchronisation can undo, which is the practical question:
    "could preprocessing fix this, or is the information actually gone?"
    """
    z = y * np.conj(ref)
    mag = np.abs(ref) ** 2
    keep = mag > 0.05 * np.mean(mag)
    if keep.sum() < 16:
        return _evm(ref, y), 0.0
    n = np.arange(len(z))
    ph = np.unwrap(np.angle(z[keep]))
    slope, icept = np.polyfit(n[keep], ph, 1)
    corrected = y * np.exp(-1j * (slope * n + icept))
    raw = _evm(ref, y)
    fixed = _evm(ref, corrected)
    # Under heavy noise the phase fit is itself noise; if "correcting" made
    # things worse, the honest conclusion is that there was no ramp to remove.
    if fixed >= raw:
        return raw, 0.0
    return fixed, float(slope)


def _evm(ref, y):
    """Error vector magnitude of y against ref, after fitting out a complex gain
    (a global scale and rotation are not distortion)."""
    d = np.vdot(ref, ref)
    g = np.vdot(ref, y) / d if abs(d) > 0 else 1.0
    err = y - g * ref
    p = np.mean(np.abs(g * ref) ** 2)
    return float(np.sqrt(np.mean(np.abs(err) ** 2) / p)) if p > 0 else 0.0


# --------------------------------------------------------------------------

def measure_all(sig, clean, y, cfg, pre=None):
    fs, sps = sig.fs, sig.sps
    rs = sig.symbol_rate
    out = {}
    out["waveform_evm_pct"] = _evm(clean, y) * 100
    resid, slope = _evm_after_sync(clean, y)
    out["residual_evm_pct"] = resid * 100
    out["implied_cfo_from_sync_hz"] = float(slope * fs / (2 * np.pi))
    out["correctable_fraction"] = float(
        1.0 - min(1.0, resid / max(_evm(clean, y), 1e-12))) if _evm(clean, y) > 1e-9 else 0.0
    out["papr_db"] = M.papr_db(y)
    out["papr_clean_db"] = M.papr_db(clean)

    if sig.linear:
        # With timing recovery off the receiver samples on the nominal grid,
        # which is what makes a static timing offset visible instead of being
        # silently absorbed.
        force = None if cfg.get("rx_timing_recovery", True) else 0
        mf_on = cfg.get("rx_matched_filter", True)
        sy, ph = M.symbol_samples(y, sig, apply_mf=mf_on, timing_phase=force, trim=14)
        sc, _ = M.symbol_samples(clean, sig, apply_mf=mf_on, timing_phase=ph, trim=14)
        tx0 = sig.symbols[14:]
        # Derive the symbol lag from the derotated signal.  Which symbol you are
        # looking at is a timing question, and mixing a phase problem into it
        # makes the answer depend on the carrier offset -- which it should not.
        sy_ds, _ = M.symbol_samples(_ideal_sync(clean, y), sig, apply_mf=mf_on,
                                    timing_phase=ph, trim=14)
        lag = M.align_symbol_lag(sy_ds, tx0)
        sy_a, tx_a = M.apply_symbol_lag(sy, tx0, lag)
        g, evm = M.align_gain(sy_a, tx_a)
        out["symbol_evm_pct"] = float(evm * 100)
        out["const_gain"] = {"mag": float(abs(g)), "deg": float(np.degrees(np.angle(g)))}
        out["timing_phase"] = int(ph)
        out["symbol_lag"] = int(lag)
        out["n_symbols_shown"] = int(len(sy_a))
        out["_sy_aligned"], out["_tx_aligned"] = sy_a, tx_a
    else:
        out["symbol_evm_pct"] = None

    f, psd = M.welch_psd(y, fs, 512)
    fc_, psd_c = M.welch_psd(clean, fs, 512)
    bw, cen = M.occupied_bandwidth(f, psd, 0.99)
    bwc, cenc = M.occupied_bandwidth(fc_, psd_c, 0.99)
    out["occupied_bw_hz"] = bw
    out["occupied_bw_clean_hz"] = bwc
    out["spectral_centroid_hz"] = cen
    out["noise_floor_db"] = M.noise_floor_db(psd)

    dc, dcrel = M.estimate_dc(y)
    out["dc"] = {"i": float(dc.real), "q": float(dc.imag), "rel_rms": float(dcrel)}
    gi, pi_, irr, floor = M.estimate_iq_imbalance(y)
    out["iq_blind"] = {"equiv_gain_db": gi, "equiv_phase_deg": pi_,
                       "image_rejection_db": irr, "measurement_floor_db": floor}

    # Pick the estimator the signal can actually support.  The M-th power trick
    # needs an M-fold symmetric constellation; OFDM has a cyclic prefix instead;
    # FSK and analog have neither, so all that is left is the spectrum's centre
    # of mass.  Running the wrong one returns a confident, wrong number.
    order = sig.info.get("order")
    if sig.family == "ofdm":
        est, strength, unamb = M.estimate_cfo_cyclic_prefix(
            y, sig.info["n_fft"], sig.info["cp_len"], fs)
        out["cfo_blind"] = {"hz": float(est) if est is not None else None,
                            "peak_sharpness": strength,
                            "method": "cyclic-prefix correlation (Van de Beek)",
                            "unambiguous_range_hz": unamb,
                            "applicable": True}
    elif sig.family == "fsk":
        est, unc, mean_est = M.estimate_cfo_fsk(
            y, fs, rs, sig.info.get("tone_spacing_symbol_rates", 1) * rs, len(y) / max(sps, 1))
        out["cfo_blind"] = {
            "hz": float(est), "uncertainty_hz": unc * 0.3,
            "peak_sharpness": 0.0,
            "method": "midpoint of the extreme frequency states",
            "reliable": True,
            "alternative": {"method": "mean instantaneous frequency",
                            "hz": float(mean_est), "uncertainty_hz": unc},
            "caveat": (f"Taking the plain mean of the instantaneous frequency instead gives "
                       f"{mean_est:.0f} Hz -- biased by +/-{unc:.0f} Hz because a finite frame "
                       f"never draws its symbols in perfect balance. The midpoint between the "
                       f"outer frequency states avoids that bias entirely, because the tones "
                       f"are symmetric about the carrier however the data falls.")}
    elif sig.family in ("psk", "qam", "apsk", "pam"):
        m_ = order if (sig.family == "psk" and order in (2, 4, 8)) else 4
        est, sharp = M.estimate_cfo_mth_power(y, fs, m=m_)
        sym_ok = sig.family != "apsk"
        out["cfo_blind"] = {
            "hz": float(est), "peak_sharpness": sharp,
            "method": f"{m_}th-power (needs {m_}-fold constellation symmetry)",
            "reliable": bool(sharp > 20 and sym_ok),
            "caveat": (None if sym_ok else
                       "APSK places points on concentric rings with different point counts, so "
                       "raising to the 4th power does not collapse the modulation into a single "
                       "tone. The estimator returns a number, but it is not a CFO estimate. "
                       "This is the chicken-and-egg at the heart of blind synchronisation: "
                       "choosing the right estimator already requires knowing the modulation.")}
    else:
        est, spread = M.estimate_cfo_spectral_centroid(y, fs)
        out["cfo_blind"] = {"hz": float(est), "peak_sharpness": 0.0,
                            "method": "spectral centroid (no constellation symmetry to exploit)",
                            "spectral_spread_hz": spread, "reliable": True,
                            "caveat": "assumes the spectrum is symmetric about its own carrier."}

    r, prom, how = M.estimate_symbol_rate(y, fs)
    out["symbol_rate_blind"] = {"hz": float(r) if r else None, "prominence": float(prom),
                                "method": how, "truth_hz": float(rs),
                                "reliable": bool(prom and prom > 5)}
    m24 = M.estimate_snr_m2m4(y)
    out["snr_blind_m2m4_db"] = float(m24) if np.isfinite(m24) else None
    out["snr_blind_note"] = (None if np.isfinite(m24) else
                             "the moment-based estimator returns an unbounded value here: it "
                             "assumes a noisy constant-modulus signal, and with no noise present "
                             "there is nothing for it to measure")
    # Oracle SNR.  It must be measured against the signal as it was *just
    # before* the noise was added -- comparing against the original clean
    # waveform would count every earlier impairment (a CFO rotation above all)
    # as if it were noise, and report nonsense.
    ref = pre if pre is not None else clean
    d = np.vdot(ref, ref)
    g = np.vdot(ref, y) / d if abs(d) > 0 else 1.0
    err = y - g * ref
    pe = float(np.mean(np.abs(err) ** 2))
    # An infinite SNR is the correct answer when no noise was added, but it is
    # not a number a plot or a JSON payload can carry.  Report it as absent with
    # the reason attached, rather than as a huge finite value that looks like a
    # measurement.
    sn = (10 * np.log10(np.mean(np.abs(g * ref) ** 2) / pe)) if pe > 0 else np.inf
    out["snr_oracle_db"] = float(sn) if np.isfinite(sn) else None
    out["snr_oracle_note"] = (None if np.isfinite(sn) else
                              "no measurable error against the reference, so the SNR is "
                              "unbounded -- nothing has been added to this signal")
    out["snr_oracle_reference"] = ("the signal immediately before AWGN was added"
                                   if pre is not None else "the clean transmit waveform")

    if sig.linear and sig.ideal is not None:
        sy2, tx2 = out["_sy_aligned"], out["_tx_aligned"]
        out["constellation_diag"] = M.constellation_diagnostics(sy2, sig.ideal, tx=tx2)
        sc2, _ = M.symbol_samples(clean, sig, timing_phase=out["timing_phase"], trim=14)
        sc2a, txc = M.apply_symbol_lag(sc2, sig.symbols[14:],
                                       M.align_symbol_lag(sc2, sig.symbols[14:]))
        out["constellation_diag_clean"] = M.constellation_diagnostics(sc2a, sig.ideal, tx=txc)
        # The same measurement after an ideal synchroniser has removed the bulk
        # gain and linear phase ramp.  Comparing the two answers "is the
        # structure destroyed, or merely rotated out of view?"
        y_sync = _ideal_sync(clean, y)
        ss, _ = M.symbol_samples(y_sync, sig, apply_mf=mf_on, timing_phase=ph, trim=14)
        ssa, txs = M.apply_symbol_lag(ss, sig.symbols[14:],
                                      M.align_symbol_lag(ss, sig.symbols[14:]))
        out["constellation_diag_synced"] = M.constellation_diagnostics(ssa, sig.ideal, tx=txs)
    else:
        out["constellation_diag"] = None
        out["constellation_diag_clean"] = None
        out["constellation_diag_synced"] = None

    src = (M.symbol_samples(y, sig, trim=14)[0] if sig.linear else y)
    out["cumulants"] = M.cumulants(src)
    out["cumulants_ideal"] = M.IDEAL_CUMULANTS.get(sig.mod)

    if sig.linear:
        mf, _ = M.matched_filter(y, sig)
        I, Q = M.eye_traces(mf, sps, 140, 2, phase=out["timing_phase"])
        op, jit = M.eye_opening(I, sps)
        out["eye_opening"] = float(op)
        out["eye_jitter"] = float(jit)
    return out


def verify(cfg, reports, meas, sig):
    """Predicted vs measured, for the impairments that can be checked blind."""
    checks = []

    def add(name, predicted, measured, tol, unit, note=""):
        ok = abs(measured - predicted) <= tol
        checks.append({"name": name, "predicted": float(predicted),
                       "measured": float(measured), "unit": unit,
                       "tolerance": float(tol), "agrees": bool(ok), "note": note})

    if "cfo" in reports:
        cb = meas["cfo_blind"]
        if cb.get("reliable", True):
            coarse = "centroid" in cb["method"]
            add("Carrier frequency offset", reports["cfo"]["cfo_hz"],
                cb["hz"] if cb["hz"] is not None else 0.0,
                max(0.05 * abs(reports["cfo"]["cfo_hz"]) + cb.get("uncertainty_hz", 0.0),
                    (sig.fs / 256 if coarse else sig.fs / len(sig.x))), "Hz",
                f"recovered blind by the {cb['method']} method, with no knowledge of the "
                f"configured value")
        else:
            checks.append({
                "name": "Carrier frequency offset", "predicted": reports["cfo"]["cfo_hz"],
                "measured": cb["hz"] if cb["hz"] is not None else 0.0, "unit": "Hz",
                "tolerance": 0.0, "agrees": None, "inconclusive": True,
                "note": "the blind estimator does not apply to this signal. "
                        + (cb.get("caveat") or "")})
    if "awgn" in reports and meas["snr_oracle_db"] is not None:
        add("Signal-to-noise ratio", reports["awgn"]["snr_db"], meas["snr_oracle_db"], 1.0, "dB",
            "measured as the exact error against the clean reference")
    if "dc_offset" in reports:
        a = reports["dc_offset"]["magnitude_rel_rms"]
        add("DC offset magnitude", a / np.sqrt(1 + a * a), meas["dc"]["rel_rms"], 0.02,
            "x RMS", "the reading is relative to the RMS after the offset was added")
    if "iq_imbalance" in reports:
        add("Image rejection", reports["iq_imbalance"]["image_rejection_db"],
            meas["iq_blind"]["image_rejection_db"],
            max(3.0, 0.15 * abs(reports["iq_imbalance"]["image_rejection_db"])), "dB",
            f"blind estimate from E[x^2]; floor for this frame is "
            f"{meas['iq_blind']['measurement_floor_db']:.0f} dB")
    if "quantization" in reports:
        add("Quantisation SNR", reports["quantization"]["theoretical_sqnr_db"],
            reports["quantization"]["measured_sqnr_db"], 3.0, "dB",
            "6.02 bits + 1.76 - headroom, against the measured error power")
    if not reports:
        checks.append({"name": "Clean reference", "predicted": 0.0,
                       "measured": meas["waveform_evm_pct"], "unit": "% EVM",
                       "tolerance": 0.5, "agrees": meas["waveform_evm_pct"] < 0.5,
                       "note": "no impairments enabled, so the error should be zero"})
    srb = meas["symbol_rate_blind"]
    if srb["reliable"]:
        add("Blind symbol-rate estimate", srb["truth_hz"], srb["hz"] or 0.0,
            0.06 * srb["truth_hz"], "Hz",
            f"{srb['method']}; line prominence {srb['prominence']:.1f}x")
    else:
        checks.append({
            "name": "Blind symbol-rate estimate", "predicted": srb["truth_hz"],
            "measured": srb["hz"] or 0.0, "unit": "Hz", "tolerance": 0.0,
            "agrees": None, "inconclusive": True,
            "note": (f"{srb['method']}; line prominence only "
                     f"{srb['prominence']:.1f}x, below the reliability threshold. This is a "
                     f"non-detection, not a measurement -- the number happens to be close or "
                     f"not, but nothing in the data supports it.")})
    return checks


# --------------------------------------------------------------------------

def build_plots(sig, clean, y, cfg, reports, meas):
    fs, sps = sig.fs, sig.sps
    n = len(y)
    rs = sig.symbol_rate
    P = {}

    # ---- constellation -------------------------------------------------
    if sig.linear:
        # With timing recovery off the receiver samples on the nominal grid,
        # which is what makes a static timing offset visible instead of being
        # silently absorbed.
        force = None if cfg.get("rx_timing_recovery", True) else 0
        mf_on = cfg.get("rx_matched_filter", True)
        sy, ph = M.symbol_samples(y, sig, apply_mf=mf_on, timing_phase=force, trim=14)
        sc, _ = M.symbol_samples(clean, sig, apply_mf=mf_on, timing_phase=ph, trim=14)
        g = meas.get("const_gain", {"mag": 1.0})
        scale = g["mag"] if g["mag"] > 0 else 1.0
    else:
        sy, sc, ph, scale = y, clean, 0, float(np.sqrt(np.mean(np.abs(y) ** 2)))
    sy_d, idx = _dec(sy, MAX_CONST_PTS)
    sc_d, _ = _dec(sc, MAX_CONST_PTS)
    raw_d, ridx = _dec(y, MAX_CONST_PTS)
    P["constellation"] = {
        "symbols": {"i": _f(sy_d.real, 4), "q": _f(sy_d.imag, 4),
                    "t": _f(idx / max(len(sy) - 1, 1), 4)},
        "symbols_clean": {"i": _f(sc_d.real, 4), "q": _f(sc_d.imag, 4)},
        "raw": {"i": _f(raw_d.real, 4), "q": _f(raw_d.imag, 4),
                "t": _f(ridx / max(n - 1, 1), 4)},
        "ideal": ({"i": _f((sig.ideal * scale).real), "q": _f((sig.ideal * scale).imag)}
                  if sig.ideal is not None and sig.family != "ofdm" else None),
        "scale": scale,
        "has_symbol_view": bool(sig.linear),
        "timing_phase": int(ph),
    }

    # ---- time domain ---------------------------------------------------
    yd, ti = _dec(y, MAX_TRACE_PTS)
    cd, _ = _dec(clean, MAX_TRACE_PTS)
    t_ms = ti / fs * 1e3
    P["iq_time"] = {"t": _f(t_ms, 6), "i": _f(yd.real, 4), "q": _f(yd.imag, 4),
                    "i_clean": _f(cd.real, 4), "q_clean": _f(cd.imag, 4),
                    "sps": sps, "symbol_period_ms": 1e3 / rs}
    P["magnitude"] = {"t": _f(t_ms, 6), "mag": _f(np.abs(yd), 4), "mag_clean": _f(np.abs(cd), 4),
                      "rms": float(np.sqrt(np.mean(np.abs(y) ** 2))),
                      "papr_db": meas["papr_db"]}
    if "fading" in reports:
        env, _ = _dec(np.abs(reports["fading"]["gain_envelope"]), MAX_TRACE_PTS)
        P["magnitude"]["channel_envelope"] = _f(env)

    # Unwrapping the raw phase of a PSK/QAM signal is a trap: the modulation
    # itself jumps by up to 180 degrees between symbols, and np.unwrap resolves
    # those jumps arbitrarily, so the trace random-walks by tens of radians on a
    # perfectly clean signal.  Removing the modulation first -- raise to the
    # M-th power, unwrap, divide by M -- leaves only the carrier phase, which is
    # the thing this view is actually for.
    # Two different phase questions, kept separate because conflating them is
    # what makes phase plots confusing.
    #
    #   "signal phase"   = angle(clean)      -- what the modulation itself does.
    #                                           For FSK this ramps by design.
    #   "carrier phase"  = angle(y . conj(clean)) -- what the impairment chain
    #                                           did on top.  Exactly zero on a
    #                                           clean signal, for every
    #                                           modulation, with no assumption
    #                                           about constellation symmetry.
    #
    # Sampling only where the clean envelope is strong avoids the pulse-shaping
    # nulls, where the phase is undefined and the unwrap would wander.
    up_raw = np.unwrap(np.angle(y))
    mag = np.abs(clean)
    strong = mag > 0.35 * np.sqrt(np.mean(mag ** 2))
    idx_s = np.flatnonzero(strong)
    if len(idx_s) > 32:
        rel = y[idx_s] * np.conj(clean[idx_s])
        carrier = np.unwrap(np.angle(rel))
        carrier = carrier - carrier[0]
        t_ph = idx_s / fs * 1e3
    else:
        carrier = np.zeros(n)
        t_ph = np.arange(n) / fs * 1e3
        idx_s = np.arange(n)
    sig_phase = np.unwrap(np.angle(clean))
    sig_phase = sig_phase - sig_phase[0]

    upd, _ = _dec(carrier, MAX_TRACE_PTS)
    t_phd, _ = _dec(t_ph, MAX_TRACE_PTS)
    sigd, _ = _dec(sig_phase, MAX_TRACE_PTS)
    rawd, _ = _dec(up_raw, MAX_TRACE_PTS)
    P["phase"] = {"t": _f(t_phd, 6), "t_raw": _f(t_ms, 6),
                  "wrapped": _f(np.angle(yd), 4),
                  "unwrapped": _f(upd, 4),
                  "signal_phase": _f(sigd, 4),
                  "unwrapped_raw": _f(rawd, 4),
                  "method": "angle(received x conj(clean)), sampled where the envelope is strong",
                  "total_drift_rad": float(carrier[-1] - carrier[0]) if len(carrier) else 0.0,
                  "raw_drift_rad": float(up_raw[-1] - up_raw[0]),
                  "signal_drift_rad": float(sig_phase[-1] - sig_phase[0]),
                  "span_fraction": float((t_ph[-1] - t_ph[0]) / (n / fs * 1e3)) if len(t_ph) > 1 else 1.0}

    fi = M.inst_freq(y, fs)
    fic = M.inst_freq(clean, fs)
    sm = max(1, sps // 2)
    fid, _ = _dec(np.convolve(fi, np.ones(sm) / sm, "same"), MAX_TRACE_PTS)
    ficd, _ = _dec(np.convolve(fic, np.ones(sm) / sm, "same"), MAX_TRACE_PTS)
    levels = None
    if sig.family == "fsk":
        h, L = sig.info["mod_index_h"], sig.info["levels"]
        levels = [float(a * h * rs / 2) for a in range(-(L - 1), L, 2)]
    P["inst_freq"] = {"t": _f(t_ms, 6), "f": _f(fid / 1e3, 3), "f_clean": _f(ficd / 1e3, 3),
                      "levels_khz": [l / 1e3 for l in levels] if levels else None,
                      "unit": "kHz", "smoothing_samples": sm}

    # ---- spectrum ------------------------------------------------------
    ff, mg = M.fft_mag_db(y, fs, max_points=1024)
    _, mgc = M.fft_mag_db(clean, fs, max_points=1024)
    P["fft"] = {"f": _f(ff / 1e3, 3), "mag": _f(mg, 2), "mag_clean": _f(mgc, 2),
                "unit": "kHz"}
    fp, pp = M.welch_psd(y, fs, 512)
    _, ppc = M.welch_psd(clean, fs, 512)
    bw, cen = M.occupied_bandwidth(fp, pp, 0.99)
    P["psd"] = {"f": _f(fp / 1e3, 3), "psd": _f(pp, 2), "psd_clean": _f(ppc, 2),
                "noise_floor_db": meas["noise_floor_db"],
                "occupied_bw_khz": bw / 1e3, "centroid_khz": cen / 1e3,
                "symbol_rate_khz": rs / 1e3,
                "nominal_bw_khz": rs * (1 + sig.info.get("rolloff", 0.35)) / 1e3
                if sig.linear else None,
                "unit": "kHz"}

    # STFT window length, in symbol periods.  This is the time-frequency
    # trade-off made adjustable rather than hidden: a short window resolves fast
    # frequency hops but smears frequency, a long one does the reverse, and
    # neither can be sharp at once.  Four symbols is a compromise that resolves
    # FSK tone spacing while still showing the hopping.
    sym_len = sig.info.get("symbol_len") if sig.family == "ofdm" else sps
    # Default the window to what the family's story needs: FSK's story is the
    # hopping, so favour time resolution; OFDM and dense QAM need frequency
    # resolution to show subcarrier structure and spectral shape.
    default_sym = {"fsk": 2, "ofdm": 8, "analog": 8}.get(sig.family, 4)
    want = int(round(float(cfg.get("stft_symbols") or default_sym) * max(sym_len, 1)))
    nps = int(2 ** round(np.log2(max(16, min(512, want, max(16, n // 8))))))
    # Transform only the span that will be displayed, at full hop resolution.
    # Computing over the whole frame and then throwing away 90% of the columns
    # leaves a handful of blocks where the structure should be.
    span = int(min(n, max(8 * sym_len, cfg.get("stft_span_symbols", 48) * max(sym_len, 1))))
    hop = max(1, nps // 8)
    sf, st, S = M.spectrogram(y[:span], fs, nperseg=nps, noverlap=nps - hop,
                              nfft=max(nps * 4, 128))
    if S.shape[0] > SPEC_MAX:
        k = np.linspace(0, S.shape[0] - 1, SPEC_MAX).astype(int)
        S, sf = S[k], sf[k]
    if S.shape[1] > SPEC_MAX:
        k = np.linspace(0, S.shape[1] - 1, SPEC_MAX).astype(int)
        S, st = S[:, k], st[k]
    vmax = float(np.percentile(S, 99.5))
    P["spectrogram"] = {"f": _f(sf / 1e3, 2), "t": _f(st * 1e3, 4),
                        "nperseg": nps,
                        "window_symbols": round(nps / max(sym_len, 1), 2),
                        "freq_resolution_khz": float(fs / nps / 1e3),
                        "time_resolution_ms": float(nps / fs * 1e3),
                        "span_symbols": round(span / max(sym_len, 1), 1),
                        "span_fraction": round(span / n, 3),
                        "zero_pad": int(max(nps * 4, 128) // nps),
                        "S": [np.round(row).astype(int).tolist() for row in S],
                        "vmin": float(vmax - 55), "vmax": vmax, "unit": "kHz"}

    # ---- eye -----------------------------------------------------------
    if sig.linear:
        mf, _ = M.matched_filter(y, sig)
        I, Q = M.eye_traces(mf, sps, 90, 2, phase=meas["timing_phase"])
        s = float(np.max(np.abs(I))) or 1.0
        op, jit = M.eye_opening(I, sps)
        P["eye"] = {"t": _f((np.arange(I.shape[1]) / sps - 1.0), 4),
                    "traces_i": [_f(r / s, 4) for r in I],
                    "traces_q": [_f(r / s, 4) for r in Q],
                    "opening": op, "jitter": jit, "sps": sps}
    else:
        P["eye"] = None

    # ---- autocorrelation ------------------------------------------------
    maxlag = min(400, n // 4)
    r = M.autocorrelation(y, maxlag)
    rc = M.autocorrelation(clean, maxlag)
    P["autocorr"] = {"lag": list(range(len(r))), "r": _f(r, 4), "r_clean": _f(rc, 4),
                     "sps": sps,
                     "expect_peak_lag": (sig.info["n_fft"] if sig.family == "ofdm" else None)}

    # ---- cumulants ------------------------------------------------------
    cum = meas["cumulants"]
    P["cumulants"] = {"measured": {k: round(v, 4) for k, v in cum.items()},
                      "ideal": meas["cumulants_ideal"],
                      "table": M.IDEAL_CUMULANTS,
                      "n_symbols": int(len(sy))}

    # ---- cyclostationarity ----------------------------------------------
    if sig.family == "ofdm":
        a_ref = fs / sig.info["symbol_len"]
        prof = M.cyclic_profile(y, fs, a_ref, span=3.0, max_lag_samples=100)
    else:
        a_ref = rs
        prof = M.cyclic_profile(y, fs, rs, span=2.6, sps=sps)
    ad, ai = _dec(prof["alphas"], 900)
    P["cyclic"] = {"alpha_khz": _f(ad / 1e3, 3),
                   "profile": _f(prof["profile"][ai], 5),
                   "conj_profile": _f(prof["conj_profile"][ai], 5),
                   "marker_khz": a_ref / 1e3,
                   "marker_label": ("1 / OFDM symbol" if sig.family == "ofdm" else "symbol rate"),
                   "line": M.cyclic_line_strength(prof, a_ref, 1),
                   "conj_at_zero": float(prof["conj_profile"][0]),
                   "alpha_resolution_hz": prof["alpha_resolution_hz"]}

    # ---- amplitude histogram --------------------------------------------
    a_y, a_c = np.abs(y), np.abs(clean)
    hi = float(max(a_y.max(), a_c.max()))
    edges = np.linspace(0, hi, 61)
    P["amp_hist"] = {"edges": _f(edges, 4),
                     "counts": np.histogram(a_y, edges)[0].tolist(),
                     "counts_clean": np.histogram(a_c, edges)[0].tolist()}

    # ---- PAPR CCDF -------------------------------------------------------
    p = np.abs(y) ** 2 / np.mean(np.abs(y) ** 2)
    thr = np.linspace(0, max(12.0, 10 * np.log10(p.max() + 1e-12)), 60)
    P["papr_ccdf"] = {"threshold_db": _f(thr, 3),
                      "prob": _f([float(np.mean(10 * np.log10(p + 1e-18) > t)) for t in thr], 6),
                      "prob_clean": _f([float(np.mean(
                          10 * np.log10(np.abs(clean) ** 2 / np.mean(np.abs(clean) ** 2) + 1e-18) > t))
                          for t in thr], 6)}

    # ---- AM/AM transfer (only meaningful with a nonlinearity) ------------
    if "pa" in reports or "clipping" in reports:
        ain = np.abs(clean)
        aout = np.abs(y)
        k = np.argsort(ain)
        kk = k[np.linspace(0, len(k) - 1, 1200).astype(int)]
        P["am_am"] = {"in": _f(ain[kk], 4), "out": _f(aout[kk], 4),
                      "linear_ref": _f(ain[kk] * float(np.mean(aout) / max(np.mean(ain), 1e-12)), 4),
                      "am_pm_deg": _f(np.degrees(np.angle(y[kk] * np.conj(clean[kk]))), 3)}
    else:
        P["am_am"] = None

    # ---- channel response ------------------------------------------------
    if "multipath" in reports:
        r_ = reports["multipath"]
        d = np.asarray(r_["delays_s"]); gdb = np.asarray(r_["gains_db"])
        L = int(np.ceil(d.max() * fs)) + 1
        h = np.zeros(max(L, 8), dtype=complex)
        for di, gi_ in zip(d, gdb):
            h[int(round(di * fs))] += 10 ** (gi_ / 20.0)
        H = np.fft.fftshift(np.fft.fft(h, 1024))
        fh = np.fft.fftshift(np.fft.fftfreq(1024, 1 / fs))
        P["channel"] = {"tap_delay_us": _f(d * 1e6, 4), "tap_gain_db": _f(gdb, 2),
                        "f_khz": _f(fh / 1e3, 3),
                        "H_db": _f(20 * np.log10(np.abs(H) + 1e-9), 2),
                        "coherence_bw_khz": r_["coherence_bandwidth_hz"] / 1e3,
                        "rms_delay_spread_us": r_["rms_delay_spread_s"] * 1e6}
    else:
        P["channel"] = None

    # ---- OFDM subcarrier view --------------------------------------------
    if sig.family == "ofdm":
        nfft, cp = sig.info["n_fft"], sig.info["cp_len"]
        L = nfft + cp
        ns = len(y) // L
        grid = []
        for s_ in range(ns):
            blk = y[s_ * L + cp: s_ * L + cp + nfft]
            if len(blk) == nfft:
                grid.append(np.fft.fft(blk) / np.sqrt(nfft))
        if grid:
            G = np.array(grid)
            used = np.concatenate([np.arange(1, sig.info["n_used"] // 2 + 1),
                                   np.arange(nfft - sig.info["n_used"] // 2, nfft)])
            pts = G[:, used].ravel()
            pd, _ = _dec(pts, MAX_CONST_PTS)
            P["ofdm"] = {"sub_i": _f(pd.real), "sub_q": _f(pd.imag),
                         "n_ofdm_symbols": int(len(grid)),
                         "subcarrier_power_db": _f(
                             20 * np.log10(np.mean(np.abs(G), axis=0) + 1e-12), 2),
                         "subcarrier_index": list(range(-nfft // 2, nfft // 2)),
                         "used_mask": [1 if ((k % nfft) in set(used.tolist())) else 0
                                       for k in range(-nfft // 2, nfft // 2)],
                         "ideal_i": _f(sig.ideal.real), "ideal_q": _f(sig.ideal.imag)}
    else:
        P["ofdm"] = None

    # ---- stage-by-stage transformation -----------------------------------
    return P


def stage_snapshots(sig, clean, stages):
    """Constellation of the signal after each chain stage, for the
    clean -> impairment -> result view."""
    out = [{"key": "clean", "label": "Clean transmit waveform", "stage": "transmitter",
            "delta_evm_pct": 0.0, **_const_of(clean, sig)}]
    for s in stages:
        out.append({"key": s["key"], "label": s["key"].replace("_", " "),
                    "stage": s["stage"], "delta_evm_pct": s["delta_evm_pct"],
                    **_const_of(s["snapshot"], sig)})
    return out


def _const_of(x, sig, n=1200):
    if sig.linear:
        s, _ = M.symbol_samples(x, sig, trim=14)
    else:
        s = x
    d, idx = _dec(s, n)
    return {"i": _f(d.real, 4), "q": _f(d.imag, 4),
            "t": _f(idx / max(len(s) - 1, 1), 4)}


# --------------------------------------------------------------------------

def run(user_cfg):
    cfg = _cfg(user_cfg)
    sig = generate(cfg["mod"], int(cfg["n_samples"]), float(cfg["fs"]), int(cfg["sps"]),
                   float(cfg["rolloff"]), int(cfg["seed"]),
                   mod_index=cfg.get("mod_index"), bt=cfg.get("bt"),
                   msg_bw=cfg.get("msg_bw") or float(cfg["fs"]) / 40.0,
                   am_depth=cfg.get("am_depth"), freq_dev=cfg.get("freq_dev"),
                   n_fft=int(cfg["n_fft"]), n_used=int(cfg["n_used"]),
                   cp_len=int(cfg["cp_len"]), sub_mod=cfg["sub_mod"])
    clean = sig.x.copy()
    y, reports, stages = apply_chain(sig, cfg)
    pre_awgn = None
    for i, st in enumerate(stages):
        if st["key"] == "awgn":
            pre_awgn = stages[i - 1]["snapshot"] if i > 0 else clean
            break
    meas = measure_all(sig, clean, y, cfg, pre=pre_awgn)
    geo = sev.geometry(sig)
    sevs = {}
    for k, r in reports.items():
        fn = sev.SEVERITY_FUNCS.get(k)
        if fn:
            sevs[k] = fn(cfg["impairments"].get(k, {}), sig, r, geo)
    checks = verify(cfg, reports, meas, sig)
    plots = build_plots(sig, clean, y, cfg, reports, meas)
    for k in ("_sy_aligned", "_tx_aligned"):
        meas.pop(k, None)
    return {
        "config": {k: v for k, v in cfg.items()},
        "signal": {
            "mod": sig.mod, "family": sig.family, "fs": sig.fs, "sps": sig.sps,
            "symbol_rate": sig.symbol_rate, "n_samples": len(sig.x),
            "duration_ms": sig.duration * 1e3,
            "n_symbols": len(sig.x) / max(sig.sps, 1),
            "info": {k: v for k, v in sig.info.items() if not isinstance(v, np.ndarray)},
        },
        "geometry": {k: (v if not isinstance(v, np.ndarray) else v.tolist())
                     for k, v in geo.items()},
        "reports": {k: {kk: (vv.tolist() if isinstance(vv, np.ndarray) else
                             (complex(vv).real if isinstance(vv, complex) else vv))
                        for kk, vv in r.items() if kk != "gain_envelope"}
                    for k, r in reports.items()},
        "measurements": meas,
        "severity": sevs,
        "overall": sev.overall(sevs, meas["waveform_evm_pct"]),
        "verification": checks,
        "plots": plots,
        "chain": stage_snapshots(sig, clean, stages),
        "active": list(reports.keys()),
    }
