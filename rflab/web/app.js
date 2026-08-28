import { DRAW, readout, HERO } from './plots.js';
import { C, refreshTheme } from './render.js';

const $ = (s,r=document)=>r.querySelector(s);
const el = (t,c,h)=>{const e=document.createElement(t); if(c)e.className=c;
  if(h!==undefined)e.innerHTML=h; return e;};
const esc = s => String(s===null||s===undefined?'':s)
  .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const F=(v,d=2)=>(v===null||v===undefined||!isFinite(v))?'--':(+v).toFixed(d);
const SEV=['NEGLIGIBLE','LOW','MODERATE','HIGH','SEVERE'];
const svClass = l => 'sv'+Math.max(0,SEV.indexOf(l));

const S = {
  meta:null, res:null, cfg:null, ui:{constMode:'symbols', colorByTime:true, showClean:true,
    showBoundaries:true, showCentroids:true, phaseWrapped:false, tWin:1, layout:'auto'},
  collapsed:{}, challenge:null, busy:false, pending:null, viewFilter:null
};

/* ---------------- config ---------------- */
function readConfig(){
  const c = { mod:$('#mod').value,
    n_samples:+$('#nsamp').value, fs:+$('#fs').value*1e6, sps:+$('#sps').value,
    rolloff:+$('#beta').value, seed:+$('#seed').value,
    rx_matched_filter:$('#rxmf').checked, rx_timing_recovery:$('#rxtr').checked,
    stft_symbols:+$('#stftw').value, stft_span_symbols:+$('#stfts').value,
    impairments:{} };
  const fam = famOf(c.mod);
  if (fam==='fsk'){ c.mod_index = +$('#hidx').value; if($('#btp')) c.bt = +$('#btp').value; }
  if (fam==='analog'){ c.msg_bw = +$('#msgbw').value*1e3; c.am_depth = +$('#amdepth').value;
    c.freq_dev = +$('#fdev').value*1e3; }
  if (fam==='ofdm'){ c.n_fft=+$('#nfft').value; c.cp_len=+$('#cplen').value;
    c.n_used=+$('#nused').value; c.sub_mod=$('#submod').value; }
  for (const g of S.meta.impairments){
    const node = $(`#imp-${g.key}`); if(!node) continue;
    const on = node.classList.contains('on');
    const p = {enabled:on};
    for (const pr of g.params){
      const inp = $(`#p-${g.key}-${pr.key}`); if(!inp) continue;
      p[pr.key] = pr.choices ? inp.value : +inp.value;
    }
    if (on) c.impairments[g.key]=p;
  }
  return c;
}
const famOf = m => (S.meta.modulation_profiles[m]||{}).family || 'psk';

function applyConfig(patch){
  if (!patch) return;
  if (patch.mod){ $('#mod').value = patch.mod; buildModParams(); }
  for (const [k,id] of [['n_samples','nsamp'],['sps','sps'],['rolloff','beta'],['seed','seed']])
    if (patch[k]!==undefined && $('#'+id)) $('#'+id).value = patch[k];
  if (patch.fs!==undefined) $('#fs').value = patch.fs/1e6;
  if (patch.impairments){
    for (const g of S.meta.impairments){
      const node=$(`#imp-${g.key}`); if(!node) continue;
      const want = patch.impairments[g.key];
      node.classList.toggle('on', !!(want && want.enabled));
      if (want) for (const pr of g.params){
        const inp=$(`#p-${g.key}-${pr.key}`);
        if (inp && want[pr.key]!==undefined){ inp.value = want[pr.key]; syncLabel(g.key,pr); }
      }
    }
  }
  syncAllLabels(); run();
}

/* ---------------- run ---------------- */
let timer=null;
function schedule(){ clearTimeout(timer); timer=setTimeout(run, 90); }

async function run(){
  if (S.busy){ S.pending = true; return; }
  S.busy = true; document.body.classList.add('loading');
  const cfg = readConfig(); S.cfg = cfg;
  try{
    const r = await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(cfg)});
    const j = await r.json();
    if (j.error) throw new Error(j.error + '\n' + (j.trace||[]).join('\n'));
    S.res = j; S.challenge = null;
    render();
  } catch(e){
    $('#grid').innerHTML=''; $('#grid').append(el('div','err', esc(e.message)));
  } finally {
    S.busy=false; document.body.classList.remove('loading');
    if (S.pending){ S.pending=false; schedule(); }
  }
}

/* ---------------- render ---------------- */
function render(){
  const r=S.res; if(!r) return;
  renderStatus(); renderGrid(); renderTutor(); renderChain();
}

function renderStatus(){
  const r=S.res, m=r.measurements, o=r.overall;
  const p=S.meta.modulation_profiles[r.signal.mod];
  $('#status').innerHTML =
    `<span><b>${esc(p?p.name:r.signal.mod)}</b></span>`+
    `<span>Rs <b>${F(r.signal.symbol_rate/1e3,1)}</b> kBaud</span>`+
    `<span>fs <b>${F(r.signal.fs/1e6,2)}</b> MHz</span>`+
    `<span><b>${r.signal.n_samples}</b> samples / <b>${F(r.signal.n_symbols,0)}</b> symbols</span>`+
    (function(){ const d=m.constellation_diag;
      if (d && !d.model_valid)
        return `<span>EVM <b>no carrier lock</b></span>`+
               `<span>after ideal sync <b>${F(m.residual_evm_pct,2)}%</b></span>`;
      return `<span>EVM <b>${m.symbol_evm_pct!==null?F(m.symbol_evm_pct,2)+'%':F(m.waveform_evm_pct,1)+'%'}</b></span>`;
    })()+
    `<span class="sev ${svClass(o.level)}">${o.level}</span>`+
    (r.active.length?`<span>${r.active.length} impairment${r.active.length>1?'s':''}</span>`
                    :`<span style="color:var(--ok)">clean reference</span>`);
}

function cardFor(view, i){
  const r=S.res, vp=S.meta.views[view]||{};
  const card=el('div','card'+((HERO.has(view)&&S.ui.layout==='auto')?' hero':''));
  const hd=el('div','hd');
  hd.append(el('h4',null,esc(vp.title||view)));
  if (i===0) hd.append(el('span','pri','PRIMARY'));
  hd.append(el('span','q',esc(vp.question||'')));
  const bx=el('button','btn','Explain'); bx.onclick=()=>openExplain(view); hd.append(bx);
  card.append(hd);
  const wrap=el('div','cw'); const cv=document.createElement('canvas'); wrap.append(cv);
  card.append(wrap);
  const ro=readout(view,r);
  if (ro.length) card.append(el('div','readout',
    ro.map(([k,v])=>`<span>${esc(k)} <b>${esc(v)}</b></span>`).join('')));
  requestAnimationFrame(()=>{ try{ DRAW[view](cv, r, S.ui); }
    catch(e){ console.error(view,e); wrap.append(el('div','err','render error in '+view+': '+esc(e.message))); } });
  return card;
}

function renderGrid(){
  const r=S.res, g=$('#grid'); g.innerHTML='';
  g.classList.toggle('one', S.ui.layout==='single');
  let views = r.tutor.priority_views;
  if (S.viewFilter) views = views.filter(v=>v===S.viewFilter);
  views.forEach((v,i)=>g.append(cardFor(v,i)));
}

function renderChain(){
  const r=S.res, c=$('#chain'); c.innerHTML='';
  if (r.chain.length<2){ $('#chainGrp').style.display='none'; return; }
  $('#chainGrp').style.display='';
  r.chain.forEach((st,i)=>{
    const d=el('div','ch'+(i===r.chain.length-1?' sel':''));
    const cv=document.createElement('canvas'); d.append(cv);
    d.append(el('div','lb',esc(st.label)+
      (i? `<div class="ev">+${F(st.delta_evm_pct,1)}% EVM</div>`
        : `<div class="ev">${esc(st.stage)}</div>`)));
    c.append(d);
    requestAnimationFrame(()=>{
      const p=new (window.__Plot)(cv,{height:104,square:true,padL:4,padR:4,padT:4,padB:4});
      let all=st.i.concat(st.q); let m=Math.max(...all.map(Math.abs))*1.1||1;
      p.domain(-m,m,-m,m).frame('','',{xticks:[],yticks:[]});
      p.scatter(st.i,st.q,{t:st.t,r:1.1,alpha:.8});
    });
  });
}

/* ---------------- tutor ---------------- */
function panel(id,title,bodyHtml,openDefault=true){
  const collapsed = S.collapsed[id]!==undefined ? S.collapsed[id] : !openDefault;
  const d=el('div','tt'+(collapsed?' col':''));
  const h=el('h4',null,esc(title)+`<span class="ch">${collapsed?'+':'−'}</span>`);
  h.onclick=()=>{ S.collapsed[id]=!d.classList.contains('col'); d.classList.toggle('col');
    h.querySelector('.ch').textContent=d.classList.contains('col')?'+':'−'; };
  d.append(h); d.append(el('div','b',bodyHtml));
  return d;
}
const kv = rows => `<div class="kv">${rows.map(r=>r.note
  ? `<div class="note">${esc(r.note)}</div>`
  : `<span>${esc(r[0])}</span><b>${esc(r[1])}</b>`).join('')}</div>`;

function sevBlock(key,s){
  const rows=(s.metrics||[]).map(mm=>{
    const v = typeof mm.value==='number' ? F(mm.value, Math.abs(mm.value)<1?4:2) : mm.value;
    return [mm.label, v + (mm.unit?' '+mm.unit:'')];
  });
  const notes=(s.metrics||[]).filter(mm=>mm.note).map(mm=>`<div style="font-size:11px;color:var(--tx3);margin:-3px 0 6px">${esc(mm.label)}: ${esc(mm.note)}</div>`).join('');
  return `<p><span class="sev ${svClass(s.level)}">${s.level}</span> <strong>${esc(s.headline)}</strong></p>`+
    `<div class="meter"><i style="width:${Math.round(s.score*100)}%;background:var(--s${Math.max(0,SEV.indexOf(s.level))})"></i></div>`+
    `<p style="margin-top:8px">${esc(s.why)}</p>`+kv(rows)+notes;
}

function renderTutor(){
  const r=S.res, t=r.tutor, m=r.measurements, out=$('#tutor'); out.innerHTML='';
  const mp=S.meta.modulation_profiles[r.signal.mod];

  // overall
  let h=`<p><span class="sev ${svClass(r.overall.level)}">${r.overall.level}</span> ${esc(r.overall.why)}</p>`;
  const locked = !(m.constellation_diag && !m.constellation_diag.model_valid);
  h+=kv([['Waveform EVM vs clean',F(m.waveform_evm_pct,2)+' %'],
         ['Residual after ideal sync',F(m.residual_evm_pct,2)+' %'],
         ['Removable by preprocessing',F(100*m.correctable_fraction,0)+' %'],
         ...((locked && m.symbol_evm_pct!==null)?[['Symbol EVM',F(m.symbol_evm_pct,2)+' %']]:[])]);
  h+=`<p style="font-size:11.5px;color:var(--tx3)">"Residual after ideal sync" is what survives a
      perfect gain, frequency and phase correction — the damage no front-end can undo.</p>`;
  if (!locked) h+=`<p style="font-size:11.5px;color:var(--warn)">There is no carrier lock, so an
      EVM against fixed constellation points is not a meaningful number here and is not shown.
      The waveform figure above is dominated by bulk rotation rather than by distortion — which
      is exactly why the residual-after-sync row is the one to read.</p>`;
  out.append(panel('ov','Verdict',h));

  // verification
  let v='';
  for (const c of r.verification){
    const cls = c.inconclusive?'mid':(c.agrees?'ok':'no');
    const tag = c.inconclusive?'INCONCLUSIVE':(c.agrees?'AGREES':'DISAGREES');
    v+=`<div class="vd ${cls}"><div class="t">${esc(c.name)} — ${tag}</div>
      <div class="d">configured <b>${F(c.predicted,c.unit==='Hz'?0:2)} ${esc(c.unit)}</b>,
      measured <b>${F(c.measured,c.unit==='Hz'?0:2)} ${esc(c.unit)}</b>${
        c.tolerance?` (tolerance ±${F(c.tolerance,c.unit==='Hz'?0:2)})`:''}<br>${esc(c.note||'')}</div></div>`;
  }
  out.append(panel('vf','Does the physics agree?',v));

  // what should I see
  let pr='';
  for (const it of t.prediction){
    pr+=`<p><strong>${esc(it.topic)}</strong>${it.predicted_severity
      ? ` <span class="sev ${svClass(it.predicted_severity)}">${it.predicted_severity}</span>`:''}<br>${esc(it.expect)}</p>`;
    if (it.quantified) pr+=`<p style="color:var(--tx3);font-size:11.5px">Quantified: ${esc(it.quantified)}</p>`;
    if (it.best_views) pr+=`<p style="font-size:11.5px">Best views: ${it.best_views.map(v=>
      `<a href="#" data-view="${v}" class="vlink" style="color:var(--live)">${esc((S.meta.views[v]||{}).title||v)}</a>`).join(', ')}</p>`;
  }
  out.append(panel('pd','What should I see?',pr,false));

  // compare
  let cp='';
  for (const row of t.compare.rows){
    const good=/confirmed/.test(row.verdict);
    cp+=`<div class="vd ${good?'ok':'mid'}"><div class="t">${esc(row.impairment)} — ${esc(row.verdict)}</div>
      <div class="d"><em style="color:var(--tx3)">predicted:</em> ${esc(row.predicted)}<br>
      <em style="color:var(--tx3)">observed:</em> ${esc(row.observed)}</div></div>`;
  }
  for (const s of t.compare.surprises)
    cp+=`<div class="vd no"><div class="t">Worth noting</div><div class="d">${esc(s)}</div></div>`;
  out.append(panel('cm','Compare with actual',cp));

  // severity detail
  for (const [k,s] of Object.entries(r.severity)){
    const ip=S.meta.impairment_profiles[k]||{};
    out.append(panel('sv-'+k, (ip.name||k)+' — severity', sevBlock(k,s), false));
  }

  // modulation profile
  if (mp){
    let mh=`<p>${esc(mp.what)}</p>`;
    mh+=kv([['Family',mp.family],['Bits per symbol',mp.bits===null?'n/a (analog)':mp.bits],
      ['Carries information in',mp.carries],
      ...(r.geometry.d_min?[['d_min (unit power)',F(r.geometry.d_min,3)],
        ['Phase tolerance',F(r.geometry.phase_tolerance_deg,1)+' °']]:[]),
      ...(r.geometry.tone_spacing_hz?[['Tone spacing',F(r.geometry.tone_spacing_hz/1e3,1)+' kHz']]:[]),
      ...(r.geometry.subcarrier_spacing_hz?[['Subcarrier spacing',F(r.geometry.subcarrier_spacing_hz/1e3,2)+' kHz'],
        ['Cyclic prefix',r.geometry.cp_len+' samples']]:[])]);
    mh+=`<p><strong>Constellation.</strong> ${esc(mp.constellation)}</p>`;
    mh+=`<p><strong>Amplitude.</strong> ${esc(mp.amplitude)}</p>`;
    mh+=`<p><strong>Phase.</strong> ${esc(mp.phase)}</p>`;
    mh+=`<p><strong>Frequency.</strong> ${esc(mp.frequency)}</p>`;
    mh+=`<p><strong>Bandwidth.</strong> ${esc(mp.bandwidth)}</p>`;
    mh+=`<p><strong>Classification difficulty.</strong> ${esc(mp.difficulty)}</p>`;
    mh+=`<p><strong>Commonly confused with</strong><ul class="bl">${(mp.confusions||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul></p>`;
    mh+=(mp.guide_points||[]).map(g=>`<p><span class="tag g">study guide</span>${esc(g)}</p>`).join('');
    mh+=(mp.rf_points||[]).map(g=>`<p><span class="tag r">rf context</span>${esc(g)}</p>`).join('');
    out.append(panel('mp','About '+mp.name, mh, false));
  }

  // impairment profiles
  for (const k of r.active){
    const ip=S.meta.impairment_profiles[k]; if(!ip) continue;
    let ih=kv([['Where it happens',ip.stage],['Modelled in synthetic data',ip.in_synthetic],
      ['Hard to model realistically',ip.hard_to_model],['Correctable',ip.correctable],
      ['Can a classifier learn around it',ip.classifier_can_learn]]);
    ih+=`<p><strong>Physical origin.</strong> ${esc(ip.origin)}</p>`;
    ih+=`<p><strong>Model.</strong> ${esc(ip.model)}</p>`;
    ih+=`<p><strong>On the constellation.</strong> ${esc(ip.on_constellation)}</p>`;
    ih+=`<p><strong>On the spectrum.</strong> ${esc(ip.on_spectrum)}</p>`;
    ih+=`<p><strong>Over time.</strong> ${esc(ip.over_time)}</p>`;
    ih+=(ip.guide_points||[]).map(g=>`<p><span class="tag g">study guide</span>${esc(g)}</p>`).join('');
    ih+=(ip.rf_points||[]).map(g=>`<p><span class="tag r">rf context</span>${esc(g)}</p>`).join('');
    out.append(panel('ip-'+k,'About '+ip.name, ih, false));
  }

  // why care
  const w=t.why_care;
  let wh='';
  const sec=(t2,arr)=>arr&&arr.length?`<p><strong>${t2}</strong></p><ul class="bl">${arr.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'';
  wh+=sec('For automatic modulation classification',w.amc);
  wh+=sec('For real SDR systems',w.sdr);
  wh+=sec('For the synthetic-to-real gap',w.sim_to_real);
  wh+=sec('Can preprocessing fix it?',w.preprocessing);
  wh+=sec('Device fingerprint risk',w.fingerprint);
  out.append(panel('wc','Why should I care?',wh,false));

  // try next
  let nx='';
  for (const s of t.next){
    nx+=`<div class="nx ${s.kind==='next'?'next':''}" data-cfg='${esc(JSON.stringify(s.config))}'>
      <div class="l">${s.kind==='next'?'▶ ':''}${esc(s.label)}</div><div class="w">${esc(s.why)}</div></div>`;
  }
  out.append(panel('nx','Try this next',nx));

  out.querySelectorAll('.nx').forEach(n=>n.onclick=()=>{
    const c=JSON.parse(n.dataset.cfg);
    if (c.__challenge__){ $('#chalBtn').click(); return; }
    applyConfig(c);
    $('#stage').scrollTop=0;
  });
  out.querySelectorAll('.vlink').forEach(a=>a.onclick=e=>{ e.preventDefault();
    const card=[...$('#grid').children].find(c=>c.querySelector('h4') &&
      c.querySelector('h4').textContent===((S.meta.views[a.dataset.view]||{}).title));
    if(card) card.scrollIntoView({behavior:'smooth',block:'center'});
  });
}

/* ---------------- explain modal ---------------- */
function openExplain(view){
  const e = S.res.tutor.explain[view];
  const vp = S.meta.views[view]||{};
  if (!e){ toast('No explanation for this view.'); return; }
  let h='';
  h+=`<p><strong>The question this view answers.</strong> ${esc(e.question)}</p>`;
  h+=`<p><strong>What it is.</strong> ${esc(e.what)}</p>`;
  h+=`<p><strong>Axes.</strong> ${esc(e.axes)}</p>`;
  h+=`<p><strong>What the marks mean.</strong> ${esc(e.marks)}</p>`;
  h+=`<p><strong>A clean signal looks like.</strong> ${esc(e.clean_expectation)}</p>`;
  h+=`<p><strong>What you are actually seeing now.</strong></p><ul class="bl">${
    e.observed.map(o=>`<li>${esc(o)}</li>`).join('')}</ul>`;
  if (e.changed && e.changed.length){
    h+=`<p><strong>What changed, and why.</strong></p>`;
    for (const c of e.changed){
      h+=`<p>${c.impairment?`<strong>${esc(c.impairment)}</strong>${c.severity
        ?` <span class="sev ${svClass(c.severity)}">${c.severity}</span>`:''} — `:''}${esc(c.effect)}
        ${c.headline?`<br><span style="color:var(--tx3)">${esc(c.headline)}</span>`:''}</p>`;
    }
  }
  if (e.severity && e.severity.length){
    h+=`<p><strong>How severe.</strong></p>`;
    for (const s of e.severity) h+=sevBlock(s.impairment,s);
  }
  if (e.why_it_matters && e.why_it_matters.length)
    h+=`<p><strong>Why this view matters here.</strong></p><ul class="bl">${
      e.why_it_matters.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;
  h+=`<p><strong>What this teaches.</strong></p><ul class="bl">${
    (e.teaches||[]).map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;
  h+=`<p><strong>Caution.</strong> ${esc(e.caution)}</p>`;
  if (e.look_next) h+=`<p><strong>Look at next.</strong> ${esc(e.look_next.title)} — ${esc(e.look_next.because)}</p>`;
  showModal(vp.title||view, h);
}

function showModal(title, html, extra){
  $('#modalT').textContent=title;
  $('#modalB').innerHTML=html;
  if (extra) $('#modalB').append(extra);
  $('#modal').classList.add('on');
}
$('#modalX')&&0;

/* ---------------- challenges ---------------- */
async function startChallenge(kind){
  const token = 'c'+Math.floor(Math.random()*1e9);
  S.busy=true; document.body.classList.add('loading');
  try{
    const r=await fetch('/api/challenge',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({kind,token})});
    const j=await r.json();
    if (j.error) throw new Error(j.error);
    S.challenge={kind,token,spec:j.challenge};
    S.res={...j.result, active:[], severity:{}, reports:{}, verification:[],
      overall:{level:'NEGLIGIBLE',why:''}, geometry:{},
      signal:{...j.result.signal, mod:'?', family:'?', info:{}},
      tutor:{priority_views:['constellation','magnitude','inst_freq','psd','spectrogram',
        'iq_time','phase','eye','autocorr','amp_hist'].filter(v=>j.result.plots[v]),
        explain:{}, prediction:[], compare:{rows:[],surprises:[]}, why_care:{}, next:[]},
      chain:[]};
    renderChallengeUI();
  }catch(e){ toast('Challenge failed: '+e.message); }
  finally{ S.busy=false; document.body.classList.remove('loading'); }
}

function renderChallengeUI(){
  const c=S.challenge, r=S.res;
  $('#status').innerHTML=`<span class="sev sv2">CHALLENGE</span><span><b>${esc(c.spec.title)}</b></span>`+
    `<span>everything identifying the signal is hidden</span>`;
  const g=$('#grid'); g.innerHTML='';
  r.tutor.priority_views.forEach((v,i)=>{
    const card=el('div','card'+(HERO.has(v)?' hero':''));
    const hd=el('div','hd'); hd.append(el('h4',null,esc((S.meta.views[v]||{}).title||v)));
    hd.append(el('span','q',esc((S.meta.views[v]||{}).question||''))); card.append(hd);
    const wrap=el('div','cw'), cv=document.createElement('canvas'); wrap.append(cv); card.append(wrap);
    g.append(card);
    requestAnimationFrame(()=>{ try{ DRAW[v](cv,r,{...S.ui,showClean:false}); }catch(e){} });
  });
  const out=$('#tutor'); out.innerHTML='';
  let h=`<p>${esc(c.spec.prompt)}</p>`;
  h+=`<p style="color:var(--tx3);font-size:11.5px">${esc(c.spec.hint)}</p>`;
  if (c.spec.numeric) h+=`<label class="f"><span>Your estimate (Hz)</span>
    <input type="number" id="guess" placeholder="e.g. 800"></label>`;
  else h+=`<label class="f"><span>Your answer</span><select id="guess">${
    (c.spec.options||[]).map(o=>`<option value="${esc(o)}">${esc(o)}</option>`).join('')}</select></label>`;
  h+=`<div class="row"><button class="btn p" id="submitG">Commit answer</button>
      <button class="btn" id="exitC">Leave challenge</button></div>`;
  out.append(panel('ch',c.spec.title,h));
  $('#submitG').onclick=submitGuess; $('#exitC').onclick=()=>run();
}

async function submitGuess(){
  const c=S.challenge, guess=$('#guess').value;
  const r=await fetch('/api/grade',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({kind:c.kind,token:c.token,guess})});
  const j=await r.json();
  const rev=await fetch('/api/reveal',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({kind:c.kind,token:c.token})});
  const rj=await rev.json();
  let h=`<p><span class="sev ${j.correct?'sv0':'sv4'}">${j.correct?'CORRECT':'NOT QUITE'}</span>
    ${esc(j.note)}</p>`;
  h+=`<p>The configuration was:</p>`;
  h+=kv([['Modulation',rj.config.mod],
    ...Object.entries(rj.config.impairments||{}).map(([k,v])=>[k,
      Object.entries(v).filter(([kk])=>kk!=='enabled').map(([kk,vv])=>`${kk}=${vv}`).join(', ')])]);
  h+=`<p style="margin-top:8px">Load this configuration to inspect it with all the labels and
      the tutor switched back on.</p>`;
  const btn=el('button','btn p','Load this configuration');
  btn.onclick=()=>{ $('#modal').classList.remove('on');
    const cfg=rj.config; const patch={mod:cfg.mod,impairments:{}};
    for (const [k,v] of Object.entries(cfg.impairments||{})) patch.impairments[k]={...v,enabled:true};
    // translate engine-level multipath back to the UI parameters
    if (patch.impairments.multipath){ const mp=patch.impairments.multipath;
      patch.impairments.multipath={enabled:true, delay2_us:(mp.delays_us||[0,2])[1]||2,
        gain2_db:(mp.gains_db||[0,-3])[1]||-3, delay3_us:0, gain3_db:-40}; }
    applyConfig(patch); };
  showModal('Result', h, btn);
}

/* ---------------- UI build ---------------- */
function syncLabel(gk,pr){
  const inp=$(`#p-${gk}-${pr.key}`), lab=$(`#l-${gk}-${pr.key}`);
  if(inp&&lab) lab.textContent = pr.choices ? inp.value
    : (+inp.value).toLocaleString(undefined,{maximumFractionDigits:4})+(pr.unit?' '+pr.unit:'');
}
function syncAllLabels(){ for(const g of S.meta.impairments) for(const pr of g.params) syncLabel(g.key,pr); }

function buildImpairments(){
  const box=$('#imps'); box.innerHTML='';
  for (const g of S.meta.impairments){
    const ip=S.meta.impairment_profiles[g.key]||{};
    const d=el('div','imp'); d.id='imp-'+g.key;
    const hd=el('div','hd',`<div class="sw"></div><span>${esc(g.label)}</span>
      <span class="stage">${esc(ip.stage||'')}</span>`);
    hd.onclick=()=>{ d.classList.toggle('on'); schedule(); };
    d.append(hd);
    const pp=el('div','pp');
    for (const pr of g.params){
      const lab=el('label','f');
      lab.innerHTML=`<span>${esc(pr.label)} <b id="l-${g.key}-${pr.key}"></b></span>`;
      let inp;
      if (pr.choices){ inp=el('select'); inp.innerHTML=pr.choices.map(c=>
        `<option${c===pr.default?' selected':''}>${esc(c)}</option>`).join(''); }
      else { inp=el('input'); inp.type='range'; inp.min=pr.min; inp.max=pr.max;
        inp.step=pr.step; inp.value=pr.default; }
      inp.id=`p-${g.key}-${pr.key}`;
      inp.oninput=()=>{ syncLabel(g.key,pr); if(d.classList.contains('on')) schedule(); };
      inp.onchange=()=>{ syncLabel(g.key,pr); if(d.classList.contains('on')) schedule(); };
      lab.append(inp); pp.append(lab);
    }
    const info=el('button','btn','What is this impairment?');
    info.onclick=e=>{ e.stopPropagation();
      let h=kv([['Where',ip.stage],['In synthetic data',ip.in_synthetic],
        ['Hard to model',ip.hard_to_model],['Correctable',ip.correctable]]);
      h+=`<p><strong>Origin.</strong> ${esc(ip.origin)}</p><p><strong>Model.</strong> ${esc(ip.model)}</p>
        <p><strong>Constellation.</strong> ${esc(ip.on_constellation)}</p>
        <p><strong>Spectrum.</strong> ${esc(ip.on_spectrum)}</p>
        <p><strong>Over time.</strong> ${esc(ip.over_time)}</p>
        <p><strong>AMC.</strong> ${esc(ip.amc)}</p><p><strong>SDR.</strong> ${esc(ip.sdr)}</p>`;
      h+=(ip.guide_points||[]).map(x=>`<p><span class="tag g">study guide</span>${esc(x)}</p>`).join('');
      h+=(ip.rf_points||[]).map(x=>`<p><span class="tag r">rf context</span>${esc(x)}</p>`).join('');
      showModal(ip.name||g.label,h); };
    pp.append(info);
    d.append(pp); box.append(d);
  }
  syncAllLabels();
}

function buildModParams(){
  const fam=famOf($('#mod').value), box=$('#modp'); box.innerHTML='';
  const rng=(id,label,min,max,step,val,unit)=>`<label class="f"><span>${label}
    <b id="lb-${id}"></b></span><input type="range" id="${id}" min="${min}" max="${max}"
    step="${step}" value="${val}" data-unit="${unit||''}"></label>`;
  if (fam==='fsk') box.innerHTML = rng('hidx','Modulation index h',0.1,2,0.05,
      ({'2fsk':1,'4fsk':1,'cpfsk':0.5,'msk':0.5,'gfsk':0.5,'gmsk':0.5})[$('#mod').value]||0.5,'')
    + (['gfsk','gmsk'].includes($('#mod').value)?rng('btp','Gaussian BT',0.1,1,0.05,
        $('#mod').value==='gmsk'?0.3:0.5,''):'');
  else if (fam==='analog') box.innerHTML = rng('msgbw','Message bandwidth',1,200,1,25,'kHz')
    + rng('amdepth','AM modulation depth',0,1.5,0.05,0.8,'')
    + rng('fdev','FM peak deviation',1,400,1,
        $('#mod').value==='wbfm'?125:25,'kHz');
  else if (fam==='ofdm') box.innerHTML =
      `<label class="f"><span>Subcarrier modulation</span><select id="submod">${
        ['bpsk','qpsk','16qam','64qam','256qam'].map(m=>`<option${m==='16qam'?' selected':''}>${m}</option>`).join('')}</select></label>`
    + rng('nfft','FFT size',16,256,16,64,'') + rng('nused','Used subcarriers',8,200,2,52,'')
    + rng('cplen','Cyclic prefix',0,64,1,16,'samples');
  box.querySelectorAll('input,select').forEach(inp=>{
    const up=()=>{ const b=$('#lb-'+inp.id); if(b) b.textContent=inp.value+
      (inp.dataset.unit?' '+inp.dataset.unit:''); };
    up(); inp.oninput=()=>{up(); schedule();}; inp.onchange=()=>{up(); schedule();};
  });
}

/* ---------------- theme ---------------- */
function setTheme(mode, redraw=true){
  document.documentElement.setAttribute('data-theme', mode);
  try{ localStorage.setItem('rflab-theme', mode); }catch(e){}
  const b=$('#themeBtn'); if(b) b.textContent = mode==='light' ? 'Dark' : 'Light';
  // Canvases hold no live link to CSS, so the palette has to be re-read and
  // every plot redrawn -- a class swap alone would leave dark plots on a white
  // page.
  refreshTheme();
  if (redraw && S.res) { renderGrid(); renderChain(); }
}
function initTheme(){
  let m='dark';
  try{ m = localStorage.getItem('rflab-theme') ||
      (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
        ? 'light' : 'dark'); }catch(e){}
  setTheme(m, false);
}

function toast(msg){ const t=$('#toast'); t.textContent=msg; t.classList.add('on');
  setTimeout(()=>t.classList.remove('on'),2200); }

/* ---------------- boot ---------------- */
async function boot(){
  initTheme();
  S.meta = await (await fetch('/api/meta')).json();
  const groups={psk:'Phase shift keying',qam:'Quadrature amplitude',pam:'Amplitude / PAM',
    apsk:'APSK (rings)',fsk:'Frequency shift keying',analog:'Analog',ofdm:'Multicarrier'};
  const sel=$('#mod');
  for (const [fam,label] of Object.entries(groups)){
    const og=el('optgroup'); og.label=label;
    for (const m of S.meta.modulations) if(m.family===fam){
      const o=el('option',null,esc(m.name)); o.value=m.key; og.append(o); }
    if (og.children.length) sel.append(og);
  }
  sel.value='qpsk';
  sel.onchange=()=>{ buildModParams(); run(); };
  buildModParams(); buildImpairments();

  for (const id of ['nsamp','sps','beta','seed','fs','stftw','stfts'])
    $('#'+id).oninput=()=>{ const b=$('#lb-'+id);
      if(b) b.textContent = (id==='stftw' && +$('#'+id).value===0) ? 'auto' : $('#'+id).value;
      schedule(); };
  for (const id of ['rxmf','rxtr']) $('#'+id).onchange=run;
  $('#reseed').onclick=()=>{ $('#seed').value=Math.floor(Math.random()*9999);
    $('#lb-seed').textContent=$('#seed').value; run(); };

  const bind=(id,fn)=>{ const e=$('#'+id); if(e) e.onclick=()=>{ fn(); renderGrid(); }; };
  $('#cmode').onchange=()=>{ S.ui.constMode=$('#cmode').value; renderGrid(); };
  $('#tclr').onchange=()=>{ S.ui.colorByTime=$('#tclr').checked; renderGrid(); };
  $('#sclean').onchange=()=>{ S.ui.showClean=$('#sclean').checked; renderGrid(); };
  $('#sbnd').onchange=()=>{ S.ui.showBoundaries=$('#sbnd').checked; renderGrid(); };
  $('#pwrap').onchange=()=>{ S.ui.phaseWrapped=$('#pwrap').checked; renderGrid(); };
  $('#twin').oninput=()=>{ S.ui.tWin=+$('#twin').value; S.ui.tWinTouched=true;
    $('#lb-twin').textContent=Math.round(S.ui.tWin*100)+'%'; renderGrid(); };
  $('#twinAuto').onclick=()=>{ S.ui.tWinTouched=false; $('#twin').value=1;
    $('#lb-twin').textContent='auto'; renderGrid(); };
  $('#layout').onchange=()=>{ S.ui.layout=$('#layout').value; renderGrid(); };

  $('#chalBtn').onclick=()=>{
    let h='<p>Pick a challenge. The signal is generated with the answer hidden on the server; every label, reference trace and tutor panel is stripped from the page until you commit.</p>';
    for (const [k,c] of Object.entries(S.meta.challenges))
      h+=`<div class="nx" data-k="${k}"><div class="l">${esc(c.title)}</div>
        <div class="w">${esc(c.prompt)}</div></div>`;
    showModal('Challenges',h);
    $('#modalB').querySelectorAll('.nx').forEach(n=>n.onclick=()=>{
      $('#modal').classList.remove('on'); startChallenge(n.dataset.k); });
  };
  $('#themeBtn').onclick=()=>setTheme(
    document.documentElement.getAttribute('data-theme')==='light' ? 'dark' : 'light');
  $('#resetBtn').onclick=()=>location.reload();
  $('#modalX').onclick=()=>$('#modal').classList.remove('on');
  $('#modal').onclick=e=>{ if(e.target.id==='modal') $('#modal').classList.remove('on'); };
  document.addEventListener('keydown',e=>{ if(e.key==='Escape') $('#modal').classList.remove('on'); });
  let rt=null; window.addEventListener('resize',()=>{ clearTimeout(rt);
    rt=setTimeout(()=>{ if(S.res) renderGrid(); },200); });

  const { Plot } = await import('./render.js'); window.__Plot = Plot;
  run();
}
boot();
