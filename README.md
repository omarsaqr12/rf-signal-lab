# RF Signal Lab

**Interactive RF signal simulator and DSP learning tool**  
Python · NumPy/SciPy · JavaScript · Canvas · signal processing

Generate a modulated I/Q signal, introduce realistic *modeled* channel and receiver impairments, and see how its constellation, waveform, spectrum, and other representations change. Contextual explanations connect the measurements to modulation recognition and receiver design. This is a **local educational simulator**, not a live SDR receiver, 5G modem, or validated hardware-in-the-loop system.

## Run it locally

Requires Python 3, NumPy, and SciPy. The HTTP server uses Python's standard library; the browser interface has no JavaScript package-install step.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install numpy scipy
./run.sh
```

Open **http://127.0.0.1:8765**. The server binds to localhost by default; the repository does not include a hosted demo or a public deployment. On Windows, use your environment's activation command and `python -m rflab.server 8765` instead of `./run.sh`.

### A three-minute walkthrough

1. Choose **QPSK** with no impairment. Inspect the constellation and time-domain I/Q trace.
2. Enable **AWGN** and lower SNR from 20 dB to 0 dB. Watch the clusters spread and compare the measured decision margin.
3. Disable AWGN and enable **carrier frequency offset**. Compare the raw constellation with phase versus time, then explore what ideal synchronization can remove.
4. Switch to **2-FSK** or **OFDM**. Notice why instantaneous frequency or the cyclic-prefix view can be more informative than a constellation.

All examples run on generated signals; no dataset, radio, or GPU is needed.

## What is implemented

| Capability | In the lab |
| --- | --- |
| Signal generation | 28 documented modulation options spanning PSK, QAM, ASK/PAM, FSK, analog AM/FM, and OFDM. |
| Impairment chain | 13 configurable models including noise, carrier/clock offsets, phase noise, multipath/fading, interference, amplifier compression, I/Q imbalance, DC offset, clipping, and quantization. |
| Visual analysis | 17 views, including constellation, I/Q, FFT/PSD, spectrogram, eye diagram, autocorrelation, cumulants, cyclostationarity, and OFDM subcarriers. |
| Guided learning | Measurement-driven plot explanations, theory-versus-measurement comparisons, follow-up experiments, and eight blind identification challenges. |
| Verification | Physics checks, report-generation checks, a modulation-by-impairment smoke sweep, and a separate browser screenshot harness. Each checks a different part of the system. |

The interface prioritizes views relevant to the selected modulation and impairments. For example, FSK is easier to inspect through instantaneous frequency than through a static constellation.

## Implementation at a glance

```text
Configuration in the browser
        ↓
Python signal generation + ordered impairment chain
        ↓
Measurements, diagnostic plots, and explanatory tutor
        ↓
Local JSON API → dependency-free JavaScript/Canvas interface
```

- [`rflab/dsp/`](rflab/dsp/) — modulation, pulse shaping, impairments, and measurements.
- [`rflab/experiment.py`](rflab/experiment.py) — runs a configuration and packages results for the UI.
- [`rflab/tutor/`](rflab/tutor/) — severity calculations, view selection, explanations, and challenges.
- [`rflab/server.py`](rflab/server.py) and [`rflab/web/`](rflab/web/) — localhost API and interactive browser interface.
- [`qa/`](qa/) — independent numerical checks, generated verification report, configuration sweep, and screenshot harness.

The simulator retains a clean reference signal so it can compute diagnostics such as reference-based error vector magnitude. That reference is an *oracle available to the simulation*, not something a real receiver automatically knows.

## Verify the implementation

With the same Python environment activated:

```bash
python qa/verify_physics.py  # analytic checks of selected DSP cases
python qa/report.py          # numeric comparisons + tutor excerpts; regenerates qa/VERIFICATION.md
python qa/sweep.py           # cross-modulation and parameter-extreme smoke checks
```

The [GitHub Actions workflow](.github/workflows/qa.yml) runs the numerical checks on pull requests and uploads the regenerated report. The [September 16 CI run](https://github.com/omarsaqr12/rf-signal-lab/actions/runs/35083811502) recorded 48/48 analytic checks and 22/22 report comparisons passing. These counts cover specific scripted cases; they are not a blanket certification of every waveform, plot, or RF device. See [verification scope and known limitations](qa/REVIEW_NOTES.md).

For a *separate* visual review, install Playwright and its Chromium browser, start the local server, then run `python qa/shoot.py OUTDIR`. The harness captures screenshots for inspection; it does not make a screenshot correct merely by saving it. Do not confuse numerical QA with manual browser review.

## Scope and limitations

Channel and hardware effects here are mathematical models. Severity and synchronization diagnostics are pedagogical approximations tied to generated samples and, for some calculations, a clean reference. No over-the-air capture, device generalization, model accuracy on real RF, or end-to-end SDR latency is established by this repository. See the verification notes before citing the generated report.
