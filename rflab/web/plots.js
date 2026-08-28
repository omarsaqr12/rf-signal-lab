/* One draw function per view.  Annotations are the teaching content, so they
   are drawn in data coordinates against measured quantities -- never decorative. */
import { Plot, C, ext, pad, timeColor } from './render.js';

const F = (v, d=2) => (v===null||v===undefined||!isFinite(v)) ? '--' : v.toFixed(d);
const seq = (n, a, b) => Array.from({length:n}, (_,i)=>a + (b-a)*i/(n-1||1));

/* Default time span per view, in symbol periods.  Showing a whole 512-symbol
   frame in 450 pixels gives under one pixel per symbol, which turns FSK's
   discrete frequency levels into a solid scribble.  The window slider expands
   these; these are just the starting points that make the structure legible. */
const WINDOW_SYMBOLS = { iq_time: 24, inst_freq: 28, magnitude: 90 };
function windowFrac(view, res, ui){
  if (ui.tWinTouched) return ui.tWin;
  const nsym = WINDOW_SYMBOLS[view];
  if (!nsym) return 1;
  const total = res.signal.n_symbols || (res.signal.n_samples/res.signal.sps);
  return Math.min(1, Math.max(0.02, nsym/total));
}

export const HERO = new Set(['spectrogram','eye','ofdm','channel']);

/* ------------------------------------------------------------------ */
export function constellation(cv, res, ui) {
  const p = res.plots.constellation, m = res.measurements, sig = res.signal;
  const d = m.constellation_diag;
  const mode = ui.constMode || (p.has_symbol_view ? 'symbols' : 'raw');
  const src = mode === 'raw' ? p.raw : p.symbols;
  const pl = new Plot(cv, {height: ui.height||400, square:true, padL:40, padB:26});
  if (!src || !src.i.length) return pl.empty('No constellation data.');

  let all = src.i.concat(src.q);
  if (p.ideal) all = all.concat(p.ideal.i, p.ideal.q);
  let [lo,hi] = ext(all); const r = Math.max(Math.abs(lo),Math.abs(hi))*1.12;
  pl.domain(-r, r, -r, r).frame('I','Q');

  // Decision boundaries for the ideal constellation: the Voronoi edges are what
  // "a symbol error" actually means, so they are worth drawing.
  if (p.ideal && ui.showBoundaries !== false && p.ideal.i.length <= 64) {
    const n = p.ideal.i.length;
    pl.clip(g => {
      g.strokeStyle=C.bound; g.lineWidth=1; g.setLineDash([2,3]);
      // Draw each bisector only as far as half the neighbour spacing either
      // side of the midpoint.  Running them to the plot edge produces long
      // diagonals across empty space that read as structure rather than as
      // decision boundaries.
      for (let a=0;a<n;a++) for (let b=a+1;b<n;b++) {
        const ax=p.ideal.i[a], ay=p.ideal.q[a], bx=p.ideal.i[b], by=p.ideal.q[b];
        const dx=bx-ax, dy=by-ay, dd=Math.hypot(dx,dy);
        if (dd > 1.45*(p.scale*(d?d.d_min_scaled:1))) continue;   // near neighbours only
        const mx=(ax+bx)/2, my=(ay+by)/2, L=dd*0.5;
        const ux=-dy/dd, uy=dx/dd;
        g.beginPath();
        g.moveTo(pl.px(mx-ux*L), pl.py(my-uy*L));
        g.lineTo(pl.px(mx+ux*L), pl.py(my+uy*L));
        g.stroke();
      }
      g.setLineDash([]);
    });
  }
  if (ui.showClean && p.symbols_clean && mode==='symbols')
    pl.scatter(p.symbols_clean.i, p.symbols_clean.q, {color:C.clean, r:1.2, alpha:.30});

  if (mode === 'trajectory') {
    const xs = p.raw.i, ys = p.raw.q;
    pl.clip(g=>{ g.lineWidth=.6; g.globalAlpha=.5;
      for(let i=1;i<xs.length;i++){ g.strokeStyle=timeColor(p.raw.t[i]);
        g.beginPath(); g.moveTo(pl.px(xs[i-1]),pl.py(ys[i-1]));
        g.lineTo(pl.px(xs[i]),pl.py(ys[i])); g.stroke(); }
      g.globalAlpha=1; });
  } else {
    pl.scatter(src.i, src.q, ui.colorByTime!==false ? {t:src.t, r: mode==='raw'?1.1:1.7, alpha:.75}
                                                    : {color:C.live, r: mode==='raw'?1.1:1.7, alpha:.6});
  }

  if (p.ideal) {
    for (let i=0;i<p.ideal.i.length;i++)
      pl.marker(p.ideal.i[i], p.ideal.q[i], C.ideal, {r:4.2, w:1.1});
    // Tolerance ring: the radius at which a displaced sample crosses a boundary.
    if (d && d.model_valid && res.geometry.d_min){
      const rr = res.geometry.d_min/2*p.scale;
      pl.ring(p.ideal.i[0], p.ideal.q[0], rr, C.warn, {dash:[3,3], w:1});
      pl.tag(pl.px(p.ideal.i[0]), pl.py(p.ideal.q[0]+rr)-13,
             'd_min/2 decision radius', C.warn, 'center');
    }
  }
  if (d && d.model_valid && ui.showCentroids !== false && d.per_cluster)
    for (const c of d.per_cluster) pl.marker(c.centroid_i, c.centroid_q, C.bad,
                                             {r:2.4, shape:'cross', w:1.2});

  const notes = [];
  if (d) {
    if (!d.model_valid) notes.push('no cluster structure — see tutor');
    else notes.push(`margin ${F(d.separation_sigma,1)}σ · tan/rad ${F(d.tangential_over_radial,2)}`);
  }
  if (notes.length) pl.note(notes[0], d && !d.model_valid ? C.bad : C.tx2, 'tr');
  pl.note(mode==='symbols' ? 'matched filter, 1 sample/symbol'
        : mode==='raw' ? `all samples (${sig.sps}/symbol)` : 'trajectory', C.tx3, 'bl');
  return pl;
}

/* ------------------------------------------------------------------ */
export function iq_time(cv, res, ui) {
  const p = res.plots.iq_time;
  const pl = new Plot(cv, {height: ui.height||210});
  const win = windowFrac('iq_time', res, ui);
  const nMax = Math.max(40, Math.floor(p.t.length*win));
  const t=p.t.slice(0,nMax), I=p.i.slice(0,nMax), Q=p.q.slice(0,nMax);
  pl.domain(t[0], t[t.length-1], ...pad(ext(I.concat(Q)))).frame('time (ms)','amplitude');
  if (ui.showClean!==false){
    pl.line(t, p.i_clean.slice(0,nMax), C.clean, 1, .30);
    pl.line(t, p.q_clean.slice(0,nMax), C.clean, 1, .18);
  }
  // Symbol boundaries: makes samples-per-symbol legible rather than abstract.
  if (p.symbol_period_ms*6 < (t[t.length-1]-t[0])) {
    const nsym = Math.floor((t[t.length-1]-t[0])/p.symbol_period_ms);
    if (nsym < 90) for (let k=0;k<=nsym;k++)
      pl.vline(t[0]+k*p.symbol_period_ms, C.symtick, {dash:[1,4]});
  }
  pl.line(t, I, C.live, 1.3);
  pl.line(t, Q, C.mag, 1.3);
  pl.note(`${res.signal.sps} samples/symbol · showing ${Math.round(win*100)}% of the frame`,
          C.tx3, 'bl');
  return pl;
}

export function magnitude(cv, res, ui) {
  const p = res.plots.magnitude, pl = new Plot(cv,{height:ui.height||190});
  const win=windowFrac('magnitude',res,ui), n=Math.max(40,Math.floor(p.t.length*win));
  const t=p.t.slice(0,n);
  let all=p.mag.slice(0,n).concat(p.mag_clean.slice(0,n));
  pl.domain(t[0],t[t.length-1],0,ext(all)[1]*1.08).frame('time (ms)','|x|');
  pl.hline(p.rms, C.ideal, {dash:[5,4], label:`RMS ${F(p.rms,3)}`});
  if (ui.showClean!==false) pl.line(t,p.mag_clean.slice(0,n),C.clean,1,.35);
  if (p.channel_envelope) pl.line(t,p.channel_envelope.slice(0,n),C.info,1.4,.85);
  pl.line(t,p.mag.slice(0,n),C.live,1.3);
  pl.note(`PAPR ${F(p.papr_db,2)} dB`, C.tx2,'tr');
  return pl;
}

export function phase(cv, res, ui) {
  const p = res.plots.phase, pl = new Plot(cv,{height:ui.height||190});
  const wrapped = ui.phaseWrapped;
  const y  = wrapped ? p.wrapped : p.unwrapped;
  const tx = wrapped ? p.t_raw   : p.t;
  const lbl = wrapped ? 'wrapped phase (rad)' : 'carrier phase (rad)';
  let all = y.slice();
  const showSig = !wrapped && ui.showClean!==false;
  if (showSig) all = all.concat(p.signal_phase);
  pl.domain(tx[0],tx[tx.length-1],...pad(ext(all))).frame('time (ms)', lbl);
  if (showSig) pl.line(p.t_raw, p.signal_phase, C.clean, 1, .38);
  pl.line(tx,y,C.live,1.3);
  if (!wrapped && res.reports.cfo){
    const f=res.reports.cfo.cfo_hz, t0=tx[0], t1=tx[tx.length-1];
    const y0=y[0], y1=y0 + 2*Math.PI*f*(t1-t0)/1000;
    pl.segment(t0,y0,t1,y1,C.warn,{dash:[6,4],w:1.2});
    pl.note(`predicted slope = 2π·${F(f,0)} Hz`, C.warn,'tr');
  }
  if (!wrapped){
    pl.note('cyan = impairment-induced carrier phase' + (showSig?'; amber = the modulation\u2019s own phase':''),
            C.tx3,'bl');
  }
  return pl;
}

export function inst_freq(cv, res, ui) {
  const p = res.plots.inst_freq, pl = new Plot(cv,{height:ui.height||200});
  const win=windowFrac('inst_freq',res,ui), n=Math.max(40,Math.floor(p.t.length*win));
  const t=p.t.slice(0,n), f=p.f.slice(0,n);
  let all=f.slice(); if(p.levels_khz) all=all.concat(p.levels_khz);
  pl.domain(t[0],t[t.length-1],...pad(ext(all),.12)).frame('time (ms)','frequency (kHz)');
  if (p.levels_khz) for (const L of p.levels_khz)
    pl.hline(L, C.ok, {dash:[5,4], label:`${F(L,1)} kHz`});
  if (p.f_clean && ui.showClean!==false) pl.line(t,p.f_clean.slice(0,n),C.clean,1,.30);
  pl.line(t,f,C.live,1.2);
  if (res.reports.cfo) pl.hline(res.reports.cfo.cfo_hz/1000, C.warn,{dash:[2,3],
    label:`CFO ${F(res.reports.cfo.cfo_hz/1000,2)} kHz`});
  pl.note(`smoothed over ${p.smoothing_samples} samples · showing ${
    Math.round(win*100)}% of the frame`, C.tx3,'bl');
  return pl;
}

/* ------------------------------------------------------------------ */
function spectrumLike(cv, res, ui, key) {
  const p = res.plots[key], pl = new Plot(cv,{height:ui.height||205});
  const yk = key==='psd' ? p.psd : p.mag;
  const yc = key==='psd' ? p.psd_clean : p.mag_clean;
  let [lo,hi]=ext(yk); lo=Math.max(lo, hi-95);
  pl.domain(p.f[0],p.f[p.f.length-1],lo-3,hi+7)
    .frame('frequency (kHz)', key==='psd'?'PSD (dB/Hz)':'magnitude (dB)');
  if (key==='psd'){
    const c=p.centroid_khz, b=p.occupied_bw_khz/2;
    pl.band(c-b,c+b,C.live,.07);
    pl.vline(c-b,C.live,{dash:[3,3]}); pl.vline(c+b,C.live,{dash:[3,3],
      label:`99% BW ${F(p.occupied_bw_khz,1)} kHz`, align:'right'});
    pl.hline(p.noise_floor_db,C.ideal,{dash:[5,4],label:`noise floor ${F(p.noise_floor_db,1)} dB`});
    if (p.nominal_bw_khz) pl.note(`theory (1+β)Rs = ${F(p.nominal_bw_khz,1)} kHz`, C.tx3,'bl');
  }
  if (yc && ui.showClean!==false) pl.line(p.f,yc,C.clean,1,.42);
  pl.line(p.f,yk,C.live,1.1);
  pl.vline(0,C.gridStrong,{dash:[2,4]});
  if (res.reports.interference){
    const f0=res.reports.interference.freq_offset_hz/1000;
    pl.vline(f0,C.bad,{dash:[4,3],label:`interferer ${F(f0,0)} kHz`});
  }
  if (res.reports.dc_offset) pl.vline(0,C.bad,{dash:[3,3],label:'DC'});
  if (res.reports.cfo) pl.vline(res.reports.cfo.cfo_hz/1000,C.warn,{dash:[3,3],label:'CFO shift'});
  return pl;
}
export const psd = (cv,r,u)=>spectrumLike(cv,r,u,'psd');
export const fft = (cv,r,u)=>spectrumLike(cv,r,u,'fft');

export function spectrogram(cv, res, ui) {
  const p = res.plots.spectrogram, pl = new Plot(cv,{height:ui.height||260, padL:46});
  // Crop to a time window for the same reason the other time views do: 512
  // symbols across 500 pixels is one pixel per symbol, and FSK hopping simply
  // cannot be resolved at that density however good the STFT is.
  const t = p.t, S = p.S;
  pl.domain(t[0],t[t.length-1],p.f[0],p.f[p.f.length-1]).frame('time (ms)','frequency (kHz)');
  pl.heat(S,t,p.f,p.vmin,p.vmax);
  const g=pl.g; g.strokeStyle=C.axis; g.lineWidth=1;
  g.strokeRect(Math.round(pl.L)+.5,Math.round(pl.T)+.5,Math.round(pl.R-pl.L),Math.round(pl.B-pl.T));
  if (res.plots.inst_freq && res.plots.inst_freq.levels_khz)
    for (const L of res.plots.inst_freq.levels_khz)
      pl.hline(L,C.ok,{dash:[5,4],w:1.4,label:`${F(L,0)} kHz`});
  if (res.reports.interference)
    pl.hline(res.reports.interference.freq_offset_hz/1000,C.bad,{dash:[4,3],label:'interferer'});
  if (res.reports.cfo)
    pl.hline(res.reports.cfo.cfo_hz/1000,C.warn,{dash:[3,3],label:'CFO'});
  pl.note(`${F(p.vmin,0)} … ${F(p.vmax,0)} dB`, C.tx2,'br');
  pl.note(`window ${p.window_symbols} sym · Δf ${F(p.freq_resolution_khz,1)} kHz · `+
          `Δt ${F(p.time_resolution_ms,3)} ms · ${p.span_symbols} symbols shown`, C.tx3,'bl');
  return pl;
}

/* ------------------------------------------------------------------ */
export function eye(cv, res, ui) {
  const p = res.plots.eye, pl = new Plot(cv,{height:ui.height||230});
  if (!p) return pl.empty('An eye diagram needs a linearly modulated signal with a matched filter. Not defined for FSK, FM or OFDM.');
  const xs = p.t;
  pl.domain(xs[0],xs[xs.length-1],-1.05,1.05).frame('time (symbol periods)','I amplitude');
  pl.band(-0.12,0.12,C.live,.06);
  pl.traces(p.traces_i, C.live, .7, .30, xs);
  pl.vline(0,C.warn,{dash:[4,3],label:'decision instant'});
  if (p.opening>0.01) pl.hband(-p.opening,p.opening,C.ok,.09);
  pl.note(`eye opening ${F(p.opening,3)}`, p.opening>0.15?C.ok:p.opening>0.03?C.warn:C.bad,'tr');
  pl.note('I rail; Q is similar', C.tx3,'bl');
  return pl;
}

export function autocorr(cv, res, ui) {
  const p = res.plots.autocorr, pl = new Plot(cv,{height:ui.height||190});
  pl.domain(0,p.lag[p.lag.length-1],0,1.05).frame('lag (samples)','|R(τ)| normalised');
  if (ui.showClean!==false) pl.line(p.lag,p.r_clean,C.clean,1,.35);
  pl.line(p.lag,p.r,C.live,1.2);
  for (let k=1;k*p.sps<=p.lag[p.lag.length-1] && k<=8;k++)
    pl.vline(k*p.sps,C.bound,{dash:[2,4]});
  if (p.expect_peak_lag){
    pl.vline(p.expect_peak_lag,C.ok,{dash:[4,3],label:`N_FFT = ${p.expect_peak_lag} (cyclic prefix)`});
  } else pl.note(`ticks every ${p.sps} samples = 1 symbol`, C.tx3,'tr');
  return pl;
}

export function cyclic(cv, res, ui) {
  const p = res.plots.cyclic, pl = new Plot(cv,{height:ui.height||200});
  const [lo,hi]=ext(p.profile.concat(p.conj_profile));
  pl.domain(0,p.alpha_khz[p.alpha_khz.length-1],0,hi*1.15||1)
    .frame('cycle frequency α (kHz)','|R^α| / power');
  pl.line(p.alpha_khz,p.conj_profile,C.mag,1,.65);
  pl.line(p.alpha_khz,p.profile,C.live,1.2);
  pl.vline(p.marker_khz,C.ok,{dash:[4,3],label:`α = ${p.marker_label}`});
  if (p.marker_khz*2 < p.alpha_khz[p.alpha_khz.length-1])
    pl.vline(p.marker_khz*2,C.ok,{dash:[2,4],label:'2α'});
  if (p.line) pl.note(`line contrast ${F(p.line.contrast_db,1)} dB`,
    p.line.contrast_db>12?C.ok:C.warn,'tr');
  pl.note(`conj@α=0 = ${F(p.conj_at_zero,3)}`, C.mag,'bl');
  return pl;
}

export function cumulants(cv, res, ui) {
  const p = res.plots.cumulants, pl = new Plot(cv,{height:ui.height||200,padL:46,padB:34});
  const keys=['C20','C21','C40','C41','C42','C63'];
  const meas=keys.map(k=>p.measured[k]||0);
  const ideal=keys.map(k=>(p.ideal&&p.ideal[k]!==undefined)?p.ideal[k]:null);
  const others=[];
  for (const [mod,vals] of Object.entries(p.table||{}))
    keys.forEach((k,i)=>{ if(vals[k]!==undefined) others.push([i,vals[k],mod]); });
  const hi=Math.max(...meas, ...ideal.filter(v=>v!==null), ...others.map(o=>o[1]),1)*1.15;
  pl.domain(-0.6,keys.length-0.4,0,hi)
    .frame('','normalised |cumulant|',{xticks:keys.map((_,i)=>i), xfmt:v=>keys[Math.round(v)]||''});
  pl.clip(g=>{ g.globalAlpha=.5; g.strokeStyle=C.ideal; g.lineWidth=1;
    for(const [i,v] of others){ const x=pl.px(i), y=pl.py(v);
      g.beginPath(); g.moveTo(x-13,y); g.lineTo(x+13,y); g.stroke(); }
    g.globalAlpha=1; });
  pl.bars(keys.map((_,i)=>i), meas, C.live, {frac:.42});
  pl.clip(g=>{ g.strokeStyle=C.clean; g.lineWidth=1.8;
    ideal.forEach((v,i)=>{ if(v===null)return; const x=pl.px(i), y=pl.py(v);
      g.beginPath(); g.moveTo(x-15,y); g.lineTo(x+15,y); g.stroke(); }); });
  pl.note(`${p.n_symbols} symbols`, C.tx3,'tr');
  return pl;
}

export function amp_hist(cv, res, ui) {
  const p = res.plots.amp_hist, pl = new Plot(cv,{height:ui.height||185});
  const ctr=[]; for(let i=0;i<p.counts.length;i++) ctr.push((p.edges[i]+p.edges[i+1])/2);
  const hi=Math.max(...p.counts,...p.counts_clean)*1.1||1;
  pl.domain(p.edges[0],p.edges[p.edges.length-1],0,hi).frame('|x|','count');
  if (ui.showClean!==false) pl.bars(ctr,p.counts_clean,C.clean,{alpha:.28,frac:.95});
  pl.bars(ctr,p.counts,C.live,{alpha:.75,frac:.95});
  if (res.reports.clipping)
    pl.vline(res.reports.clipping.clip_level_rel_rms*res.plots.magnitude.rms,C.bad,
      {dash:[4,3],label:'clip level'});
  return pl;
}

export function papr_ccdf(cv, res, ui) {
  const p = res.plots.papr_ccdf, pl = new Plot(cv,{height:ui.height||190});
  const lg = v => v<=0 ? -5 : Math.log10(v);
  pl.domain(0,p.threshold_db[p.threshold_db.length-1],-4.2,0.1)
    .frame('threshold above average (dB)','P(PAPR > x)',{yfmt:v=>'1e'+v.toFixed(0)});
  if (ui.showClean!==false) pl.line(p.threshold_db,p.prob_clean.map(lg),C.clean,1.1,.45);
  pl.line(p.threshold_db,p.prob.map(lg),C.live,1.3);
  pl.vline(res.measurements.papr_db,C.warn,{dash:[4,3],
    label:`measured ${F(res.measurements.papr_db,1)} dB`});
  return pl;
}

export function am_am(cv, res, ui) {
  const p = res.plots.am_am, pl = new Plot(cv,{height:ui.height||220});
  if (!p) return pl.empty('No nonlinearity is active. Enable the power amplifier or clipping to see a transfer curve.');
  const [x0,x1]=ext(p.in), [y0,y1]=ext(p.out.concat(p.linear_ref||[]));
  pl.domain(0,x1*1.05,0,Math.max(y1,x1)*1.05).frame('input |x|','output |y|');
  if (p.linear_ref) pl.line(p.in,p.linear_ref,C.ideal,1.2,.7);
  pl.scatter(p.in,p.out,{color:C.live,r:1.2,alpha:.5});
  if (res.reports.pa){
    const a=res.reports.pa.a_sat_over_rms*res.plots.magnitude.rms;
    pl.vline(a,C.warn,{dash:[4,3],label:'saturation'});
  }
  if (res.reports.clipping)
    pl.hline(res.reports.clipping.clip_level_rel_rms*res.plots.magnitude.rms,C.bad,
      {dash:[4,3],label:'clip ceiling'});
  pl.note('dashed grey = ideal linear', C.tx3,'bl');
  return pl;
}

export function channel(cv, res, ui) {
  const p = res.plots.channel;
  const pl = new Plot(cv,{height:ui.height||230});
  if (!p) return pl.empty('No multipath channel configured. Enable Multipath to see the impulse and frequency response.');
  const half = Math.floor((pl.h - 34)/2);
  // impulse response (top half) drawn as its own sub-plot
  const p1 = new Plot(cv,{height:pl.h, padT:8, padB:pl.h-half+6, padL:46});
  p1.domain(-0.4, Math.max(...p.tap_delay_us)*1.15+0.4,
            Math.min(...p.tap_gain_db)-6, 3).frame('','tap gain (dB)');
  p1.stems(p.tap_delay_us, p.tap_gain_db, C.live);
  p1.note(`τrms ${F(p.rms_delay_spread_us,3)} µs`, C.tx2,'tr');
  p1.note('impulse response — delay (µs)', C.tx3,'bl');
  const p2 = new Plot(cv,{height:pl.h, padT:half+18, padB:26, padL:46});
  const [lo,hi]=ext(p.H_db);
  p2.domain(p.f_khz[0],p.f_khz[p.f_khz.length-1],lo-2,hi+2)
    .frame('frequency (kHz)','|H| (dB)');
  p2.line(p.f_khz,p.H_db,C.live,1.2);
  const bw = res.plots.psd.occupied_bw_khz/2, c=res.plots.psd.centroid_khz;
  p2.band(c-bw,c+bw,C.clean,.08);
  const cb = p.coherence_bw_khz;
  p2.note(`coherence BW ${cb===null?'unbounded':F(cb,0)+' kHz'} · signal BW ${F(bw*2,0)} kHz`,
          (cb!==null && cb < bw*2) ? C.warn : C.ok,'tr');
  return pl;
}

export function ofdm(cv, res, ui) {
  const p = res.plots.ofdm, pl = new Plot(cv,{height:ui.height||240});
  if (!p) return pl.empty('Not an OFDM signal.');
  const half = Math.floor(pl.w*0.46);
  const p1 = new Plot(cv,{height:pl.h, padL:40, padR:pl.w-half, padB:26, square:true});
  let all=p.sub_i.concat(p.sub_q,p.ideal_i,p.ideal_q);
  let r=Math.max(...all.map(Math.abs))*1.1;
  p1.domain(-r,r,-r,r).frame('I','Q');
  p1.scatter(p.sub_i,p.sub_q,{color:C.live,r:1.4,alpha:.55});
  for(let i=0;i<p.ideal_i.length;i++) p1.marker(p.ideal_i[i],p.ideal_q[i],C.ideal,{r:4,w:1.1});
  p1.note('per-subcarrier after FFT', C.tx3,'bl');
  const p2 = new Plot(cv,{height:pl.h, padL:half+34, padR:12, padB:26});
  const [lo,hi]=ext(p.subcarrier_power_db);
  p2.domain(p.subcarrier_index[0],p.subcarrier_index[p.subcarrier_index.length-1],
            Math.max(lo,hi-60),hi+3).frame('subcarrier','power (dB)');
  p2.clip(g=>{ g.globalAlpha=.12; g.fillStyle=C.live;
    p.used_mask.forEach((u,i)=>{ if(!u) return;
      const x=p2.px(p.subcarrier_index[i]); g.fillRect(x-2,p2.T,4,p2.B-p2.T); });
    g.globalAlpha=1; });
  p2.line(p.subcarrier_index,p.subcarrier_power_db,C.live,1.2);
  p2.note(`${p.n_ofdm_symbols} OFDM symbols`, C.tx3,'tr');
  p2.note('shaded = used', C.tx3,'bl');
  return pl;
}

export const DRAW = { constellation, iq_time, magnitude, phase, inst_freq, fft, psd,
  spectrogram, eye, autocorr, cyclic, cumulants, amp_hist, papr_ccdf, am_am, channel, ofdm };

export function readout(view, res) {
  const m=res.measurements, p=res.plots, g=res.geometry, d=m.constellation_diag;
  const R=[];
  const add=(k,v)=>R.push([k,v]);
  switch(view){
    case 'constellation':
      if (d && d.model_valid){ add('margin',`${F(d.separation_sigma,1)} σ`);
        add('cloud σ',F(d.mean_cluster_std,4)); add('tan/rad',F(d.tangential_over_radial,2));
        add('rotation',`${F(d.net_rotation_deg,1)}°`); }
      else if (d) add('status','no carrier lock — ring');
      if (d && !d.model_valid) add('EVM after ideal sync',`${F(m.residual_evm_pct,2)}%`);
      else if (m.symbol_evm_pct!==null) add('symbol EVM',`${F(m.symbol_evm_pct,2)}%`);
      if (g.d_min) add('d_min',F(g.d_min,3));
      break;
    case 'iq_time': add('samples',res.signal.n_samples); add('sps',res.signal.sps);
      add('duration',`${F(res.signal.duration_ms,3)} ms`); break;
    case 'magnitude': add('PAPR',`${F(m.papr_db,2)} dB`);
      add('clean PAPR',`${F(m.papr_clean_db,2)} dB`);
      if(d) add('amp CV',F(d.amplitude_cv,3)); break;
    case 'phase': add('carrier drift',`${F(p.phase.total_drift_rad,2)} rad`);
      add('turns',F(p.phase.total_drift_rad/6.2832,2));
      add('modulation phase',`${F(p.phase.signal_drift_rad,1)} rad`);
      add('blind CFO',`${F(m.cfo_blind.hz,1)} Hz`); break;
    case 'inst_freq': if(p.inst_freq.levels_khz)
        add('tone levels',p.inst_freq.levels_khz.map(v=>F(v,1)).join(' / ')+' kHz');
      add('occupied BW',`${F(m.occupied_bw_hz/1000,1)} kHz`); break;
    case 'psd': case 'fft':
      add('99% BW',`${F(p.psd.occupied_bw_khz,1)} kHz`);
      add('centroid',`${F(p.psd.centroid_khz,2)} kHz`);
      add('noise floor',`${F(p.psd.noise_floor_db,1)} dB`);
      add('symbol rate',`${F(p.psd.symbol_rate_khz,1)} kBaud`); break;
    case 'eye': if(p.eye){ add('opening',F(p.eye.opening,3)); add('jitter',F(p.eye.jitter,3)); }
      break;
    case 'cyclic': add('α marker',`${F(p.cyclic.marker_khz,1)} kHz`);
      if(p.cyclic.line) add('line contrast',`${F(p.cyclic.line.contrast_db,1)} dB`);
      add('conj@0',F(p.cyclic.conj_at_zero,3));
      add('α resolution',`${F(p.cyclic.alpha_resolution_hz,0)} Hz`); break;
    case 'cumulants': for(const k of ['C40','C42'])
        add(`|${k}|`, F(p.cumulants.measured[k],3) + (p.cumulants.ideal&&p.cumulants.ideal[k]!==undefined
          ? ` (th ${F(p.cumulants.ideal[k],2)})` : ''));
      break;
    case 'papr_ccdf': add('PAPR',`${F(m.papr_db,2)} dB`); break;
    case 'am_am': if(res.reports.pa){ add('IBO',`${F(res.reports.pa.ibo_db,1)} dB`);
        add('peak compression',`${F(res.reports.pa.peak_compression_db,2)} dB`); }
      if(res.reports.clipping) add('clipped',`${F(100*res.reports.clipping.fraction_clipped,2)}%`);
      break;
    case 'channel': if(p.channel){ add('τrms',`${F(p.channel.rms_delay_spread_us,3)} µs`);
        add('coherence BW', p.channel.coherence_bw_khz===null?'unbounded (flat)':
            `${F(p.channel.coherence_bw_khz,0)} kHz`); } break;
    case 'ofdm': if(p.ofdm){ add('subcarrier spacing',`${F(g.subcarrier_spacing_hz/1000,2)} kHz`);
        add('CP',`${g.cp_len} samples`); add('OFDM symbols',p.ofdm.n_ofdm_symbols); } break;
    case 'autocorr': if(p.autocorr.expect_peak_lag) add('expected peak lag',p.autocorr.expect_peak_lag);
      add('1 symbol',`${p.autocorr.sps} samples`); break;
    case 'spectrogram': add('STFT window',`${p.spectrogram.nperseg} samples`);
      add('= symbols',p.spectrogram.window_symbols);
      add('span shown',`${p.spectrogram.span_symbols} symbols`);
      add('zero-pad',`${p.spectrogram.zero_pad}x (display only)`);
      add('Δf',`${F(p.spectrogram.freq_resolution_khz,1)} kHz`);
      add('Δt',`${F(p.spectrogram.time_resolution_ms,3)} ms`); break;
    case 'amp_hist': if(d) add('amp CV',F(d.amplitude_cv,3));
      if(res.reports.quantization) add('codes used',res.reports.quantization.codes_used_i); break;
  }
  return R;
}
