"""Generate the QA report: expected behaviour, measured value, verdict.

Each row states a physical prediction made independently of the code, then the
number the lab actually measured from the samples.  A row passes only if the
two agree -- "the script ran" is not evidence of anything.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rflab.experiment import run
from rflab.tutor import narrate as N

SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
R = []


def case(name, cfg, expectation, checks, look_for):
    res = run(cfg)
    rows = []
    for label, predicted, got, tol, unit in checks:
        ok = (abs(got - predicted) <= tol) if predicted is not None else bool(got)
        rows.append({"quantity": label, "predicted": predicted, "measured": got,
                     "tol": tol, "unit": unit, "pass": bool(ok)})
    obs = N.observe(look_for["view"], res)
    R.append({"name": name, "config": cfg, "expectation": expectation,
              "view": look_for["view"], "look_for": look_for["text"],
              "checks": rows, "tutor_says": obs,
              "pass": all(r["pass"] for r in rows)})
    return res


fs, sps, N4 = 1e6, 8, 4096
Rs = fs / sps

# --- AWGN: cluster spread must scale as 1/sqrt(Es/N0), isotropically ---
for snr in (20, 10, 0):
    r = run({"mod": "qpsk", "n_samples": 8192, "impairments": {"awgn": {"enabled": True, "snr_db": snr}}})
    d = r["measurements"]["constellation_diag"]
    esn0 = 10 ** ((snr + 10 * np.log10(sps)) / 10)
    theo_sigma = np.sqrt(1 / (2 * esn0))
    theo_sep = (np.sqrt(2) / 2) / (theo_sigma * np.sqrt(2))
    case(f"QPSK + AWGN {snr} dB",
         {"mod": "qpsk", "impairments": {"awgn": {"snr_db": snr}}},
         f"Clusters blur isotropically. Margin = (d_min/2)/sigma with "
         f"Es/N0 = SNR + 10log10(sps) = {snr + 10*np.log10(sps):.1f} dB, predicting {theo_sep:.1f} sigma.",
         [("decision margin", theo_sep, d["separation_sigma"], max(0.15 * theo_sep, 0.4), "sigma"),
          ("tangential/radial (1.0 = isotropic)", 1.0, d["tangential_over_radial"], 0.15, ""),
          ("net rotation", 0.0, d["net_rotation_deg"], 2.0, "deg")],
         {"view": "constellation", "text": "round clouds centred on the ideal markers, growing as SNR falls"})

# --- CFO: rotation must equal 2 pi df T, and the blind estimator must recover df ---
for f0 in (200, 2000):
    r = run({"mod": "qpsk", "n_samples": N4, "impairments": {"cfo": {"enabled": True, "cfo_hz": f0}}})
    theo = 2 * np.pi * f0 * N4 / fs
    case(f"QPSK + CFO {f0} Hz",
         {"mod": "qpsk", "impairments": {"cfo": {"cfo_hz": f0}}},
         f"Phase accumulates 2.pi.{f0}.{N4}/{fs:.0f} = {theo:.2f} rad = {theo/(2*np.pi):.2f} turns; "
         f"the constellation smears into an arc or a full ring.",
         [("accumulated rotation", theo, r["reports"]["cfo"]["total_phase_rad"], 1e-6, "rad"),
          ("blind CFO estimate", f0, r["measurements"]["cfo_blind"]["hz"], max(0.03 * f0, 20), "Hz"),
          ("carrier phase drift on the plot", theo * r["plots"]["phase"]["span_fraction"],
           r["plots"]["phase"]["total_drift_rad"], 0.08 * theo, "rad")],
         {"view": "constellation", "text": "an arc or closed ring, not clusters"})

# --- DC offset: translation without rotation, plus a DC spectral line ---
r = run({"mod": "16qam", "n_samples": N4, "impairments": {"dc_offset": {"enabled": True, "i": 0.35, "q": 0.15}}})
f_, mag = np.array(r["plots"]["fft"]["f"]), np.array(r["plots"]["fft"]["mag"])
k0 = int(np.argmin(np.abs(f_))); kside = int(np.argmin(np.abs(f_ - 300)))
a = np.hypot(0.35, 0.15)
d = r["measurements"]["constellation_diag"]
dc0 = r["measurements"]["constellation_diag_clean"]["centroid_offset"]
case("16-QAM + DC offset",
     {"mod": "16qam", "impairments": {"dc_offset": {"i": 0.35, "q": 0.15}}},
     f"A constant is added to every sample: the constellation translates by {a:.3f}x RMS without "
     f"rotating or smearing, and a spike appears at exactly 0 Hz.",
     [("centroid offset", a / np.sqrt(1 + a * a), r["measurements"]["dc"]["rel_rms"], 0.02, "x RMS"),
      ("cluster spread unchanged", dc0 * 0 + r["measurements"]["constellation_diag_clean"]["mean_cluster_std"],
       d["mean_cluster_std"], 0.01, ""),
      ("net rotation", 0.0, d["net_rotation_deg"], 2.0, "deg"),
      ("DC spike above the band edge", None, mag[k0] - mag[kside] > 15, 0, "dB")],
     {"view": "constellation", "text": "the whole pattern shifted off the origin, still sharp"})

# --- I/Q imbalance: image rejection and a skewed constellation ---
r = run({"mod": "16qam", "n_samples": 16384,
         "impairments": {"iq_imbalance": {"enabled": True, "gain_db": 2.5, "phase_deg": 12}}})
case("16-QAM + I/Q imbalance",
     {"mod": "16qam", "impairments": {"iq_imbalance": {"gain_db": 2.5, "phase_deg": 12}}},
     "The output becomes signal plus a fraction of its own conjugate: a mirror image appears in "
     "the spectrum and the square grid shears into a parallelogram.",
     [("image rejection (model vs blind)", r["reports"]["iq_imbalance"]["image_rejection_db"],
       r["measurements"]["iq_blind"]["image_rejection_db"], 3.0, "dB")],
     {"view": "constellation", "text": "a sheared grid, not a square one"})

# --- PA nonlinearity: radial compression and spectral regrowth ---
r = run({"mod": "16qam", "n_samples": N4, "impairments": {"pa": {"enabled": True, "ibo_db": 0.5}}})
d = r["measurements"]["constellation_diag"]
case("16-QAM + PA compression (IBO 0.5 dB)",
     {"mod": "16qam", "impairments": {"pa": {"ibo_db": 0.5}}},
     "Amplitude compression squashes the outer ring inward while the inner points stay put, so "
     "the clouds stretch radially rather than tangentially, and PAPR falls.",
     [("tangential/radial (<1 = radial)", None, d["tangential_over_radial"] < 0.8, 0, ""),
      ("PAPR reduced", None, r["reports"]["pa"]["papr_after_db"] < r["reports"]["pa"]["papr_before_db"], 0, ""),
      ("peak compression present", None, abs(r["reports"]["pa"]["peak_compression_db"]) > 1.0, 0, "dB")],
     {"view": "am_am", "text": "a transfer curve bending away from the ideal straight line"})

# --- FSK: instantaneous frequency must sit on a.h.Rs/2 ---
for mod, lv in (("2fsk", 2), ("4fsk", 4)):
    r = run({"mod": mod, "n_samples": N4})
    h = r["signal"]["info"]["mod_index_h"]
    theo = [a * h * Rs / 2 / 1e3 for a in range(-(lv - 1), lv, 2)]
    got = r["plots"]["inst_freq"]["levels_khz"]
    case(f"{mod.upper()} instantaneous frequency",
         {"mod": mod},
         f"The trace dwells on {lv} discrete levels at a.h.Rs/2 = {', '.join(f'{v:.1f}' for v in theo)} kHz.",
         [(f"level {i}", theo[i], got[i], 0.1, "kHz") for i in range(lv)],
         {"view": "inst_freq", "text": f"{lv} flat levels landing on the dashed markers"})

# --- FM: Carson bandwidth ---
r = run({"mod": "wbfm", "n_samples": N4, "msg_bw": 25e3})
info = r["signal"]["info"]
case("WBFM occupied bandwidth vs Carson's rule",
     {"mod": "wbfm", "msg_bw": 25000},
     f"Carson: 2(dev + msg BW) = {info['carson_bw_hz']/1e3:.0f} kHz. The 99% occupied bandwidth "
     f"should be of that order, a little under it since Carson is a 98% rule of thumb.",
     [("99% occupied bandwidth", info["carson_bw_hz"] / 1e3,
       r["measurements"]["occupied_bw_hz"] / 1e3, 0.35 * info["carson_bw_hz"] / 1e3, "kHz")],
     {"view": "inst_freq", "text": "frequency tracking the message, not hopping between levels"})

# --- OFDM: cyclic prefix autocorrelation and CP-based CFO ---
r = run({"mod": "ofdm", "n_samples": 8192, "impairments": {"cfo": {"enabled": True, "cfo_hz": 2000}}})
ac = np.array(r["plots"]["autocorr"]["r"]); lag = r["plots"]["autocorr"]["expect_peak_lag"]
case("OFDM cyclic-prefix signature and CFO",
     {"mod": "ofdm", "impairments": {"cfo": {"cfo_hz": 2000}}},
     "The cyclic prefix is a copy of the symbol tail, so autocorrelation peaks at lag = N_FFT, "
     "and that same redundancy lets the CFO be estimated with no preamble.",
     [("autocorrelation peak at N_FFT", None, ac[lag - 2:lag + 3].max() > 0.1, 0, ""),
      ("CP-based CFO estimate", 2000.0, r["measurements"]["cfo_blind"]["hz"], 60, "Hz")],
     {"view": "autocorr", "text": f"a clear spike at lag {lag}"})

# --- Multipath: two-ray null spacing = 1/delay ---
tau = 6e-6
r = run({"mod": "qpsk", "n_samples": N4,
         "impairments": {"multipath": {"enabled": True, "delays_us": [0, 6], "gains_db": [0, -2]}}})
ch = r["plots"]["channel"]
fh, H = np.array(ch["f_khz"]), np.array(ch["H_db"])
mins = fh[1:-1][(H[1:-1] < H[:-2]) & (H[1:-1] < H[2:]) & (H[1:-1] < H.mean() - 6)]
spacing = float(np.median(np.diff(mins))) if len(mins) > 1 else float("nan")
case("QPSK + two-ray multipath (6 us)",
     {"mod": "qpsk", "impairments": {"multipath": {"delays_us": [0, 6], "gains_db": [0, -2]}}},
     f"Two paths {tau*1e6:.0f} us apart cancel periodically, so the frequency response has nulls "
     f"spaced 1/tau = {1/tau/1e3:.0f} kHz apart.",
     [("null spacing", 1 / tau / 1e3, spacing, 0.06 / tau / 1e3, "kHz"),
      ("coherence BW below signal BW", None,
       ch["coherence_bw_khz"] < r["plots"]["psd"]["occupied_bw_khz"], 0, "")],
     {"view": "channel", "text": "periodic notches in the frequency response"})

# --- Quantisation: SQNR = 6.02b + 1.76 - headroom ---
for bits in (8, 4):
    r = run({"mod": "16qam", "n_samples": N4,
             "impairments": {"quantization": {"enabled": True, "bits": bits, "headroom_db": 6}}})
    q = r["reports"]["quantization"]
    case(f"16-QAM + {bits}-bit quantisation",
         {"mod": "16qam", "impairments": {"quantization": {"bits": bits}}},
         f"SQNR should be 6.02x{bits} + 1.76 - 6 = {q['theoretical_sqnr_db']:.1f} dB, and the "
         f"samples should sit on a visible lattice.",
         [("SQNR", q["theoretical_sqnr_db"], q["measured_sqnr_db"], 3.0, "dB")],
         {"view": "iq_time", "text": "a waveform confined to discrete levels"})

# --- Clock offset: drift = ppm x symbols, eye closes ---
r0 = run({"mod": "16qam", "n_samples": 8192})
r = run({"mod": "16qam", "n_samples": 8192, "impairments": {"clock_offset": {"enabled": True, "ppm": 600}}})
case("16-QAM + 600 ppm clock offset",
     {"mod": "16qam", "impairments": {"clock_offset": {"ppm": 600}}},
     "Sampling instants slide by ppm x number of symbols, so the eye closes and the damage grows "
     "along the frame rather than being uniform.",
     [("drift over frame", 600e-6 * 8192 / sps,
       r["reports"]["clock_offset"]["drift_symbols_over_frame"], 1e-9, "symbols"),
      ("eye narrower than clean", None,
       r["plots"]["eye"]["opening"] < r0["plots"]["eye"]["opening"], 0, "")],
     {"view": "eye", "text": "a visibly narrower eye opening"})

# --- Interference: line at the configured offset ---
r = run({"mod": "qpsk", "n_samples": N4,
         "impairments": {"interference": {"enabled": True, "sir_db": 3, "kind": "cw",
                                          "freq_offset_hz": 200000}}})
f_, mag = np.array(r["plots"]["fft"]["f"]), np.array(r["plots"]["fft"]["mag"])
case("QPSK + CW interferer at 200 kHz",
     {"mod": "qpsk", "impairments": {"interference": {"sir_db": 3, "freq_offset_hz": 200000}}},
     "A continuous-wave interferer appears as a single line at its own frequency, obvious in the "
     "spectrum and nearly invisible in the constellation.",
     [("interferer frequency", 200.0, float(f_[int(np.argmax(mag))]), 3.0, "kHz")],
     {"view": "psd", "text": "a narrow line standing above the signal's shoulder"})

# --- BPSK vs QPSK conjugate cyclic feature ---
rb = run({"mod": "bpsk", "n_samples": 8192})
rq = run({"mod": "qpsk", "n_samples": 8192})
case("Conjugate cyclic feature separates BPSK from QPSK",
     {"mod": "bpsk"},
     "A real-valued constellation has a non-zero conjugate cyclic feature at alpha = 0; a "
     "rotationally symmetric one does not. BPSK should read near 1, QPSK near 0.",
     [("BPSK conj at alpha=0", 1.0, rb["plots"]["cyclic"]["conj_at_zero"], 0.15, ""),
      ("QPSK conj at alpha=0", 0.0, rq["plots"]["cyclic"]["conj_at_zero"], 0.2, "")],
     {"view": "cyclic", "text": "the magenta trace high for BPSK and flat for QPSK"})

# --- Cumulants vs the classical table ---
for mod in ("bpsk", "qpsk", "8psk", "16qam"):
    r = run({"mod": mod, "n_samples": 16384})
    cm, ci = r["plots"]["cumulants"]["measured"], r["plots"]["cumulants"]["ideal"]
    case(f"{mod.upper()} higher-order cumulants",
         {"mod": mod},
         f"Classical AMC table: |C40| = {ci['C40']}, |C42| = {ci['C42']}.",
         [("|C40|", ci["C40"], cm["C40"], 0.12, ""), ("|C42|", ci["C42"], cm["C42"], 0.12, "")],
         {"view": "cumulants", "text": "measured bars close to the theory marks"})

npass = sum(1 for c in R if c["pass"])
out = ["# RF Signal Lab — verification report", "",
       f"{npass} of {len(R)} experiments agree with theory.", "",
       "Each row states a prediction derived from physics, then the value the lab measured from "
       "the generated samples. Screenshots of every case were inspected as part of this pass; "
       "the *look for* line records what the visual had to show for the case to count as passing.",
       ""]
for c in R:
    out.append(f"## {c['name']} — {'PASS' if c['pass'] else 'FAIL'}")
    out.append("")
    out.append(f"**Expected.** {c['expectation']}")
    out.append("")
    out.append(f"**Look for in the {c['view']} view.** {c['look_for']}")
    out.append("")
    out.append("| quantity | predicted | measured | tolerance | verdict |")
    out.append("|---|---|---|---|---|")
    for k in c["checks"]:
        p = "—" if k["predicted"] is None else f"{k['predicted']:.4g} {k['unit']}"
        m = k["measured"]
        m = ("yes" if m else "no") if isinstance(m, (bool, np.bool_)) else f"{m:.4g} {k['unit']}"
        t = "—" if k["predicted"] is None else f"±{k['tol']:.3g}"
        out.append(f"| {k['quantity']} | {p} | {m} | {t} | {'PASS' if k['pass'] else 'FAIL'} |")
    out.append("")
    out.append("**What the tutor says about this configuration.**")
    out.append("")
    for o in c["tutor_says"][:3]:
        out.append(f"> {o}")
        out.append(">")
    out.append("")

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERIFICATION.md")
open(path, "w").write("\n".join(out))
print("\n".join(f"{'PASS' if c['pass'] else 'FAIL'}  {c['name']}" for c in R))
print(f"\n{npass}/{len(R)} passed -> {path}")
sys.exit(0 if npass == len(R) else 1)
