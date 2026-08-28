"""Exhaustive smoke sweep: every modulation against every impairment, plus the
whole tutor pipeline, checking that nothing errors and no value is non-finite."""
import os, sys, math, itertools, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from rflab.dsp.modulators import ALL_MODS
from rflab.server import build_response, IMPAIRMENT_UI

IMPS = {g["key"]: {"enabled": True,
                   **{p["key"]: p["default"] for p in g["params"]}} for g in IMPAIRMENT_UI}

fails, checked = [], 0


def bad(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            r = bad(v, f"{path}.{k}")
            if r: return r
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o[:400]):
            r = bad(v, f"{path}[{i}]")
            if r: return r
    elif isinstance(o, float) and not math.isfinite(o):
        return path
    elif isinstance(o, (np.floating,)) and not math.isfinite(float(o)):
        return path
    return None


for mod in ALL_MODS:
    for name, imp in [("none", {})] + [(k, {k: v}) for k, v in IMPS.items()]:
        checked += 1
        try:
            r = build_response({"mod": mod, "n_samples": 4096, "impairments": imp})
            b = bad(r)
            if b:
                fails.append((mod, name, f"non-finite at {b}"))
            for v in r["tutor"]["priority_views"]:
                if r["plots"].get(v) is None:
                    fails.append((mod, name, f"priority view {v} has no data"))
            if not r["tutor"]["explain"]:
                fails.append((mod, name, "no explanations generated"))
        except Exception as exc:
            fails.append((mod, name, f"{type(exc).__name__}: {exc}"))
            traceback.print_exc()

# all impairments at once
for mod in ("qpsk", "16qam", "2fsk", "ofdm", "wbfm"):
    checked += 1
    try:
        r = build_response({"mod": mod, "n_samples": 4096, "impairments": IMPS})
        b = bad(r)
        if b: fails.append((mod, "ALL", f"non-finite at {b}"))
    except Exception as exc:
        fails.append((mod, "ALL", f"{type(exc).__name__}: {exc}"))

# parameter extremes
EXTREMES = [
    {"mod": "qpsk", "n_samples": 512, "sps": 2, "rolloff": 0.0},
    {"mod": "256qam", "n_samples": 16384, "sps": 32, "rolloff": 1.0},
    {"mod": "ofdm", "n_samples": 16384, "n_fft": 256, "cp_len": 64, "n_used": 200},
    {"mod": "ofdm", "n_samples": 1024, "n_fft": 16, "cp_len": 0, "n_used": 8},
    {"mod": "2fsk", "n_samples": 2048, "mod_index": 0.1},
    {"mod": "2fsk", "n_samples": 2048, "mod_index": 2.0},
    {"mod": "wbfm", "n_samples": 4096, "msg_bw": 1000.0, "freq_dev": 400000.0},
    {"mod": "qpsk", "n_samples": 4096, "impairments": {"awgn": {"enabled": True, "snr_db": -20}}},
    {"mod": "qpsk", "n_samples": 4096, "impairments": {"cfo": {"enabled": True, "cfo_hz": 50000}}},
    {"mod": "16qam", "n_samples": 4096, "impairments": {"quantization": {"enabled": True, "bits": 2}}},
    {"mod": "16qam", "n_samples": 4096, "impairments": {"clipping": {"enabled": True, "headroom_db": 0}}},
    {"mod": "qpsk", "n_samples": 4096, "impairments": {"pa": {"enabled": True, "ibo_db": -3, "model": "saleh"}}},
    {"mod": "qpsk", "n_samples": 4096, "impairments": {"fading": {"enabled": True, "kind": "rayleigh", "doppler_hz": 5000, "n_taps": 8, "tap_spacing_us": 20}}},
    {"mod": "qpsk", "n_samples": 4096, "rx_timing_recovery": False, "rx_matched_filter": False},
]
for cfg in EXTREMES:
    checked += 1
    try:
        r = build_response(cfg)
        b = bad(r)
        if b: fails.append((cfg.get("mod"), str(cfg)[:70], f"non-finite at {b}"))
    except Exception as exc:
        fails.append((cfg.get("mod"), str(cfg)[:70], f"{type(exc).__name__}: {exc}"))
        traceback.print_exc()

print(f"{checked} configurations exercised")
if fails:
    print(f"{len(fails)} FAILURES:")
    for f in fails[:40]: print("  ", f)
else:
    print("no failures")
sys.exit(1 if fails else 0)
