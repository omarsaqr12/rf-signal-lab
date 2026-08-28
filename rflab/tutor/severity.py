"""Severity, computed from physics rather than from a lookup table.

The rule this module follows: a severity label is only worth showing if it can
name the physical quantity that produced it.  "CFO = 2 kHz is MODERATE" is
almost meaningless -- 2 kHz is nothing to a 10 MBaud link and catastrophic to a
1 kBaud one.  So every judgement here is a ratio between the impairment and
something about this signal: its minimum constellation distance, its symbol
period, its frame duration, its subcarrier spacing.

The unifying idea for constellation-bearing modulations is a tolerance budget.
A symbol decision fails when a sample is displaced by more than half the
minimum distance d_min between constellation points.  So:

    phase tolerance      = (d_min / 2) / r_max      radians
    amplitude tolerance  =  d_min / 2               (unit-average-power units)

r_max is the outermost constellation radius, because the outer points are
displaced furthest by a given rotation.  Those two numbers turn every
impairment into the same question: how much of the budget did it spend?
"""
import numpy as np

LEVELS = ["NEGLIGIBLE", "LOW", "MODERATE", "HIGH", "SEVERE"]


def _level(x, t_low, t_mod, t_high, t_sev):
    """Map a ratio onto a label plus a 0-1 score that is continuous across
    the boundaries, so nothing jumps from LOW to SEVERE on a tiny nudge."""
    edges = [t_low, t_mod, t_high, t_sev]
    i = int(np.searchsorted(edges, x))
    i = min(i, 4)
    lo = 0.0 if i == 0 else edges[i - 1]
    hi = edges[i] if i < 4 else edges[3] * 4
    frac = 0.0 if hi <= lo else np.clip((x - lo) / (hi - lo), 0, 1)
    return LEVELS[i], float(np.clip((i + frac) / 5.0, 0, 1))


def geometry(sig):
    """The tolerance budget for this modulation."""
    g = {"family": sig.family, "mod": sig.mod}
    if sig.family == "ofdm":
        nfft = sig.info["n_fft"]
        scs = sig.fs / nfft
        sub = sig.ideal
        d = np.abs(sub[:, None] - sub[None, :])
        np.fill_diagonal(d, np.inf)
        g.update({"subcarrier_spacing_hz": float(scs),
                  "cp_len": sig.info["cp_len"],
                  "cp_duration_s": sig.info["cp_len"] / sig.fs,
                  "sub_d_min": float(d.min()),
                  "sub_r_max": float(np.abs(sub).max()),
                  "sub_phase_tolerance_rad": float(d.min() / 2 / np.abs(sub).max()),
                  "bits_per_symbol": sig.info.get("bits_per_symbol")})
        return g
    if sig.ideal is not None and len(sig.ideal) > 1:
        p = sig.ideal
        d = np.abs(p[:, None] - p[None, :])
        np.fill_diagonal(d, np.inf)
        d_min = float(d.min())
        r_max = float(np.abs(p).max())
        r_mean = float(np.mean(np.abs(p)))
        phases = np.unique(np.round(np.angle(p), 6))
        amps = np.unique(np.round(np.abs(p), 6))
        g.update({
            "order": len(p), "d_min": d_min, "r_max": r_max, "r_mean": r_mean,
            "n_distinct_phases": int(len(phases)),
            "n_distinct_amplitudes": int(len(amps)),
            "phase_tolerance_rad": d_min / 2.0 / max(r_max, 1e-9),
            "phase_tolerance_deg": float(np.degrees(d_min / 2.0 / max(r_max, 1e-9))),
            "amplitude_tolerance": d_min / 2.0,
            "bits_per_symbol": sig.info.get("bits_per_symbol"),
        })
    elif sig.family == "fsk":
        h = sig.info.get("mod_index_h", 1.0)
        rs = sig.symbol_rate
        g.update({"order": sig.info.get("levels", 2),
                  "tone_spacing_hz": h * rs,
                  "freq_tolerance_hz": h * rs / 2.0,
                  "bits_per_symbol": sig.info.get("bits_per_symbol")})
    else:  # analog
        g.update({"msg_bw_hz": sig.info.get("msg_bw_hz")})
    return g


def _q(z):
    from scipy.special import erfc
    return 0.5 * erfc(z / np.sqrt(2))


# --------------------------------------------------------------------------

def awgn_severity(cfg, sig, rep, geo):
    snr = rep["snr_db"]
    sps = sig.sps if sig.linear else 1
    esn0_db = snr + 10 * np.log10(max(sps, 1))
    esn0 = 10 ** (esn0_db / 10.0)
    sigma = np.sqrt(1.0 / (2 * esn0))          # per axis, at the symbol instant
    m = [{"label": "Sample SNR", "value": snr, "unit": "dB"},
         {"label": "Es/N0 after matched filter", "value": esn0_db, "unit": "dB",
          "note": f"matched filtering adds 10log10(sps) = {10*np.log10(max(sps,1)):.1f} dB"},
         {"label": "Noise sigma per axis at symbol", "value": sigma, "unit": ""}]

    if "d_min" in geo:
        sep = (geo["d_min"] / 2.0) / sigma
        # Nearest-neighbour union bound on the symbol error rate.
        ser = min(1.0, 2.0 * _q(sep))
        m += [{"label": "d_min / 2 in noise sigmas", "value": sep, "unit": "sigma",
               "note": "how many noise standard deviations of margin each decision has"},
              {"label": "Estimated symbol error rate", "value": ser, "unit": "",
               "note": "nearest-neighbour bound; the real curve is close at high SNR"}]
        lvl, score = _level(1.0 / max(sep, 1e-6), 1 / 5.5, 1 / 4.0, 1 / 2.8, 1 / 1.8)
        why = (
            f"{geo['mod'].upper()} normalised to unit average power has a minimum "
            f"distance of d_min = {geo['d_min']:.3f} between neighbouring constellation "
            f"points, so each decision has a margin of d_min/2 = {geo['d_min']/2:.3f}. "
            f"At {snr:.1f} dB sample SNR the matched filter leaves Es/N0 = {esn0_db:.1f} dB, "
            f"which is a per-axis noise sigma of {sigma:.4f}. The margin is therefore "
            f"{sep:.2f} sigma wide, giving roughly {ser:.2e} symbol errors. "
        )
        if sep > 5.5:
            why += "Clusters stay visually distinct and well inside their decision regions."
        elif sep > 4.0:
            why += "Clusters are visibly fuzzy but still clearly separated."
        elif sep > 2.8:
            why += "Adjacent clouds are starting to touch; the outer points blur first."
        elif sep > 1.8:
            why += "Clouds overlap substantially; counting the points by eye gets unreliable."
        else:
            why += ("Neighbouring clouds have merged. The constellation geometry that "
                    "identifies this modulation is largely destroyed at this SNR.")
        headline = f"decision margin is {sep:.1f} noise sigma"
    elif geo["family"] == "fsk":
        # A frequency discriminator needs enough SNR to keep phase-difference
        # noise below half the tone spacing.
        dev = geo["freq_tolerance_hz"]
        sigma_f = sig.fs / (2 * np.pi) * np.sqrt(2 / max(10 ** (snr / 10.0), 1e-9))
        sep = dev / max(sigma_f / np.sqrt(sig.sps), 1e-9)
        m += [{"label": "Half tone spacing", "value": dev, "unit": "Hz"},
              {"label": "Frequency-estimate margin", "value": sep, "unit": "sigma"}]
        lvl, score = _level(1.0 / max(sep, 1e-6), 1 / 5.0, 1 / 3.5, 1 / 2.2, 1 / 1.4)
        headline = f"frequency decision margin is {sep:.1f} sigma"
        why = (f"FSK decides between tones {geo['tone_spacing_hz']/1e3:.1f} kHz apart, so the "
               f"usable margin is half that: {dev/1e3:.1f} kHz. At {snr:.1f} dB the noise on the "
               f"instantaneous-frequency estimate, averaged over one symbol, is about "
               f"{sigma_f/np.sqrt(sig.sps)/1e3:.1f} kHz, leaving {sep:.1f} sigma of margin. "
               "Notice this is a frequency question, not a constellation question -- the "
               "constellation view tells you very little about FSK under noise.")
    elif geo["family"] == "ofdm":
        sub_d = geo["sub_d_min"]
        sigma_sub = np.sqrt(1.0 / (2 * 10 ** (snr / 10.0)))
        sep = (sub_d / 2) / sigma_sub
        m += [{"label": "Per-subcarrier d_min", "value": sub_d, "unit": ""},
              {"label": "Subcarrier decision margin", "value": sep, "unit": "sigma"}]
        lvl, score = _level(1.0 / max(sep, 1e-6), 1 / 5.5, 1 / 4.0, 1 / 2.8, 1 / 1.8)
        headline = f"per-subcarrier margin is {sep:.1f} sigma"
        why = (f"The composite OFDM waveform looks like Gaussian noise whatever the SNR, so "
               f"judge this after the FFT instead. Each subcarrier carries "
               f"{sig.info['sub_mod'].upper()} with d_min = {sub_d:.3f}, and at {snr:.1f} dB "
               f"that leaves {sep:.1f} sigma of margin per subcarrier.")
    else:
        lvl, score = _level(-snr, -20, -10, 0, 10)
        headline = f"{snr:.0f} dB SNR on an analog waveform"
        why = (f"There is no constellation here, so noise shows up directly as a noisy "
               f"recovered message. At {snr:.1f} dB the demodulated output carries roughly "
               f"that much SNR for AM; FM does better above its threshold thanks to the "
               f"demodulator's noise-quieting effect, and much worse below it.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def cfo_severity(cfg, sig, rep, geo):
    f0 = rep["cfo_hz"]
    rs = sig.symbol_rate
    n = len(sig.x)
    total_rad = abs(rep["total_phase_rad"])
    per_sym_rad = 2 * np.pi * abs(f0) / rs
    m = [{"label": "CFO", "value": f0, "unit": "Hz"},
         {"label": "CFO / symbol rate", "value": f0 / rs, "unit": "",
          "note": "the scale-free way to state a frequency offset"},
         {"label": "Phase rotation per symbol", "value": np.degrees(per_sym_rad), "unit": "deg"},
         {"label": "Total rotation over the frame", "value": total_rad / (2 * np.pi),
          "unit": "revolutions"},
         {"label": "Frame duration", "value": n / sig.fs * 1e3, "unit": "ms"}]

    if geo["family"] == "ofdm":
        scs = geo["subcarrier_spacing_hz"]
        eps = abs(f0) / scs
        ici_db = 10 * np.log10(max((np.pi * eps) ** 2 / 3.0, 1e-12))
        m += [{"label": "CFO / subcarrier spacing", "value": eps, "unit": ""},
              {"label": "Inter-carrier interference", "value": ici_db, "unit": "dB",
               "note": "relative to subcarrier power, approx (pi.eps)^2/3"}]
        lvl, score = _level(eps, 0.005, 0.02, 0.05, 0.15)
        headline = f"{eps*100:.2f}% of a subcarrier spacing, ICI at {ici_db:.0f} dB"
        why = (f"OFDM is the case where CFO stops being a rotation and becomes "
               f"interference. Subcarriers are only orthogonal when sampled exactly on "
               f"their own frequency; an offset of {f0:.0f} Hz against a "
               f"{scs/1e3:.2f} kHz spacing is {eps*100:.2f}% of a bin, which leaks roughly "
               f"{ici_db:.0f} dB of inter-carrier interference into every subcarrier. "
               f"Unlike a single-carrier rotation, this cannot be undone by derotating "
               f"after the FFT -- the orthogonality is already gone.")
    elif geo["family"] == "fsk":
        tol = geo["freq_tolerance_hz"]
        r = abs(f0) / tol
        m += [{"label": "CFO / half tone spacing", "value": r, "unit": ""}]
        lvl, score = _level(r, 0.05, 0.2, 0.5, 1.0)
        headline = f"{r*100:.0f}% of the half tone spacing"
        why = (f"For FSK a carrier offset simply slides every tone by the same "
               f"{f0:.0f} Hz. The tones stay {geo['tone_spacing_hz']/1e3:.1f} kHz apart, so "
               f"the pattern of frequency states survives -- only its absolute position "
               f"moves. That is why FSK is far more forgiving of CFO than PSK: a classifier "
               f"reading the spacing between frequency states, rather than their absolute "
               f"values, barely notices. The offset is {r*100:.0f}% of the half tone spacing.")
    elif "phase_tolerance_rad" in geo:
        tol = geo["phase_tolerance_rad"]
        budget_sym = per_sym_rad / tol
        budget_frame = total_rad / tol
        smear = total_rad / (2 * np.pi)
        m += [{"label": "Phase tolerance of this constellation",
               "value": geo["phase_tolerance_deg"], "unit": "deg",
               "note": f"(d_min/2)/r_max for {geo['mod'].upper()}"},
              {"label": "Rotation per symbol / tolerance", "value": budget_sym, "unit": "x"},
              {"label": "Rotation per frame / tolerance", "value": budget_frame, "unit": "x"}]
        lvl, score = _level(budget_frame, 0.1, 0.5, 2.0, 10.0)
        headline = (f"{total_rad/(2*np.pi):.2f} revolutions over the frame, "
                    f"{budget_frame:.0f}x the phase budget")
        why = (
            f"A CFO of {f0:.0f} Hz at fs = {sig.fs/1e6:.2f} MHz advances the phase by "
            f"2pi{f0:.0f}/{sig.fs:.0f} = {rep['phase_per_sample_rad']:.6f} rad every sample. "
            f"Over this {n}-sample frame ({n/sig.fs*1e3:.2f} ms) that accumulates to "
            f"{total_rad:.2f} rad = {smear:.2f} full revolutions. "
            f"{geo['mod'].upper()} tolerates about {geo['phase_tolerance_deg']:.1f} deg of "
            f"rotation before a sample crosses into a neighbouring decision region "
            f"(that is (d_min/2)/r_max = ({geo['d_min']:.3f}/2)/{geo['r_max']:.3f}). "
            f"The frame spends {budget_frame:.1f}x that budget. "
        )
        if smear >= 1.0:
            why += ("Because the rotation exceeds a full turn, samples from every symbol "
                    "state are observed at every angle: the constellation fills into a ring "
                    "and the phase information that identifies a PSK order is gone, not "
                    "merely degraded.")
        elif budget_frame > 2:
            why += ("Clusters are drawn out into arcs. You can still see how many arcs "
                    "there are, which is why the class is often still recoverable here.")
        elif budget_frame > 0.5:
            why += "Clusters are noticeably smeared along the tangential direction."
        else:
            why += ("The whole frame rotates by less than one decision region, so this "
                    "looks much like a static phase offset.")
    else:
        lvl, score = _level(abs(f0) / max(geo.get("msg_bw_hz", rs), 1), 0.01, 0.05, 0.2, 1.0)
        headline = f"{f0:.0f} Hz offset on an analog carrier"
        why = (f"For AM a carrier offset makes the recovered envelope beat at {abs(f0):.0f} Hz "
               f"unless an envelope detector is used; for FM it appears as a constant DC "
               f"shift on the demodulated output, since FM reads frequency directly.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def phase_offset_severity(cfg, sig, rep, geo):
    d = rep["phase_offset_deg"]
    m = [{"label": "Phase offset", "value": d, "unit": "deg"}]
    if "phase_tolerance_deg" in geo and geo.get("n_distinct_phases", 0) > 0:
        sym = 360.0 / geo["n_distinct_phases"] if geo["family"] == "psk" else 90.0
        eff = abs(((d + sym / 2) % sym) - sym / 2)
        m += [{"label": "Rotational symmetry of the constellation", "value": sym, "unit": "deg"},
              {"label": "Effective offset after symmetry", "value": eff, "unit": "deg",
               "note": "rotating by exactly one symmetry step maps the constellation onto itself"},
              {"label": "Phase tolerance", "value": geo["phase_tolerance_deg"], "unit": "deg"}]
        lvl, score = _level(eff / max(geo["phase_tolerance_deg"], 1e-6), 0.15, 0.5, 1.0, 2.0)
        headline = f"{eff:.1f} deg after accounting for {sym:.0f} deg symmetry"
        why = (f"A constant phase offset rotates the whole constellation rigidly -- nothing "
               f"smears. {geo['mod'].upper()} has {sym:.0f} deg rotational symmetry, so a "
               f"rotation of exactly {sym:.0f} deg would be undetectable: the constellation "
               f"lands back on itself. Your {d:.1f} deg reduces to an effective "
               f"{eff:.1f} deg of displacement. This is the mildest of the phase impairments "
               f"and it is exactly why differential schemes (DBPSK, DQPSK) exist -- they "
               f"encode in phase changes, so a constant rotation cancels out entirely.")
    else:
        lvl, score = _level(abs(d) / 180.0, 0.1, 0.3, 0.6, 1.0)
        headline = f"{d:.0f} deg rigid rotation"
        why = ("This modulation does not carry information in absolute phase, so a constant "
               "rotation changes the picture without changing the content.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def phase_noise_severity(cfg, sig, rep, geo):
    rms = rep["realised_rms_deg"]
    lw = rep["linewidth_hz"]
    m = [{"label": "Oscillator linewidth", "value": lw, "unit": "Hz"},
         {"label": "Stationary jitter setting", "value": rep["stationary_rms_deg"], "unit": "deg"},
         {"label": "Realised RMS phase over the frame", "value": rms, "unit": "deg"},
         {"label": "Total wander across the frame", "value": rep["realised_drift_deg"], "unit": "deg"}]
    tol = geo.get("phase_tolerance_deg")
    if tol:
        r = rms / tol
        m.append({"label": "RMS phase / phase tolerance", "value": r, "unit": "x"})
        lvl, score = _level(r, 0.1, 0.33, 0.8, 2.0)
        headline = f"{rms:.1f} deg RMS against a {tol:.1f} deg budget"
        why = (
            f"Phase noise displaces samples tangentially -- along the arc, not radially -- "
            f"so clusters stretch into short arcs whose length grows with radius. "
            f"The realised RMS phase here is {rms:.2f} deg against "
            f"{geo['mod'].upper()}'s {tol:.1f} deg tolerance, i.e. {r:.2f}x the budget. "
        )
        if lw > 0:
            why += (f"A {lw:.0f} Hz linewidth means the phase random-walks rather than jitters "
                    f"about a fixed value: variance grows linearly with time, so the wander "
                    f"reached {abs(rep['realised_drift_deg']):.0f} deg by the end of the frame. "
                    f"Longer frames are strictly worse, which is the opposite of AWGN where "
                    f"longer frames help. ")
        if geo.get("n_distinct_amplitudes", 1) > 1:
            why += (f"Because the displacement scales with radius, the outer ring of this "
                    f"{geo['mod'].upper()} constellation is hit "
                    f"{geo['r_max']/max(geo['r_mean'],1e-9):.2f}x harder than the average point.")
    else:
        lvl, score = _level(rms / 45.0, 0.1, 0.3, 0.7, 1.5)
        headline = f"{rms:.1f} deg RMS phase jitter"
        why = ("This waveform does not use absolute phase for its symbol decisions, so phase "
               "noise mostly appears as a widened spectrum rather than a decision error.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def clock_offset_severity(cfg, sig, rep, geo):
    ppm = rep["ppm"]
    drift = abs(rep["drift_symbols_over_frame"])
    stat = abs(rep["static_timing_offset_symbols"])
    m = [{"label": "Sample clock error", "value": ppm, "unit": "ppm"},
         {"label": "Static timing offset", "value": stat, "unit": "symbols"},
         {"label": "Drift accumulated over the frame", "value": drift, "unit": "symbols"},
         {"label": "Frame length", "value": len(sig.x) / max(sig.sps, 1), "unit": "symbols"}]
    worst = drift + stat
    lvl, score = _level(worst, 0.02, 0.08, 0.25, 0.5)
    headline = f"{worst:.3f} symbol of timing error by the end of the frame"
    why = (
        f"A {ppm:.0f} ppm clock error means the receiver's idea of a sample period is wrong by "
        f"one part in {1e6/max(abs(ppm),1e-9):.0f}. Over {len(sig.x)} samples "
        f"({len(sig.x)/max(sig.sps,1):.0f} symbols) the sampling instants slide by "
        f"{abs(rep['drift_samples_over_frame']):.2f} samples = {drift:.3f} symbol periods"
        + (f", on top of a static {stat:.2f} symbol offset" if stat > 0 else "") + ". "
    )
    if worst < 0.02:
        why += "That is far inside the flat top of the pulse, so the eye barely moves."
    elif worst < 0.08:
        why += ("Samples are taken slightly off the pulse peak, adding a little ISI. The eye "
                "narrows but stays open.")
    elif worst < 0.25:
        why += ("The later symbols in the frame are sampled noticeably off-centre while the "
                "early ones are fine, so the constellation clouds smear radially and the "
                "damage grows along the frame -- an important asymmetry that a static timing "
                "error does not produce.")
    else:
        why += ("Sampling has slid a large fraction of a symbol. The eye closes, ISI dominates, "
                "and past half a symbol the receiver starts decoding the wrong symbol entirely.")
    why += (" This is the impairment where frame length matters most directly: halving the "
            "frame halves the accumulated drift.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def multipath_severity(cfg, sig, rep, geo):
    tau = rep["rms_delay_spread_s"]
    T = 1.0 / sig.symbol_rate
    r = tau / T
    bw = sig.symbol_rate * (1 + sig.info.get("rolloff", 0.35))
    bc = rep["coherence_bandwidth_hz"]
    bc = float("inf") if bc is None else bc
    m = [{"label": "RMS delay spread", "value": tau * 1e6, "unit": "us"},
         {"label": "Symbol period", "value": T * 1e6, "unit": "us"},
         {"label": "Delay spread / symbol period", "value": r, "unit": ""},
         {"label": "Coherence bandwidth", "value": bc / 1e3, "unit": "kHz"},
         {"label": "Signal bandwidth", "value": bw / 1e3, "unit": "kHz"},
         {"label": "Signal BW / coherence BW", "value": bw / max(bc, 1e-9), "unit": "",
          "note": "greater than 1 means the channel is frequency selective"}]
    lvl, score = _level(r, 0.02, 0.1, 0.3, 0.8)
    selective = bw > bc
    headline = (f"delay spread is {r:.3f} of a symbol; channel is "
                f"{'frequency selective' if selective else 'flat'}")
    why = (
        f"The paths arrive spread over an RMS delay of {tau*1e6:.2f} us against a symbol "
        f"period of {T*1e6:.2f} us, a ratio of {r:.3f}. The coherence bandwidth "
        f"1/(5.tau_rms) is {bc/1e3:.0f} kHz while the signal occupies {bw/1e3:.0f} kHz. "
    )
    if not selective:
        why += ("Because the signal is narrower than the coherence bandwidth the whole band "
                "fades together: this is flat fading, and its entire effect is one complex "
                "gain -- a scale and a rotation. The constellation shape survives intact.")
    else:
        why += ("The signal is wider than the coherence bandwidth, so different frequencies "
                "within the same signal are attenuated differently. That is frequency-selective "
                "fading: the channel acts as a filter, energy from one symbol leaks into the "
                "next, and the constellation distorts in a way no single complex gain can "
                "undo. Look at the channel frequency response for the notches, and at the eye "
                "diagram for the ISI they cause.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def fading_severity(cfg, sig, rep, geo):
    fd = rep["f_doppler_hz"]
    ct = rep["coherence_time_s"]
    ct = float("inf") if ct is None else ct
    dur = len(sig.x) / sig.fs
    fades = dur / ct if np.isfinite(ct) and ct > 0 else 0.0
    m = [{"label": "Channel type", "value": rep["kind"], "unit": ""},
         {"label": "Doppler spread", "value": fd, "unit": "Hz"},
         {"label": "Coherence time", "value": ct * 1e3 if np.isfinite(ct) else float("inf"), "unit": "ms"},
         {"label": "Frame duration", "value": dur * 1e3, "unit": "ms"},
         {"label": "Independent fades within the frame", "value": fades, "unit": ""},
         {"label": "Fade depth (median to 1st percentile)", "value": rep["fade_depth_db"], "unit": "dB"}]
    if rep["kind"] == "rician":
        k = rep["k_factor_db"]
        m.insert(1, {"label": "Rician K factor", "value": k, "unit": "dB",
                     "note": "line-of-sight power over scattered power"})
        base = _level(-k, -14, -8, -2, 6)
    else:
        base = ("HIGH", 0.65)
    lvl, score = base
    if fades > 2:
        i = min(LEVELS.index(lvl) + 1, 4)
        lvl, score = LEVELS[i], min(1.0, score + 0.15)
    headline = (f"{rep['kind']}, {rep['fade_depth_db']:.1f} dB fade depth, "
                f"{fades:.1f} independent fades in the frame")
    if rep["kind"] == "rician":
        kk = 10 ** (rep["k_factor_db"] / 10.0)
        why = (f"A Rician channel with K = {rep['k_factor_db']:.1f} dB puts "
               f"{100*kk/(1+kk):.0f}% of the power in a stable line-of-sight path and "
               f"{100/(1+kk):.0f}% in random scatter. ")
        if rep["k_factor_db"] > 10:
            why += "With that much dominant LOS the channel behaves nearly like clean AWGN. "
        elif rep["k_factor_db"] < 0:
            why += ("With the scatter outweighing the LOS this is barely distinguishable from "
                    "Rayleigh. ")
    else:
        why = ("Rayleigh means no dominant path at all -- the received signal is the sum of "
               "many comparable scatterers, so its envelope follows a Rayleigh distribution "
               "and deep fades are routine rather than exceptional. This is the pessimistic "
               "channel model. ")
    why += (f"The Doppler spread of {fd:.0f} Hz gives a coherence time of "
            f"{ct*1e3:.2f} ms" if np.isfinite(ct) else
            "With zero Doppler the channel is frozen for the whole frame")
    if np.isfinite(ct):
        why += (f" against a {dur*1e3:.2f} ms frame, so the channel changes about "
                f"{fades:.1f} times while you watch. ")
        if fades < 0.2:
            why += ("The channel is essentially static across the frame: you see one "
                    "particular fade, not the fading process. Whether that frame is easy or "
                    "hard is then a lottery -- which is exactly why fading results have to be "
                    "averaged over many channel draws, never read off one frame.")
        else:
            why += ("You can see the amplitude actually varying within the frame. Look at the "
                    "magnitude-versus-time plot: that wandering envelope is the channel, not "
                    "the modulation.")
    else:
        why += ". The single complex gain drawn for this frame is all you see."
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def pa_severity(cfg, sig, rep, geo):
    ibo = rep["ibo_db"]
    papr = rep["papr_before_db"]
    eff = ibo - papr
    m = [{"label": "Input back-off", "value": ibo, "unit": "dB"},
         {"label": "Waveform PAPR", "value": papr, "unit": "dB"},
         {"label": "Peak headroom (IBO - PAPR)", "value": eff, "unit": "dB",
          "note": "negative means the peaks are driven past saturation"},
         {"label": "Compression at the peak", "value": rep["peak_compression_db"], "unit": "dB"},
         {"label": "Samples above 0.7 of saturation",
          "value": 100 * rep["fraction_samples_near_saturation"], "unit": "%"},
         {"label": "PAPR after the amplifier", "value": rep["papr_after_db"], "unit": "dB"}]
    if rep["max_am_pm_deg"]:
        m.append({"label": "Peak AM/PM conversion", "value": rep["max_am_pm_deg"], "unit": "deg"})
    lvl, score = _level(-eff, -6, -2, 1, 4)
    headline = f"{eff:+.1f} dB of headroom above the peaks, {rep['peak_compression_db']:.1f} dB peak compression"
    why = (
        f"The amplifier saturates at {rep['a_sat_over_rms']:.2f}x the signal RMS "
        f"({ibo:.1f} dB back-off), while this waveform's peaks reach {papr:.2f} dB above RMS. "
        f"That leaves {eff:+.1f} dB of headroom for the peaks. "
    )
    if eff > 3:
        why += "The amplifier stays in its linear region for essentially every sample. "
    elif eff > 0:
        why += ("Only the rarest peaks touch compression, so the constellation's outer points "
                "pull inward slightly while the inner ones are untouched. ")
    else:
        why += (f"The peaks are driven into saturation: the outermost samples are compressed "
                f"by {abs(rep['peak_compression_db']):.1f} dB, which pulls the outer "
                f"constellation ring inward and leaves the inner ring where it was. That "
                f"differential squashing is the visual signature of AM/AM distortion. ")
    why += (f"PAPR fell from {papr:.2f} to {rep['papr_after_db']:.2f} dB, which is the "
            f"amplifier flattening the peaks. Because clipping a waveform in time spreads it "
            f"in frequency, check the spectrum for regrowth in the adjacent channel -- that "
            f"is the part regulators care about, and it is invisible in the constellation.")
    if geo.get("n_distinct_amplitudes", 1) > 1:
        why += (f" {geo['mod'].upper()} uses {geo['n_distinct_amplitudes']} distinct amplitude "
                f"levels to carry data, so amplitude compression attacks the information "
                f"directly. A constant-envelope scheme would barely notice this setting.")
    else:
        why += (" This modulation is constant-envelope, so the amplifier sees an almost "
                "unvarying input and compresses everything equally -- which is precisely why "
                "constant-envelope schemes are chosen for power-limited transmitters.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def iq_severity(cfg, sig, rep, geo):
    irr = rep["image_rejection_db"]
    ratio = 10 ** (-irr / 20.0)
    m = [{"label": "Gain imbalance", "value": rep["gain_imbalance_db"], "unit": "dB"},
         {"label": "Phase imbalance", "value": rep["phase_imbalance_deg"], "unit": "deg"},
         {"label": "Image rejection", "value": irr, "unit": "dB",
          "note": "how far below the signal its mirror image sits"},
         {"label": "Image amplitude / signal amplitude", "value": ratio, "unit": ""}]
    if "d_min" in geo:
        disp = ratio * geo["r_max"]
        budget = disp / (geo["d_min"] / 2)
        m.append({"label": "Worst-case displacement / (d_min/2)", "value": budget, "unit": "x"})
        lvl, score = _level(budget, 0.1, 0.3, 0.7, 1.5)
        headline = f"{irr:.0f} dB image rejection, {budget:.2f}x the decision margin"
        geom = (f"a {geo['mod'].upper()} grid becomes a parallelogram" if geo["family"] == "qam"
                else "a circular constellation becomes an ellipse")
    else:
        lvl, score = _level(-irr, -45, -35, -25, -15)
        headline = f"{irr:.0f} dB image rejection"
        budget = None
        geom = "the I and Q rails no longer describe a circle"
    why = (
        f"The I and Q paths are separate analog circuits. A {rep['gain_imbalance_db']:.2f} dB "
        f"gain difference and {rep['phase_imbalance_deg']:.2f} deg departure from a perfect "
        f"90 deg quadrature mean the output is no longer purely the signal: it is the signal "
        f"plus {ratio*100:.2f}% of its own complex conjugate. "
        f"The conjugate is a mirror image about DC, so in the spectrum a component at +f grows "
        f"a spurious twin at -f, {irr:.0f} dB down; in the constellation {geom}. "
    )
    if budget is not None:
        why += (f"The worst-displaced point moves by {ratio*geo['r_max']:.4f}, which is "
                f"{budget:.2f}x the {geo['d_min']/2:.3f} decision margin. ")
    why += ("This one is worth singling out for a different reason: it is a property of the "
            "specific receiver, essentially fixed over time. That makes it useless as a "
            "modulation cue but excellent as a device fingerprint -- and it means a classifier "
            "can quietly learn to identify the radio instead of the waveform.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def dc_severity(cfg, sig, rep, geo):
    mag = rep["magnitude_rel_rms"]
    m = [{"label": "DC offset magnitude", "value": mag, "unit": "x RMS"},
         {"label": "I component", "value": rep["i_offset_rel"], "unit": "x RMS"},
         {"label": "Q component", "value": rep["q_offset_rel"], "unit": "x RMS"}]
    if "d_min" in geo:
        budget = mag / (geo["d_min"] / 2)
        m.append({"label": "Offset / decision margin", "value": budget, "unit": "x"})
        lvl, score = _level(budget, 0.1, 0.3, 0.8, 2.0)
        headline = f"constellation shifted by {budget:.2f}x its decision margin"
        extra = (f"Every point moves by the same {mag:.3f} (in unit-power units), which is "
                 f"{budget:.2f}x the {geo['d_min']/2:.3f} margin, so ")
        extra += ("the shift is smaller than the margin and decisions still land correctly."
                  if budget < 1 else
                  "the shift alone is enough to push points across decision boundaries even "
                  "with no noise at all.")
    else:
        lvl, score = _level(mag, 0.05, 0.15, 0.35, 0.7)
        headline = f"DC offset at {mag:.2f}x the signal RMS"
        extra = ""
    why = (
        f"Direct-conversion receivers leak their own local oscillator into the signal path, "
        f"and that leakage lands at exactly 0 Hz. The result is a constant complex value added "
        f"to every sample: the entire constellation is translated away from the origin without "
        f"rotating, scaling or smearing. {extra} "
        f"In the spectrum it shows as a single spike at DC that no amount of averaging removes. "
        f"The fix is almost free -- subtract the mean, one line of code -- which is why "
        f"real receivers always do it and why O'Shea's over-the-air captures were deliberately "
        f"tuned about 1 MHz off-channel to keep the signal away from this artefact entirely."
    )
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def quant_severity(cfg, sig, rep, geo):
    bits = rep["bits"]
    m = [{"label": "ADC resolution", "value": bits, "unit": "bits"},
         {"label": "Headroom below full scale", "value": rep["headroom_db"], "unit": "dB"},
         {"label": "Theoretical SQNR", "value": rep["theoretical_sqnr_db"], "unit": "dB",
          "note": "6.02.bits + 1.76 - headroom"},
         {"label": "Measured SQNR", "value": rep["measured_sqnr_db"], "unit": "dB"},
         {"label": "Distinct codes used on I", "value": rep["codes_used_i"], "unit": ""},
         {"label": "Quantisation step", "value": rep["step_size_rel_rms"], "unit": "x RMS"}]
    if "d_min" in geo:
        steps = geo["d_min"] / max(rep["step_size_rel_rms"], 1e-12)
        m.append({"label": "Quantisation steps per d_min", "value": steps, "unit": ""})
        lvl, score = _level(1.0 / max(steps, 1e-6), 1 / 40, 1 / 16, 1 / 6, 1 / 2.5)
        headline = f"{steps:.0f} quantisation steps across the gap between constellation points"
        extra = (f"The gap between neighbouring constellation points, d_min = {geo['d_min']:.3f}, "
                 f"is spanned by {steps:.0f} quantisation steps. ")
        extra += ("That is plenty of resolution -- quantisation is nowhere near the limiting "
                  "factor here." if steps > 16 else
                  "Constellation points now sit on a visible lattice; the clouds turn into "
                  "discrete dots arranged on a grid." if steps > 4 else
                  "The converter's grid is comparable to the constellation's own spacing, so "
                  "quantisation is directly destroying symbol information.")
    else:
        lvl, score = _level(-rep["measured_sqnr_db"], -40, -30, -20, -12)
        headline = f"{rep['measured_sqnr_db']:.0f} dB quantisation SNR"
        extra = ""
    why = (
        f"An {bits}-bit converter with {rep['headroom_db']:.0f} dB of headroom gives at best "
        f"6.02x{bits} + 1.76 - {rep['headroom_db']:.0f} = {rep['theoretical_sqnr_db']:.1f} dB of "
        f"signal-to-quantisation-noise ratio, and the samples measure "
        f"{rep['measured_sqnr_db']:.1f} dB. {extra}"
        f"Headroom is the real tension: too little and the peaks clip, too much and the signal "
        f"only exercises a few of the {rep['codes_available']} available codes. Here I uses "
        f"{rep['codes_used_i']} of them."
    )
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def clip_severity(cfg, sig, rep, geo):
    fr = rep["fraction_clipped"]
    m = [{"label": "Headroom above RMS", "value": rep["headroom_db"], "unit": "dB"},
         {"label": "Samples clipped", "value": 100 * fr, "unit": "%"},
         {"label": "Clip level", "value": rep["clip_level_rel_rms"], "unit": "x RMS"},
         {"label": "PAPR before", "value": rep["papr_before_db"], "unit": "dB"},
         {"label": "PAPR after", "value": rep["papr_after_db"], "unit": "dB"}]
    lvl, score = _level(fr, 0.0002, 0.005, 0.03, 0.12)
    headline = f"{100*fr:.2f}% of samples hard-limited"
    why = (
        f"The converter's full scale sits {rep['headroom_db']:.1f} dB above the signal RMS, and "
        f"{100*fr:.2f}% of samples ({rep['n_clipped']}) exceed it and get hard-limited. "
        f"PAPR drops from {rep['papr_before_db']:.2f} to {rep['papr_after_db']:.2f} dB. "
        f"Clipping is nonlinear, so it does two things at once: it flattens the waveform peaks "
        f"in time, and -- because a sharp corner in time is broadband in frequency -- it splashes "
        f"energy outside the signal's own bandwidth. Look at the time-domain plot for flat tops "
        f"and at the spectrum for the shoulders that appear beside the main lobe. "
    )
    if sig.mod == "ofdm" or rep["papr_before_db"] > 7:
        why += ("This waveform has a high PAPR, so it is unusually exposed to clipping: rare "
                "large peaks are exactly what a high-PAPR signal has in abundance.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


def interference_severity(cfg, sig, rep, geo):
    sir = rep["sir_db"]
    off = rep["freq_offset_hz"]
    bw = sig.symbol_rate * (1 + sig.info.get("rolloff", 0.35)) if sig.linear else sig.fs / 8
    inband = abs(off) < bw / 2
    m = [{"label": "Signal-to-interference ratio", "value": sir, "unit": "dB"},
         {"label": "Interferer type", "value": rep["kind"], "unit": ""},
         {"label": "Frequency offset", "value": off / 1e3, "unit": "kHz"},
         {"label": "Signal bandwidth", "value": bw / 1e3, "unit": "kHz"},
         {"label": "Interferer sits", "value": "in band" if inband else "adjacent channel", "unit": ""}]
    lvl, score = _level(-sir, -25, -15, -5, 5)
    if not inband:
        score *= 0.6
        lvl = LEVELS[max(0, min(4, int(score * 5)))]
    headline = f"{sir:.0f} dB SIR, {'in band' if inband else 'out of band'}"
    why = (
        f"A {rep['kind']} interferer sits {off/1e3:+.0f} kHz from centre at {sir:.0f} dB below "
        f"the wanted signal, whose own bandwidth is {bw/1e3:.0f} kHz. "
    )
    if inband:
        why += ("It falls inside the signal band, so no filter can remove it without also "
                "removing signal. It adds a rotating vector to every sample, which smears the "
                "constellation into rings or arcs depending on its frequency.")
    else:
        why += ("It falls outside the signal band, so a channel-select filter would remove most "
                "of it. Whether it hurts depends entirely on whether your receive chain filters "
                "before or after the point you are looking at.")
    why += (" The spectrum and spectrogram are the right places to look: interference is almost "
            "invisible in a constellation but unmistakable as a line in the frequency domain. "
            "This is also the impairment synthetic datasets model least often -- they assume "
            "one signal alone in an empty band, which real spectrum never is.")
    return dict(level=lvl, score=score, headline=headline, why=why, metrics=m)


SEVERITY_FUNCS = {
    "awgn": awgn_severity, "cfo": cfo_severity, "phase_offset": phase_offset_severity,
    "phase_noise": phase_noise_severity, "clock_offset": clock_offset_severity,
    "multipath": multipath_severity, "fading": fading_severity, "pa": pa_severity,
    "iq_imbalance": iq_severity, "dc_offset": dc_severity,
    "quantization": quant_severity, "clipping": clip_severity,
    "interference": interference_severity,
}


def overall(severities, evm_total):
    """Combine per-impairment severities into one headline judgement."""
    if not severities:
        return {"level": "NEGLIGIBLE", "score": 0.0,
                "why": "No impairments are enabled: this is the reference waveform."}
    scores = [s["score"] for s in severities.values()]
    top = max(scores)
    # Impairments compound rather than simply add, but not linearly.
    combined = min(1.0, top + 0.35 * (sum(scores) - top))
    lvl = LEVELS[min(4, int(combined * 5))]
    worst = max(severities.items(), key=lambda kv: kv[1]["score"])[0]
    return {"level": lvl, "score": combined, "dominant": worst,
            "evm_total_pct": evm_total,
            "why": (f"{len(severities)} impairment(s) active. The dominant one is "
                    f"{worst.replace('_',' ')}. Total error against the clean reference "
                    f"is {evm_total:.1f}% EVM.")}
