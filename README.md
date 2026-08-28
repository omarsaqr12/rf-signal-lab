# RF Signal Lab

An interactive laboratory for learning RF signal structure by breaking signals on purpose and
watching what happens. Every plot comes with a tutor that reads the actual measurements — not the
configuration — and explains what is on screen, why it looks that way, how severe the effect is in
physically meaningful units, and what it means for automatic modulation classification and for real
SDR hardware.

```
./run.sh            # then open http://127.0.0.1:8765
```

Requires Python 3 with `numpy` and `scipy`. Nothing else — the server is standard library and the
front end is dependency-free.

---

## What it does

**28 modulations** — BPSK, QPSK, 8PSK, 16PSK, 16/64/256-QAM, 4-PAM, OOK, 4-ASK, 16/32-APSK,
DBPSK, DQPSK, π/4-DQPSK, OQPSK, 2/4-FSK, CPFSK, MSK, GFSK, GMSK, AM-DSB-WC, AM-DSB-SC, AM-SSB,
FM, WBFM, OFDM.

**13 impairments**, applied in the order a real signal meets them:

```
TX → PA nonlinearity → multipath → fading → interference
   → CFO, phase offset, phase noise (receiver LO)
   → sample clock offset → AWGN → I/Q imbalance, DC offset
   → clipping → quantisation (ADC) → RX
```

The order is not cosmetic. Apply I/Q imbalance before the channel and you get a signal no radio
could physically produce.

**Light and dark themes** — toggle in the header, remembered across sessions, defaulting to your
system preference. Both are driven from one set of CSS custom properties that the canvas reads at
draw time, so plots and chrome cannot drift apart. The two colour ramps are inverted deliberately:
on a dark page stronger reads as brighter, on a light page as darker, because a near-white "hot"
pixel would vanish into a white background.

**17 views** — constellation, I/Q vs time, magnitude, phase, instantaneous frequency, FFT, PSD,
spectrogram, eye diagram, autocorrelation, higher-order cumulants, cyclostationarity, amplitude
histogram, PAPR CCDF, AM/AM transfer, channel response, OFDM subcarrier view. The lab promotes
whichever views actually reveal what is switched on, so an FSK signal leads with instantaneous
frequency rather than a constellation that would show a featureless circle.

---

## The ideas the lab is built around

### Severity is a ratio, not a threshold

"CFO = 2 kHz is moderate" is close to meaningless — 2 kHz is nothing to a 10 MBaud link and
catastrophic to a 1 kBaud one. Every severity judgement here is a ratio between the impairment and
something about *this* signal. For constellation-bearing modulations that is a tolerance budget:

```
phase tolerance     = (d_min / 2) / r_max      radians
amplitude tolerance =  d_min / 2
```

which yields, for unit-average-power constellations:

| modulation | d_min | phase tolerance |
|---|---|---|
| QPSK | 1.414 | 40.5° |
| 16-QAM | 0.632 | 13.5° |
| 64-QAM | 0.309 | 5.8° |
| 256-QAM | 0.153 | 2.7° |

The same 5° of phase noise is negligible for QPSK and fatal for 256-QAM, and the lab says so with
the arithmetic attached.

### Cluster shape identifies the cause, not just the damage

Three impairments all read as "the constellation is blurred". They are separable by measuring how
the clouds are stretched:

| measured | cause |
|---|---|
| tangential ≈ radial | additive noise — isotropic |
| tangential ≫ radial | phase noise or residual CFO |
| radial ≫ tangential | amplifier compression, timing error |
| centres moved, spread unchanged | DC offset (translation) or phase offset (rotation) |
| centres displaced systematically, spread unchanged | I/Q imbalance — deterministic shear |

A companion figure, deterministic displacement over random scatter, separates repeatable distortion
(correctable, and a device fingerprint) from random distortion (not correctable). It reads ~0.1 for
noise and ~97 for I/Q imbalance.

### The tutor describes what is measurable, not what was configured

If an impairment is too weak to see, it says so. If the constellation has closed into a ring, it
reports that cluster statistics are meaningless there rather than printing a number — and then
shows what the structure looks like after ideal synchronisation, which answers whether the
information was destroyed or merely rotated out of view.

### Every experiment is checked against physics

The right rail carries a verification panel comparing what you configured against what blind
estimators recover from the samples alone: CFO by the M-th power method (or the cyclic prefix for
OFDM, or the midpoint of the frequency states for FSK), symbol rate by the envelope line or cyclic
autocorrelation, image rejection from the improper second moment. Where an estimator does not apply
— the 4th-power trick on APSK, for instance — it reports **inconclusive** rather than a confident
wrong number, and explains why.

### Residual after ideal synchronisation

Alongside raw EVM, the lab reports what survives a perfect gain, frequency and phase correction.
That single number answers "could preprocessing fix this?" directly: pure CFO leaves 0%, additive
noise leaves all of it.

---

## Learning aids

- **Explain this plot** — a contextual walkthrough of any view: the question it answers, its axes,
  what a clean signal looks like, what you are seeing now, what changed and why, how severe, and
  what to look at next.
- **What should I see? / Compare with actual** — commit to a theoretical prediction, then see it
  checked against the measurement with an explicit verdict.
- **Why should I care?** — AMC impact, SDR impact, whether the effect appears in synthetic
  datasets, whether it is correctable, and whether it carries device identity.
- **Try this next** — a guided curriculum that proposes the next experiment and says what question
  it answers. One click loads it.
- **Challenges** — eight blind identification exercises. The answer stays on the server and every
  label, reference trace and tutor panel is stripped from the page until you commit a guess.
- **Clean → impaired strip** — the constellation after each stage of the chain, with the error each
  stage added.

Content is sourced in two labelled kinds: **study guide** for points made in the *RF Modulation
Recognition Study Guide*, and **rf context** for standard RF/DSP knowledge added to go deeper.
Nothing is attributed to the guide that the guide does not say.

---

## Verification

```
python3 qa/verify_physics.py    # 48 numeric checks of the DSP against closed-form theory
python3 qa/report.py            # 22 experiments: prediction vs measurement -> qa/VERIFICATION.md
python3 qa/sweep.py             # 411 configurations: every modulation x every impairment
.qavenv/bin/python qa/shoot.py OUTDIR   # drives the real page, captures every view
```

The physics suite checks things like: AWGN EVM equals 1/√(SNR·sps) after matched filtering;
quantisation SQNR equals 6.02·bits + 1.76 − headroom; a two-ray channel's frequency-response nulls
are spaced 1/τ; Rayleigh envelope mean/RMS is √π/2; the FSK instantaneous frequency sits on
a·h·Rs/2; the OFDM autocorrelation peaks at lag = N_FFT.

Bugs this process caught, all of which produced plausible-looking wrong output:

- `np.fft.fft(x, n)` with `n < len(x)` silently **truncates** the input, so a windowed spectrum
  showed only the Hann window's rising edge.
- `putImageData` ignores the canvas DPR transform, so the spectrogram covered 2/3 of its panel on
  any HiDPI display.
- Unwrapping the raw phase of a PSK signal random-walks tens of radians on a perfectly clean
  frame, because the modulation's own 180° jumps are exactly what unwrapping cannot resolve.
- The blind image-rejection estimate was 6 dB out from dropping the factor of 2 in
  ρ = 2|a||b|/(|a|²+|b|²).
- Symbol-lag alignment by plain correlation fails once the carrier rotates, making every downstream
  number catastrophic for a reason unrelated to the impairment being studied.
- Measuring cluster spread against the global ideal grid counted a DC offset — which displaces
  every cluster identically and smears nothing — as blurring.

---

## Layout

```
rflab/
  dsp/          pulse shaping, constellations, modulators, impairments, measurement
  tutor/        severity engine, modulation/impairment/view profiles, narration, challenges
  experiment.py runs a configuration end to end and packages it for the UI
  server.py     stdlib HTTP server and JSON API
  web/          index.html, style.css, render.js (canvas core), plots.js, app.js
qa/             physics checks, verification report, sweep, screenshot harness
```
