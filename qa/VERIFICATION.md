# Verification report — generated on demand

**This file is an index, not a test result.** The previously tracked report mixed numerical checks of impaired signals with tutor narration produced from clean signals. It was retired on September 16, 2026; its original contents remain accessible in Git history.

To generate a current report from this checkout, install NumPy and SciPy and run:

```bash
python qa/verify_physics.py
python qa/report.py
```

The second command replaces this index with a full, machine-generated `qa/VERIFICATION.md`. The [September 16 corrected CI report](https://github.com/omarsaqr12/rf-signal-lab/actions/runs/35083811502/artifacts/10441561779) records 22/22 selected numerical comparisons; the same run recorded 48/48 selected analytic physics checks. Download the report artifact from GitHub Actions while it is retained, or regenerate it locally. Consult [`REVIEW_NOTES.md`](REVIEW_NOTES.md) for the tests' exact scope and limitations.

The script's numeric cases and tutor excerpts use separate simulations; some frame lengths differ. A numerical PASS does **not** certify the narrated screenshot, all impairment combinations, or real SDR hardware. Visual inspection requires the separate Playwright screenshot workflow and human review.
