# Engineering notes: RF Signal Lab

This document adds technical context to the [project overview](../README.md). The application is a teaching simulator: the values shown by its diagnostics are functions of generated samples and stated model assumptions, not measurements from an over-the-air receiver.

## Signal-to-explanation pipeline

The browser sends a modulation and impairment configuration to [`rflab/server.py`](../rflab/server.py). [`rflab/experiment.py`](../rflab/experiment.py) generates the clean reference signal, applies enabled impairments in [`rflab/dsp/impairments.py`](../rflab/dsp/impairments.py), records per-stage changes, and assembles measurements and plot data. The tutor modules use those measurements to choose relevant views and describe the resulting signal. The JavaScript interface renders the returned data using Canvas; it does not implement a separate RF simulator.

The clean reference is deliberately retained to support oracle diagnostics (such as reference-based EVM) and stage-by-stage comparisons. These make effects easier to teach but must not be confused with blind measurements available to a deployed SDR.

## Why units and observation length matter

A frequency offset of a few kilohertz has different effects at different symbol rates and frame durations. Similarly, sample-clock error is small per sample but accumulates over a frame. The lab expresses severity relative to signal properties and the actual configured duration where applicable. Any short label such as *mild* or *severe* is a pedagogical summary, not a modulation-independent receiver specification.

The order of impairments models a particular transmit/channel/receive chain: PA nonlinearity, propagation and interference, local-oscillator effects, sample-clock mismatch, receiver noise and analog defects, then clipping/quantization. Alternative physical architectures may order or couple effects differently; this simulator is not a universal hardware model.

## Plots are complementary evidence

- AWGN generally broadens constellation clusters; carrier-frequency offset introduces a phase ramp that can turn a static constellation into arcs or rings.
- DC offset translates a constellation; I/Q imbalance can shear it or introduce a spectral image. Both differ from isotropic additive noise, but effects can coexist and their signatures are not unique in every configuration.
- FSK frequency states are often easier to recognize in instantaneous frequency than in constellation space. OFDM has useful cyclic-prefix and subcarrier structure.
- An idealized gain/carrier synchronization diagnostic estimates how much modeled distortion can be corrected by those operations. It does not implement or validate a real synchronization receiver.

These statements motivate inspection; quantitative claims should be checked against the enabled configuration and the [verification notes](../qa/REVIEW_NOTES.md), not inferred from a screenshot alone.

## Failure modes that shaped the implementation

The original development notes record several plausible-looking errors: an FFT call silently truncating a longer input, high-DPI Canvas image placement not honoring the usual transform, raw PSK phase unwrapping confusing modulation jumps with carrier drift, an image-rejection estimate missing a factor of two, symbol alignment failing under carrier rotation, and DC translation being counted as cluster spread. Their corresponding calculations live in [`rflab/dsp/`](../rflab/dsp/) and [`rflab/web/`](../rflab/web/). This list documents development history; it does not establish that every remaining path has been independently validated.

## Reproduction and limitations

Run the analytic checks, report generator, and configuration sweep using the commands in the [README](../README.md). The [CI workflow](../.github/workflows/qa.yml) captures browser screenshots separately, which require visual inspection. Generated fixtures are not real RF recordings, and tests of these models do not establish modulation-classifier transfer accuracy or physical SDR performance.
