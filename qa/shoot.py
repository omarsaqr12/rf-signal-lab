"""Screenshot harness.  Drives the real page in a real browser and captures
what a student would actually see, so the visuals can be inspected rather than
assumed."""
import json, os, sys, time
from playwright.sync_api import sync_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/rfshots"
URL = "http://127.0.0.1:8765/"
os.makedirs(OUT, exist_ok=True)

# name -> (config patch applied through the page's own controls)
CASES = json.load(open(os.path.join(os.path.dirname(__file__), "cases.json")))


def apply(page, cfg):
    page.evaluate("""(cfg) => {
      const $=s=>document.querySelector(s);
      $('#mod').value = cfg.mod; $('#mod').dispatchEvent(new Event('change'));
      const set=(id,v)=>{const e=$('#'+id); if(e&&v!==undefined){e.value=v;
        e.dispatchEvent(new Event('input'));}};
      set('nsamp',cfg.n_samples); set('sps',cfg.sps); set('beta',cfg.rolloff);
      set('seed',cfg.seed); set('fs',cfg.fs);
      if(cfg.rx_timing_recovery!==undefined){const e=$('#rxtr'); e.checked=cfg.rx_timing_recovery;}
      document.querySelectorAll('.imp').forEach(n=>n.classList.remove('on'));
      for (const [k,v] of Object.entries(cfg.impairments||{})){
        const n=$('#imp-'+k); if(!n) continue; n.classList.add('on');
        for (const [pk,pv] of Object.entries(v)){ if(pk==='enabled') continue;
          const inp=$(`#p-${k}-${pk}`); if(inp){ inp.value=pv;
            inp.dispatchEvent(new Event('input')); } }
      }
      window.__go && window.__go();
    }""", cfg)


with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1800, "height": 1150}, device_scale_factor=1.5)
    errs = []
    pg.on("console", lambda m: errs.append(f"[{m.type}] {m.text}") if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(f"[pageerror] {e}"))
    pg.goto(URL, wait_until="networkidle")
    pg.wait_for_selector("#grid .card canvas", timeout=15000)

    # expose a re-run hook so the harness can drive the page's own pipeline
    pg.evaluate("window.__go = () => { document.querySelector('#mod')"
                ".dispatchEvent(new Event('change')); }")

    index = []
    for case in CASES:
        name, cfg = case["name"], case["config"]
        apply(pg, cfg)
        pg.wait_for_timeout(700)
        pg.wait_for_function("!document.body.classList.contains('loading')", timeout=15000)
        pg.wait_for_timeout(450)
        full = os.path.join(OUT, f"{name}.png")
        pg.screenshot(path=full)
        shots = {"full": full}
        # individual plot cards, so each visual can be inspected on its own
        for want in case.get("cards", []):
            h = pg.query_selector_all("#grid .card")
            for c in h:
                t = c.query_selector("h4")
                if t and want.lower() in t.inner_text().lower():
                    p = os.path.join(OUT, f"{name}__" + "".join(c if c.isalnum() else "_" for c in want) + ".png")
                    c.screenshot(path=p); shots[want] = p
                    break
        state = pg.evaluate("() => { const r=window.__state ? window.__state() : null; return r; }")
        index.append({"name": name, "config": cfg, "shots": shots, "state": state})
        print(f"shot {name}: {', '.join(shots.keys())}")

    json.dump(index, open(os.path.join(OUT, "index.json"), "w"), indent=1)
    if errs:
        print("\nCONSOLE ERRORS:")
        for e in errs[:40]:
            print("  ", e)
    else:
        print("\nno console errors")
    b.close()
