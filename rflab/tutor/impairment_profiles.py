"""Educational profile for every impairment, plus which views reveal it."""

# Ordered view priority per impairment.  The lab promotes these automatically,
# because looking for I/Q imbalance in a spectrogram or interference in a
# constellation wastes the experiment.
VIEW_PRIORITY = {
    "awgn":          ["constellation", "psd", "eye", "iq_time", "amp_hist"],
    "cfo":           ["constellation", "phase", "inst_freq", "fft", "spectrogram"],
    "phase_offset":  ["constellation", "phase"],
    "phase_noise":   ["constellation", "phase", "psd", "eye"],
    "clock_offset":  ["eye", "constellation", "iq_time", "phase"],
    "multipath":     ["channel", "eye", "psd", "constellation", "fft"],
    "fading":        ["magnitude", "constellation", "phase", "psd"],
    "pa":            ["am_am", "constellation", "psd", "papr_ccdf", "amp_hist"],
    "iq_imbalance":  ["constellation", "fft", "psd", "iq_time"],
    "dc_offset":     ["constellation", "fft", "iq_time"],
    "quantization":  ["iq_time", "constellation", "amp_hist", "psd"],
    "clipping":      ["iq_time", "am_am", "psd", "papr_ccdf", "constellation"],
    "interference":  ["psd", "spectrogram", "fft", "constellation", "iq_time"],
}

P = {}


def _p(key, **kw):
    P[key] = kw


_p("awgn",
   name="AWGN — Additive White Gaussian Noise", stage="receiver thermal noise",
   origin="Thermal agitation of electrons in the receiver's own front end, plus noise picked up "
          "by the antenna. It is present in every receiver ever built and sets the noise floor "
          "below which nothing can be heard.",
   model="y[n] = x[n] + w[n],  w ~ CN(0, sigma^2). White means flat across frequency; Gaussian "
         "means each sample is drawn from a normal distribution independently of the others.",
   on_signal="Adds an independent random complex number to every sample.",
   on_constellation="Each point becomes a circular fuzzy cloud whose radius is set by sigma. "
                    "The geometry stays put; it just blurs.",
   on_spectrum="Raises the noise floor uniformly. The signal's shape is unchanged, it simply "
               "sits on a higher pedestal.",
   over_time="Statistically identical from start to finish. No drift, no accumulation.",
   amc="Sets a hard ceiling on what any classifier can do. The guide insists on reporting "
       "accuracy versus SNR rather than a single averaged number, because a single number "
       "mostly reflects how many low-SNR samples happened to be in the test set.",
   sdr="Unavoidable, but its level is controllable through antenna gain, low-noise amplifier "
       "figure and bandwidth. Narrowing the receive filter to the signal bandwidth is the "
       "cheapest SNR you will ever get.",
   in_synthetic="Always. This is the one impairment simulations model perfectly.",
   hard_to_model="No. The model is exact.",
   guide_points=["The guide calls AWGN the baseline impairment, notes it is the one simulations "
                 "model perfectly, and points out the real trouble is that many synthetic "
                 "datasets model only this while reality piles on everything else."],
   rf_points=["Sample SNR and Es/N0 are not the same number. A matched filter rejects noise "
              "outside the symbol bandwidth, so at 8 samples per symbol it recovers about 9 dB. "
              "The lab shows both, because conflating them is a common way to misjudge a link."],
   correctable="No. Noise cannot be subtracted, only averaged down by using more symbols.",
   classifier_can_learn="Partly -- training across SNR teaches graceful degradation, but no "
                        "amount of training recovers information that noise has destroyed.")

_p("cfo",
   name="CFO — Carrier Frequency Offset", stage="receiver local oscillator",
   origin="The transmitter and receiver each generate their carrier from a separate crystal, "
          "and no two crystals agree exactly. A 2 ppm part at 2.4 GHz is already 4.8 kHz out.",
   model="y[n] = x[n] . exp(j 2 pi df n / fs). A multiplication by a complex exponential, which "
         "in the frequency domain is a rigid translation of the whole spectrum.",
   on_signal="Rotates every sample by a phase that grows linearly with time.",
   on_constellation="The clusters spin. Over a whole frame they smear into arcs, and once the "
                    "accumulated rotation passes a full turn, into complete rings.",
   on_spectrum="Slides the entire spectrum sideways by df. The shape is untouched.",
   over_time="Strictly accumulating. The last symbol of a frame is always worse off than the "
             "first, so longer frames are hurt more.",
   amc="The classic sim-to-real killer. It destroys exactly the phase structure that "
       "distinguishes PSK orders, so a spun QPSK signal is genuinely indistinguishable from "
       "8PSK or 16PSK. QAM keeps its amplitude rings but loses the grid.",
   sdr="Every real radio has it. It is estimated and corrected during synchronisation -- but "
       "blind estimation is circular, since the classic M-th power method needs the "
       "constellation order you were trying to classify.",
   in_synthetic="Sometimes, and the guide notes it is often understated relative to reality.",
   hard_to_model="No -- one line of code. The difficulty is choosing a physically calibrated "
                 "range rather than an arbitrary one.",
   guide_points=["The guide calls CFO 'the single most important impairment to understand', "
                 "gives the USRP B210's roughly 2 ppm stability as typical, and spells out that "
                 "spinning QPSK long enough makes it indistinguishable from any other "
                 "constant-amplitude scheme.",
                 "It also makes the structural point that the classical fix requires the answer "
                 "you are trying to find -- which is why blind AMC pipelines often leave CFO "
                 "uncorrected and handle it with augmentation instead."],
   rf_points=["For OFDM, CFO is a categorically different problem. It is not a rotation you can "
              "undo after the FFT: it destroys subcarrier orthogonality and injects "
              "inter-carrier interference of roughly (pi.epsilon)^2/3 relative to subcarrier "
              "power, where epsilon is the offset in subcarrier spacings."],
   correctable="Yes, completely, if you can estimate it. The lab's residual-after-sync figure "
               "shows exactly how much of the damage a perfect estimator would remove.",
   classifier_can_learn="Yes, through augmentation over a physically plausible range -- but the "
                        "invariance costs capacity, and once the rotation exceeds a full turn "
                        "the class information is genuinely gone, not merely hidden.")

_p("phase_offset",
   name="Phase offset", stage="receiver local oscillator",
   origin="Arbitrary initial oscillator phase plus propagation delay. There is no reason for the "
          "receiver's phase reference to match the transmitter's.",
   model="y[n] = x[n] . exp(j theta), a single fixed rotation.",
   on_signal="Rotates every sample by the same angle.",
   on_constellation="Rigid rotation. Nothing smears, nothing scales.",
   on_spectrum="No effect whatsoever -- the magnitude spectrum is blind to a constant phase.",
   over_time="Static.",
   amc="The mildest phase impairment. It breaks any classifier that learned absolute point "
       "positions, which is a good reason not to learn them.",
   sdr="Universal and normally irrelevant, because receivers either recover phase or use "
       "differential encoding.",
   in_synthetic="Sometimes. Random phase rotation is nearly free as an augmentation and the "
                "guide recommends it.",
   hard_to_model="No.",
   guide_points=["The guide notes that a 90-degree rotation maps QPSK onto itself, 'a nice "
                 "illustration of why absolute phase is often meaningless and why differential "
                 "schemes exist'."],
   rf_points=["Rotational symmetry means the effective offset is theta modulo 360/M degrees. "
              "Set 90 degrees on QPSK and the constellation is literally unchanged; set 45 and "
              "it is maximally displaced. Same knob, opposite consequences."],
   correctable="Yes, trivially, and differential schemes remove the need entirely.",
   classifier_can_learn="Yes, and it should -- random phase augmentation is nearly free.")

_p("phase_noise",
   name="Phase noise", stage="receiver local oscillator",
   origin="Oscillators do not hold a perfectly steady phase. Thermal and flicker noise inside "
          "the oscillator make the phase wander, and the wander gets worse as carrier frequency "
          "rises -- a serious constraint at millimetre wave.",
   model="y[n] = x[n] . exp(j phi[n]). A free-running oscillator gives a random walk whose "
         "variance grows with time (Lorentzian linewidth); a locked one gives bounded jitter "
         "about a stable mean.",
   on_signal="Randomly rotates each sample by a small, correlated amount.",
   on_constellation="Points smear tangentially -- along the arc, not radially. Outer points "
                    "smear further than inner ones, because arc length grows with radius.",
   on_spectrum="Broadens the spectral line: energy leaks from the carrier into skirts around it.",
   over_time="A random walk drifts without bound; stationary jitter does not. They look "
             "different on a phase-versus-time plot, and the lab models them separately.",
   amc="Blurs high-order constellations preferentially. A scheme whose phase tolerance is "
       "smaller than the oscillator's RMS phase noise simply cannot be supported, however much "
       "transmit power is available.",
   sdr="Very real, device-specific, and one of the impairments that gets worse as you move up "
       "in frequency.",
   in_synthetic="Rarely, per the guide's table.",
   hard_to_model="Somewhat. A realistic model needs the oscillator's actual phase-noise "
                 "profile, which is a measured curve rather than a single number.",
   guide_points=["The guide describes phase noise as a time-varying random rotation that blurs "
                 "points tangentially, becoming severe at high carrier frequencies and a real "
                 "concern for millimetre-wave 5G. Its table marks phase noise as rarely "
                 "modelled in synthetic data."],
   rf_points=["The tangential-only signature is what separates phase noise from AWGN visually. "
              "AWGN produces round clouds; phase noise produces arcs that get longer as you "
              "move outward. On a QPSK constellation both look like blur -- on 64-QAM the "
              "difference is obvious."],
   correctable="Partly. A tracking loop follows slow wander but cannot remove fast jitter.",
   classifier_can_learn="Partly, and it is device-specific enough to be a fingerprint risk.")

_p("clock_offset",
   name="Sample clock offset and timing error", stage="receiver sample clock",
   origin="The same crystal problem one level down: the receiver's sampling clock does not "
          "match the transmitter's symbol clock, so its idea of a symbol period slowly drifts.",
   model="The receiver samples at t = n(1 + epsilon)/fs instead of n/fs. Implemented here by "
         "genuine fractional-delay resampling, not by rounding to the nearest sample.",
   on_signal="Sampling instants slide progressively away from the pulse peaks.",
   on_constellation="Points smear radially inward as samples are taken off the pulse peak, and "
                    "the damage grows along the frame rather than being uniform.",
   on_spectrum="Very little -- this is a time-domain effect and the spectrum barely shows it.",
   over_time="Accumulates linearly. The end of a long frame can be badly misaligned while the "
             "start was fine.",
   amc="Blurs symbols together and, past half a symbol of drift, starts decoding the wrong "
       "symbol entirely. It also breaks any model trained at a fixed samples-per-symbol.",
   sdr="Universal. Handled by a timing-recovery loop -- Gardner, Mueller and Muller, early-late "
       "gate -- feeding an interpolator.",
   in_synthetic="Sometimes. RadioML explicitly varies sample clock rate and offset.",
   hard_to_model="No, but doing it properly needs fractional resampling rather than integer "
                 "shifts.",
   guide_points=["The guide notes RadioML models sample-rate and clock offset explicitly, and "
                 "that 'the dataset designers bothered tells you how central these are'.",
                 "It also flags the related sim-to-real trap: a model trained at 8 samples per "
                 "symbol fed 20 samples per symbol collapses even though nothing is wrong with "
                 "the data."],
   rf_points=["This is the impairment where frame length matters most directly. Drift is "
              "ppm x number of symbols, so halving the frame halves the damage -- the opposite "
              "of AWGN, where longer frames help. The two pull against each other, and that "
              "tension is a real design decision."],
   correctable="Yes, by timing recovery -- but you must know the symbol rate first, which is "
               "another blind-estimation problem.",
   classifier_can_learn="Partly. Random resampling augmentation helps.")

_p("multipath",
   name="Multipath propagation", stage="channel",
   origin="The wave reaches the antenna by several routes at once -- direct path plus "
          "reflections off walls, ground, vehicles. Each arrives at its own delay, amplitude "
          "and phase, and the antenna sums them.",
   model="y(t) = sum_i a_i . x(t - tau_i) . exp(j theta_i). A convolution with a complex "
         "impulse response.",
   on_signal="Convolves the signal with the channel, so each sample mixes in energy from "
             "neighbouring symbols.",
   on_constellation="Flat fading gives one complex gain: a scale and a rotation, geometry "
                    "intact. Frequency-selective fading distorts the geometry itself, because "
                    "no single gain can describe it.",
   on_spectrum="Notches. Paths that arrive out of phase cancel at particular frequencies, "
               "spaced by 1 / delay difference.",
   over_time="Static if nothing moves; time-varying with Doppler if anything does.",
   amc="Frequency-selective fading is genuinely destructive -- the guide rates it severe and "
       "says constellation structure is lost.",
   sdr="The defining feature of indoor and urban propagation. Handled by equalisation, or "
       "sidestepped entirely by OFDM's per-subcarrier division.",
   in_synthetic="Rarely, and simplistically, per the guide's table.",
   hard_to_model="Yes. Real multipath is environment-specific, richer than a few taps, and "
                 "time-varying in ways simple models do not capture.",
   guide_points=["The guide distinguishes flat from frequency-selective fading by whether delay "
                 "spread is small or comparable to the symbol duration, and notes that "
                 "frequency-selective fading causes inter-symbol interference which is "
                 "'genuinely destructive to constellation structure'.",
                 "It also observes that OFDM's equalisation is one complex division per "
                 "subcarrier, 'the main reason OFDM dominates modern systems'."],
   rf_points=["The decisive comparison is delay spread against symbol period, not the number of "
              "paths. A ten-path channel with 10 ns spread is flat to a 1 microsecond symbol; a "
              "two-path channel with 2 microseconds of spread is brutally selective. Watch the "
              "ratio, not the taps."],
   correctable="Partly, by equalisation -- zero-forcing amplifies noise at the notches, MMSE "
               "balances the two, blind CMA works only for constant-modulus signals.",
   classifier_can_learn="Partly. The guide cites mixed training including fading channels as an "
                        "effective, low-cost mitigation.")

_p("fading",
   name="Rayleigh / Rician fading with Doppler", stage="channel",
   origin="Many scatterers with comparable strength give Rayleigh statistics; add a dominant "
          "line-of-sight path and it becomes Rician. Motion of the transmitter, receiver or "
          "scatterers turns the static pattern into a time-varying one.",
   model="A complex Gaussian process per tap, shaped to a Jakes Doppler spectrum. Rician adds a "
         "deterministic component whose power ratio to the scatter is the K factor.",
   on_signal="Multiplies by a wandering complex gain.",
   on_constellation="The whole constellation breathes -- scaling and rotating -- over the frame.",
   on_spectrum="Flat fading scales the whole spectrum together; the shape survives.",
   over_time="Changes on the scale of the coherence time, roughly 0.423 / Doppler spread.",
   amc="Makes amplitude features unreliable. A single frame shows one particular fade, so "
       "results must be averaged over many channel draws -- reading a fading result off one "
       "frame is a classic error.",
   sdr="The everyday reality of mobile and indoor links.",
   in_synthetic="Sometimes, usually as a simple Rayleigh or Rician tap model.",
   hard_to_model="Partly. The statistics are standard; matching a specific real environment is not.",
   guide_points=["The guide describes Rayleigh as the pessimistic no-line-of-sight model and "
                 "Rician as LOS plus scatter parameterised by K, and reports that models trained "
                 "on AWGN-only data degrade substantially under both, while mixed training is an "
                 "effective low-cost fix."],
   rf_points=["Compare coherence time against frame duration. Fewer than about 0.2 fades per "
              "frame and the channel is frozen -- you are seeing one draw, not the process. More "
              "than a couple and the envelope visibly wanders inside the frame."],
   correctable="Partly, by tracking and equalisation; deep fades destroy information outright.",
   classifier_can_learn="Yes, with fading included in training, per the guide's cited result.")

_p("pa",
   name="Power amplifier nonlinearity", stage="transmitter",
   origin="Amplifiers are linear only up to a point. Driven harder they compress, and the "
          "compression depends on the instantaneous amplitude -- AM/AM distortion -- often with "
          "an amplitude-dependent phase shift too, AM/PM.",
   model="Rapp for solid-state (smooth compression, negligible AM/PM), Saleh for travelling-wave "
         "tubes (compression plus significant AM/PM). Input back-off sets how far below "
         "saturation the average power sits.",
   on_signal="Squashes the peaks while leaving small samples alone.",
   on_constellation="Outer points pull inward while inner points stay put, warping the "
                    "constellation rather than uniformly scaling it.",
   on_spectrum="Spectral regrowth -- shoulders appear either side of the main lobe, because a "
               "nonlinearity generates intermodulation products.",
   over_time="Instantaneous and memoryless; it acts sample by sample.",
   amc="Hurts high-order QAM disproportionately, since QAM's large amplitude swings are exactly "
       "what gets compressed. Constant-envelope schemes barely notice.",
   sdr="Universal in transmitters, and a major reason for the power-versus-linearity trade. It "
       "is also strongly device-specific, so it doubles as an RF fingerprint.",
   in_synthetic="Rarely, per the guide's table.",
   hard_to_model="Yes. Real amplifiers have memory effects and device-to-device variation that "
                 "memoryless models miss.",
   guide_points=["The guide identifies PA nonlinearity as causing amplitude compression, "
                 "amplitude-dependent phase rotation and spectral regrowth, affecting high-order "
                 "QAM disproportionately -- and names this as one reason APSK exists for "
                 "satellite links."],
   rf_points=["Regulators care about the regrowth, not the constellation: adjacent-channel power "
              "is what gets a transmitter rejected. It is invisible in the constellation and "
              "obvious in the spectrum, which is a good lesson about picking the right view."],
   correctable="Partly, by digital predistortion at the transmitter. Nothing at the receiver "
               "can undo it well.",
   classifier_can_learn="Partly, but it carries device identity, so a classifier may learn the "
                        "radio instead of the waveform.")

_p("iq_imbalance",
   name="I/Q imbalance", stage="receiver analog",
   origin="The I and Q paths are physically separate analog circuits -- separate mixers, "
          "filters, amplifiers. If their gains differ slightly, or their phase difference is not "
          "exactly 90 degrees, the quadrature relationship is broken.",
   model="y = a.x + b.conj(x). The conjugate term is the whole story: it is a mirror image of "
         "the signal about DC.",
   on_signal="Mixes in a scaled copy of the signal's own complex conjugate.",
   on_constellation="Circles become ellipses; square grids become parallelograms. A systematic "
                    "geometric skew, not a blur.",
   on_spectrum="A spurious image: a component at +f grows a twin at -f, suppressed by the image "
               "rejection ratio.",
   over_time="Essentially static -- it is a property of the hardware.",
   amc="A systematic, device-specific distortion. It shifts the constellation geometry a "
       "classifier keys on, and it is stable enough to be learned as a device signature.",
   sdr="Present in every direct-conversion receiver. Calibrated out in good designs, never "
       "perfectly.",
   in_synthetic="Rarely, per the guide's table.",
   hard_to_model="Not the model -- the values. They differ per device and drift with temperature.",
   guide_points=["The guide describes I/Q imbalance as a device-specific, largely static "
                 "distortion that skews the constellation, circles into ellipses and grids into "
                 "parallelograms. It groups this with the hardware impairments that underpin RF "
                 "fingerprinting, and warns a model may learn 'this is device A' rather than "
                 "'this is QPSK'."],
   rf_points=["Single-sideband signals make the cleanest demonstration. AM-SSB should have one "
              "empty sideband; imbalance fills it, and the depth of that image reads the "
              "receiver's image rejection straight off the spectrum."],
   correctable="Yes, by calibration or blind compensation, since the model has only two parameters.",
   classifier_can_learn="Yes, and that is the danger -- it may learn it as device identity.")

_p("dc_offset",
   name="DC offset", stage="receiver analog",
   origin="Direct-conversion receivers leak their own local oscillator into the signal path. "
          "Because the LO is at the same frequency the signal is being mixed down from, the "
          "leakage lands at exactly 0 Hz.",
   model="y[n] = x[n] + c, a constant complex value added to every sample.",
   on_signal="Adds a constant.",
   on_constellation="Translates the whole constellation off the origin. No rotation, no scaling, "
                    "no blur.",
   on_spectrum="A single spike at DC that averaging never removes -- it is signal, not noise.",
   over_time="Static, though it drifts slowly with temperature.",
   amc="Adds a spurious component and shifts every decision region. Easy to remove, and worth "
       "removing before anything else.",
   sdr="Standard in direct-conversion front ends. The guide notes O'Shea's over-the-air work "
       "deliberately tuned about 1 MHz off-channel to move the signal away from it.",
   in_synthetic="Rarely, per the guide's table.",
   hard_to_model="No.",
   guide_points=["The guide lists DC offset as leakage putting a constant at zero frequency, "
                 "shifting the constellation off-centre, and gives 'subtract the mean of the "
                 "complex samples' as a one-line preprocessing step that is 'cheap and almost "
                 "always worth doing'."],
   rf_points=["Mean removal is only free if the signal itself has no DC component. Unipolar "
              "schemes -- OOK, 4-ASK -- genuinely carry information at DC, so blind mean "
              "removal damages them. Try it on OOK and on QPSK and compare."],
   correctable="Yes, one line: x = x - mean(x).",
   classifier_can_learn="Yes, but there is no reason to make it: removal is free.")

_p("quantization",
   name="Quantisation", stage="ADC",
   origin="The analog-to-digital converter has finite resolution -- 8, 12, 14, 16 bits -- so "
          "every sample is rounded to the nearest available code.",
   model="Round to the nearest multiple of the step size, then clip at full scale. Best-case "
         "SNR is 6.02 x bits + 1.76 dB, less whatever headroom the peaks demand.",
   on_signal="Snaps every sample onto a lattice.",
   on_constellation="Points land on a visible grid of allowed values. At low resolution the "
                    "clouds become discrete dots.",
   on_spectrum="Raises the noise floor with quantisation noise, roughly white if the signal is "
               "busy enough to dither itself.",
   over_time="Uniform.",
   amc="Only matters when the step size becomes comparable to the constellation spacing. The "
       "lab reports quantisation steps per d_min, which is the number that decides it.",
   sdr="A real design constraint, tangled up with gain setting: too little gain wastes codes, "
       "too much clips the peaks.",
   in_synthetic="Rarely, per the guide's table.",
   hard_to_model="No, though real converters add differential nonlinearity and jitter.",
   guide_points=["The guide notes finite ADC resolution adds quantisation noise, and that poor "
                 "gain settings either waste dynamic range or clip."],
   rf_points=["Headroom is the hidden variable. A high-PAPR waveform such as OFDM needs several "
              "more dB of headroom than a constant-envelope one, and every dB of headroom is a "
              "dB of SQNR given away. Same converter, different effective resolution."],
   correctable="No. Information below the least significant bit is gone.",
   classifier_can_learn="Partly, by training at the deployment resolution.")

_p("clipping",
   name="Clipping and AGC limiting", stage="ADC front end",
   origin="Signal peaks that exceed the converter's full scale are hard-limited. It happens when "
          "gain is set too high, or when automatic gain control has not yet settled after a "
          "sudden change in level.",
   model="Limit the magnitude at a threshold while preserving the phase.",
   on_signal="Flattens the tops of the largest excursions.",
   on_constellation="Outer points collapse onto a circle of constant radius.",
   on_spectrum="Strong regrowth. A sharp corner in time is broadband in frequency, so energy "
               "splashes well outside the signal's own bandwidth.",
   over_time="Occurs only on the peaks, so it is bursty rather than uniform.",
   amc="Destroys the amplitude information that QAM and APSK depend on, and the regrowth can "
       "make a signal look wider than it is.",
   sdr="Common, and one of the most under-appreciated causes of a bad capture.",
   in_synthetic="Rarely.",
   hard_to_model="No, but AGC dynamics -- attack and decay behaviour -- are.",
   guide_points=["The guide lists AGC artefacts and clipping among the hardware impairments "
                 "simulations usually skip, and notes AGC transients introduce amplitude "
                 "dynamics unrelated to the modulation."],
   rf_points=["Look at the PAPR CCDF before and after. Clipping does not just cut the peak, it "
              "changes the entire tail of the amplitude distribution -- and for OFDM that tail "
              "is where all the rare, large peaks live."],
   correctable="No, the clipped information is gone. Prevention is by gain management.",
   classifier_can_learn="Partly.")

_p("interference",
   name="Co-channel and adjacent-channel interference", stage="over the air",
   origin="Other transmitters. Simulations usually assume one signal alone in an empty band; "
          "real spectrum is never empty.",
   model="Add another signal -- a continuous-wave tone, a chirp, or a modulated carrier -- at a "
         "chosen frequency offset and signal-to-interference ratio.",
   on_signal="Superimposes a second, unrelated waveform.",
   on_constellation="A tone adds a rotating vector, smearing points into rings or arcs. A "
                    "modulated interferer just adds structured noise.",
   on_spectrum="Obvious. A line or a second lobe appears exactly where the interferer sits.",
   over_time="Depends on the interferer; a chirp sweeps, a transmission bursts.",
   amc="Can dominate the input entirely. The guide argues the realistic task is detect, isolate, "
       "then classify -- not classify a clean isolated signal.",
   sdr="Everyday reality. Real bands contain other users, leakage from neighbours, and impulsive "
       "noise from motors and switching supplies.",
   in_synthetic="Almost never, per the guide's table.",
   hard_to_model="Yes. Realistic occupancy is a property of a place and a time, not a parameter.",
   guide_points=["The guide's impairment table marks interference as 'almost never' modelled in "
                 "synthetic data, and argues the genuinely realistic version of the task is "
                 "'detect that a signal is present, isolate it, then classify it'."],
   rf_points=["Whether an interferer matters depends on where your receive filter sits. An "
              "adjacent-channel interferer that looks alarming in a wideband capture may be "
              "entirely removed by channel selection. Move the offset in and out of band and "
              "watch the constellation stop caring."],
   correctable="In-band: no. Out-of-band: yes, by filtering.",
   classifier_can_learn="Poorly, because interference is unbounded in variety.")


def profile(key):
    return P.get(key)
