/* Minimal canvas plotting core.
   Written by hand rather than pulled from a chart library because the
   annotations here are the teaching content -- ideal symbol positions,
   decision boundaries, tolerance rings, bandwidth markers, eye openings --
   and those need exact control over placement in data coordinates. */

/* Palette is read from CSS custom properties so the two themes share one
   source of truth: change a token in style.css and the plots follow. */
export const C = {};

function cssVar(cs, name, fallback) {
  const v = cs.getPropertyValue(name).trim();
  return v || fallback;
}

export function refreshTheme() {
  const cs = getComputedStyle(document.documentElement);
  Object.assign(C, {
    bg:         cssVar(cs, '--bg', '#0a0d12'),
    panel:      cssVar(cs, '--plot-bg', '#111620'),
    grid:       cssVar(cs, '--plot-grid', '#161d27'),
    gridStrong: cssVar(cs, '--plot-grid2', '#212b39'),
    axis:       cssVar(cs, '--plot-axis', '#3a4658'),
    tagbg:      cssVar(cs, '--plot-tagbg', '#080b10'),
    bound:      cssVar(cs, '--plot-bound', '#243044'),
    symtick:    cssVar(cs, '--plot-symtick', '#1e2836'),
    tx:         cssVar(cs, '--tx', '#dae2ed'),
    tx2:        cssVar(cs, '--tx2', '#93a1b5'),
    tx3:        cssVar(cs, '--tx3', '#65758c'),
    live:       cssVar(cs, '--live', '#38d6e8'),
    clean:      cssVar(cs, '--clean', '#f2a93b'),
    ideal:      cssVar(cs, '--ideal', '#8b9bb4'),
    ok:         cssVar(cs, '--ok', '#4ec97a'),
    warn:       cssVar(cs, '--warn', '#f0c246'),
    bad:        cssVar(cs, '--bad', '#ef6b5e'),
    info:       cssVar(cs, '--info', '#8b7ff0'),
    mag:        cssVar(cs, '--mag', '#c77dff'),
    heat:       cssVar(cs, '--heat', 'dark'),
  });
  return C;
}
refreshTheme();

const MONO = "11px 'SF Mono',ui-monospace,Menlo,Consolas,monospace";
const MONO_S = "10px 'SF Mono',ui-monospace,Menlo,Consolas,monospace";

/* Time colour ramp: deep blue (start of frame) -> cyan -> amber (end).
   Perceptually ordered so "which samples came later" is readable at a glance. */
const TIME_STOPS = {
  dark:  [[0.00,42,68,140],[0.30,40,150,190],[0.58,56,214,232],
          [0.80,190,200,120],[1.00,242,169,59]],
  /* On white, a pale start would vanish, so the light ramp runs
     deep-blue -> teal -> olive -> burnt-amber: all dark enough to read, and
     still monotonic so "later in the frame" stays legible. */
  light: [[0.00,32,52,120],[0.30,17,110,140],[0.58,11,127,147],
          [0.80,120,120,40],[1.00,168,98,5]],
};

export function timeColor(t, alpha) {
  t = Math.max(0, Math.min(1, t));
  const stops = TIME_STOPS[C.heat === 'light' ? 'light' : 'dark'];
  let i = 0; while (i < stops.length-2 && t > stops[i+1][0]) i++;
  const a = stops[i], b = stops[i+1];
  const u = (t - a[0]) / (b[0] - a[0] || 1);
  const r = Math.round(a[1]+(b[1]-a[1])*u), g = Math.round(a[2]+(b[2]-a[2])*u),
        bl = Math.round(a[3]+(b[3]-a[3])*u);
  return `rgba(${r},${g},${bl},${alpha===undefined?1:alpha})`;
}

const HEAT_STOPS = {
  /* On a dark page, stronger reads as brighter.  On a light page that
     convention inverts -- a near-white "hot" pixel would disappear into the
     background -- so the light ramp runs pale to dark instead. */
  dark:  [[0,8,12,28],[0.25,20,60,110],[0.5,32,160,180],[0.75,220,200,90],[1,255,252,235]],
  light: [[0,253,254,255],[0.34,222,236,243],[0.58,132,190,208],[0.80,38,116,150],[1,10,26,48]],
};

export function heatColor(v) {
  v = Math.max(0, Math.min(1, v));
  const s = HEAT_STOPS[C.heat === 'light' ? 'light' : 'dark'];
  let i = 0; while (i < s.length-2 && v > s[i+1][0]) i++;
  const a = s[i], b = s[i+1], u = (v-a[0])/(b[0]-a[0]||1);
  return `rgb(${Math.round(a[1]+(b[1]-a[1])*u)},${Math.round(a[2]+(b[2]-a[2])*u)},${Math.round(a[3]+(b[3]-a[3])*u)})`;
}

function niceTicks(lo, hi, target) {
  if (!(isFinite(lo) && isFinite(hi)) || hi <= lo) return [lo || 0];
  const raw = (hi - lo) / Math.max(2, target);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / mag;
  const step = (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
  const out = [];
  for (let v = Math.ceil(lo/step)*step; v <= hi + step*1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

function fmt(v, step) {
  if (v === 0) return '0';
  const a = Math.abs(v);
  if (a >= 1e6) return (v/1e6).toFixed(a/1e6 < 10 ? 2 : 1) + 'M';
  if (a >= 1e4) return (v/1e3).toFixed(0) + 'k';
  const d = step && step < 1 ? Math.min(4, Math.ceil(-Math.log10(step))) : (a < 1 ? 2 : a < 10 ? 1 : 0);
  return v.toFixed(d);
}

export class Plot {
  constructor(canvas, opts = {}) {
    this.cv = canvas;
    this.o = Object.assign({ padL: 46, padR: 12, padT: 10, padB: 26, square: false }, opts);
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || 400;
    const h = opts.height || 220;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    canvas.style.height = h + 'px';
    const g = canvas.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    this.g = g; this.w = w; this.h = h; this.dpr = dpr;
    this.L = this.o.padL; this.R = w - this.o.padR;
    this.T = this.o.padT; this.B = h - this.o.padB;
  }

  domain(x0, x1, y0, y1) {
    if (!(isFinite(x0)&&isFinite(x1))) { x0 = 0; x1 = 1; }
    if (!(isFinite(y0)&&isFinite(y1))) { y0 = 0; y1 = 1; }
    if (x1 === x0) { x0 -= 1; x1 += 1; }
    if (y1 === y0) { y0 -= 1; y1 += 1; }
    if (this.o.square) {
      /* Letterbox the *drawing area* into a centred square rather than
         inflating the data range.  Stretching the domain to match a wide,
         short panel is technically "equal units per pixel" but it pushes the
         data into a sliver in the middle and wastes the panel -- which is
         exactly what it did before this was fixed. */
      const pw = this.R - this.L, ph = this.B - this.T;
      const side = Math.min(pw, ph);
      const cxp = (this.L + this.R) / 2, cyp = (this.T + this.B) / 2;
      this.L = cxp - side/2; this.R = cxp + side/2;
      this.T = cyp - side/2; this.B = cyp + side/2;
      const cx = (x0+x1)/2, cy = (y0+y1)/2;
      const half = Math.max(x1-x0, y1-y0) / 2;
      x0 = cx - half; x1 = cx + half; y0 = cy - half; y1 = cy + half;
    }
    this.x0=x0; this.x1=x1; this.y0=y0; this.y1=y1;
    return this;
  }
  px(x){ return this.L + (x - this.x0)/(this.x1 - this.x0) * (this.R - this.L); }
  py(y){ return this.B - (y - this.y0)/(this.y1 - this.y0) * (this.B - this.T); }
  ux(p){ return this.x0 + (p - this.L)/(this.R - this.L) * (this.x1 - this.x0); }
  uy(p){ return this.y0 + (this.B - p)/(this.B - this.T) * (this.y1 - this.y0); }

  frame(xlabel, ylabel, opt = {}) {
    const g = this.g;
    g.save(); g.fillStyle = C.panel; g.fillRect(this.L, this.T, this.R-this.L, this.B-this.T);
    const xt = opt.xticks || niceTicks(this.x0, this.x1, this.w > 420 ? 7 : 5);
    const yt = opt.yticks || niceTicks(this.y0, this.y1, 5);
    const xs = xt.length>1?xt[1]-xt[0]:1, ys = yt.length>1?yt[1]-yt[0]:1;
    g.strokeStyle = C.grid; g.lineWidth = 1; g.beginPath();
    for (const v of xt){ const p = Math.round(this.px(v))+.5; if(p<this.L||p>this.R)continue;
      g.moveTo(p, this.T); g.lineTo(p, this.B); }
    for (const v of yt){ const p = Math.round(this.py(v))+.5; if(p<this.T||p>this.B)continue;
      g.moveTo(this.L, p); g.lineTo(this.R, p); }
    g.stroke();
    if (this.x0 < 0 && this.x1 > 0) { g.strokeStyle=C.gridStrong; g.beginPath();
      const p=Math.round(this.px(0))+.5; g.moveTo(p,this.T); g.lineTo(p,this.B); g.stroke(); }
    if (this.y0 < 0 && this.y1 > 0) { g.strokeStyle=C.gridStrong; g.beginPath();
      const p=Math.round(this.py(0))+.5; g.moveTo(this.L,p); g.lineTo(this.R,p); g.stroke(); }
    g.strokeStyle = C.axis; g.lineWidth = 1;
    g.strokeRect(Math.round(this.L)+.5, Math.round(this.T)+.5,
                 Math.round(this.R-this.L), Math.round(this.B-this.T));
    g.fillStyle = C.tx3; g.font = MONO_S; g.textAlign='center'; g.textBaseline='top';
    for (const v of xt){ const p=this.px(v); if(p<this.L-1||p>this.R+1)continue;
      g.fillText(opt.xfmt?opt.xfmt(v):fmt(v,xs), p, this.B+4); }
    g.textAlign='right'; g.textBaseline='middle';
    for (const v of yt){ const p=this.py(v); if(p<this.T-1||p>this.B+1)continue;
      g.fillText(opt.yfmt?opt.yfmt(v):fmt(v,ys), this.L-5, p); }
    if (xlabel){ g.fillStyle=C.tx3; g.font=MONO_S; g.textAlign='right'; g.textBaseline='bottom';
      g.fillText(xlabel, this.R, this.h-1); }
    if (ylabel){ g.save(); g.translate(9, this.T+2); g.rotate(-Math.PI/2);
      g.fillStyle=C.tx3; g.font=MONO_S; g.textAlign='right'; g.textBaseline='top';
      g.fillText(ylabel, 0, 0); g.restore(); }
    g.restore(); return this;
  }

  clip(fn){ const g=this.g; g.save(); g.beginPath();
    g.rect(this.L,this.T,this.R-this.L,this.B-this.T); g.clip(); fn(g); g.restore(); }

  line(xs, ys, color, width = 1.2, alpha = 1) {
    this.clip(g => { g.globalAlpha=alpha; g.strokeStyle=color; g.lineWidth=width;
      g.lineJoin='round'; g.beginPath();
      let on=false;
      for (let i=0;i<xs.length;i++){ const y=ys[i];
        if (y===null||!isFinite(y)){ on=false; continue; }
        const px=this.px(xs[i]), py=this.py(y);
        if(!on){ g.moveTo(px,py); on=true; } else g.lineTo(px,py); }
      g.stroke(); g.globalAlpha=1; });
    return this;
  }

  /* Many short traces sharing one style -- eye diagrams, trajectories. */
  traces(list, color, width = 0.7, alpha = 0.35, xs) {
    this.clip(g => { g.globalAlpha=alpha; g.strokeStyle=color; g.lineWidth=width;
      for (const ys of list){ g.beginPath();
        for (let i=0;i<ys.length;i++){ const px=this.px(xs[i]), py=this.py(ys[i]);
          i?g.lineTo(px,py):g.moveTo(px,py); }
        g.stroke(); }
      g.globalAlpha=1; });
    return this;
  }

  scatter(xs, ys, opt = {}) {
    const r = opt.r || 1.5, tc = opt.t;
    this.clip(g => {
      g.globalAlpha = opt.alpha === undefined ? 0.85 : opt.alpha;
      if (!tc) g.fillStyle = opt.color || C.live;
      for (let i=0;i<xs.length;i++){
        const px=this.px(xs[i]), py=this.py(ys[i]);
        if (px<this.L-3||px>this.R+3||py<this.T-3||py>this.B+3) continue;
        if (tc) g.fillStyle = timeColor(tc[i]);
        g.beginPath(); g.arc(px,py,r,0,6.2832); g.fill();
      }
      g.globalAlpha=1;
    });
    return this;
  }

  bars(xs, ys, color, opt={}) {
    const n = xs.length;
    const bw = Math.max(1, (this.R-this.L)/n * (opt.frac||0.8));
    this.clip(g=>{ g.globalAlpha=opt.alpha===undefined?0.85:opt.alpha;
      g.fillStyle=color;
      const base=this.py(Math.max(this.y0,0));
      for(let i=0;i<n;i++){ const px=this.px(xs[i]), py=this.py(ys[i]);
        g.fillRect(px-bw/2, Math.min(py,base), bw, Math.abs(base-py)); }
      g.globalAlpha=1; });
    return this;
  }

  stems(xs, ys, color) {
    this.clip(g=>{ g.strokeStyle=color; g.fillStyle=color; g.lineWidth=1.4;
      const base=this.py(this.y0);
      for(let i=0;i<xs.length;i++){ const px=this.px(xs[i]), py=this.py(ys[i]);
        g.beginPath(); g.moveTo(px,base); g.lineTo(px,py); g.stroke();
        g.beginPath(); g.arc(px,py,2.6,0,6.2832); g.fill(); } });
    return this;
  }

  heat(S, xs, ys, vmin, vmax) {
    /* putImageData bypasses the canvas transform, so the buffer has to be built
       at device resolution and written at device coordinates.  Building it in
       CSS pixels instead silently paints only 1/dpr of the panel -- which looks
       like "the signal stopped early" rather than like a bug. */
    const g = this.g, nr = S.length, nc = S[0].length, dpr = this.dpr;
    const iw = (this.R - this.L) * dpr, ih = (this.B - this.T) * dpr;
    const W = Math.max(1, Math.round(iw)), H = Math.max(1, Math.round(ih));
    const img = g.createImageData(W, H);
    const x0 = xs[0], x1 = xs[xs.length-1], y0 = ys[0], y1 = ys[ys.length-1];
    const rgb = new Array(65);
    for (let k=0;k<=64;k++){ const m = heatColor(k/64).match(/\d+/g);
      rgb[k] = [+m[0], +m[1], +m[2]]; }
    for (let py=0; py<H; py++){
      const yv = y1 - (py/(H-1||1))*(y1-y0);
      let r = Math.round((yv - y0)/((y1-y0)||1) * (nr-1));
      r = Math.max(0, Math.min(nr-1, r));
      const row = S[r];
      for (let px=0; px<W; px++){
        const xv = x0 + (px/(W-1||1))*(x1-x0);
        let c = Math.round((xv - x0)/((x1-x0)||1) * (nc-1));
        c = Math.max(0, Math.min(nc-1, c));
        let v = (row[c]-vmin)/((vmax-vmin)||1);
        v = v<0?0:v>1?1:v;
        const col = rgb[Math.round(v*64)];
        const o = (py*W+px)*4;
        img.data[o]=col[0]; img.data[o+1]=col[1]; img.data[o+2]=col[2]; img.data[o+3]=255;
      }
    }
    g.putImageData(img, Math.round(this.L*dpr), Math.round(this.T*dpr));
    return this;
  }

  /* ---- annotation primitives ---- */
  vline(x, color, opt={}) {
    this.clip(g=>{ g.strokeStyle=color; g.lineWidth=opt.w||1;
      if(opt.dash!==false) g.setLineDash(opt.dash||[4,3]);
      const p=Math.round(this.px(x))+.5; g.beginPath(); g.moveTo(p,this.T); g.lineTo(p,this.B);
      g.stroke(); g.setLineDash([]); });
    if (opt.label) this.tag(this.px(x), opt.labelY||this.T+3, opt.label, color, opt.align||'left');
    return this;
  }
  hline(y, color, opt={}) {
    this.clip(g=>{ g.strokeStyle=color; g.lineWidth=opt.w||1;
      if(opt.dash!==false) g.setLineDash(opt.dash||[4,3]);
      const p=Math.round(this.py(y))+.5; g.beginPath(); g.moveTo(this.L,p); g.lineTo(this.R,p);
      g.stroke(); g.setLineDash([]); });
    if (opt.label) this.tag(opt.labelX||this.R-3, this.py(y)-8, opt.label, color, 'right');
    return this;
  }
  band(x0, x1, color, alpha=0.09) {
    this.clip(g=>{ g.globalAlpha=alpha; g.fillStyle=color;
      const a=this.px(x0), b=this.px(x1); g.fillRect(Math.min(a,b),this.T,Math.abs(b-a),this.B-this.T);
      g.globalAlpha=1; });
    return this;
  }
  hband(y0, y1, color, alpha=0.09) {
    this.clip(g=>{ g.globalAlpha=alpha; g.fillStyle=color;
      const a=this.py(y0), b=this.py(y1); g.fillRect(this.L,Math.min(a,b),this.R-this.L,Math.abs(b-a));
      g.globalAlpha=1; });
    return this;
  }
  ring(x, y, rData, color, opt={}) {
    this.clip(g=>{ g.strokeStyle=color; g.lineWidth=opt.w||1;
      if(opt.dash) g.setLineDash(opt.dash);
      const cx=this.px(x), cy=this.py(y);
      const rp=Math.abs(this.px(x+rData)-cx);
      g.beginPath(); g.arc(cx,cy,rp,0,6.2832); g.stroke(); g.setLineDash([]); });
    return this;
  }
  marker(x, y, color, opt={}) {
    this.clip(g=>{ const px=this.px(x), py=this.py(y), r=opt.r||4;
      g.strokeStyle=color; g.lineWidth=opt.w||1.4;
      if (opt.shape==='cross'){ g.beginPath(); g.moveTo(px-r,py); g.lineTo(px+r,py);
        g.moveTo(px,py-r); g.lineTo(px,py+r); g.stroke(); }
      else { g.beginPath(); g.arc(px,py,r,0,6.2832); g.stroke();
        if(opt.fill){ g.fillStyle=opt.fill; g.fill(); } } });
    return this;
  }
  segment(x0,y0,x1,y1,color,opt={}) {
    this.clip(g=>{ g.strokeStyle=color; g.lineWidth=opt.w||1;
      if(opt.dash) g.setLineDash(opt.dash);
      g.beginPath(); g.moveTo(this.px(x0),this.py(y0)); g.lineTo(this.px(x1),this.py(y1));
      g.stroke(); g.setLineDash([]); });
    return this;
  }
  tag(px, py, text, color, align='left') {
    const g=this.g; g.save(); g.font=MONO_S; g.textBaseline='top';
    const w=g.measureText(text).width+7;
    let x = align==='right' ? px-w : align==='center' ? px-w/2 : px+3;
    x = Math.max(this.L+1, Math.min(x, this.R-w-1));
    py = Math.max(this.T+1, Math.min(py, this.B-14));
    g.globalAlpha=.88; g.fillStyle=C.tagbg; g.fillRect(x,py,w,13);
    g.globalAlpha=1; g.strokeStyle=color; g.lineWidth=1;
    g.beginPath(); g.moveTo(x,py+.5); g.lineTo(x,py+12.5); g.stroke();
    g.fillStyle=color; g.textAlign='left'; g.fillText(text, x+4, py+1.5);
    g.restore(); return this;
  }
  note(text, color, corner='tr') {
    const g=this.g; g.save(); g.font=MONO_S; g.textBaseline='top';
    const w=g.measureText(text).width+8;
    const x = corner.includes('r') ? this.R-w-4 : this.L+4;
    const y = corner.includes('b') ? this.B-16 : this.T+4;
    g.globalAlpha=.88; g.fillStyle=C.tagbg; g.fillRect(x,y,w,14);
    g.globalAlpha=1; g.fillStyle=color||C.tx2; g.textAlign='left'; g.fillText(text,x+4,y+2);
    g.restore(); return this;
  }
  empty(msg) {
    const g=this.g; g.save(); g.fillStyle=C.panel; g.fillRect(0,0,this.w,this.h);
    g.fillStyle=C.tx3; g.font=MONO; g.textAlign='center'; g.textBaseline='middle';
    const words = msg.split(' '); const lines=[]; let cur='';
    for (const wd of words){ if ((cur+' '+wd).length>44){ lines.push(cur); cur=wd; }
      else cur = cur ? cur+' '+wd : wd; }
    lines.push(cur);
    lines.forEach((l,i)=>g.fillText(l, this.w/2, this.h/2 + (i-(lines.length-1)/2)*15));
    g.restore(); return this;
  }
}

export const ext = (a) => {
  let lo=Infinity, hi=-Infinity;
  for (const v of a){ if(v===null||!isFinite(v))continue; if(v<lo)lo=v; if(v>hi)hi=v; }
  if(!isFinite(lo)){ lo=0; hi=1; }
  return [lo,hi];
};
export const pad = ([lo,hi], f=0.06) => { const d=(hi-lo)||1; return [lo-d*f, hi+d*f]; };
