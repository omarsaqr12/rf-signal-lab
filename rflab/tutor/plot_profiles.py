"""What each view is for, what its axes mean, and what a clean signal looks like."""

V = {}


def _v(key, **kw):
    V[key] = kw


_v("constellation",
   title="I/Q Constellation",
   question="What geometric structure does this modulation create in the complex plane?",
   what=("Every received sample is a complex number. Plot its real part horizontally and its "
         "imaginary part vertically and time disappears -- what is left is the shape the "
         "modulation draws. For digital schemes sampled once per symbol at the right instant, "
         "that shape is a small set of clusters, and the pattern of clusters is close to a "
         "fingerprint of the scheme."),
   axes="Horizontal: in-phase component I. Vertical: quadrature component Q. Both in "
        "unit-average-power units, so the numbers are comparable across modulations.",
   marks=("Filled points are received samples. Hollow rings are the ideal constellation "
          "positions. Point colour runs from the start of the frame to its end, which turns a "
          "static scatter into a record of what happened over time -- rotation, drift and "
          "fading all become visible the moment you colour by time."),
   clean="Tight, round, well-separated clusters sitting exactly on the ideal markers.",
   teaches=["cluster geometry and how it maps to bits", "rotation versus spreading versus skew "
            "versus translation -- four different impairments with four different signatures",
            "why absolute position is not a reliable feature"],
   caution=("Almost useless for FSK, FM and OFDM. A constant-envelope signal draws a circle "
            "whatever it is doing, and the OFDM composite is a Gaussian blob by construction. "
            "Reaching for a constellation on those is the most common way to look at the right "
            "data through the wrong window."))

_v("iq_time",
   title="I and Q versus time",
   question="How does the complex signal actually evolve, sample by sample?",
   what=("The two real waveforms a receiver hands you. This is literally what goes into a 1D "
         "CNN or a sequence model, so it is worth knowing what it looks like."),
   axes="Horizontal: time in milliseconds. Vertical: amplitude, unit-average-power units.",
   marks="Solid traces are the impaired signal; faint traces behind them are the clean "
         "reference. Vertical ticks mark symbol boundaries.",
   clean="Smooth pulse-shaped transitions between symbol values, with the two rails moving "
         "independently.",
   teaches=["pulse shaping and samples per symbol", "how bursts, transients and clipping look",
            "why the I/Q pair is the raw material for everything else"],
   caution="Hard to read modulation type from directly -- that is exactly why the constellation "
           "and spectrum exist.")

_v("magnitude",
   title="Magnitude versus time",
   question="How does the signal's amplitude behave?",
   what=("The envelope, sqrt(I^2 + Q^2). It answers one question immediately: does this "
         "modulation use amplitude to carry information, or not?"),
   axes="Horizontal: time in milliseconds. Vertical: |x|.",
   marks="Solid line is the impaired envelope, faint line the clean one, and where a fading "
         "channel is active a third trace shows the channel gain on its own.",
   clean="Flat for PSK, FSK, MSK and FM. Structured and varying for QAM, PAM, APSK and AM. "
         "Spiky for OFDM.",
   teaches=["constant-envelope versus amplitude-varying families", "fading, AGC and clipping",
            "PAPR, and why it constrains amplifier design"],
   caution="A flat envelope does not mean a clean signal -- it means the modulation is "
           "constant-envelope. Check what the modulation is before reading anything into it.")

_v("phase",
   title="Phase versus time",
   question="How does the signal's phase evolve, and is it drifting?",
   what=("Unwrapped phase removes the 2 pi jumps so that steady drift shows up as a straight "
         "line. A tilt in this plot is a frequency offset, full stop -- the slope is 2 pi times "
         "the offset."),
   axes="Horizontal: time in milliseconds. Vertical: unwrapped phase in radians.",
   marks="Solid: impaired. Faint: clean reference. A fitted straight line, where present, is "
         "the linear trend a synchroniser would remove.",
   clean="For PSK, a trace that hops between discrete levels but does not trend. For FSK, a "
         "piecewise-linear ramp. For a clean signal there is no overall tilt.",
   teaches=["CFO as a linear phase ramp", "phase noise as wander about the trend",
            "phase continuity, and why continuous-phase schemes are spectrally narrow"],
   caution="Unwrapping fails at very low SNR: once phase steps exceed pi between samples the "
           "unwrap is guessing, and the plot can show drift that is not really there.")

_v("inst_freq",
   title="Instantaneous frequency",
   question="How does the signal's frequency change with time?",
   what=("The derivative of phase, computed as the angle of x[n] . conj(x[n-1]) so that "
         "unwrapping cannot go wrong. This is the natural home of the FSK and FM families: "
         "where a constellation shows them nothing, this shows them everything."),
   axes="Horizontal: time in milliseconds. Vertical: frequency in kHz relative to the carrier.",
   marks="Solid: impaired. Faint: clean. Dashed horizontal lines mark the theoretical tone "
         "positions for FSK.",
   clean="For FSK, a trace that visits discrete levels. For FM, a trace that follows the "
         "message. For PSK/QAM, spikes at symbol transitions and near-zero between them.",
   teaches=["FSK tone structure and modulation index", "FM deviation and Carson bandwidth",
            "CFO as a constant vertical offset, Doppler as slow drift"],
   caution="Noisy by nature -- it is a derivative, which amplifies high-frequency noise. The "
           "lab smooths it over half a symbol; heavier smoothing hides real transitions.")

_v("fft",
   title="FFT magnitude spectrum",
   question="What frequencies are present in this frame?",
   what=("A single windowed transform of the whole frame. High frequency resolution, but noisy "
         "-- each bin is one realisation, not an average."),
   axes="Horizontal: frequency in kHz relative to the tuned centre. Vertical: magnitude in dB.",
   marks="Solid: impaired. Faint: clean. Markers show DC, the occupied bandwidth edges, and any "
         "interference peak found.",
   clean="A flat-topped main lobe with roll-off set by the pulse shaping, centred on zero.",
   teaches=["bandwidth and where it comes from", "frequency offset as a rigid translation",
            "DC spikes, spectral regrowth, interference lines"],
   caution="A raw FFT is not a PSD. Its variance does not fall as you take more samples, it just "
           "gets more bins -- which is exactly what the PSD view fixes.")

_v("psd",
   title="Power spectral density (Welch)",
   question="How is power distributed over frequency, on average?",
   what=("Welch's method: cut the frame into overlapping segments, transform each, and average "
         "the magnitudes. Averaging is the whole point. A single FFT has about 100% standard "
         "deviation per bin no matter how long the frame is -- lengthening the frame buys "
         "resolution, not stability. Averaging K segments cuts the variance by K, which is what "
         "makes a noise floor readable as a level rather than a fuzz."),
   axes="Horizontal: frequency in kHz. Vertical: power spectral density in dB per Hz.",
   marks="Solid: impaired. Faint: clean. Shaded band marks the 99% occupied bandwidth; a "
         "horizontal line marks the estimated noise floor.",
   clean="A smooth flat-topped lobe over a flat noise floor.",
   teaches=["the difference between a spectrum estimate and a single transform",
            "occupied bandwidth, noise floor and their ratio", "spectral regrowth and adjacent-"
            "channel leakage"],
   caution="Segment length trades resolution against variance. Short segments give a smooth but "
           "blurry estimate; long ones a sharp but noisy one.")

_v("spectrogram",
   title="Spectrogram (STFT)",
   question="How does the frequency content evolve over time?",
   what=("A sequence of short transforms laid side by side, so frequency runs one way and time "
         "the other. Turning a signal into an image is also why spectrograms feed vision-style "
         "architectures."),
   axes="Horizontal: time in ms. Vertical: frequency in kHz. Colour: power in dB.",
   marks="Brighter is stronger. The colour range is clipped to the top 55 dB so the structure "
         "does not disappear into the floor.",
   clean="A steady horizontal band for a stationary signal; visible frequency hopping for FSK.",
   teaches=["FSK transitions and frequency hopping", "bursts, chirps and Doppler drift",
            "interference that occupies only part of the time or band"],
   caution="Time and frequency resolution trade against each other and cannot both be sharp. A "
           "short window resolves fast hops but smears frequency; a long one does the reverse.")

_v("eye",
   title="Eye diagram",
   question="What happens when the waveform is folded on the symbol period?",
   what=("Slice the matched-filtered waveform into two-symbol segments and overlay them all. If "
         "timing is good and there is no intersymbol interference, every trace passes through "
         "the same few points at the symbol instant and an open 'eye' appears."),
   axes="Horizontal: time in symbol periods, with 0 at the ideal sampling instant. Vertical: "
        "amplitude of the I rail.",
   marks="Each faint line is one segment. The shaded box marks the eye opening; the vertical "
         "line marks the decision instant.",
   clean="Wide open eye with sharply defined crossing points.",
   teaches=["timing recovery and why the sampling instant matters",
            "ISI as a closing eye", "noise as a thickening of the traces",
            "how pulse shaping controls the crossings"],
   caution="Only meaningful for linearly modulated signals with a matched filter applied. Not "
           "defined for FSK, FM or OFDM.")

_v("autocorr",
   title="Autocorrelation",
   question="Does the signal repeat itself at any particular lag?",
   what=("Correlation of the signal with a delayed copy of itself. Repeating structure shows as "
         "a peak at the lag of the repeat."),
   axes="Horizontal: lag in samples. Vertical: normalised correlation magnitude.",
   marks="Solid: impaired. Faint: clean. A marker sits at the lag where a peak is expected -- "
         "for OFDM, the FFT length.",
   clean="A single peak at zero lag, decaying to the pulse-shaping correlation width.",
   teaches=["symbol periodicity", "the OFDM cyclic-prefix signature",
            "why correlation underpins detection and synchronisation"],
   caution="A peak means periodicity, not necessarily the periodicity you were looking for. "
           "Interference has structure too.")

_v("cumulants",
   title="Higher-order cumulants",
   question="What statistical structure separates modulation families without needing "
            "synchronisation?",
   what=("Normalised fourth- and sixth-order cumulants. These take characteristically different "
         "values for different constellations and -- crucially -- do not require phase or timing "
         "recovery. They were the backbone of feature-based AMC before deep learning."),
   axes="Bars: measured cumulant magnitude, against the theoretical value for this modulation "
        "and for the alternatives.",
   marks="Solid bar: measured. Outlined bar: theory for the configured modulation. Faint marks: "
         "theory for other modulations, so you can see which ones this measurement could be "
         "confused with.",
   clean="Measured values close to theory, with scatter that shrinks as the number of symbols "
         "grows.",
   teaches=["|C40| = 1 for QPSK and 0 for 8PSK, which separates them with no phase reference",
            "why classical AMC leaned on these", "estimator variance: cumulants are "
            "high-order moments and need many symbols to settle"],
   caution="Fourth- and sixth-order statistics converge slowly. A few hundred symbols gives a "
           "noisy estimate, and high-order QAM values sit close together to begin with.")

_v("cyclic",
   title="Cyclostationarity",
   question="Does the signal have statistical periodicity tied to its own structure?",
   what=("A modulated signal's statistics repeat at the symbol rate even when the signal itself "
         "looks random. Measuring |R^alpha(tau)| across cycle frequencies alpha reveals lines at "
         "multiples of the symbol rate that noise does not produce -- which is why cyclic "
         "detection can find signals that energy detection misses entirely."),
   axes="Horizontal: cycle frequency alpha in kHz. Vertical: normalised cyclic correlation.",
   marks="Solid: the ordinary cyclic profile, with a marker at the symbol rate. The second "
         "trace is the conjugate profile, which is non-zero only for real-valued "
         "constellations (BPSK, PAM, ASK) and near zero for QPSK and above.",
   clean="A sharp line at the symbol rate standing well above a low floor.",
   teaches=["blind symbol-rate estimation", "signal detection below the noise floor",
            "the conjugate feature as a BPSK-versus-QPSK discriminator"],
   caution="Cyclic lines are extremely narrow -- roughly 1/observation time. A coarse alpha grid "
           "steps straight over them and reports nothing, which looks identical to a genuine "
           "absence.")

_v("amp_hist",
   title="Amplitude histogram",
   question="How is the signal's amplitude distributed?",
   what="The distribution of |x| over the frame. Different families have visibly different "
        "shapes.",
   axes="Horizontal: |x|. Vertical: count.",
   marks="Filled: impaired. Outline: clean.",
   clean="A single narrow spike for constant-envelope schemes; discrete peaks for PAM and "
         "APSK; a Rayleigh-like curve for OFDM.",
   teaches=["constant-envelope versus amplitude-varying at a glance",
            "quantisation as a comb of allowed values", "clipping as a hard wall at the limit",
            "Rayleigh fading statistics"],
   caution="Throws away all time information.")

_v("papr_ccdf",
   title="PAPR complementary CDF",
   question="How often does the signal exceed a given peak-to-average ratio?",
   what=("The probability that instantaneous power exceeds a threshold. This is the curve "
         "amplifier and converter headroom is actually designed against -- not the single "
         "worst-case peak, which is a lottery, but the tail."),
   axes="Horizontal: threshold in dB above average power. Vertical: probability of exceeding it, "
        "log scale.",
   marks="Solid: impaired. Faint: clean.",
   clean="A steep drop for constant-envelope schemes; a long tail for OFDM.",
   teaches=["why OFDM needs so much amplifier back-off", "how clipping and compression truncate "
            "the tail", "the link between PAPR and power efficiency"],
   caution="The far tail is estimated from a handful of samples and is correspondingly noisy.")

_v("am_am",
   title="AM/AM and AM/PM transfer",
   question="What does the nonlinearity actually do, as a function of input amplitude?",
   what=("Output amplitude plotted against input amplitude, sample by sample. A perfectly linear "
         "device would give a straight line; compression bends it over. The companion AM/PM "
         "trace shows phase shift as a function of amplitude."),
   axes="Horizontal: input |x|. Vertical: output |y|, and separately phase shift in degrees.",
   marks="Points are samples. The dashed line is the ideal linear response.",
   clean="A straight line through the origin.",
   teaches=["compression and saturation", "AM/PM conversion, which rotates large samples",
            "why back-off trades efficiency against linearity"],
   caution="Only shown when a nonlinearity is active; there is nothing to see otherwise.")

_v("channel",
   title="Channel impulse and frequency response",
   question="What is the multipath channel doing to the signal?",
   what=("The tap delays and gains, and the frequency response they produce. Notches appear "
         "where paths cancel, spaced by the reciprocal of the delay difference."),
   axes="Taps: delay in microseconds against gain in dB. Response: frequency in kHz against "
        "gain in dB.",
   marks="Stems are the paths. The curve is the resulting frequency response, with the "
         "coherence bandwidth marked.",
   clean="A single tap and a flat response.",
   teaches=["how delay spread creates frequency selectivity",
            "coherence bandwidth as the width over which the channel is roughly constant",
            "why OFDM divides the band into pieces narrower than this"],
   caution="Shown only when multipath is configured.")

_v("ofdm",
   title="OFDM subcarrier view",
   question="What is actually being carried on each subcarrier?",
   what=("Remove the cyclic prefix, take the FFT of each OFDM symbol, and the per-subcarrier "
         "constellation appears. This is the only place the subcarrier modulation is visible -- "
         "the composite time-domain waveform hides it completely."),
   axes="Constellation: I against Q for all used subcarriers. Profile: subcarrier index against "
        "average power in dB.",
   marks="Points are demodulated subcarrier values; the power profile shows which subcarriers "
         "are occupied and which are guard bands.",
   clean="A clean per-subcarrier constellation and a flat power profile across the used band.",
   teaches=["why 'classify the modulation of a 5G signal' is two different questions",
            "guard bands and the DC null",
            "how CFO turns from a rotation into inter-carrier interference"],
   caution="Requires correct symbol alignment. Uncorrected CFO scrambles this view far more "
           "than it scrambles a single-carrier constellation.")


def profile(key):
    return V.get(key)


def all_views():
    return V
