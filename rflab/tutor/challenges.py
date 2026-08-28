"""Blind identification challenges.

The point is not the score.  It is that you look at the plots and commit to an
answer before the label is revealed, which is the only way to find out whether
the associations have actually stuck.
"""
import hashlib
import numpy as np

CHALLENGES = {
    "identify_modulation": {
        "title": "Identify the modulation",
        "prompt": "A signal has been generated with a hidden modulation and no impairments "
                  "beyond mild noise. Work out what it is from the plots.",
        "hint": "Start with the magnitude plot: is the envelope constant? That splits the "
                "candidates in half before you look at anything else. Then use the "
                "constellation for the phase/amplitude families and the instantaneous "
                "frequency for the rest.",
        "pool": ["bpsk", "qpsk", "8psk", "16qam", "64qam", "pam4", "2fsk", "4fsk", "gmsk", "ofdm"],
        "answer_key": "mod",
    },
    "identify_impairment": {
        "title": "Identify the impairment",
        "prompt": "A known modulation has one hidden impairment applied. Which one?",
        "hint": "The cluster shape is the fastest discriminator. Round clouds mean additive "
                "noise. Arcs stretched along the circle mean a phase-domain cause. Smearing in "
                "and out means an amplitude-domain cause. A pattern that has moved without "
                "blurring means DC offset. A pattern that rotated rigidly means phase offset.",
        "pool": ["awgn", "cfo", "phase_offset", "phase_noise", "dc_offset", "iq_imbalance",
                 "pa", "clipping", "quantization", "clock_offset", "interference", "multipath"],
        "answer_key": "impairment",
    },
    "awgn_vs_phase_noise": {
        "title": "Additive noise or phase noise?",
        "prompt": "The constellation is blurred. Is the cause additive noise or phase noise?",
        "hint": "Both blur. Only one blurs isotropically. Look at whether the clouds are round "
                "or stretched along the arc, and whether outer points are hit harder than inner "
                "ones.",
        "pool": ["awgn", "phase_noise"],
        "answer_key": "impairment",
    },
    "dc_vs_phase_offset": {
        "title": "DC offset or phase offset?",
        "prompt": "The constellation is not where you expected. Has it moved, or turned?",
        "hint": "A DC offset translates every point by the same vector, so the pattern keeps its "
                "orientation and loses its centring. A phase offset rotates about the origin, so "
                "the centring is kept and the orientation changes. Check the FFT too: only one "
                "of them puts a spike at 0 Hz.",
        "pool": ["dc_offset", "phase_offset"],
        "answer_key": "impairment",
    },
    "rayleigh_vs_rician": {
        "title": "Rayleigh or Rician?",
        "prompt": "A fading channel is active. Is there a dominant line-of-sight path?",
        "hint": "Look at magnitude versus time and the amplitude histogram. Rayleigh has no "
                "dominant path, so deep fades are routine and the envelope regularly collapses. "
                "Rician has a stable component holding the envelope up, so the fades are "
                "shallower and the histogram peaks away from zero.",
        "pool": ["rayleigh", "rician"],
        "answer_key": "fading_kind",
    },
    "estimate_cfo": {
        "title": "Estimate the frequency offset by eye",
        "prompt": "Read the carrier frequency offset off the plots, then check your answer.",
        "hint": "The unwrapped phase plot is the direct route: its slope is 2.pi.df. Count how "
                "many full turns the constellation makes across the frame and divide by the "
                "frame duration. Or read the shift of the spectrum.",
        "pool": None,
        "answer_key": "cfo_hz",
        "numeric": True,
    },
    "clipping_or_compression": {
        "title": "Hard clipping or smooth compression?",
        "prompt": "The amplitude is being limited. Is it a hard clip or an amplifier bending over?",
        "hint": "The AM/AM transfer curve settles this immediately: hard clipping gives a flat "
                "ceiling with samples piled exactly on it, while amplifier compression gives a "
                "smooth bend. The amplitude histogram shows the same thing.",
        "pool": ["clipping", "pa"],
        "answer_key": "impairment",
    },
    "fsk_order": {
        "title": "How many frequency states?",
        "prompt": "An FSK-family signal is present. How many distinct frequency levels does it use?",
        "hint": "Instantaneous frequency, not the constellation. Count the levels the trace "
                "dwells on. The spectrogram shows the same thing as horizontal bars.",
        "pool": ["2fsk", "4fsk"],
        "answer_key": "mod",
    },
}

_LEVELS = {
    "awgn": lambda r: {"enabled": True, "snr_db": float(r.choice([3, 6, 10, 14]))},
    "cfo": lambda r: {"enabled": True, "cfo_hz": float(r.choice([150, 400, 900, 2500]))},
    "phase_offset": lambda r: {"enabled": True, "deg": float(r.choice([20, 35, 50, 70]))},
    "phase_noise": lambda r: {"enabled": True, "rms_deg": float(r.choice([2, 4, 7]))},
    "dc_offset": lambda r: {"enabled": True, "i": float(r.choice([0.15, 0.25, 0.4])),
                            "q": float(r.choice([0.0, 0.1, -0.15]))},
    "iq_imbalance": lambda r: {"enabled": True, "gain_db": float(r.choice([1.0, 1.8, 2.5])),
                               "phase_deg": float(r.choice([5, 8, 12]))},
    "pa": lambda r: {"enabled": True, "ibo_db": float(r.choice([0.0, 1.5, 3.0]))},
    "clipping": lambda r: {"enabled": True, "headroom_db": float(r.choice([1.5, 2.5, 3.5]))},
    "quantization": lambda r: {"enabled": True, "bits": int(r.choice([3, 4, 5]))},
    "clock_offset": lambda r: {"enabled": True, "ppm": float(r.choice([200, 400, 800]))},
    "interference": lambda r: {"enabled": True, "sir_db": float(r.choice([0, 5, 10])),
                               "kind": "cw",
                               "freq_offset_hz": float(r.choice([-200e3, 60e3, 180e3]))},
    "multipath": lambda r: {"enabled": True, "delays_us": [0.0, float(r.choice([2, 4, 8]))],
                            "gains_db": [0.0, float(r.choice([-2, -4, -6]))]},
}


def _seed_of(token):
    return int(hashlib.sha256(token.encode()).hexdigest()[:8], 16)


def make(kind, token):
    """Build a hidden configuration.  The token is what the UI holds; the answer
    is derived from it, so the answer never travels to the browser early."""
    spec = CHALLENGES.get(kind)
    if not spec:
        return None
    r = np.random.default_rng(_seed_of(token))
    cfg = {"n_samples": 8192, "seed": int(r.integers(0, 10000)), "sps": 8}
    answer = {}

    if kind == "identify_modulation":
        mod = str(r.choice(spec["pool"]))
        cfg["mod"] = mod
        cfg["impairments"] = {"awgn": {"enabled": True, "snr_db": float(r.choice([18, 22, 26]))}}
        answer = {"value": mod, "label": mod.upper()}
    elif kind == "fsk_order":
        mod = str(r.choice(spec["pool"]))
        cfg["mod"] = mod
        cfg["impairments"] = {"awgn": {"enabled": True, "snr_db": 20.0}}
        answer = {"value": mod, "label": f"{mod.upper()} ({mod[0]} frequency states)"}
    elif kind == "rayleigh_vs_rician":
        kindf = str(r.choice(["rayleigh", "rician"]))
        cfg["mod"] = str(r.choice(["qpsk", "16qam"]))
        cfg["impairments"] = {
            "fading": {"enabled": True, "kind": kindf,
                       "k_factor_db": float(r.choice([6, 10, 12])),
                       "doppler_hz": float(r.choice([300, 600, 1200])), "n_taps": 1},
            "awgn": {"enabled": True, "snr_db": 25.0}}
        answer = {"value": kindf, "label": kindf.capitalize()}
    elif kind == "estimate_cfo":
        f0 = float(r.choice([120, 300, 750, 1500, 3000]))
        cfg["mod"] = str(r.choice(["qpsk", "8psk", "16qam"]))
        cfg["impairments"] = {"cfo": {"enabled": True, "cfo_hz": f0},
                              "awgn": {"enabled": True, "snr_db": 22.0}}
        answer = {"value": f0, "label": f"{f0:.0f} Hz",
                  "tolerance": max(0.2 * f0, 50),
                  "check": "within 20% counts as correct"}
    else:
        key = str(r.choice(spec["pool"]))
        cfg["mod"] = str(r.choice(["qpsk", "16qam", "8psk"]))
        imps = {_k: v for _k, v in [(key, _LEVELS[key](r))]}
        if key != "awgn":
            imps["awgn"] = {"enabled": True, "snr_db": 26.0}
        cfg["impairments"] = imps
        answer = {"value": key, "label": key.replace("_", " ")}

    return {"kind": kind, "title": spec["title"], "prompt": spec["prompt"],
            "hint": spec["hint"], "options": spec["pool"],
            "numeric": spec.get("numeric", False),
            "config": cfg, "answer": answer}


def grade(kind, token, guess):
    ch = make(kind, token)
    if not ch:
        return {"ok": False}
    a = ch["answer"]
    if ch["numeric"]:
        try:
            g = float(guess)
        except (TypeError, ValueError):
            return {"correct": False, "answer": a, "note": "Enter a number in Hz."}
        ok = abs(g - a["value"]) <= a["tolerance"]
        return {"correct": ok, "answer": a, "your_guess": g,
                "note": (f"The true offset was {a['value']:.0f} Hz; you said {g:.0f} Hz, "
                         f"an error of {abs(g-a['value']):.0f} Hz "
                         f"({100*abs(g-a['value'])/max(a['value'],1):.0f}%).")}
    ok = str(guess).lower() == str(a["value"]).lower()
    return {"correct": ok, "answer": a, "your_guess": guess,
            "note": ("Correct." if ok else f"The answer was {a['label']}.")}
