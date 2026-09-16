# RF Signal Lab: verification and review record

**Review date:** September 16, 2026. This is a record of selected test evidence, not a certification of every simulator configuration or a live SDR system.

## Corrected evidence defects

1. The original `qa/report.py` ran numeric comparisons with enabled impairments but separately generated tutor excerpts without `enabled: true`. The engine silently skipped the requested impairment. Narration now enables and confirms each requested impairment.
2. The original multipath RMS delay-spread test compared the reported result against itself. It now derives the expected two-ray spread independently as `tau * sqrt(a) / (1 + a)`, where `a = 10**(gain_db/10)` is the delayed-path power ratio.
3. The tracked pre-fix `qa/VERIFICATION.md` was replaced with a **clearly labeled generation index**, not passed off as a corrected result. The original is recoverable from Git history. Run `python qa/report.py` to create the full report or download the time-limited artifact from CI.

## Executed checks

[GitHub Actions run 35085215340](https://github.com/omarsaqr12/rf-signal-lab/actions/runs/35085215340) on Ubuntu 24.04 and Python 3.11:

| Check | Observed outcome | Evidence |
| --- | --- | --- |
| `python qa/verify_physics.py` | **48 PASS, 0 FAIL** | Job log, including the independently computed delay-spread check |
| `python qa/report.py` | **22/22 selected numeric comparisons passed** | [Generated report artifact](https://github.com/omarsaqr12/rf-signal-lab/actions/runs/35085215340/artifacts/10442156202) |
| `python qa/sweep.py` | **411 configurations exercised; no failures** | Numerical job log; checks for crashes, non-finite values, and missing tutor/priority-view data |
| Browser screenshot harness | **24 named cases captured; no browser-console errors reported** | [Screenshot artifact](https://github.com/omarsaqr12/rf-signal-lab/actions/runs/35085215340/artifacts/10441519944) |

The screenshot artifact contains 24 complete-page images, cropped plot images, and a case index. A contact-sheet review and closer inspection of selected clean/noise/CFO cases confirmed the page renders and the expected coarse structures appear. This was **not** a pixel-by-pixel review of every plot or a validation of every annotation.

## Outstanding limitation found during visual review

The QPSK CFO screenshot shows ideal constellation markers shrinking inward while the received points form a ring at roughly unchanged amplitude. In `rflab/experiment.py`, `build_plots()` scales the ideal markers using a complex gain fitted across the carrier-rotating received frame; the gain can collapse through coherent cancellation. [Issue #2](https://github.com/omarsaqr12/rf-signal-lab/issues/2) records the reproduction, likely cause, and regression criteria. Do not treat the CFO overlay as a validated amplitude reference until corrected. This visual problem does not by itself invalidate the separate CFO numerical checks.

## Evidence boundaries

Numerical comparisons and tutor excerpts still run in **separate simulations**, sometimes with different frame lengths (the 600-ppm clock example uses 8,192 samples numerically and 4,096 for narration). Their per-frame measurements are not paired. The report labels the distinction; future work should use one exact configuration or explicitly join the runs by configuration and seed.

The analytical checks cover selected physics cases; the 411-case sweep checks execution and basic data integrity, not physical fidelity of every combination. Browser capture checks that cases render, not that every plotted quantity is correct. No physical SDR, real-world receiver, or modulation-recognition transfer accuracy was tested here.

To rerun the numerical checks in an environment with NumPy and SciPy:

```bash
python qa/verify_physics.py
python qa/report.py
python qa/sweep.py
```

For browser capture, install Playwright/Chromium, start `python -m rflab.server 8765`, and run `python qa/shoot.py OUTDIR`. Inspect its output and the console-error summary. The command list itself is not test evidence.
