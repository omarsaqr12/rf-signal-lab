"""Local web server for the RF Signal Lab.

Standard library only, deliberately: the lab should start with `python3 -m
rflab.server` on any machine that has numpy and scipy, with nothing to install.
"""
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from rflab.experiment import run as run_experiment, DEFAULTS
from rflab.dsp.modulators import ALL_MODS
from rflab.dsp.impairments import CHAIN_ORDER, CHAIN_STAGE
from rflab.tutor import narrate as N
from rflab.tutor import challenges as CH
from rflab.tutor.modulations import all_profiles, FAMILY_VIEWS
from rflab.tutor.impairment_profiles import P as IMP_PROFILES, VIEW_PRIORITY
from rflab.tutor.plot_profiles import all_views

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class Enc(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            v = float(o)
            return v if np.isfinite(v) else None
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, complex):
            return {"re": o.real, "im": o.imag}
        if isinstance(o, (bool, np.bool_)):
            return bool(o)
        return super().default(o)


def _clean(o):
    """JSON has no NaN or Infinity; replace them so the browser can parse."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float):
        return o if np.isfinite(o) else None
    if isinstance(o, (np.floating, np.integer)):
        v = float(o)
        return v if np.isfinite(v) else None
    return o


IMPAIRMENT_UI = [
    {"key": "awgn", "label": "AWGN", "params": [
        {"key": "snr_db", "label": "SNR", "unit": "dB", "min": -20, "max": 40, "step": 0.5,
         "default": 15}]},
    {"key": "cfo", "label": "Carrier frequency offset", "params": [
        {"key": "cfo_hz", "label": "CFO", "unit": "Hz", "min": -50000, "max": 50000, "step": 10,
         "default": 1000, "log": True}]},
    {"key": "phase_offset", "label": "Phase offset", "params": [
        {"key": "deg", "label": "Rotation", "unit": "deg", "min": -180, "max": 180, "step": 1,
         "default": 30}]},
    {"key": "phase_noise", "label": "Phase noise", "params": [
        {"key": "linewidth_hz", "label": "Oscillator linewidth", "unit": "Hz", "min": 0,
         "max": 20000, "step": 10, "default": 0},
        {"key": "rms_deg", "label": "Stationary jitter", "unit": "deg RMS", "min": 0, "max": 30,
         "step": 0.1, "default": 3}]},
    {"key": "clock_offset", "label": "Sample clock / timing", "params": [
        {"key": "ppm", "label": "Clock error", "unit": "ppm", "min": -2000, "max": 2000,
         "step": 5, "default": 100},
        {"key": "timing_offset_symbols", "label": "Static timing offset", "unit": "symbols",
         "min": -0.5, "max": 0.5, "step": 0.01, "default": 0}]},
    {"key": "multipath", "label": "Multipath", "params": [
        {"key": "delay2_us", "label": "Second path delay", "unit": "us", "min": 0, "max": 40,
         "step": 0.1, "default": 2},
        {"key": "gain2_db", "label": "Second path gain", "unit": "dB", "min": -30, "max": 0,
         "step": 0.5, "default": -3},
        {"key": "delay3_us", "label": "Third path delay", "unit": "us", "min": 0, "max": 40,
         "step": 0.1, "default": 0},
        {"key": "gain3_db", "label": "Third path gain", "unit": "dB", "min": -40, "max": 0,
         "step": 0.5, "default": -40}]},
    {"key": "fading", "label": "Fading channel", "params": [
        {"key": "kind", "label": "Type", "choices": ["rayleigh", "rician"], "default": "rician"},
        {"key": "k_factor_db", "label": "Rician K", "unit": "dB", "min": -10, "max": 20,
         "step": 0.5, "default": 6},
        {"key": "doppler_hz", "label": "Doppler spread", "unit": "Hz", "min": 0, "max": 5000,
         "step": 10, "default": 200},
        {"key": "n_taps", "label": "Taps", "unit": "", "min": 1, "max": 8, "step": 1,
         "default": 1},
        {"key": "tap_spacing_us", "label": "Tap spacing", "unit": "us", "min": 0.1, "max": 20,
         "step": 0.1, "default": 1}]},
    {"key": "pa", "label": "Power amplifier", "params": [
        {"key": "model", "label": "Model", "choices": ["rapp", "saleh"], "default": "rapp"},
        {"key": "ibo_db", "label": "Input back-off", "unit": "dB", "min": -3, "max": 20,
         "step": 0.25, "default": 6},
        {"key": "rapp_p", "label": "Rapp smoothness p", "unit": "", "min": 0.5, "max": 6,
         "step": 0.1, "default": 2}]},
    {"key": "iq_imbalance", "label": "I/Q imbalance", "params": [
        {"key": "gain_db", "label": "Gain mismatch", "unit": "dB", "min": 0, "max": 6,
         "step": 0.05, "default": 1},
        {"key": "phase_deg", "label": "Phase mismatch", "unit": "deg", "min": 0, "max": 30,
         "step": 0.1, "default": 5}]},
    {"key": "dc_offset", "label": "DC offset", "params": [
        {"key": "i", "label": "I offset", "unit": "x RMS", "min": -1, "max": 1, "step": 0.01,
         "default": 0.2},
        {"key": "q", "label": "Q offset", "unit": "x RMS", "min": -1, "max": 1, "step": 0.01,
         "default": 0}]},
    {"key": "clipping", "label": "Clipping", "params": [
        {"key": "headroom_db", "label": "Headroom above RMS", "unit": "dB", "min": 0, "max": 15,
         "step": 0.1, "default": 3}]},
    {"key": "quantization", "label": "Quantisation", "params": [
        {"key": "bits", "label": "ADC bits", "unit": "", "min": 2, "max": 16, "step": 1,
         "default": 6},
        {"key": "headroom_db", "label": "Headroom", "unit": "dB", "min": 0, "max": 20,
         "step": 0.5, "default": 6}]},
    {"key": "interference", "label": "Interference", "params": [
        {"key": "kind", "label": "Type", "choices": ["cw", "modulated", "chirp"],
         "default": "cw"},
        {"key": "sir_db", "label": "Signal-to-interference", "unit": "dB", "min": -20, "max": 40,
         "step": 0.5, "default": 10},
        {"key": "freq_offset_hz", "label": "Frequency offset", "unit": "Hz", "min": -500000,
         "max": 500000, "step": 1000, "default": 150000},
        {"key": "bandwidth_hz", "label": "Interferer bandwidth", "unit": "Hz", "min": 10000,
         "max": 500000, "step": 5000, "default": 125000}]},
]


def expand_impairments(ui):
    """Translate the flat UI parameters into what the engine expects."""
    out = {}
    for k, v in (ui or {}).items():
        if not v or not v.get("enabled"):
            continue
        p = dict(v)
        if k == "multipath":
            delays, gains = [0.0], [0.0]
            if p.get("delay2_us", 0) > 0 or p.get("gain2_db", -99) > -35:
                delays.append(float(p.get("delay2_us", 2)))
                gains.append(float(p.get("gain2_db", -3)))
            if p.get("gain3_db", -99) > -35:
                delays.append(float(p.get("delay3_us", 4)))
                gains.append(float(p.get("gain3_db", -6)))
            p = {"enabled": True, "delays_us": delays, "gains_db": gains}
        out[k] = p
    return out


def build_response(cfg):
    cfg = dict(cfg or {})
    cfg["impairments"] = expand_impairments(cfg.get("impairments"))
    res = run_experiment(cfg)
    views = N.priority_views(res)
    res["tutor"] = {
        "priority_views": views,
        "explain": {v: N.explain_plot(v, res) for v in views},
        "prediction": N.prediction(res),
        "compare": N.compare(res),
        "why_care": N.why_care(res),
        "next": N.next_experiments(res),
    }
    return res


def meta():
    profs = all_profiles()
    return {
        "modulations": [
            {"key": k, "name": profs[k]["name"], "family": profs[k]["family"],
             "bits": profs[k]["bits"]} for k in ALL_MODS],
        "modulation_profiles": profs,
        "impairments": IMPAIRMENT_UI,
        "impairment_profiles": IMP_PROFILES,
        "chain_order": CHAIN_ORDER,
        "chain_stage": CHAIN_STAGE,
        "view_priority": VIEW_PRIORITY,
        "family_views": FAMILY_VIEWS,
        "views": all_views(),
        "defaults": {k: v for k, v in DEFAULTS.items() if k != "impairments"},
        "challenges": {k: {"title": v["title"], "prompt": v["prompt"], "hint": v["hint"],
                           "options": v["pool"], "numeric": v.get("numeric", False)}
                       for k, v in CH.CHALLENGES.items()},
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(_clean(body), cls=Enc, allow_nan=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/meta":
            return self._send(200, meta())
        if path == "/" or path == "/index.html":
            return self._file("index.html")
        if path.startswith("/static/"):
            return self._file(path[len("/static/"):])
        return self._send(404, {"error": "not found"})

    def _file(self, rel):
        fp = os.path.normpath(os.path.join(WEB, rel))
        if not fp.startswith(WEB) or not os.path.isfile(fp):
            return self._send(404, {"error": "not found"})
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        with open(fp, "rb") as f:
            self._send(200, f.read(), ctype)

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})
        try:
            t0 = time.time()
            if path == "/api/run":
                out = build_response(payload)
                out["server_ms"] = round((time.time() - t0) * 1000, 1)
                return self._send(200, out)
            if path == "/api/challenge":
                ch = CH.make(payload.get("kind"), payload.get("token", "t"))
                if not ch:
                    return self._send(400, {"error": "unknown challenge"})
                res = build_response(ch["config"])
                # The answer stays on the server until the user commits a guess.
                return self._send(200, {
                    "challenge": {k: v for k, v in ch.items() if k not in ("answer", "config")},
                    "result": _hide(res)})
            if path == "/api/grade":
                return self._send(200, CH.grade(payload.get("kind"), payload.get("token", "t"),
                                                payload.get("guess")))
            if path == "/api/reveal":
                ch = CH.make(payload.get("kind"), payload.get("token", "t"))
                return self._send(200, {"config": ch["config"],
                                        "result": build_response(ch["config"])})
        except Exception as exc:                     # surface errors, do not hide them
            traceback.print_exc()
            return self._send(500, {"error": str(exc),
                                    "trace": traceback.format_exc().splitlines()[-6:]})
        return self._send(404, {"error": "not found"})


def _hide(res):
    """Strip every label from a challenge payload so the plots give nothing away."""
    r = json.loads(json.dumps(_clean(res), cls=Enc, allow_nan=False))
    r["signal"] = {k: v for k, v in r["signal"].items()
                   if k in ("fs", "sps", "n_samples", "duration_ms", "symbol_rate", "n_symbols")}
    for k in ("severity", "reports", "verification", "overall", "geometry", "chain",
              "active", "config", "tutor"):
        r.pop(k, None)
    m = r.get("measurements", {})
    for k in list(m):
        if k in ("cumulants_ideal", "constellation_diag", "constellation_diag_clean",
                 "constellation_diag_synced", "cfo_blind", "symbol_rate_blind", "snr_oracle_db",
                 "snr_oracle_reference", "residual_evm_pct", "correctable_fraction",
                 "waveform_evm_pct", "symbol_evm_pct", "implied_cfo_from_sync_hz",
                 "const_gain", "iq_blind", "dc"):
            m.pop(k, None)
    p = r.get("plots", {})
    if p.get("constellation"):
        p["constellation"]["ideal"] = None
        p["constellation"]["symbols_clean"] = None
    for key in ("iq_time", "magnitude", "phase", "inst_freq", "fft", "psd", "papr_ccdf"):
        if p.get(key):
            for f in ("i_clean", "q_clean", "mag_clean", "unwrapped_clean", "f_clean",
                      "mag_clean", "psd_clean", "prob_clean", "channel_envelope",
                      "levels_khz", "nominal_bw_khz"):
                p[key].pop(f, None)
    if p.get("cumulants"):
        p["cumulants"]["ideal"] = None
    if p.get("am_am"):
        p["am_am"].pop("linear_ref", None)
    return r


def serve(port=8765, host="127.0.0.1"):
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"RF Signal Lab -> http://{host}:{port}")
    print("Ctrl-C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        srv.shutdown()


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    serve(p)
