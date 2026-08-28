"""Contextual narration: what is actually on screen, why, and what to do next.

Rule enforced throughout: describe what the measurements say, not what the
configuration implies.  If a configured impairment is too weak to show, say so.
If something unexpected turns up, say that too.  A tutor that describes an
effect the plot does not contain teaches the student to distrust their eyes.
"""
import numpy as np

from .modulations import profile as mod_profile, FAMILY_VIEWS
from .impairment_profiles import profile as imp_profile, VIEW_PRIORITY
from .plot_profiles import profile as view_profile


def _n(v, nd=2):
    if v is None:
        return "n/a"
    if isinstance(v, str):
        return v
    if not np.isfinite(v):
        return "infinite"
    return f"{v:,.{nd}f}"


def priority_views(res):
    """Which views to promote, given what is switched on."""
    order, seen = [], set()
    for k in res["active"]:
        for v in VIEW_PRIORITY.get(k, []):
            if v not in seen:
                seen.add(v); order.append(v)
    fam = res["signal"]["family"]
    for v in FAMILY_VIEWS.get(fam, []):
        if v not in seen:
            seen.add(v); order.append(v)
    for v in ["constellation", "iq_time", "psd", "fft", "spectrogram", "phase",
              "inst_freq", "magnitude", "eye", "autocorr", "cumulants", "cyclic",
              "amp_hist", "papr_ccdf", "am_am", "channel", "ofdm"]:
        if v not in seen and res["plots"].get(v) is not None:
            seen.add(v); order.append(v)
    return [v for v in order if res["plots"].get(v) is not None]


# --------------------------------------------------------------------------
# What is actually visible
# --------------------------------------------------------------------------

def observe(view, res):
    """Data-driven description of what this particular plot currently shows."""
    m = res["measurements"]
    sig = res["signal"]
    d = m.get("constellation_diag")
    dc = m.get("constellation_diag_clean")
    act = res["active"]
    out = []

    if view == "constellation":
        if d is None:
            if sig["family"] == "fsk":
                out.append(
                    f"There are no clusters here and there should not be. {sig['mod'].upper()} "
                    f"has a constant envelope and a continuously advancing phase, so every "
                    f"sample sits on a circle of the same radius. The amplitude coefficient of "
                    f"variation is {_n(100*0,1)}% by construction. Everything this modulation "
                    f"encodes is in the instantaneous-frequency view instead.")
            elif sig["family"] == "ofdm":
                out.append(
                    "This is a featureless disc, and that is the correct answer rather than a "
                    "failure. An OFDM symbol is the sum of dozens of independent subcarriers, so "
                    "by the central limit theorem the composite is approximately complex "
                    "Gaussian no matter what the subcarriers carry. The per-subcarrier "
                    "constellation only exists after the cyclic prefix is removed and the FFT "
                    "taken -- see the OFDM subcarrier view.")
            else:
                out.append(
                    "This modulation is analog: the message is continuous, so there is no "
                    "discrete set of symbol states to cluster into.")
            return out

        ds = m.get("constellation_diag_synced")
        if not d.get("model_valid", True):
            rot = res["reports"].get("cfo", {}).get("total_rotations")
            out.append(
                "These samples do not form clusters at all, so cluster statistics would be "
                "meaningless and are not reported. Each transmitted state is appearing at many "
                "different angles, which fills the plane into a ring or an arc.")
            if rot:
                out.append(
                    f"The cause is measurable: the phase accumulates {_n(abs(rot),2)} full "
                    f"revolutions across this frame, so a symbol sent early and the same symbol "
                    f"sent late land on opposite sides of the circle.")
            out.append(
                f"Correlation between the received samples and the transmitted symbols is only "
                f"{_n(d['coherence'],3)} -- below the 0.5 threshold at which a single gain and "
                f"rotation still describes the picture.")
            if ds and ds.get("model_valid"):
                out.append(
                    f"Switch on the ideal-synchroniser overlay and the structure returns: after "
                    f"removing the bulk rotation the clusters have a margin of "
                    f"{_n(ds['separation_sigma'],1)} sigma and a tangential/radial ratio of "
                    f"{_n(ds['tangential_over_radial'],2)}. The geometry was rotated out of "
                    f"view, not destroyed -- which is precisely why this impairment is "
                    f"correctable and noise is not.")
            else:
                out.append(
                    "Even after ideal derotation the structure does not come back, so the "
                    "damage here is not a recoverable rotation.")
            return out

        sep, tr = d["separation_sigma"], d["tangential_over_radial"]
        out.append(
            f"{d['clusters_populated']} of {d['clusters_expected']} constellation states are "
            f"populated by {d['n_points']} symbol samples. Each cloud has a standard deviation "
            f"of {_n(d['mean_cluster_std'],4)} against a half-spacing of "
            f"{_n(d['d_min_scaled']/2,4)}, so the decision margin measures {_n(sep,1)} sigma.")

        if sep > 20:
            out.append("The clusters are effectively points -- nothing measurable is blurring them.")
        elif sep > 5:
            out.append("Clouds are visible but comfortably separated.")
        elif sep > 3:
            out.append("Clouds are large enough that neighbours are beginning to touch.")
        elif sep > 1.5:
            out.append("Neighbouring clouds overlap. Counting the states by eye is now unreliable.")
        else:
            out.append("The clouds have merged into a single mass; the constellation geometry "
                       "is no longer readable.")

        # Cause attribution from cluster shape.
        if sep < 30:
            if tr > 1.6:
                out.append(
                    f"The clouds are {_n(tr,1)}x wider tangentially than radially -- stretched "
                    f"along the arc rather than in and out. That anisotropy is a phase-domain "
                    f"signature (phase noise or residual frequency offset), not additive noise, "
                    f"which would be isotropic.")
            elif tr < 0.65:
                out.append(
                    f"The clouds are {_n(1/max(tr,1e-9),1)}x wider radially than tangentially -- "
                    f"stretched in and out rather than along the arc. That points at an "
                    f"amplitude-domain cause: amplifier compression, timing error or gain "
                    f"variation, not phase.")
            else:
                out.append(
                    f"The clouds are close to circular (tangential/radial = {_n(tr,2)}), which "
                    f"is the isotropic signature of additive noise rather than any phase- or "
                    f"amplitude-specific effect.")

        det = d.get("deterministic_over_random", 0.0)
        base_det = (dc or {}).get("deterministic_over_random", 0.0)
        if det > max(3 * base_det, 0.6):
            out.append(
                f"The cluster centres are displaced from their ideal positions by "
                f"{_n(d['shear_rms_error'],4)} RMS -- {_n(det,1)}x the random scatter within a "
                f"cluster. That ratio matters: noise moves centres barely at all and scatters "
                f"samples a lot, so a large ratio means the distortion is systematic and "
                f"repeatable rather than random. Systematic distortion is correctable in "
                f"principle, and it is also the kind that carries a device's fingerprint.")
        if abs(d["net_rotation_deg"]) > 1.0:
            out.append(
                f"The whole constellation is rotated by {_n(d['net_rotation_deg'],1)} degrees "
                f"relative to the transmitted symbols.")
        base_c = dc["centroid_offset"] if dc else 0.0
        if d["centroid_offset"] > max(3 * base_c, 0.02):
            out.append(
                f"The centre of mass sits {_n(d['centroid_offset'],3)} away from the origin "
                f"(the clean reference sits at {_n(base_c,3)}), so the whole pattern is "
                f"translated -- the signature of a DC offset, which shifts without rotating "
                f"or smearing.")
        if d["angular_uniformity"] > 0.985 and sig["family"] in ("psk", "qam"):
            out.append(
                "Sample angles are now almost uniformly distributed around the circle. The "
                "phase structure that identifies the modulation order has been filled in "
                "completely -- this is a ring, not a set of clusters.")
        return out

    if view == "magnitude":
        cv = (d["amplitude_cv"] if d else None)
        pa = m["papr_db"]
        out.append(f"Peak-to-average power ratio is {_n(pa,2)} dB "
                   f"(clean reference: {_n(m['papr_clean_db'],2)} dB).")
        if sig["family"] == "fsk" or sig["mod"] in ("fm", "wbfm"):
            out.append("The envelope is flat because this modulation is constant-envelope. Any "
                       "variation you see here is the channel or the receiver, never the "
                       "message.")
        if "fading" in act:
            r = res["reports"]["fading"]
            out.append(f"The channel envelope wanders over {_n(r['envelope_range_db'],1)} dB "
                       f"within this frame, with a median-to-1st-percentile fade depth of "
                       f"{_n(r['fade_depth_db'],1)} dB.")
        if "clipping" in act:
            r = res["reports"]["clipping"]
            out.append(f"{_n(100*r['fraction_clipped'],2)}% of samples are hard-limited, which "
                       f"is why the envelope has flat tops at {_n(r['clip_level_rel_rms'],2)}x RMS.")
        return out

    if view == "phase":
        ph = res["plots"]["phase"]
        drift = ph["total_drift_rad"]
        out.append(
            f"Two traces, answering two different questions. The cyan one is the carrier phase "
            f"the impairment chain added: angle(received x conjugate(clean)), which is exactly "
            f"zero on an unimpaired signal for every modulation. It moves "
            f"{_n(drift,2)} radians ({_n(drift/(2*np.pi),2)} full turns) across the frame. The "
            f"amber one is the modulation's own phase, which for a continuous-phase scheme "
            f"ramps by {_n(ph['signal_drift_rad'],1)} radians by design and means nothing is "
            f"wrong.")
        out.append(
            f"Note what is not plotted: unwrapping the raw sample phase, all a blind receiver "
            f"has, reads {_n(ph['raw_drift_rad'],1)} radians here. Most of that is an artefact "
            f"-- a modulation's own phase jumps of up to 180 degrees are precisely the case "
            f"unwrapping cannot resolve, so that trace random-walks even on a clean signal. The "
            f"blind estimator that does work is in the verification panel.")
        if "cfo" in act:
            r = res["reports"]["cfo"]
            out.append(f"A constant slope is a frequency offset. The dashed line is the slope "
                       f"{_n(r['cfo_hz'],1)} Hz predicts; the blind estimator independently "
                       f"reads {_n(m['cfo_blind']['hz'],1)} Hz from the samples alone.")
        if "phase_noise" in act:
            r = res["reports"]["phase_noise"]
            out.append(f"Superimposed on the trend is {_n(r['realised_rms_deg'],2)} degrees RMS "
                       f"of wander. " + ("Because this is a random walk rather than bounded "
                                         "jitter, it grows with time rather than staying put."
                                         if r["linewidth_hz"] > 0 else
                                         "This is bounded jitter about a stable mean, not a "
                                         "walk -- it does not grow with frame length."))
        if abs(drift) < 0.05 and "cfo" not in act:
            out.append("The carrier trace is flat: no impairment in this configuration is "
                       "touching the carrier phase.")
        return out

    if view == "inst_freq":
        p = res["plots"]["inst_freq"]
        if p["levels_khz"]:
            out.append(f"The theoretical tone positions for {sig['mod'].upper()} are "
                       f"{', '.join(_n(l,1) for l in p['levels_khz'])} kHz, marked by the "
                       f"dashed lines. The trace should visit those levels and dwell there.")
        if sig["mod"] in ("fm", "wbfm"):
            i = sig["info"]
            out.append(f"Instantaneous frequency is tracking the message directly, with a peak "
                       f"deviation of {_n(i.get('freq_dev_hz',0)/1e3,1)} kHz and modulation "
                       f"index beta = {_n(i.get('modulation_index_beta',0),2)}. Carson's rule "
                       f"predicts {_n(i.get('carson_bw_hz',0)/1e3,1)} kHz of occupied bandwidth; "
                       f"the spectrum measures {_n(m['occupied_bw_hz']/1e3,1)} kHz.")
        if "cfo" in act:
            out.append(f"A carrier offset shifts this whole trace vertically by "
                       f"{_n(res['reports']['cfo']['cfo_hz']/1e3,2)} kHz without changing the "
                       f"spacing between levels -- which is exactly why FSK tolerates CFO far "
                       f"better than PSK does.")
        if sig["family"] not in ("fsk",) and sig["mod"] not in ("fm", "wbfm"):
            out.append("For a phase- or amplitude-modulated signal this view is mostly spikes at "
                       "symbol transitions; it is not the natural window on this modulation.")
        return out

    if view in ("psd", "fft"):
        p = res["plots"]["psd"]
        out.append(f"The 99% occupied bandwidth measures {_n(p['occupied_bw_khz'],1)} kHz, "
                   f"centred at {_n(p['centroid_khz'],2)} kHz.")
        if p["nominal_bw_khz"]:
            out.append(f"Theory for a root-raised-cosine pulse at "
                       f"{_n(sig['symbol_rate']/1e3,1)} kBaud with rolloff "
                       f"{sig['info'].get('rolloff')} predicts "
                       f"(1 + rolloff) x Rs = {_n(p['nominal_bw_khz'],1)} kHz.")
        out.append(f"The noise floor sits at {_n(p['noise_floor_db'],1)} dB.")
        if "cfo" in act:
            out.append(f"The whole spectrum is translated by "
                       f"{_n(res['reports']['cfo']['cfo_hz']/1e3,2)} kHz -- shifted, not "
                       f"reshaped, because a frequency offset is a multiplication by a complex "
                       f"exponential.")
        if "interference" in act:
            r = res["reports"]["interference"]
            out.append(f"A {r['kind']} interferer is present at "
                       f"{_n(r['freq_offset_hz']/1e3,1)} kHz, {_n(r['sir_db'],1)} dB below the "
                       f"wanted signal.")
        if "pa" in act or "clipping" in act:
            out.append("Compare the skirts against the clean trace: any energy outside the "
                       "clean signal's own bandwidth is spectral regrowth generated by the "
                       "nonlinearity, and it is what limits how hard a transmitter may be driven.")
        if "dc_offset" in act:
            out.append("The spike at exactly 0 Hz is the DC offset. It is a single bin because "
                       "a constant in time is a delta in frequency.")
        return out

    if view == "eye":
        e = res["plots"].get("eye")
        if not e:
            return ["An eye diagram needs a linearly modulated signal and a matched filter; "
                    "it is not defined for this modulation."]
        out.append(f"The eye opening measures {_n(e['opening'],3)} of the full trace excursion "
                   f"at the decision instant.")
        if e["opening"] > 0.4:
            out.append("Wide open -- timing has plenty of margin.")
        elif e["opening"] > 0.15:
            out.append("Partly closed. There is still a clear decision point but the margin has "
                       "shrunk.")
        elif e["opening"] > 0.03:
            out.append("Nearly closed. Small timing errors will now cause symbol errors.")
        else:
            out.append("Closed. There is no instant at which the levels are cleanly separated.")
        if "clock_offset" in act:
            r = res["reports"]["clock_offset"]
            out.append(f"The clock error accumulates {_n(r['drift_symbols_over_frame'],4)} "
                       f"symbols of drift across the frame, so later traces are sampled further "
                       f"off-centre than earlier ones -- the eye is not uniformly blurred, it "
                       f"degrades along the frame.")
        return out

    if view == "autocorr":
        a = res["plots"]["autocorr"]
        if a["expect_peak_lag"]:
            r = np.asarray(a["r"])
            lag = a["expect_peak_lag"]
            near = r[max(0, lag - 2):lag + 3]
            out.append(f"For OFDM the diagnostic is a peak at lag = FFT length = {lag} samples, "
                       f"where the cyclic prefix correlates with the tail it was copied from. "
                       f"The measured correlation there is {_n(float(near.max()),3)}.")
            if near.max() > 0.1:
                out.append("That peak is present, which identifies this as OFDM regardless of "
                           "what the constellation shows.")
            else:
                out.append("That peak is not clearly present here -- either the impairments have "
                           "destroyed the cyclic-prefix correlation, or the frame is too short.")
        else:
            out.append("A clean linearly modulated signal correlates with itself only over the "
                       "span of its pulse shape, so this decays quickly and stays low.")
        return out

    if view == "cyclic":
        c = res["plots"]["cyclic"]
        line = c.get("line") or {}
        out.append(f"The cycle-frequency axis is marked at {_n(c['marker_khz'],1)} kHz "
                   f"({c['marker_label']}). The measured line there stands "
                   f"{_n(line.get('contrast_db',0),1)} dB above the local floor.")
        if line.get("contrast_db", 0) > 12:
            out.append("That is a clear cyclostationary feature: the signal's statistics really "
                       "do repeat at this rate, which is what makes blind symbol-rate estimation "
                       "and below-noise-floor detection possible.")
        else:
            out.append("The line is weak here, so this measurement is not currently supporting a "
                       "symbol-rate estimate.")
        cz = c["conj_at_zero"]
        out.append(
            f"The conjugate feature at alpha = 0 reads {_n(cz,3)}. Values near 1 mean a "
            f"real-valued constellation (BPSK, PAM, ASK); values near 0 mean a rotationally "
            f"symmetric one (QPSK and above, QAM). This one says "
            + ("real-valued." if cz > 0.5 else
               "rotationally symmetric." if cz < 0.2 else
               "something in between -- worth checking against the modulation."))
        out.append(f"Cyclic lines are only about {_n(c['alpha_resolution_hz'],0)} Hz wide at this "
                   f"frame length, which is why a coarse sweep of alpha finds nothing at all.")
        return out

    if view == "cumulants":
        cu = res["plots"]["cumulants"]
        meas_, ideal = cu["measured"], cu["ideal"]
        if ideal:
            parts = [f"|{k}| measured {_n(meas_.get(k),3)} against theory {_n(ideal[k],2)}"
                     for k in ideal]
            out.append(sig["mod"].upper() + ": " + "; ".join(parts) + ".")
            # Explain a large discrepancy rather than leaving it hanging: under a
            # phase impairment these statistics are supposed to move, and saying
            # so is the lesson.
            worst = max((abs(meas_.get(k, 0) - ideal[k]) / max(abs(ideal[k]), 0.25)
                         for k in ideal), default=0)
            phase_imp = [k for k in ("cfo", "phase_noise") if k in act]
            if worst > 0.4 and phase_imp:
                out.append(
                    f"The measured values have moved a long way from the table, and that is the "
                    f"expected consequence of {', '.join(p.replace('_',' ') for p in phase_imp)} "
                    f"rather than an estimation failure. C40 in particular is a phase-sensitive "
                    f"statistic: it is what separates QPSK (|C40| = 1) from 8PSK (|C40| = 0). "
                    f"Smear the constellation into a ring and the measurement slides toward the "
                    f"8PSK value whatever was actually transmitted. This is precisely why "
                    f"classical cumulant-based classifiers needed synchronisation first, and "
                    f"why the phase-insensitive |C42| holds up better here.")
            elif worst > 0.4:
                out.append(
                    f"The measured values sit well away from the table. With "
                    f"{cu['n_symbols']} symbols that may simply be estimator variance -- "
                    f"fourth- and sixth-order statistics converge slowly -- so try a longer "
                    f"frame before concluding anything from the gap.")
        out.append(f"Estimated from {cu['n_symbols']} symbols. Fourth- and sixth-order "
                   f"statistics converge slowly, so expect visible scatter at this sample count "
                   f"-- and expect it to be worse for high-order QAM, whose theoretical values "
                   f"sit close together to begin with.")
        return out

    if view == "am_am":
        if not res["plots"].get("am_am"):
            return ["No nonlinearity is active, so there is no transfer curve to look at."]
        if "pa" in act:
            r = res["reports"]["pa"]
            out.append(f"The curve bends away from the linear reference above roughly "
                       f"{_n(r['a_sat_over_rms'],2)}x RMS. Peak compression measures "
                       f"{_n(r['peak_compression_db'],2)} dB, and "
                       f"{_n(100*r['fraction_samples_near_saturation'],1)}% of samples sit above "
                       f"70% of saturation.")
            if r["max_am_pm_deg"]:
                out.append(f"The Saleh model also rotates large samples: up to "
                           f"{_n(r['max_am_pm_deg'],1)} degrees of AM/PM conversion, which is "
                           f"why a nonlinearity can look like a phase impairment.")
        if "clipping" in act:
            r = res["reports"]["clipping"]
            out.append(f"Hard limiting produces a flat ceiling rather than a smooth bend: "
                       f"{_n(100*r['fraction_clipped'],2)}% of samples land exactly on it.")
        return out

    if view == "channel":
        c = res["plots"].get("channel")
        if not c:
            return ["No multipath channel is configured."]
        cbw = c["coherence_bw_khz"]
        out.append(f"RMS delay spread is {_n(c['rms_delay_spread_us'],3)} us, giving a coherence "
                   f"bandwidth of {'unbounded' if cbw is None else _n(cbw,1) + ' kHz'} against a "
                   f"signal bandwidth of {_n(res['plots']['psd']['occupied_bw_khz'],1)} kHz.")
        sel = cbw is not None and cbw < res["plots"]["psd"]["occupied_bw_khz"]
        out.append("The signal is wider than the coherence bandwidth, so different parts of it "
                   "are attenuated differently: this is frequency-selective fading and the "
                   "notches in the response are where paths cancel."
                   if sel else
                   "The signal is narrower than the coherence bandwidth, so the whole band fades "
                   "together. This is flat fading, and its entire effect is one complex gain.")
        return out

    if view == "ofdm":
        o = res["plots"].get("ofdm")
        if not o:
            return ["Not an OFDM signal."]
        out.append(f"{o['n_ofdm_symbols']} OFDM symbols were demodulated by removing the cyclic "
                   f"prefix and taking the FFT. The subcarrier constellation shown is "
                   f"{sig['info']['sub_mod'].upper()}, which is invisible in the time-domain "
                   f"constellation.")
        if "cfo" in act:
            s_ = res["severity"].get("cfo", {})
            out.append("Carrier offset is active, and this is where OFDM differs from everything "
                       "else: " + s_.get("headline", ""))
        return out

    if view == "spectrogram":
        out.append("Time runs horizontally, frequency vertically, and brightness is power.")
        if sig["family"] == "fsk":
            out.append("For FSK this is the clearest view there is: each symbol appears as a "
                       "short horizontal bar at its own frequency, and the pattern of bars is "
                       "the data.")
        if "interference" in act:
            out.append("The interferer appears as a separate horizontal feature at its own "
                       "frequency, distinct from the wanted signal.")
        if "cfo" in act:
            out.append("A constant frequency offset shifts the whole picture vertically without "
                       "tilting it; a drifting offset would tilt it.")
        return out

    if view == "iq_time":
        out.append(f"There are {sig['sps']} samples per symbol, so one symbol period spans "
                   f"{sig['sps']} points on this axis.")
        if "quantization" in act:
            r = res["reports"]["quantization"]
            out.append(f"With {r['bits']}-bit resolution the waveform is confined to a lattice "
                       f"of steps {_n(r['step_size_rel_rms'],4)}x RMS apart; "
                       f"{r['codes_used_i']} distinct codes are actually exercised on I.")
        if "clipping" in act:
            out.append("Look for flat tops: those are samples that hit the limit.")
        return out

    if view == "amp_hist":
        out.append(f"Amplitude coefficient of variation is "
                   f"{_n(d['amplitude_cv'],3) if d else 'n/a'}.")
        if sig["family"] == "ofdm":
            out.append("OFDM's amplitude follows a Rayleigh-like distribution because the "
                       "composite is a sum of many independent contributions -- that long tail "
                       "is the PAPR problem in picture form.")
        if "quantization" in act:
            out.append("The comb structure is the ADC's lattice of allowed values.")
        if "clipping" in act:
            out.append("The spike at the top is the pile-up of samples that were limited.")
        return out

    if view == "papr_ccdf":
        out.append(f"Measured PAPR is {_n(m['papr_db'],2)} dB against "
                   f"{_n(m['papr_clean_db'],2)} dB clean.")
        if sig["family"] == "ofdm":
            out.append("The long tail is why OFDM transmitters need several dB more amplifier "
                       "back-off than a constant-envelope waveform of the same average power.")
        return out

    return ["No specific observations available for this view."]


# --------------------------------------------------------------------------

def explain_plot(view, res):
    vp = view_profile(view) or {}
    body = {
        "title": vp.get("title", view),
        "question": vp.get("question"),
        "what": vp.get("what"),
        "axes": vp.get("axes"),
        "marks": vp.get("marks"),
        "clean_expectation": vp.get("clean"),
        "teaches": vp.get("teaches", []),
        "caution": vp.get("caution"),
        "observed": observe(view, res),
        "changed": what_changed(view, res),
        "severity": relevant_severity(view, res),
        "why_it_matters": why_view_matters(view, res),
        "look_next": look_next(view, res),
    }
    return body


def what_changed(view, res):
    """Which active impairment is responsible for what is different here."""
    out = []
    for k in res["active"]:
        if view in VIEW_PRIORITY.get(k, [])[:4]:
            p = imp_profile(k) or {}
            s = res["severity"].get(k, {})
            field = {"constellation": "on_constellation", "psd": "on_spectrum",
                     "fft": "on_spectrum", "spectrogram": "on_spectrum"}.get(view, "on_signal")
            out.append({
                "impairment": p.get("name", k),
                "effect": p.get(field) or p.get("on_signal"),
                "severity": s.get("level"),
                "headline": s.get("headline"),
            })
    if not out:
        out.append({"impairment": None,
                    "effect": ("No enabled impairment targets this view in particular, so what "
                               "you are seeing is close to the clean reference for this "
                               "modulation.")})
    return out


def relevant_severity(view, res):
    items = []
    for k in res["active"]:
        if view in VIEW_PRIORITY.get(k, []):
            s = res["severity"].get(k)
            if s:
                items.append({"impairment": k, **s})
    return items


def why_view_matters(view, res):
    sig = res["signal"]
    mp = mod_profile(sig["mod"]) or {}
    lines = []
    if view in (mp.get("views") or [])[:3]:
        lines.append(f"This is one of the primary views for {mp.get('name', sig['mod'])}: "
                     f"{mp.get('carries')}.")
    for k in res["active"]:
        if view == (VIEW_PRIORITY.get(k) or [None])[0]:
            p = imp_profile(k) or {}
            lines.append(f"It is also the single most informative view for "
                         f"{p.get('name', k)}.")
    return lines


def look_next(view, res):
    pv = priority_views(res)
    i = pv.index(view) if view in pv else -1
    nxt = pv[i + 1] if 0 <= i < len(pv) - 1 else (pv[0] if pv else None)
    if not nxt:
        return None
    vp = view_profile(nxt) or {}
    return {"view": nxt, "title": vp.get("title"), "because": vp.get("question")}


# --------------------------------------------------------------------------
# Prediction, then comparison
# --------------------------------------------------------------------------

def prediction(res):
    """What theory says you should see, written before looking at the data."""
    sig = res["signal"]
    mp = mod_profile(sig["mod"]) or {}
    items = [{
        "topic": f"{mp.get('name', sig['mod'])} — baseline",
        "expect": (f"{mp.get('constellation')} Amplitude: {mp.get('amplitude')} "
                   f"Frequency: {mp.get('frequency')}"),
    }]
    geo = res["geometry"]
    if "d_min" in geo:
        items.append({
            "topic": "Tolerance budget",
            "expect": (f"Unit-power {sig['mod'].upper()} has d_min = {_n(geo['d_min'],3)}, so "
                       f"each decision has {_n(geo['d_min']/2,3)} of margin and the "
                       f"constellation tolerates about {_n(geo['phase_tolerance_deg'],1)} degrees "
                       f"of rotation before samples cross a boundary."),
        })
    for k in res["active"]:
        p = imp_profile(k) or {}
        s = res["severity"].get(k, {})
        items.append({
            "topic": p.get("name", k),
            "expect": (f"{p.get('on_constellation')} In the spectrum: {p.get('on_spectrum')} "
                       f"Over time: {p.get('over_time')}"),
            "predicted_severity": s.get("level"),
            "quantified": s.get("headline"),
            "best_views": VIEW_PRIORITY.get(k, [])[:3],
        })
    if not res["active"]:
        items.append({"topic": "No impairments",
                      "expect": "This is the reference waveform. Everything you see is the "
                                "modulation itself, with no channel or hardware effect at all. "
                                "Learn this picture first -- every later comparison is against it."})
    return items


def compare(res):
    """Prediction against measurement, with honest verdicts."""
    m = res["measurements"]
    d = m.get("constellation_diag")
    dcl = m.get("constellation_diag_clean")
    rows = []

    for k in res["active"]:
        s = res["severity"].get(k, {})
        p = imp_profile(k) or {}
        expected = s.get("headline", "")
        verdict, detail = "confirmed", ""

        if k == "awgn" and d and dcl and d.get("model_valid", True):
            grew = d["mean_cluster_std"] / max(dcl["mean_cluster_std"], 1e-9)
            detail = (f"Cluster spread grew {_n(grew,1)}x versus the clean reference, and the "
                      f"clouds are isotropic (tangential/radial = "
                      f"{_n(d['tangential_over_radial'],2)}) as additive noise requires.")
            verdict = "confirmed" if grew > 1.5 else "too weak to see"
        elif k == "cfo" and d:
            rot = abs(res["reports"]["cfo"]["total_phase_rad"])
            ds = m.get("constellation_diag_synced")
            if not d.get("model_valid", True):
                detail = (f"The constellation has closed into a ring: correlation with the "
                          f"transmitted symbols is only {_n(d['coherence'],3)} and sample angles "
                          f"are {_n(100*d['angular_uniformity'],1)}% of the way to uniform. The "
                          f"blind estimator still recovers {_n(m['cfo_blind']['hz'],1)} Hz, and "
                          f"after ideal derotation the margin returns to "
                          f"{_n(ds['separation_sigma'],1) if ds else 'n/a'} sigma.")
            else:
                detail = (f"Measured net rotation {_n(d['net_rotation_deg'],1)} degrees, "
                          f"tangential spread {_n(d['tangential_over_radial'],1)}x radial, "
                          f"angular uniformity {_n(d['angular_uniformity'],3)}. Blind estimator "
                          f"recovered {_n(m['cfo_blind']['hz'],1)} Hz.")
            verdict = ("confirmed" if rot > 0.15 else "present but too weak to see at this "
                                                      "frame length")
        elif k == "phase_offset" and d:
            got = d["net_rotation_deg"]
            want = res["reports"]["phase_offset"]["phase_offset_deg"]
            detail = (f"Measured rotation {_n(got,2)} degrees against {_n(want,2)} configured, "
                      f"with cluster spread unchanged ({_n(d['mean_cluster_std'],4)} versus "
                      f"{_n(dcl['mean_cluster_std'],4)} clean) -- a rigid rotation, exactly as "
                      f"predicted, with no smearing.")
            verdict = "confirmed"
        elif k == "phase_noise" and d and d.get("model_valid", True):
            detail = (f"Clouds are {_n(d['tangential_over_radial'],2)}x wider tangentially than "
                      f"radially, which is the tangential-only signature phase noise predicts "
                      f"and additive noise does not.")
            verdict = "confirmed" if d["tangential_over_radial"] > 1.4 else "too weak to see"
        elif k == "dc_offset" and d and dcl and d.get("model_valid", True):
            detail = (f"Constellation centre of mass moved from {_n(dcl['centroid_offset'],4)} "
                      f"to {_n(d['centroid_offset'],4)}; the blind DC estimate reads "
                      f"{_n(m['dc']['rel_rms'],4)} of RMS.")
            verdict = "confirmed" if d["centroid_offset"] > 3 * dcl["centroid_offset"] else "too weak to see"
        elif k == "iq_imbalance":
            detail = (f"Blind image-rejection estimate {_n(m['iq_blind']['image_rejection_db'],1)} "
                      f"dB against {_n(res['reports']['iq_imbalance']['image_rejection_db'],1)} dB "
                      f"from the model; the measurement floor at this frame length is "
                      f"{_n(m['iq_blind']['measurement_floor_db'],0)} dB.")
            verdict = ("confirmed"
                       if m["iq_blind"]["image_rejection_db"] < m["iq_blind"]["measurement_floor_db"] - 2
                       else "below the measurement floor -- cannot be distinguished from a "
                            "perfectly balanced receiver at this frame length")
        elif k == "pa" and d and d.get("model_valid", True):
            detail = (f"Clouds are {_n(1/max(d['tangential_over_radial'],1e-9),1)}x wider "
                      f"radially than tangentially -- amplitude distortion, not phase. Peak "
                      f"compression {_n(res['reports']['pa']['peak_compression_db'],2)} dB, "
                      f"PAPR {_n(res['reports']['pa']['papr_before_db'],2)} -> "
                      f"{_n(res['reports']['pa']['papr_after_db'],2)} dB.")
            verdict = ("confirmed" if abs(res["reports"]["pa"]["peak_compression_db"]) > 0.2
                       else "too weak to see")
        elif k == "clock_offset":
            e = res["plots"].get("eye") or {}
            detail = (f"Eye opening {_n(e.get('opening'),3)}, symbol EVM "
                      f"{_n(m['symbol_evm_pct'],2)}%, detected symbol lag "
                      f"{m.get('symbol_lag')}.")
            verdict = ("confirmed" if abs(res["reports"]["clock_offset"]
                                          ["drift_symbols_over_frame"]) > 0.02
                       or abs(res["reports"]["clock_offset"]["static_timing_offset_symbols"]) > 0.02
                       else "too weak to see")
        elif k == "interference":
            detail = (f"Look for the line in the spectrum at "
                      f"{_n(res['reports']['interference']['freq_offset_hz']/1e3,1)} kHz.")
        elif k == "quantization":
            r = res["reports"]["quantization"]
            detail = (f"Measured SQNR {_n(r['measured_sqnr_db'],1)} dB against the theoretical "
                      f"{_n(r['theoretical_sqnr_db'],1)} dB; {r['codes_used_i']} of "
                      f"{r['codes_available']} codes used.")
        elif k == "clipping":
            r = res["reports"]["clipping"]
            detail = (f"{_n(100*r['fraction_clipped'],3)}% of samples limited; PAPR "
                      f"{_n(r['papr_before_db'],2)} -> {_n(r['papr_after_db'],2)} dB.")
            verdict = "confirmed" if r["fraction_clipped"] > 1e-4 else "no samples actually clipped"
        elif k in ("multipath", "fading"):
            detail = (f"Symbol EVM {_n(m['symbol_evm_pct'],2)}%, residual after ideal "
                      f"synchronisation {_n(m['residual_evm_pct'],2)}%.")

        rows.append({"impairment": p.get("name", k), "key": k,
                     "predicted": expected, "observed": detail, "verdict": verdict})

    if not rows:
        rows.append({
            "impairment": "No impairments", "key": None,
            "predicted": "A clean reference waveform with zero error.",
            "observed": f"Waveform EVM against the ideal is {_n(m['waveform_evm_pct'],3)}%, "
                        f"which is residual pulse-shaping truncation, not an impairment.",
            "verdict": "confirmed"})

    surprises = []
    if d and dcl:
        if d["separation_sigma"] < 3 and not res["active"]:
            surprises.append("The clusters are wider than a clean signal should give, with no "
                             "impairment enabled. Worth investigating.")
    if m["symbol_rate_blind"]["hz"] and not m["symbol_rate_blind"]["reliable"]:
        surprises.append(
            f"The blind symbol-rate estimator did not find a reliable line (prominence "
            f"{_n(m['symbol_rate_blind']['prominence'],1)}x). Its answer of "
            f"{_n((m['symbol_rate_blind']['hz'] or 0)/1e3,1)} kBaud should be read as a "
            f"non-detection rather than a measurement.")
    return {"rows": rows, "surprises": surprises,
            "overall": res["overall"]}


# --------------------------------------------------------------------------

def why_care(res):
    sig = res["signal"]
    mp = mod_profile(sig["mod"]) or {}
    m = res["measurements"]
    out = {"amc": [], "sdr": [], "sim_to_real": [], "preprocessing": [], "fingerprint": []}

    out["amc"].append(
        f"{mp.get('name', sig['mod'])}: {mp.get('difficulty')} Commonly confused with: "
        + "; ".join(mp.get("confusions", []) or ["nothing in particular"]))
    for k in res["active"]:
        p = imp_profile(k) or {}
        s = res["severity"].get(k, {})
        out["amc"].append(f"{p.get('name', k)} ({s.get('level','')}): {p.get('amc')}")
        out["sdr"].append(f"{p.get('name', k)}: {p.get('sdr')}")
        out["sim_to_real"].append(
            f"{p.get('name', k)} — modelled in synthetic data: {p.get('in_synthetic')} "
            f"Hard to model realistically: {p.get('hard_to_model')}")
        out["preprocessing"].append(
            f"{p.get('name', k)} — correctable: {p.get('correctable')} "
            f"Can a classifier learn around it: {p.get('classifier_can_learn')}")
        if k in ("iq_imbalance", "pa", "dc_offset", "phase_noise", "quantization"):
            out["fingerprint"].append(
                f"{p.get('name', k)} is largely device-specific and stable over time, so a "
                f"classifier can learn it as transmitter identity rather than as modulation. "
                f"That inflates accuracy when train and test share a device and collapses it "
                f"when they do not.")

    if res["active"]:
        corr = m["correctable_fraction"]
        out["preprocessing"].insert(0, (
            f"Measured directly: a perfect synchroniser (ideal gain, frequency and phase "
            f"correction) would remove {_n(100*corr,0)}% of the total deviation, taking EVM from "
            f"{_n(m['waveform_evm_pct'],1)}% to {_n(m['residual_evm_pct'],1)}%. That residual is "
            f"the part no front-end correction can reach."))
    else:
        out["amc"].append("With no impairments this is the in-distribution case that synthetic "
                          "training data represents perfectly -- and precisely the case that "
                          "tells you nothing about real-world performance.")
        out["sim_to_real"].append(
            "The whole sim-to-real problem is that models are trained on frames like this one "
            "and deployed on frames that are not. Enable impairments one at a time and watch "
            "how far the picture moves.")
    return out


# --------------------------------------------------------------------------

def next_experiments(res):
    """A guided curriculum: what to change, and what question it answers."""
    sig = res["signal"]
    act = set(res["active"])
    imps = res["config"]["impairments"]
    sug = []

    def add(label, cfg, why, kind="explore"):
        sug.append({"label": label, "config": cfg, "why": why, "kind": kind})

    if not act:
        add("Add AWGN at 10 dB", {"impairments": {"awgn": {"enabled": True, "snr_db": 10}}},
            "Start with the one impairment simulations model perfectly. Watch the clusters "
            "spread while their positions stay put -- noise blurs, it does not move things.",
            "next")
        add("Add CFO at 500 Hz", {"impairments": {"cfo": {"enabled": True, "cfo_hz": 500}}},
            "Then compare noise-induced spreading against deterministic rotation. Both damage "
            "classification, and they look completely different. Learning to tell them apart by "
            "eye is the single most useful skill this lab can give you.")
        if sig["family"] in ("psk", "qam"):
            add("Switch to 64-QAM, same settings", {"mod": "64qam"},
                "Same channel, denser constellation. The tolerance budget drops from "
                f"{_n(res['geometry'].get('phase_tolerance_deg'),1)} degrees to about 5.8, which "
                "is why high-order QAM collapses under conditions QPSK shrugs off.")
        return sug

    if "awgn" in act:
        snr = imps["awgn"].get("snr_db", 20)
        if snr > 0:
            add(f"Drop SNR to {snr-10:.0f} dB",
                {"impairments": {"awgn": {"enabled": True, "snr_db": snr - 10}}},
                f"Find the point where the clusters stop being separable. The severity panel "
                f"reports the margin in noise sigma -- watch for it passing below about 3, "
                f"which is where neighbouring clouds start touching.", "next")
        if sig["mod"] in ("qpsk", "bpsk"):
            add("Same SNR on 256-QAM", {"mod": "256qam"},
                f"At the same SNR, d_min falls from {_n(res['geometry'].get('d_min'),3)} to "
                f"0.153. The noise has not changed; the margin has. This is the clearest "
                f"demonstration that SNR alone never tells you whether a signal is decodable.")
        if "cfo" not in act:
            add("Add CFO on top of the noise",
                {"impairments": dict(imps, cfo={"enabled": True, "cfo_hz": 800})},
                "Real signals rarely carry exactly one impairment. See whether you can still "
                "tell which effect is which once they are combined -- the cluster shape "
                "diagnostic separates them even when your eye cannot.")

    if "cfo" in act:
        f0 = imps["cfo"].get("cfo_hz", 1000)
        add(f"Increase CFO to {f0*4:.0f} Hz",
            {"impairments": dict(imps, cfo={"enabled": True, "cfo_hz": f0 * 4})},
            "Push the accumulated rotation past a full turn and watch the clusters close into a "
            "complete ring. That is the moment the phase information identifying the modulation "
            "order is genuinely destroyed rather than merely obscured.", "next")
        add("Halve the frame length", {"n_samples": max(512, res["signal"]["n_samples"] // 2)},
            "CFO damage is accumulated rotation, which is proportional to observation time. "
            "Halving the frame halves the smear -- for this impairment, shorter frames are "
            "better, the opposite of the usual rule.")
        if sig["family"] != "fsk":
            add("Same CFO on 2-FSK", {"mod": "2fsk"},
                "FSK barely notices: an offset slides all tones equally and leaves their spacing "
                "intact. Comparing the two shows that 'how bad is this impairment' has no answer "
                "independent of the modulation.")

    if "phase_noise" in act and "awgn" not in act:
        add("Add AWGN alongside the phase noise",
            {"impairments": dict(imps, awgn={"enabled": True, "snr_db": 20})},
            "Both blur the constellation. Only one does it isotropically. Use the "
            "tangential-over-radial number to separate them, then try to see it by eye.")

    if "pa" in act and sig["mod"] in ("16qam", "64qam", "256qam"):
        add("Same amplifier setting on 16-APSK", {"mod": "16apsk"},
            "APSK exists precisely because of this impairment. Same order, same back-off, fewer "
            "amplitude levels -- see how much less damage the same amplifier does.", "next")

    if "multipath" in act:
        d = imps["multipath"].get("delays_us", [0, 2])
        add(f"Increase the second path delay to {max(d)*3:.0f} us",
            {"impairments": dict(imps, multipath=dict(imps["multipath"],
                                                      delays_us=[0, max(d) * 3]))},
            "Push the delay spread past a significant fraction of the symbol period and watch "
            "flat fading become frequency-selective: notches appear in the response and the eye "
            "closes from intersymbol interference.", "next")

    if sig["family"] != "ofdm" and "cfo" in act:
        add("Try the same CFO on OFDM", {"mod": "ofdm"},
            "For single-carrier signals CFO is a rotation you can undo. For OFDM it breaks "
            "subcarrier orthogonality and injects interference that derotation cannot fix. Same "
            "impairment, categorically different consequence.")

    if not any(s["kind"] == "next" for s in sug) and sug:
        sug[0]["kind"] = "next"
    if len(sug) < 3:
        add("Run the identification challenge", {"__challenge__": True},
            "Test whether the associations have stuck: identify a hidden modulation and "
            "impairment from the plots alone.")
    return sug
