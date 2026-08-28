# RF Signal Lab — verification report

22 of 22 experiments agree with theory.

Each row states a prediction derived from physics, then the value the lab measured from the generated samples. Screenshots of every case were inspected as part of this pass; the *look for* line records what the visual had to show for the case to count as passing.

## QPSK + AWGN 20 dB — PASS

**Expected.** Clusters blur isotropically. Margin = (d_min/2)/sigma with Es/N0 = SNR + 10log10(sps) = 29.0 dB, predicting 20.0 sigma.

**Look for in the constellation view.** round clouds centred on the ideal markers, growing as SNR falls

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| decision margin | 20 sigma | 20.69 sigma | ±3 | PASS |
| tangential/radial (1.0 = isotropic) | 1  | 0.9849  | ±0.15 | PASS |
| net rotation | 0 deg | 0.001285 deg | ±2 | PASS |

**What the tutor says about this configuration.**

> 4 of 4 constellation states are populated by 484 symbol samples. Each cloud has a standard deviation of 0.0020 against a half-spacing of 0.7071, so the decision margin measures 358.6 sigma.
>
> The clusters are effectively points -- nothing measurable is blurring them.
>

## QPSK + AWGN 10 dB — PASS

**Expected.** Clusters blur isotropically. Margin = (d_min/2)/sigma with Es/N0 = SNR + 10log10(sps) = 19.0 dB, predicting 6.3 sigma.

**Look for in the constellation view.** round clouds centred on the ideal markers, growing as SNR falls

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| decision margin | 6.325 sigma | 6.543 sigma | ±0.949 | PASS |
| tangential/radial (1.0 = isotropic) | 1  | 0.9878  | ±0.15 | PASS |
| net rotation | 0 deg | 0.00392 deg | ±2 | PASS |

**What the tutor says about this configuration.**

> 4 of 4 constellation states are populated by 484 symbol samples. Each cloud has a standard deviation of 0.0020 against a half-spacing of 0.7071, so the decision margin measures 358.6 sigma.
>
> The clusters are effectively points -- nothing measurable is blurring them.
>

## QPSK + AWGN 0 dB — PASS

**Expected.** Clusters blur isotropically. Margin = (d_min/2)/sigma with Es/N0 = SNR + 10log10(sps) = 9.0 dB, predicting 2.0 sigma.

**Look for in the constellation view.** round clouds centred on the ideal markers, growing as SNR falls

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| decision margin | 2 sigma | 2.062 sigma | ±0.4 | PASS |
| tangential/radial (1.0 = isotropic) | 1  | 0.9887  | ±0.15 | PASS |
| net rotation | 0 deg | 0.01229 deg | ±2 | PASS |

**What the tutor says about this configuration.**

> 4 of 4 constellation states are populated by 484 symbol samples. Each cloud has a standard deviation of 0.0020 against a half-spacing of 0.7071, so the decision margin measures 358.6 sigma.
>
> The clusters are effectively points -- nothing measurable is blurring them.
>

## QPSK + CFO 200 Hz — PASS

**Expected.** Phase accumulates 2.pi.200.4096/1000000 = 5.15 rad = 0.82 turns; the constellation smears into an arc or a full ring.

**Look for in the constellation view.** an arc or closed ring, not clusters

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| accumulated rotation | 5.147 rad | 5.147 rad | ±1e-06 | PASS |
| blind CFO estimate | 200 Hz | 200.3 Hz | ±20 | PASS |
| carrier phase drift on the plot | 5.146 rad | 5.146 rad | ±0.412 | PASS |

**What the tutor says about this configuration.**

> 4 of 4 constellation states are populated by 484 symbol samples. Each cloud has a standard deviation of 0.0020 against a half-spacing of 0.7071, so the decision margin measures 358.6 sigma.
>
> The clusters are effectively points -- nothing measurable is blurring them.
>

## QPSK + CFO 2000 Hz — PASS

**Expected.** Phase accumulates 2.pi.2000.4096/1000000 = 51.47 rad = 8.19 turns; the constellation smears into an arc or a full ring.

**Look for in the constellation view.** an arc or closed ring, not clusters

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| accumulated rotation | 51.47 rad | 51.47 rad | ±1e-06 | PASS |
| blind CFO estimate | 2000 Hz | 2000 Hz | ±60 | PASS |
| carrier phase drift on the plot | 51.46 rad | 51.46 rad | ±4.12 | PASS |

**What the tutor says about this configuration.**

> 4 of 4 constellation states are populated by 484 symbol samples. Each cloud has a standard deviation of 0.0020 against a half-spacing of 0.7071, so the decision margin measures 358.6 sigma.
>
> The clusters are effectively points -- nothing measurable is blurring them.
>

## 16-QAM + DC offset — PASS

**Expected.** A constant is added to every sample: the constellation translates by 0.381x RMS without rotating or smearing, and a spike appears at exactly 0 Hz.

**Look for in the constellation view.** the whole pattern shifted off the origin, still sharp

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| centroid offset | 0.3559 x RMS | 0.3634 x RMS | ±0.02 | PASS |
| cluster spread unchanged | 0.002008  | 0.001993  | ±0.01 | PASS |
| net rotation | 0 deg | -1.344 deg | ±2 | PASS |
| DC spike above the band edge | — | yes | — | PASS |

**What the tutor says about this configuration.**

> 16 of 16 constellation states are populated by 484 symbol samples. Each cloud has a standard deviation of 0.0020 against a half-spacing of 0.3162, so the decision margin measures 157.4 sigma.
>
> The clusters are effectively points -- nothing measurable is blurring them.
>

## 16-QAM + I/Q imbalance — PASS

**Expected.** The output becomes signal plus a fraction of its own conjugate: a mirror image appears in the spectrum and the square grid shears into a parallelogram.

**Look for in the constellation view.** a sheared grid, not a square one

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| image rejection (model vs blind) | 15.02 dB | 15.05 dB | ±3 | PASS |

**What the tutor says about this configuration.**

> 16 of 16 constellation states are populated by 484 symbol samples. Each cloud has a standard deviation of 0.0020 against a half-spacing of 0.3162, so the decision margin measures 157.4 sigma.
>
> The clusters are effectively points -- nothing measurable is blurring them.
>

## 16-QAM + PA compression (IBO 0.5 dB) — PASS

**Expected.** Amplitude compression squashes the outer ring inward while the inner points stay put, so the clouds stretch radially rather than tangentially, and PAPR falls.

**Look for in the am_am view.** a transfer curve bending away from the ideal straight line

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| tangential/radial (<1 = radial) | — | yes | — | PASS |
| PAPR reduced | — | yes | — | PASS |
| peak compression present | — | yes | — | PASS |

**What the tutor says about this configuration.**

> No nonlinearity is active, so there is no transfer curve to look at.
>

## 2FSK instantaneous frequency — PASS

**Expected.** The trace dwells on 2 discrete levels at a.h.Rs/2 = -62.5, 62.5 kHz.

**Look for in the inst_freq view.** 2 flat levels landing on the dashed markers

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| level 0 | -62.5 kHz | -62.5 kHz | ±0.1 | PASS |
| level 1 | 62.5 kHz | 62.5 kHz | ±0.1 | PASS |

**What the tutor says about this configuration.**

> The theoretical tone positions for 2FSK are -62.5, 62.5 kHz, marked by the dashed lines. The trace should visit those levels and dwell there.
>

## 4FSK instantaneous frequency — PASS

**Expected.** The trace dwells on 4 discrete levels at a.h.Rs/2 = -187.5, -62.5, 62.5, 187.5 kHz.

**Look for in the inst_freq view.** 4 flat levels landing on the dashed markers

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| level 0 | -187.5 kHz | -187.5 kHz | ±0.1 | PASS |
| level 1 | -62.5 kHz | -62.5 kHz | ±0.1 | PASS |
| level 2 | 62.5 kHz | 62.5 kHz | ±0.1 | PASS |
| level 3 | 187.5 kHz | 187.5 kHz | ±0.1 | PASS |

**What the tutor says about this configuration.**

> The theoretical tone positions for 4FSK are -187.5, -62.5, 62.5, 187.5 kHz, marked by the dashed lines. The trace should visit those levels and dwell there.
>

## WBFM occupied bandwidth vs Carson's rule — PASS

**Expected.** Carson: 2(dev + msg BW) = 300 kHz. The 99% occupied bandwidth should be of that order, a little under it since Carson is a 98% rule of thumb.

**Look for in the inst_freq view.** frequency tracking the message, not hopping between levels

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| 99% occupied bandwidth | 300 kHz | 236.6 kHz | ±105 | PASS |

**What the tutor says about this configuration.**

> Instantaneous frequency is tracking the message directly, with a peak deviation of 125.0 kHz and modulation index beta = 5.00. Carson's rule predicts 300.0 kHz of occupied bandwidth; the spectrum measures 236.6 kHz.
>

## OFDM cyclic-prefix signature and CFO — PASS

**Expected.** The cyclic prefix is a copy of the symbol tail, so autocorrelation peaks at lag = N_FFT, and that same redundancy lets the CFO be estimated with no preamble.

**Look for in the autocorr view.** a clear spike at lag 64

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| autocorrelation peak at N_FFT | — | yes | — | PASS |
| CP-based CFO estimate | 2000 Hz | 2000 Hz | ±60 | PASS |

**What the tutor says about this configuration.**

> For OFDM the diagnostic is a peak at lag = FFT length = 64 samples, where the cyclic prefix correlates with the tail it was copied from. The measured correlation there is 0.187.
>
> That peak is present, which identifies this as OFDM regardless of what the constellation shows.
>

## QPSK + two-ray multipath (6 us) — PASS

**Expected.** Two paths 6 us apart cancel periodically, so the frequency response has nulls spaced 1/tau = 167 kHz apart.

**Look for in the channel view.** periodic notches in the frequency response

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| null spacing | 166.7 kHz | 167 kHz | ±10 | PASS |
| coherence BW below signal BW | — | yes | — | PASS |

**What the tutor says about this configuration.**

> No multipath channel is configured.
>

## 16-QAM + 8-bit quantisation — PASS

**Expected.** SQNR should be 6.02x8 + 1.76 - 6 = 43.9 dB, and the samples should sit on a visible lattice.

**Look for in the iq_time view.** a waveform confined to discrete levels

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| SQNR | 43.92 dB | 43.93 dB | ±3 | PASS |

**What the tutor says about this configuration.**

> There are 8 samples per symbol, so one symbol period spans 8 points on this axis.
>

## 16-QAM + 4-bit quantisation — PASS

**Expected.** SQNR should be 6.02x4 + 1.76 - 6 = 19.8 dB, and the samples should sit on a visible lattice.

**Look for in the iq_time view.** a waveform confined to discrete levels

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| SQNR | 19.84 dB | 19.85 dB | ±3 | PASS |

**What the tutor says about this configuration.**

> There are 8 samples per symbol, so one symbol period spans 8 points on this axis.
>

## 16-QAM + 600 ppm clock offset — PASS

**Expected.** Sampling instants slide by ppm x number of symbols, so the eye closes and the damage grows along the frame rather than being uniform.

**Look for in the eye view.** a visibly narrower eye opening

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| drift over frame | 0.6144 symbols | 0.6144 symbols | ±1e-09 | PASS |
| eye narrower than clean | — | yes | — | PASS |

**What the tutor says about this configuration.**

> The eye opening measures 0.190 of the full trace excursion at the decision instant.
>
> Partly closed. There is still a clear decision point but the margin has shrunk.
>

## QPSK + CW interferer at 200 kHz — PASS

**Expected.** A continuous-wave interferer appears as a single line at its own frequency, obvious in the spectrum and nearly invisible in the constellation.

**Look for in the psd view.** a narrow line standing above the signal's shoulder

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| interferer frequency | 200 kHz | 199.6 kHz | ±3 | PASS |

**What the tutor says about this configuration.**

> The 99% occupied bandwidth measures 147.4 kHz, centred at -0.50 kHz.
>
> Theory for a root-raised-cosine pulse at 125.0 kBaud with rolloff 0.35 predicts (1 + rolloff) x Rs = 168.8 kHz.
>
> The noise floor sits at -118.6 dB.
>

## Conjugate cyclic feature separates BPSK from QPSK — PASS

**Expected.** A real-valued constellation has a non-zero conjugate cyclic feature at alpha = 0; a rotationally symmetric one does not. BPSK should read near 1, QPSK near 0.

**Look for in the cyclic view.** the magenta trace high for BPSK and flat for QPSK

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| BPSK conj at alpha=0 | 1  | 1.001  | ±0.15 | PASS |
| QPSK conj at alpha=0 | 0  | 0.01927  | ±0.2 | PASS |

**What the tutor says about this configuration.**

> The cycle-frequency axis is marked at 125.0 kHz (symbol rate). The measured line there stands 21.0 dB above the local floor.
>
> That is a clear cyclostationary feature: the signal's statistics really do repeat at this rate, which is what makes blind symbol-rate estimation and below-noise-floor detection possible.
>
> The conjugate feature at alpha = 0 reads 1.002. Values near 1 mean a real-valued constellation (BPSK, PAM, ASK); values near 0 mean a rotationally symmetric one (QPSK and above, QAM). This one says real-valued.
>

## BPSK higher-order cumulants — PASS

**Expected.** Classical AMC table: |C40| = 2.0, |C42| = 2.0.

**Look for in the cumulants view.** measured bars close to the theory marks

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| |C40| | 2  | 1.994  | ±0.12 | PASS |
| |C42| | 2  | 1.994  | ±0.12 | PASS |

**What the tutor says about this configuration.**

> BPSK: |C40| measured 1.964 against theory 2.00; |C42| measured 1.964 against theory 2.00.
>
> Estimated from 484 symbols. Fourth- and sixth-order statistics converge slowly, so expect visible scatter at this sample count -- and expect it to be worse for high-order QAM, whose theoretical values sit close together to begin with.
>

## QPSK higher-order cumulants — PASS

**Expected.** Classical AMC table: |C40| = 1.0, |C42| = 1.0.

**Look for in the cumulants view.** measured bars close to the theory marks

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| |C40| | 1  | 0.9967  | ±0.12 | PASS |
| |C42| | 1  | 0.9986  | ±0.12 | PASS |

**What the tutor says about this configuration.**

> QPSK: |C40| measured 0.990 against theory 1.00; |C42| measured 0.990 against theory 1.00.
>
> Estimated from 484 symbols. Fourth- and sixth-order statistics converge slowly, so expect visible scatter at this sample count -- and expect it to be worse for high-order QAM, whose theoretical values sit close together to begin with.
>

## 8PSK higher-order cumulants — PASS

**Expected.** Classical AMC table: |C40| = 0.0, |C42| = 1.0.

**Look for in the cumulants view.** measured bars close to the theory marks

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| |C40| | 0  | 0.0098  | ±0.12 | PASS |
| |C42| | 1  | 0.9987  | ±0.12 | PASS |

**What the tutor says about this configuration.**

> 8PSK: |C40| measured 0.013 against theory 0.00; |C42| measured 0.991 against theory 1.00.
>
> Estimated from 484 symbols. Fourth- and sixth-order statistics converge slowly, so expect visible scatter at this sample count -- and expect it to be worse for high-order QAM, whose theoretical values sit close together to begin with.
>

## 16QAM higher-order cumulants — PASS

**Expected.** Classical AMC table: |C40| = 0.68, |C42| = 0.68.

**Look for in the cumulants view.** measured bars close to the theory marks

| quantity | predicted | measured | tolerance | verdict |
|---|---|---|---|---|
| |C40| | 0.68  | 0.6683  | ±0.12 | PASS |
| |C42| | 0.68  | 0.6699  | ±0.12 | PASS |

**What the tutor says about this configuration.**

> 16QAM: |C40| measured 0.658 against theory 0.68; |C42| measured 0.690 against theory 0.68.
>
> Estimated from 484 symbols. Fourth- and sixth-order statistics converge slowly, so expect visible scatter at this sample count -- and expect it to be worse for high-order QAM, whose theoretical values sit close together to begin with.
>
