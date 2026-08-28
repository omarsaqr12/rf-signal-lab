"""Educational profile for every modulation in the lab.

Sourcing convention used throughout the tutor:
  guide  -- the point is made in the RF Modulation Recognition Study Guide
  rf     -- standard RF/DSP knowledge added here to go deeper than the guide

Nothing is attributed to the guide that the guide does not actually say.
"""

# Which views are worth looking at first, per modulation family.  Forcing a
# constellation on an FSK signal is the single most common way to look at the
# right data through the wrong window.
FAMILY_VIEWS = {
    "psk":    ["constellation", "phase", "eye", "psd", "cyclic"],
    "qam":    ["constellation", "eye", "amp_hist", "psd", "cumulants"],
    "pam":    ["constellation", "magnitude", "eye", "psd"],
    "apsk":   ["constellation", "amp_hist", "am_am", "psd"],
    "fsk":    ["inst_freq", "spectrogram", "psd", "phase", "constellation"],
    "analog": ["magnitude", "inst_freq", "psd", "spectrogram"],
    "ofdm":   ["ofdm", "psd", "autocorr", "papr_ccdf", "constellation"],
}

M = {}


def _m(key, **kw):
    M[key] = kw


_m("bpsk",
   name="BPSK — Binary Phase Shift Keying", family="psk", bits=1,
   carries="phase, two states 180 degrees apart",
   what=("The simplest phase modulation: the carrier's phase is either 0 or 180 degrees, "
         "carrying one bit per symbol. Because the two states are as far apart as two points "
         "on a unit circle can possibly be, BPSK survives conditions that destroy everything "
         "else."),
   constellation="Two points on the real axis at +/-1. d_min = 2.0, the largest of any unit-power scheme.",
   amplitude="Constant in principle. After root-raised-cosine shaping the envelope does vary, "
             "because the pulse has to pass through zero when the phase flips by 180 degrees.",
   phase="Two discrete values. The phase trajectory passes straight through the origin on a "
         "state change, which is exactly what OQPSK and pi/4-DQPSK were invented to avoid.",
   frequency="No deliberate frequency content beyond the pulse spectrum.",
   bandwidth="(1 + rolloff) x symbol rate. One bit per symbol makes it the least "
             "spectrally efficient of the PSK family and the most robust.",
   views=["constellation", "phase", "psd", "cyclic", "eye"],
   impairments=["awgn (very tolerant)", "cfo", "multipath"],
   confusions=["Rotated BPSK looks like BPSK at a different angle, which is why absolute phase "
               "is not a usable feature.",
               "Under heavy CFO it smears into a ring like every other PSK."],
   difficulty="Easiest class to identify, and the last one still identifiable as SNR falls.",
   guide_points=["The guide calls BPSK the most robust digital scheme in common use and notes "
                 "it survives terrible SNR."],
   rf_points=["Its conjugate cyclic feature at alpha = 0 is non-zero because the constellation "
              "is real-valued -- a discriminator against QPSK that keeps working at low SNR "
              "where the constellation itself is unreadable."])

_m("qpsk",
   name="QPSK — Quadrature Phase Shift Keying", family="psk", bits=2,
   carries="phase, four states 90 degrees apart",
   what=("Four phase states, two bits per symbol. Twice BPSK's data rate in the same bandwidth "
         "for a modest SNR penalty, which is why it is everywhere."),
   constellation="Four points on a circle at 45, 135, 225, 315 degrees. d_min = sqrt(2).",
   amplitude="Nominally constant; RRC shaping makes the envelope dip between symbols, deeply "
             "so when the phase changes by 180 degrees.",
   phase="Four discrete values, 90 degrees apart. 90-degree rotational symmetry means a "
         "quarter-turn maps the constellation exactly onto itself.",
   frequency="Nothing deliberate.",
   bandwidth="(1 + rolloff) x symbol rate, same as BPSK for twice the bits.",
   views=["constellation", "phase", "eye", "psd", "cyclic"],
   impairments=["cfo (the classic)", "phase noise", "awgn", "clock offset"],
   confusions=["QPSK, OQPSK and pi/4-DQPSK share the same four-point marginal distribution and "
               "differ only in how the trajectory moves between points -- so they can only be "
               "told apart from temporal structure, never from a scatter plot.",
               "Under CFO all PSK orders converge to a ring."],
   difficulty="Easy at moderate SNR; the temporal variants are genuinely hard.",
   guide_points=["The guide singles out QPSK/OQPSK/pi-4-DQPSK as a case where a model must use "
                 "temporal structure rather than the marginal distribution of points, and "
                 "argues this is where sequence models should earn their keep.",
                 "It uses QPSK-under-CFO as the canonical illustration of the sim-to-real gap: "
                 "spin four points long enough and they become indistinguishable from 8PSK."],
   rf_points=["The 90-degree symmetry is why a 4th-power CFO estimator works: raising QPSK to "
              "the 4th power collapses all four phases onto one, leaving a clean tone at 4x "
              "the frequency offset."])

_m("8psk",
   name="8PSK", family="psk", bits=3,
   carries="phase, eight states 45 degrees apart",
   what="Eight phase states, three bits per symbol. The point where PSK starts feeling fragile.",
   constellation="Eight points evenly spaced on the unit circle. d_min = 2 sin(pi/8) = 0.765, "
                 "roughly half of QPSK's.",
   amplitude="Constant envelope in principle.",
   phase="Eight values 45 degrees apart, so the phase tolerance is about 22 degrees.",
   frequency="Nothing deliberate.",
   bandwidth="Same as BPSK and QPSK for 3 bits per symbol.",
   views=["constellation", "phase", "psd", "cumulants"],
   impairments=["phase noise", "cfo", "awgn"],
   confusions=["16PSK, and any constant-modulus scheme once phase is scrambled.",
               "A CFO-smeared QPSK signal is a classic false 8PSK."],
   difficulty="Moderate. Needs both decent SNR and phase coherence.",
   guide_points=["The guide notes 8PSK's points are 45 degrees apart and 'noticeably more "
                 "fragile', and that beyond 8PSK, QAM outperforms PSK."],
   rf_points=["|C40| is theoretically zero for 8PSK and 1.0 for QPSK, which is the classical "
              "cumulant test separating them -- and it needs no phase coherence at all."])

_m("16psk", name="16PSK", family="psk", bits=4,
   carries="phase, sixteen states 22.5 degrees apart",
   what="Rarely deployed -- at this order QAM wins -- but present in RadioML 2018 and useful "
        "for seeing how PSK degrades with order.",
   constellation="Sixteen points on the unit circle, d_min = 0.390.",
   amplitude="Constant envelope.", phase="22.5 degrees apart; tolerance around 11 degrees.",
   frequency="Nothing deliberate.", bandwidth="Same occupancy, 4 bits per symbol.",
   views=["constellation", "phase", "cumulants"],
   impairments=["phase noise", "cfo", "awgn"],
   confusions=["8PSK and 32PSK; at low SNR simply a ring."],
   difficulty="Hard. The guide lists high-order-PSK-versus-high-order-PSK as a standard confusion.",
   guide_points=["Listed as rarely used in practice but present in RadioML 2018."],
   rf_points=["At 16 phases the ring is nearly continuous, so the constellation carries almost "
              "no shape information and classifiers fall back on subtler statistics."])

_m("16qam",
   name="16-QAM", family="qam", bits=4,
   carries="amplitude and phase jointly, on a 4x4 grid",
   what=("Both amplitude and phase carry data. Four bits per symbol in the same bandwidth as "
         "BPSK's one, at the cost of much tighter spacing."),
   constellation="4x4 square grid, d_min = 2/sqrt(10) = 0.632, three distinct amplitude rings.",
   amplitude="Genuinely varying -- amplitude is part of the message. Constellation PAPR 1.8 (2.6 dB).",
   phase="Twelve distinct phases, unevenly spaced.",
   frequency="Nothing deliberate.",
   bandwidth="(1 + rolloff) x symbol rate for 4 bits per symbol.",
   views=["constellation", "eye", "amp_hist", "psd", "cumulants"],
   impairments=["awgn", "pa nonlinearity", "phase noise", "iq imbalance"],
   confusions=["64-QAM and 256-QAM once noise blurs the grid density.",
               "16-APSK, which packs the same 16 points onto rings instead of a grid."],
   difficulty="Moderate. Needs roughly 8-10 dB more SNR than QPSK for comparable reliability.",
   guide_points=["The guide names high-order-QAM-versus-high-order-QAM as the dominant error "
                 "source in AMC, and notes their constellations differ only in density.",
                 "It also warns that per-component normalisation of I and Q separately is "
                 "usually a mistake because it distorts exactly this geometry."],
   rf_points=["Because amplitude carries information, any impairment that touches amplitude -- "
              "amplifier compression, AGC, fading -- attacks QAM's payload directly, whereas a "
              "PSK signal would only lose a scale factor it never used."])

_m("64qam", name="64-QAM", family="qam", bits=6,
   carries="amplitude and phase on an 8x8 grid",
   what="Six bits per symbol. Standard in good-channel WiFi and 5G.",
   constellation="8x8 grid, d_min = 2/sqrt(42) = 0.309, half of 16-QAM's spacing.",
   amplitude="Nine distinct amplitude levels; constellation PAPR 2.33 (3.7 dB).",
   phase="Many distinct phases; phase tolerance around 5.8 degrees.",
   frequency="Nothing deliberate.", bandwidth="Same occupancy, 6 bits per symbol.",
   views=["constellation", "eye", "amp_hist", "cumulants", "psd"],
   impairments=["awgn", "phase noise", "pa nonlinearity", "quantization"],
   confusions=["16-QAM and 256-QAM. The guide expects exactly this block in the confusion matrix."],
   difficulty="Hard. Needs high SNR and a long frame to resolve the grid density.",
   guide_points=["The guide is explicit that at -20 dB no model can separate 64-QAM from "
                 "256-QAM because the information is genuinely destroyed -- a fundamental "
                 "limit, not a model failure."],
   rf_points=["Resolving an 8x8 grid needs enough symbols to populate all 64 cells. A "
              "128-sample frame at 8 samples/symbol holds only 16 symbols, which cannot "
              "possibly show the grid -- frame length is a hard constraint here, not a "
              "tuning knob."])

_m("256qam", name="256-QAM", family="qam", bits=8,
   carries="amplitude and phase on a 16x16 grid",
   what="Eight bits per symbol, the practical ceiling for terrestrial links in excellent conditions.",
   constellation="16x16 grid, d_min = 2/sqrt(170) = 0.153.",
   amplitude="Very fine amplitude structure; extremely sensitive to any gain nonlinearity.",
   phase="Phase tolerance around 2.7 degrees -- less than most oscillators' phase noise.",
   frequency="Nothing deliberate.", bandwidth="Same occupancy, 8 bits per symbol.",
   views=["constellation", "amp_hist", "eye", "cumulants"],
   impairments=["awgn", "phase noise", "pa nonlinearity", "quantization", "iq imbalance"],
   confusions=["64-QAM, and any dense blob under noise."],
   difficulty="Very hard. Everything has to be nearly perfect.",
   guide_points=["Named by the guide among the schemes modern WiFi and 5G push to under "
                 "excellent conditions."],
   rf_points=["Its 2.7-degree phase tolerance is a useful yardstick: a receiver whose "
              "oscillator has 3 degrees RMS phase noise cannot support 256-QAM no matter how "
              "much transmit power you add. Some impairments cannot be beaten with SNR."])

_m("pam4", name="4-PAM", family="pam", bits=2,
   carries="amplitude only, four bipolar levels",
   what="Four amplitude levels on a single axis. One dimension instead of two.",
   constellation="Four collinear points at -3,-1,+1,+3 (normalised). d_min = 0.894.",
   amplitude="The entire message.", phase="Only 0 and 180 degrees.",
   frequency="Nothing deliberate.", bandwidth="(1+rolloff) x symbol rate.",
   views=["constellation", "magnitude", "eye", "amp_hist"],
   impairments=["awgn", "pa nonlinearity", "fading", "agc"],
   confusions=["BPSK (same axis, fewer levels) and 16-QAM (which is two PAM4s in quadrature)."],
   difficulty="Easy to spot from the collinear constellation, if there is no rotation.",
   guide_points=["The guide describes ASK/PAM as simple and cheap with poor noise performance."],
   rf_points=["Using only one dimension wastes half the signal space: 4-PAM and QPSK both "
              "carry 2 bits per symbol, but QPSK's d_min is 1.41 against PAM's 0.89, so QPSK "
              "is about 4 dB better for free."])

_m("ook", name="OOK — On-Off Keying", family="pam", bits=1,
   carries="presence or absence of the carrier",
   what="The simplest scheme there is: carrier on for a one, off for a zero.",
   constellation="Two points, one at the origin.",
   amplitude="Switches fully on and off; the highest envelope variance of any scheme here.",
   phase="Undefined during the off periods -- there is no signal to have a phase.",
   frequency="Nothing deliberate; the abrupt switching widens the spectrum.",
   bandwidth="Set by the pulse shaping; sharp switching spreads energy far.",
   views=["magnitude", "constellation", "amp_hist", "psd"],
   impairments=["awgn", "fading", "interference"],
   confusions=["2-ASK, and pulsed transmissions of any kind."],
   difficulty="Easy from the magnitude plot: nothing else spends half its time at zero.",
   guide_points=["The guide gives OOK as the simplest possible scheme and notes its use in "
                 "low-cost IoT, RFID and optical links."],
   rf_points=["Because half the symbols carry no energy, the average power is half the peak, "
              "so for a given peak-power limit OOK is 3 dB worse than antipodal BPSK before "
              "any other consideration."])

_m("4ask", name="4-ASK", family="pam", bits=2,
   carries="amplitude, four unipolar levels",
   what="Four non-negative amplitude levels including zero.",
   constellation="Four collinear points from the origin outward.",
   amplitude="The whole message; strong DC component because levels are unipolar.",
   phase="Constant (zero) except where the level is zero.",
   frequency="Nothing deliberate.", bandwidth="(1+rolloff) x symbol rate.",
   views=["magnitude", "constellation", "amp_hist", "psd"],
   impairments=["awgn", "fading", "pa nonlinearity", "dc offset"],
   confusions=["PAM4 and OOK."],
   difficulty="Easy geometrically, but easily confused once DC removal shifts the levels.",
   guide_points=["Listed by the guide under ASK as four or eight amplitude levels along a line."],
   rf_points=["Unipolar levels put a real DC component in the signal, so blind DC removal -- "
              "normally a free win -- actively damages 4-ASK by shifting its levels."])

_m("16apsk", name="16-APSK", family="apsk", bits=4,
   carries="amplitude and phase, on two concentric rings",
   what="Sixteen points arranged as a 4-point inner ring and a 12-point outer ring, the DVB-S2 "
        "layout. Designed to survive nonlinear satellite amplifiers.",
   constellation="Two rings, radius ratio about 2.85. Only two amplitude levels instead of "
                 "16-QAM's three.",
   amplitude="Two levels only; constellation PAPR 1.28 versus 16-QAM's 1.80.",
   phase="Four phases on the inner ring, twelve on the outer.",
   frequency="Nothing deliberate.", bandwidth="(1+rolloff) x symbol rate.",
   views=["constellation", "amp_hist", "am_am", "psd"],
   impairments=["pa nonlinearity (it is built for this)", "awgn", "phase noise"],
   confusions=["16-QAM at the same order -- rings versus grid, distinguishable in principle, "
               "hard in noise."],
   difficulty="Moderate. The ring structure is distinctive when clean.",
   guide_points=["The guide notes APSK is preferred in satellite systems because it behaves "
                 "better through nonlinear amplifiers, and that RadioML 2018 includes "
                 "16/32/64/128-APSK."],
   rf_points=["Fewer amplitude levels means less for an amplifier's AM/AM curve to distort. "
              "Run the PA impairment on 16-QAM and 16-APSK side by side at the same back-off "
              "and the design rationale becomes visible immediately."])

_m("32apsk", name="32-APSK", family="apsk", bits=5,
   carries="amplitude and phase, three concentric rings",
   what="Thirty-two points on 4/12/16 rings. The next step up the DVB-S2 ladder.",
   constellation="Three rings, d_min = 0.343.",
   amplitude="Three levels.", phase="Dense, ring-dependent.",
   frequency="Nothing deliberate.", bandwidth="(1+rolloff) x symbol rate.",
   views=["constellation", "amp_hist", "am_am"],
   impairments=["pa nonlinearity", "awgn", "phase noise"],
   confusions=["32-QAM, 16-APSK."],
   difficulty="Hard.",
   guide_points=["Part of the APSK family the guide lists in RadioML 2018."],
   rf_points=["The ring radii are code-rate dependent in the real standard, so a classifier "
              "trained on one radius ratio may not transfer to another -- a neat miniature of "
              "the distribution-shift problem."])

_m("dbpsk", name="DBPSK — Differential BPSK", family="psk", bits=1,
   carries="the change in phase between consecutive symbols",
   what="BPSK where the bit is encoded in whether the phase changed, not in what the phase is.",
   constellation="Two points, but their absolute position is arbitrary and irrelevant.",
   amplitude="As BPSK.", phase="Only phase differences matter.",
   frequency="Nothing deliberate.", bandwidth="As BPSK.",
   views=["constellation", "phase", "psd"],
   impairments=["cfo (still hurts -- it changes phase between symbols too)", "awgn"],
   confusions=["BPSK. They are visually identical; only the decoding differs."],
   difficulty="Indistinguishable from BPSK on a constellation alone.",
   guide_points=["The guide explains differential variants encode information in the change in "
                 "phase, making them immune to unknown constant phase offsets -- 'a major "
                 "practical advantage, and a hint about why phase offsets are such a headache'."],
   rf_points=["Immune to constant phase offset, not to CFO: a frequency offset changes the "
              "phase between consecutive symbols, which is exactly the quantity DBPSK reads. "
              "Set a phase offset and a CFO in turn and watch which one it shrugs off."])

_m("dqpsk", name="DQPSK — Differential QPSK", family="psk", bits=2,
   carries="the change in phase, four possible increments",
   what="QPSK with differential encoding.",
   constellation="Four points; absolute orientation meaningless.",
   amplitude="As QPSK.", phase="Differences of 0, 90, 180, 270 degrees.",
   frequency="Nothing deliberate.", bandwidth="As QPSK.",
   views=["constellation", "phase", "psd"],
   impairments=["cfo", "phase noise", "awgn"],
   confusions=["QPSK, pi/4-DQPSK."],
   difficulty="Same constellation as QPSK; needs temporal structure to separate.",
   guide_points=["Named by the guide among the differential variants immune to constant phase offset."],
   rf_points=["Differential decoding squares the noise: an error in either of two consecutive "
              "symbols corrupts the difference, costing about 2-3 dB against coherent QPSK. "
              "Robustness is bought, not free."])

_m("pi4dqpsk", name="pi/4-DQPSK", family="psk", bits=2,
   carries="phase changes drawn from +/-45 and +/-135 degrees",
   what="The constellation alternates between two QPSK sets offset by 45 degrees, so the "
        "trajectory never passes through the origin.",
   constellation="Eight points visible overall, four available at any one symbol.",
   amplitude="Notably less envelope variation than QPSK because the origin is never crossed.",
   phase="Increments are always odd multiples of 45 degrees, so the phase always changes.",
   frequency="Nothing deliberate.", bandwidth="As QPSK.",
   views=["constellation", "phase", "magnitude", "eye"],
   impairments=["cfo", "phase noise"],
   confusions=["8PSK -- it shows eight points -- and QPSK, whose bit rate it shares."],
   difficulty="Deceptive: eight visible points but only 2 bits per symbol.",
   guide_points=["The guide lists pi/4-DQPSK as used in some cellular standards and groups it "
                 "with QPSK/OQPSK as a same-constellation, different-transition confusion."],
   rf_points=["Compare its magnitude-versus-time against QPSK's: the guaranteed phase change "
              "keeps the envelope away from zero, which lets a transmitter run its amplifier "
              "closer to saturation. That is the entire point of the design."])

_m("oqpsk", name="OQPSK — Offset QPSK", family="psk", bits=2,
   carries="phase, four states, with the Q rail delayed half a symbol",
   what="QPSK with the quadrature rail delayed by half a symbol period, which removes the "
        "180-degree transitions.",
   constellation="Same four points as QPSK.",
   amplitude="Markedly steadier than QPSK -- the whole reason it exists.",
   phase="Never changes by 180 degrees at once; only one rail moves at a time.",
   frequency="Nothing deliberate.", bandwidth="As QPSK.",
   views=["constellation", "iq_time", "magnitude", "eye"],
   impairments=["clock offset (the staggering makes timing subtler)", "cfo", "awgn"],
   confusions=["QPSK -- identical scatter plot."],
   difficulty="Impossible from the constellation alone; requires temporal structure.",
   guide_points=["The guide describes OQPSK as avoiding abrupt 180-degree transitions through "
                 "the origin, reducing amplitude fluctuation, and cites its use in ZigBee. It "
                 "uses QPSK-versus-OQPSK as the example of a confusion a model that treats "
                 "samples as an unordered set literally cannot resolve."],
   rf_points=["The staggering also breaks the usual blind estimators: OQPSK deliberately "
              "suppresses the once-per-symbol envelope dip that symbol-rate estimators look "
              "for, so a technique that works on every other linear scheme quietly fails here. "
              "The lab shows that failure rather than hiding it."])

_m("2fsk", name="2-FSK", family="fsk", bits=1,
   carries="frequency, two tones",
   what="Two frequency states. Information is in which tone is being sent.",
   constellation="A circle. The constellation view is almost useless for FSK -- constant "
                 "amplitude, continuously sweeping phase.",
   amplitude="Constant.", phase="Ramps at one of two rates.",
   frequency="Two discrete levels separated by h x symbol rate. This is the diagnostic view.",
   bandwidth="Roughly 2 x (deviation + symbol rate) by Carson's rule.",
   views=["inst_freq", "spectrogram", "psd", "phase"],
   impairments=["awgn", "fading", "interference"],
   confusions=["4-FSK, GFSK, CPFSK, MSK -- the whole continuous-phase family."],
   difficulty="Trivial from instantaneous frequency, hard from a constellation.",
   guide_points=["The guide notes FSK-family signals are visually distinctive in the "
                 "instantaneous-frequency domain, which classical feature-based methods "
                 "exploited heavily."],
   rf_points=["Modulation index h sets everything: h = 1 gives widely separated orthogonal "
              "tones, h = 0.5 is the minimum for orthogonality (that is MSK) and packs the "
              "spectrum tighter. Change h in the lab and watch the two spectral lobes slide "
              "together."])

_m("4fsk", name="4-FSK", family="fsk", bits=2,
   carries="frequency, four tones",
   what="Four frequency states, two bits per symbol.",
   constellation="A circle, as for all constant-envelope CPM.",
   amplitude="Constant.", phase="Ramps at one of four rates.",
   frequency="Four evenly spaced levels -- unmistakable in the instantaneous-frequency plot.",
   bandwidth="Wider than 2-FSK for the same h, since the outer tones sit further out.",
   views=["inst_freq", "spectrogram", "psd"],
   impairments=["awgn", "fading", "interference"],
   confusions=["2-FSK when noise obscures the inner levels."],
   difficulty="Easy from instantaneous frequency: count the levels.",
   guide_points=["Listed among the FSK family variants."],
   rf_points=["Counting frequency levels is the FSK analogue of counting constellation "
              "clusters, and it degrades the same way: noise fills in the gaps between levels "
              "until the histogram is unimodal."])

_m("cpfsk", name="CPFSK — Continuous-Phase FSK", family="fsk", bits=1,
   carries="frequency, with no phase discontinuity at symbol boundaries",
   what="Binary FSK where the phase is continuous across symbol boundaries, which keeps the "
        "spectrum compact.",
   constellation="A circle.", amplitude="Constant.",
   phase="Continuous -- no jumps. That continuity is what narrows the spectrum.",
   frequency="Two levels at +/- h x symbol rate / 2, here h = 0.5.",
   bandwidth="Narrower than discontinuous FSK at the same deviation.",
   views=["inst_freq", "phase", "psd", "spectrogram"],
   impairments=["awgn", "fading"],
   confusions=["GFSK, GMSK, MSK, 2-FSK."],
   difficulty="Easy as a family, hard to pin to the exact variant.",
   guide_points=["The guide lists CPFSK as continuous-phase FSK with no abrupt phase jumps, "
                 "and groups GFSK/CPFSK/GMSK as a standard confusion set."],
   rf_points=["A phase discontinuity is an instantaneous change, and instantaneous changes are "
              "broadband. Enforcing continuity is the cheapest spectral saving in modulation "
              "design -- compare the PSD skirts of CPFSK against a hard-switched 2-FSK."])

_m("msk", name="MSK — Minimum Shift Keying", family="fsk", bits=1,
   carries="frequency, h = 0.5, the minimum for orthogonality",
   what="CPFSK with modulation index exactly 0.5 -- the smallest tone spacing at which the two "
        "states remain orthogonal.",
   constellation="A circle.", amplitude="Constant.",
   phase="Advances by exactly +/-90 degrees per symbol.",
   frequency="Two levels at +/- symbol rate / 4.",
   bandwidth="Compact main lobe with fast-decaying sidelobes.",
   views=["inst_freq", "phase", "psd", "constellation"],
   impairments=["awgn", "fading", "cfo"],
   confusions=["CPFSK at h=0.5 (they are the same thing), GMSK, OQPSK."],
   difficulty="Moderate.",
   guide_points=["The guide lists MSK/GMSK as continuous-phase, constant-envelope and "
                 "spectrally efficient."],
   rf_points=["MSK has a second identity: it is also exactly OQPSK with half-sinusoid pulse "
              "shaping. The same waveform is a frequency modulation and an offset phase "
              "modulation at once, which is a good reminder that these families are labels we "
              "impose, not properties the waveform has."])

_m("gfsk", name="GFSK — Gaussian FSK", family="fsk", bits=1,
   carries="frequency, with Gaussian-smoothed transitions",
   what="FSK whose frequency transitions are smoothed by a Gaussian filter, narrowing the "
        "spectrum. The Bluetooth modulation.",
   constellation="A circle.", amplitude="Constant.",
   phase="Continuous and smooth.",
   frequency="Two levels, but the transitions between them are rounded rather than square.",
   bandwidth="Narrower than plain FSK; set by the BT product.",
   views=["inst_freq", "psd", "spectrogram"],
   impairments=["awgn", "fading", "interference"],
   confusions=["GMSK, CPFSK, 2-FSK."],
   difficulty="The family is easy; the specific variant needs the transition shape.",
   guide_points=["The guide identifies GFSK as FSK with a Gaussian filter smoothing the "
                 "frequency transitions, used in Bluetooth."],
   rf_points=["The BT product trades spectrum against intersymbol interference. Lower BT means "
              "a narrower spectrum but a frequency pulse spread over more symbols, so adjacent "
              "symbols interfere. The rounded corners in the instantaneous-frequency plot are "
              "that trade made visible."])

_m("gmsk", name="GMSK — Gaussian MSK", family="fsk", bits=1,
   carries="frequency, h = 0.5, Gaussian-shaped, BT = 0.3",
   what="MSK with a Gaussian frequency pulse. The GSM modulation.",
   constellation="A circle.", amplitude="Constant -- ideal for saturated amplifiers.",
   phase="Smoothly continuous.",
   frequency="Two nominal levels the signal never fully settles on, because BT = 0.3 spreads "
             "each frequency pulse across roughly three symbols.",
   bandwidth="Very compact, which is why GSM chose it.",
   views=["inst_freq", "psd", "spectrogram", "phase"],
   impairments=["awgn", "fading", "multipath"],
   confusions=["GFSK, MSK, CPFSK."],
   difficulty="Hard to separate from its neighbours; easy to place in the family.",
   guide_points=["The guide names GMSK as the modulation of GSM and groups it with GFSK and "
                 "CPFSK as closely related continuous-phase schemes."],
   rf_points=["Watch the measured peak frequency deviation: it falls short of the nominal "
              "h x Rs / 2 because the Gaussian pulse is spread over several symbols and "
              "neighbouring pulses partially cancel. That shortfall is deliberate ISI, traded "
              "for spectrum."])

_m("am_dsb_wc", name="AM-DSB-WC — Double Sideband with Carrier", family="analog", bits=None,
   carries="the envelope of a continuous message",
   what="Classic amplitude modulation: the message rides on the envelope and a carrier "
        "component remains, which is what lets a simple diode detector work.",
   constellation="A line segment along the real axis -- no discrete clusters, because the "
                 "message is continuous.",
   amplitude="Carries the entire message.",
   phase="Constant while the envelope stays positive; flips by 180 degrees on overmodulation.",
   frequency="Two sidebands plus a carrier line at DC.",
   bandwidth="Twice the message bandwidth.",
   views=["magnitude", "psd", "iq_time", "spectrogram"],
   impairments=["awgn", "fading", "interference"],
   confusions=["AM-DSB-SC, and WBFM when the source audio is quiet."],
   difficulty="The carrier spike at DC is a giveaway when present.",
   guide_points=["The guide notes analog modulations have no discrete constellation, and warns "
                 "that RadioML AM/FM samples with silent source audio are effectively "
                 "unclassifiable -- a known ceiling on achievable accuracy."],
   rf_points=["The carrier carries no information yet holds most of the power: at 80% "
              "modulation depth over two thirds of the transmitted power is in a spike that "
              "says nothing. Suppressing it gives AM-DSB-SC, at the cost of needing a coherent "
              "receiver."])

_m("am_dsb_sc", name="AM-DSB-SC — Suppressed Carrier", family="analog", bits=None,
   carries="the message, with no carrier component",
   what="Amplitude modulation with the carrier removed. Efficient, but needs a coherent receiver.",
   constellation="A line through the origin; the sign flips with the message.",
   amplitude="Carries the message, including sign reversals.",
   phase="Flips 180 degrees whenever the message crosses zero.",
   frequency="Two sidebands, no carrier line.",
   bandwidth="Twice the message bandwidth.",
   views=["magnitude", "psd", "iq_time"],
   impairments=["awgn", "cfo", "fading"],
   confusions=["AM-DSB-WC, BPSK (both flip phase by 180 degrees)."],
   difficulty="Moderate; the missing DC spike separates it from AM-DSB-WC.",
   guide_points=["Listed by the guide among the AM variants present in RadioML."],
   rf_points=["A carrier offset that a with-carrier AM receiver would ignore becomes fatal "
              "here: with no carrier to lock to, the offset turns the recovered message into a "
              "beat at the offset frequency."])

_m("am_ssb", name="AM-SSB — Single Sideband", family="analog", bits=None,
   carries="the message on one sideband only",
   what="One sideband transmitted, the other discarded. Half the bandwidth of DSB.",
   constellation="A rotating locus with no symmetry about the imaginary axis.",
   amplitude="Varies with the message and its Hilbert transform.",
   phase="Continuously varying.",
   frequency="Energy on one side of DC only -- the clearest signature there is.",
   bandwidth="Equal to the message bandwidth.",
   views=["psd", "spectrogram", "magnitude", "constellation"],
   impairments=["cfo", "awgn", "iq imbalance (which puts energy back in the dead sideband)"],
   difficulty="Easy: the one-sided spectrum is unmistakable.",
   confusions=["Any signal that has been badly filtered on one side."],
   guide_points=["Listed by the guide among the AM variants in RadioML."],
   rf_points=["SSB is the perfect test case for I/Q imbalance. The empty sideband should be "
              "empty; imbalance fills it with an image, and the depth of that image is a "
              "direct visual readout of the receiver's image rejection."])

_m("fm", name="FM — Frequency Modulation", family="analog", bits=None,
   carries="the message in the instantaneous frequency",
   what="The carrier frequency follows the message. Constant envelope.",
   constellation="A filled circle -- constant amplitude, all phases visited.",
   amplitude="Constant. Any amplitude variation you see is the channel, not the signal.",
   phase="The running integral of the message.",
   frequency="Tracks the message directly. This is the view that matters.",
   bandwidth="Carson's rule: 2 x (peak deviation + message bandwidth).",
   views=["inst_freq", "psd", "magnitude", "spectrogram"],
   impairments=["awgn (with a threshold effect)", "fading", "interference"],
   confusions=["WBFM, and other constant-envelope schemes."],
   difficulty="Easy as a family from instantaneous frequency.",
   guide_points=["The guide lists WBFM among the analog modulations in RadioML and flags the "
                 "AM-DSB versus WBFM confusion as a classic, driven partly by silent audio."],
   rf_points=["FM has a threshold: above roughly 10 dB the demodulator suppresses noise better "
              "than AM, below it performance collapses far faster. Sweep SNR through that "
              "region and watch the instantaneous-frequency trace go from clean to shredded "
              "over just a few dB."])

_m("wbfm", name="WBFM — Wideband FM", family="analog", bits=None,
   carries="the message in frequency, with large deviation",
   what="FM with deviation much larger than the message bandwidth -- broadcast FM radio.",
   constellation="A filled circle.", amplitude="Constant.",
   phase="Rapidly varying.",
   frequency="Swings over many times the message bandwidth.",
   bandwidth="Dominated by the deviation, not the message.",
   views=["inst_freq", "psd", "spectrogram"],
   impairments=["awgn", "fading", "interference"],
   confusions=["AM-DSB, per the guide's noted RadioML confusion."],
   difficulty="Easy from the wide, flat-topped spectrum.",
   guide_points=["Named in the guide as broadcast FM radio and part of the classic AM-DSB "
                 "versus WBFM confusion."],
   rf_points=["Wide deviation buys noise immunity by spending bandwidth: the demodulated SNR "
              "improves roughly with the square of the modulation index. That is why broadcast "
              "FM sounds clean and AM does not."])

_m("ofdm", name="OFDM — Orthogonal Frequency Division Multiplexing", family="ofdm", bits=None,
   carries="many parallel narrowband subcarriers, each with its own constellation",
   what=("Instead of one fast stream, many slow ones in parallel. An IFFT places each symbol on "
         "its own orthogonal subcarrier, and a cyclic prefix absorbs the channel's delay "
         "spread. The waveform of 5G, WiFi and LTE."),
   constellation="In the time domain, a featureless Gaussian blob -- and that is not a fault. "
                 "The real constellation only appears after removing the cyclic prefix and "
                 "taking the FFT.",
   amplitude="Highly variable. The sum of many independent subcarriers has a high "
             "peak-to-average ratio, which is a genuine hardware problem.",
   phase="Uniformly distributed; the composite carries no readable phase structure.",
   frequency="A flat block of occupied subcarriers with sharp edges.",
   bandwidth="Number of used subcarriers times the subcarrier spacing.",
   views=["ofdm", "psd", "autocorr", "papr_ccdf", "amp_hist"],
   impairments=["cfo (uniquely damaging -- it breaks orthogonality)", "clipping", "multipath",
                "phase noise"],
   confusions=["Noise, and any other high-order dense signal, in the time domain."],
   difficulty="Easy to detect as OFDM, impossible to read subcarrier modulation without "
              "synchronising first.",
   guide_points=["The guide is emphatic that an OFDM signal in the time domain looks nearly "
                 "Gaussian by the central limit theorem, that the cyclic prefix creates a "
                 "correlation peak at a lag equal to the FFT length, and that "
                 "'modulation classification of a 5G signal' is genuinely ambiguous because "
                 "the two interpretations need completely different pipelines.",
                 "It also connects OFDM to CSI: the per-subcarrier channel coefficients used in "
                 "WiFi localisation are exactly an OFDM receiver's channel estimate."],
   rf_points=["The cyclic prefix is the detector's gift. Look at the autocorrelation: the peak "
              "at lag = FFT length is the CP correlating with the tail it was copied from, and "
              "it identifies OFDM even when the constellation says nothing at all."])


def profile(mod):
    return M.get(mod)


def all_profiles():
    return M
