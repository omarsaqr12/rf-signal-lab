# Verification evidence and review status

This document describes the review branch `review/verification-integrity-20260916`, based on `d62d10702983ef493492db94eecb37323f0bafa6`. It is not a replacement for executed tests.

## Confirmed defects in the original verification evidence

1. In `qa/report.py`, the numeric comparisons ran explicitly enabled impairments but `case()` separately built the tutor excerpt from a configuration without `enabled: true`. `rflab/experiment.py` skips absent or disabled impairments. As a result, the committed `qa/VERIFICATION.md` can contain clean-signal narration next to impaired-signal numerical checks. The branch explicitly enables the specified impairments for the narration run and checks that each produced a report.
2. In `qa/verify_physics.py`, the RMS delay-spread check compared `r["rms_delay_spread_s"]` with itself, so it could not detect an incorrect reported delay spread. The branch replaces its expected value with the analytic two-ray expression `tau * sqrt(a) / (1 + a)`, where `a = 10**(gain_db/10)` is the delayed-path power ratio.

## What the evidence establishes

`qa/verify_physics.py` tests a set of specific model predictions; `qa/report.py` creates a markdown report from another set of numerical comparisons and tutor configurations. A passing check does not establish that every simulation is physically faithful, that explanations have been visually inspected in a browser, or that an SDR output has been validated. `qa/shoot.py` is a separate browser-based screenshot harness. The application is a simulator and interactive teaching tool, **not** a live SDR receiver.

**The committed `qa/VERIFICATION.md` on this branch is an earlier generated artifact and remains stale.** Do not treat its tutor excerpts as post-fix evidence. Regenerate it with `python3 qa/report.py` in an environment with NumPy and SciPy, inspect the resulting diff, and review browser screenshots before replacing or citing it as corrected. The fixes in this branch were source-reviewed against the implementation; they were not executed on an accessible checkout at the time of writing. Check the pull request's CI results for subsequent runs.

To verify in a clean environment:

```bash
python3 -m pip install numpy scipy
python3 qa/verify_physics.py
python3 qa/report.py
python3 qa/sweep.py
```

Treat each command's actual exit code and printed results as evidence, not this checklist. `qa/shoot.py` additionally needs its browser/Playwright environment and a running local server. No claim about browser layout, all impairment combinations, or numerical pass counts is made by this review note.
