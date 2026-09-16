# Verification evidence and review status

This document describes the review branch `review/verification-integrity-20260916`, based on `d62d10702983ef493492db94eecb37323f0bafa6`.

## Confirmed defects in the original verification evidence

1. In `qa/report.py`, the numeric comparisons ran explicitly enabled impairments but `case()` separately built the tutor excerpt from a configuration without `enabled: true`. `rflab/experiment.py` skips absent or disabled impairments. As a result, the earlier committed `qa/VERIFICATION.md` included clean-signal narration next to impaired-signal numerical checks. The branch enables the requested impairments for narration and errors if the engine omits any of them.
2. In `qa/verify_physics.py`, the RMS delay-spread check compared `r["rms_delay_spread_s"]` with itself, so it could not detect an incorrect reported delay spread. The branch replaces its expected value with the analytic two-ray expression `tau * sqrt(a) / (1 + a)`, where `a = 10**(gain_db/10)` is the delayed-path power ratio.

## Observed test execution

[GitHub Actions run 35083811502](https://github.com/omarsaqr12/rf-signal-lab/actions/runs/35083811502), Python 3.11 on Ubuntu 24.04 with NumPy 2.4.6 and SciPy 1.17.1:

- `python qa/verify_physics.py` — **PASS 48, FAIL 0**; includes the repaired two-ray delay-spread comparison.
- `python qa/report.py` — **PASS 22/22 numerical cases**, including enabled-impairment narration runs. [Download the generated report artifact](https://github.com/omarsaqr12/rf-signal-lab/actions/runs/35083811502/artifacts/10441561779).

The generated report now describes noisy constellation clouds and CFO arcs where the earlier committed report described an undistorted signal. The numeric checks and narrator still use **separate simulations**, sometimes with different frame lengths (for example, the 600-ppm clock-offset numeric check uses 8,192 samples, while its separate narrated run uses the default 4,096); therefore their per-frame drift values should not be compared as though they were the same observation. The generated report makes the separate-run distinction explicit, but a further code improvement should pass the exact numerical configuration into narration.

## Limits and remaining steps

**The committed `qa/VERIFICATION.md` on this branch is the earlier, stale generated artifact.** Its original screenshot-inspection claim was not independently verified during this review. Use the linked CI artifact for the corrected narrator output; before replacing the committed report, reconcile numeric/narration frame configurations, inspect the regenerated diff and review browser screenshots. `qa/shoot.py` requires a running local server and browser/Playwright environment.

The QA scripts check selected simulator predictions, not every impairment combination, full DSP correctness, real-time SDR performance, or hardware output. The simulator is an interactive teaching tool, not a live SDR receiver. No browser screenshot or full `qa/sweep.py` run was performed in this review.

To run the documented checks in a clean environment:

```bash
python3 -m pip install numpy scipy
python3 qa/verify_physics.py
python3 qa/report.py
python3 qa/sweep.py
```

Check each command's actual output; this checklist alone is not test evidence.
