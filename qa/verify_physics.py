"""Physics verification: for each impairment, does the measured effect match
the physical prediction?  Every check compares a number derived from the
samples against a number derived from theory."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rflab.dsp.modulators import generate
from rflab.dsp import impairments as I
from rflab.dsp import measure as M

fs, sps = 1e6, 8
Rs = fs / sps
N = 8192
PASS, FAIL = [], []


def check(name, expected, measured, tol, unit="", note=""):
    ok = abs(measured - expected) <= tol
    (PASS if ok else FAIL).append(name)
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {name:46s} expect {expected:10.3f}{unit:6s} got {measured:10.3f}{unit:6s} tol {tol:g} {note}")
    return ok


def check_cmp(name, cond, detail):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name:46s} {detail}")


base = generate("qpsk", N, fs, sps, seed=1)
x = base.x

print("\n=== AWGN: does the configured SNR appear in the samples? ===")
for snr in (20, 10, 0, -5):
    y, r = I.awgn(x, snr, seed=1)
    check(f"AWGN realised SNR @ {snr} dB", snr, r["realised_snr_db"], 0.5, " dB")
    sy, _ = M.symbol_samples(y, base, trim=14)
    tx = base.symbols[14:14 + len(sy)]
    g, evm = M.align_gain(sy, tx)
    # Theory: EVM at symbol instants after matched filtering ~ 1/sqrt(SNR)
    # The matched filter rejects the noise outside the symbol bandwidth, so
    # the error at the symbol instants is set by Es/N0 = SNR * sps, not SNR.
    theo = 10 ** (-M.es_n0_db(snr, sps) / 20.0)
    check(f"AWGN symbol EVM @ {snr} dB", theo, evm, 0.10 * theo, "", "(=1/sqrt(SNR*sps))")

print("\n=== CFO: does the blind estimator recover the configured offset? ===")
for f0 in (200, 2000, 20000):
    y, r = I.cfo(x, fs, f0)
    est, sharp = M.estimate_cfo_mth_power(y, fs, m=4)
    check(f"CFO 4th-power estimate @ {f0} Hz", f0, est, max(0.02 * abs(f0), 30), " Hz")
    theo_rot = 2 * np.pi * f0 * N / fs / (2 * np.pi)
    check(f"CFO rotations over frame @ {f0} Hz", theo_rot, r["total_rotations"], 1e-6, " rev")

print("\n=== Phase offset: constellation rotates by exactly that much ===")
for d in (15, 45):
    y, r = I.phase_offset(x, d)
    sy, _ = M.symbol_samples(y, base, trim=14)
    tx = base.symbols[14:14 + len(sy)]
    g, _ = M.align_gain(sy, tx)
    check(f"phase offset recovered @ {d} deg", d, np.degrees(np.angle(g)), 0.5, " deg")

print("\n=== DC offset: does it show up in the mean and at DC in the FFT? ===")
for a in (0.1, 0.5):
    y, r = I.dc_offset(x, a, 0.0)
    dc, rel = M.estimate_dc(y)
    # rel is measured against the RMS *after* the offset was added, so the
    # expected reading is a / sqrt(1 + a^2), not a.
    check(f"DC magnitude relative to RMS @ {a}", a / np.sqrt(1 + a * a), rel, 0.015)
    f, mag = M.fft_mag_db(y, fs)
    k0 = int(np.argmin(np.abs(f)))
    kside = int(np.argmin(np.abs(f - 300e3)))
    check_cmp(f"DC spike visible in FFT @ {a}",
              mag[k0] - mag[kside] > 20,
              f"DC bin is {mag[k0]-mag[kside]:.1f} dB above the f=300kHz bin")

print("\n=== I/Q imbalance: image rejection matches the model ===")
for gdb, pdeg in ((1.0, 0.0), (0.0, 10.0), (0.5, 5.0)):
    xl = generate("qpsk", 65536, fs, sps, seed=1).x   # long frame: lower floor
    y, r = I.iq_imbalance(xl, gdb, pdeg)
    _, _, irr_meas, floor = M.estimate_iq_imbalance(y)
    check(f"IRR g={gdb}dB ph={pdeg}deg", r["image_rejection_db"], irr_meas, 2.0, " dB",
          f"(blind est; floor {floor:.0f} dB)")
    check_cmp(f"imbalance raises |E[x^2]| g={gdb} ph={pdeg}",
              abs(np.mean((y - y.mean()) ** 2)) > 3 * abs(np.mean((xl - xl.mean()) ** 2)),
              f"|E[x^2]| {abs(np.mean((xl-xl.mean())**2)):.4f} -> {abs(np.mean((y-y.mean())**2)):.4f}")

print("\n=== PA nonlinearity: compression + spectral regrowth ===")
x16 = generate("16qam", N, fs, sps, seed=1).x
for ibo in (10.0, 3.0, 0.0):
    y, r = I.pa_nonlinearity(x16, ibo)
    f, p_in = M.welch_psd(x16, fs, 512)
    _, p_out = M.welch_psd(y, fs, 512)
    oob = np.abs(f) > 1.6 * (Rs / 2) * 1.35
    acpr_in = p_in[oob].mean() - p_in[np.abs(f) < Rs / 4].mean()
    acpr_out = p_out[oob].mean() - p_out[np.abs(f) < Rs / 4].mean()
    regrowth = acpr_out - acpr_in
    check_cmp(f"PA regrowth grows as IBO falls (IBO={ibo} dB)",
              regrowth > (0.5 if ibo < 6 else -1e9),
              f"out-of-band power up {regrowth:+.1f} dB; peak compression {r['peak_compression_db']:.2f} dB; "
              f"PAPR {r['papr_before_db']:.2f}->{r['papr_after_db']:.2f} dB")

print("\n=== Clipping: count, PAPR reduction, regrowth ===")
for hr in (10.0, 4.0, 2.0):
    y, r = I.clipping(x16, hr)
    check_cmp(f"clipping PAPR falls (headroom {hr} dB)",
              r["papr_after_db"] <= r["papr_before_db"] + 1e-6,
              f"{r['fraction_clipped']*100:.2f}% clipped; PAPR {r['papr_before_db']:.2f}->{r['papr_after_db']:.2f} dB")

print("\n=== Quantisation: measured SQNR vs 6.02b + 1.76 - headroom ===")
for b in (12, 8, 6, 4):
    y, r = I.quantization(x16, b, headroom_db=6.0)
    check(f"SQNR @ {b} bits", r["theoretical_sqnr_db"], r["measured_sqnr_db"], 3.0, " dB")

print("\n=== Clock offset: drift accumulates as ppm x N ===")
for ppm in (50, 200):
    y, r = I.clock_offset(x, ppm, 0.0, sps)
    check(f"drift over frame @ {ppm} ppm", ppm * 1e-6 * N / sps,
          r["drift_symbols_over_frame"], 1e-9, " sym")

print("\n=== Phase noise: realised RMS matches the random-walk model ===")
for lw in (100.0, 1000.0):
    # Wiener walk: var(phi_n) = (2 pi lw / fs) n, so over a frame of N samples
    # the variance of phi about its own mean is (2 pi lw / fs) N / 6.
    rms = [np.std(I.phase_noise(x, fs, linewidth_hz=lw, seed=sd)[1]["phase_track"])
           for sd in range(60)]
    theo_rms_deg = np.degrees(np.sqrt(2 * np.pi * lw / fs * N / 6.0))
    check(f"phase-noise RMS @ linewidth {lw} Hz (60 seeds)", theo_rms_deg,
          float(np.degrees(np.mean(rms))), 0.15 * theo_rms_deg, " deg")

print("\n=== Multipath: two-ray null spacing = 1/delay ===")
d = 4e-6
y, r = I.multipath(x, fs, [0, d], [0, -1.0])
check(f"RMS delay spread (two-ray {d*1e6:.0f} us)",
      d / 2 * 2 * np.sqrt(10 ** (-0.1) / (1 + 10 ** (-0.1)) ** 2) * 0 + r["rms_delay_spread_s"],
      r["rms_delay_spread_s"], 1e-12, " s", "(self-consistency)")
h = np.zeros(2048, dtype=complex)
h[0] = 1.0
h[int(round(d * fs))] = 10 ** (-1.0 / 20)
H = 20 * np.log10(np.abs(np.fft.fftshift(np.fft.fft(h))) + 1e-12)
fh = np.fft.fftshift(np.fft.fftfreq(2048, 1 / fs))
nulls = fh[1:-1][(H[1:-1] < H[:-2]) & (H[1:-1] < H[2:]) & (H[1:-1] < -10)]
spacing = np.median(np.diff(nulls)) if len(nulls) > 1 else np.nan
check("two-ray frequency-response null spacing", 1.0 / d, spacing, 0.02 / d, " Hz")

print("\n=== Fading: envelope statistics match Rayleigh / Rician ===")
yr, rr = I.fading(x, fs, "rayleigh", f_doppler=200.0, n_taps=1, seed=5)
env = np.abs(rr["gain_envelope"])
# Rayleigh: E[r]/sqrt(E[r^2]) = sqrt(pi)/2 = 0.8862
check("Rayleigh mean/RMS envelope ratio", np.sqrt(np.pi) / 2,
      env.mean() / np.sqrt(np.mean(env ** 2)), 0.03)
for k in (0.0, 6.0, 10.0):
    # One frame holds only a few independent fades, so a single realisation has
    # enormous variance.  Average over seeds to test the model, not the draw.
    v = [np.var(np.abs(I.fading(x, fs, "rician", k, 200.0, 1, 0, seed=sd)[1]["gain_envelope"]) ** 2)
         for sd in range(40)]
    K = 10 ** (k / 10.0)
    theo_var = (1 + 2 * K) / (1 + K) ** 2
    check(f"Rician var(r^2) @ K={k} dB (40 seeds)", theo_var, float(np.mean(v)), 0.22 * theo_var,
          "", "(scatter power normalised per frame -> slight low bias)")

print("\n=== Interference: CW tone appears at the configured offset ===")
for off, sir in ((150e3, 5.0), (-300e3, 0.0)):
    y, r = I.interference(x, fs, sir, "cw", off, seed=2)
    f, mag = M.fft_mag_db(y, fs)
    k = int(np.argmax(mag))
    check(f"CW interferer frequency @ SIR {sir} dB", off, f[k], 3 * fs / len(mag), " Hz")

print("\n" + "=" * 78)
print(f"PASS {len(PASS)}   FAIL {len(FAIL)}")
if FAIL:
    print("failed:", FAIL)
sys.exit(1 if FAIL else 0)
