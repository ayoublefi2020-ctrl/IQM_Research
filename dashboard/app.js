"use strict";
const $ = id => document.getElementById(id);
const esc = x => String(x ?? "—").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pct = x => x == null ? "—" : (100*x).toFixed(2)+"%";
const n = x => Number(x).toLocaleString();
const state={distance:3,source:"IQM_HARDWARE",pipeline:"qrisp",basis:"Z",twirling:true,decoder:"Any",rounds:3};
const palette=["#55cfc5","#8aaeff","#f3a979","#e490bc","#bbc880"];
let db, shapes={}, view="chart", frame=0, spin=.3, tilt=.55, zoom=1, panX=0, panY=0, selected=null, timer=0, selectedRecord=null, fault="X", demoStep=0;
const metrics = items => items.map(([label,value])=>`<div class="metric"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`).join("");
const segments = (key,label,choices)=>`<label>${label}</label><div class="segments">${choices.map(([name,value])=>`<button type="button" data-key="${key}" data-value="${esc(value)}" aria-pressed="${String(state[key])===String(value)}">${esc(name)}</button>`).join("")}</div>`;
function controls(){
 $("filters").innerHTML=segments("distance","Code distance",[[ "Distance 3",3],["Distance 5",5]])+
 segments("source","Data view",[["Simulation","SIMULATION"],["Hardware data","IQM_HARDWARE"]])+
 segments("pipeline","Pipeline",[["Qiskit","qiskit"],["Qrisp","qrisp"],["Stim","stim"],["All","All"]])+
 segments("basis","Memory basis",[["Z","Z"],["X","X"]])+
 segments("twirling","Gate twirling",[["On",true],["Off",false],["All","All"]])+
 `<label for="decoder">Decoder</label><select id="decoder">${["Any",...new Set(db.records.map(r=>r.decoder).filter(Boolean))].map(v=>`<option ${v===state.decoder?"selected":""}>${esc(v)}</option>`).join("")}</select>`;
 $("filters").onclick=e=>{const b=e.target.closest("button");if(!b)return;const k=b.dataset.key,v=b.dataset.value;
 state[k]=k==="distance"?+v:k==="twirling"&&v!=="All"?v==="true":v;
 if(k==="source")state.pipeline=v==="SIMULATION"?"stim":"qrisp";
 if((k==="distance"||k==="source")&&state.distance===5&&state.source==="IQM_HARDWARE"&&db.pilot){
   Object.assign(state,{pipeline:"qiskit",rounds:3,basis:"Z",twirling:false,decoder:"Any"});
   $("rounds").value=3;$("calibration").value="";$("jobFilter").value="";
 }
 // Reveal the measured X pilot when entering the basis from the default Z configuration.
 if(k==="basis"&&v==="X"&&state.distance===3&&state.source==="IQM_HARDWARE"&&
    !db.records.some(r=>same(r)&&r.rounds===state.rounds)&&
    !$("jobFilter").value&&!$("calibration").value&&state.decoder==="Any"){
   const pilot=db.records.find(r=>r.file.includes("/basis_pilot/")&&r.basis==="X"&&r.rounds===state.rounds);
   if(pilot){state.pipeline=pilot.pipeline;state.twirling=pilot.twirling;}
 }
 selected=null; controls(); render();};
 $("decoder").onchange=e=>{state.decoder=e.target.value;render();};
}
function same(r,compare=true){
 return r.distance===state.distance&&r.source===state.source&&r.basis===state.basis&&
 (!compare||((state.pipeline==="All"||r.pipeline?.toLowerCase()===state.pipeline)&&
 (state.twirling==="All"||r.twirling===state.twirling)))&&
 (state.decoder==="Any"||r.decoder===state.decoder)&&
 String(r.calibration??"").toLowerCase().includes($("calibration").value.toLowerCase()) &&
 [r.job,r.date,r.backend].join(" ").toLowerCase().includes($("jobFilter").value.toLowerCase());
}
function chart(rows,fits=null){
 if(!rows.length)return '<p>No recorded points match these filters.</p>';
 const w=730,h=360,l=69,t=30,r=26,b=60;
 const xMax=Math.max(5,...rows.map(q=>q.rounds)), yMax=Math.max(.02,...rows.map(q=>q.interval[1]))*1.12;
 const x=k=>l+k/xMax*(w-l-r),y=p=>h-b-p/yMax*(h-t-b);
 const grid=Array.from({length:6},(_,i)=>{let p=i*yMax/5;return `<path d="M${l},${y(p)}H${w-r}" stroke="#29435d"/><text x="${l-9}" y="${y(p)+4}" text-anchor="end">${pct(p)}</text>`;}).join("");
 const ticks=[...new Set(rows.map(a=>a.rounds))].sort((a,b)=>a-b).map(i=>`<text x="${x(i)}" y="${h-b+21}" text-anchor="middle">${i}</text>`).join("");
 const series=[...new Set(rows.map(a=>`${a.pipeline} · ${a.twirling===null?"unspecified":a.twirling?"twirled":"control"}`))];
 const fitLines=fits?series.map((name,i)=>{const d=name.match(/d=(\d)/)?.[1],fit=fits[d];if(!fit||fit.goodness_p<.05)return "";
 const line=Array.from({length:41},(_,j)=>{const cycles=j*xMax/40;const p=(1-(1-2*fit.rate)**cycles)/2;return `${x(cycles)},${y(p)}`;}).join(" ");
 return `<polyline points="${line}" fill="none" stroke="${palette[i%palette.length]}" stroke-dasharray="6 5"><title>Fitted simulation rate ${pct(fit.rate)} per round</title></polyline>`;}).join(""):"";
 const points=rows.map((a,i)=>{const k=series.indexOf(`${a.pipeline} · ${a.twirling===null?"unspecified":a.twirling?"twirled":"control"}`),p=x(a.rounds)+(k-(series.length-1)/2)*5,c=palette[k%palette.length];return `<g data-row="${i}" tabindex="0" role="button" style="cursor:pointer"><title>${esc(a.id)} | ${a.failures}/${a.shots} | ${pct(a.probability)} | ${esc(a.job)}</title><path d="M${p} ${y(a.interval[0])}V${y(a.interval[1])}" stroke="${c}"/><circle cx="${p}" cy="${y(a.probability)}" r="${a.rounds===state.rounds?5:3.5}" fill="${a.source==="IQM_HARDWARE"?c:"#132338"}" stroke="${c}" stroke-width="2"/></g>`;}).join("");
 return `<svg id="chart" viewBox="0 0 ${w} ${h}" xmlns="http://www.w3.org/2000/svg" font-family="Arial" font-size="12" fill="#aabbd0" aria-label="Logical failure versus stabilizer rounds"><rect width="100%" height="100%" fill="#132338"/>${grid}${ticks}${fitLines}${points}<text x="${w/2}" y="${h-10}" text-anchor="middle">Stabilizer rounds</text></svg><div class="key">${series.map((s,i)=>`<span style="color:${palette[i%palette.length]}">● ${esc(s)} &nbsp;</span>`).join("")} · 95% Wilson intervals · Click a point for provenance · Ctrl-scroll to zoom · Shift-drag to pan</div><button id="svgExport">Download SVG</button> <button id="pngExport">Download PNG</button>`;
}
function twirlLesson(host, initial=0){
 const names=["Control gate","Twirled gate","Track the frame","Hardware result"];
 const copy=[
   "Follow the gold Z-check ancilla on the 17-qubit patch. In the archived Qiskit control circuit its first native gate rotates through a quarter turn.",
   "For this random seed, the same gate rotates through three quarters of a turn about the same drive axis. The extra half turn contributes a Pauli operation.",
   "The compiler keeps track of that extra Pauli as later gates act. It closes the bit-flip frame at readout so the ideal detector and logical parities agree with the control.",
   "We recommend distance 3 on Emerald. Twirled Qrisp had the lowest observed failure probability among the four matched configurations. The intervals overlap."
 ];
 let step=initial,yaw=.38;
 host.innerHTML='<div class="toolbar"><h3>Gate twirling on the distance-3 patch</h3><label>Rotate model <input type="range" min="-70" max="70" value="22"></label></div><div class="lessonDrawing"></div><div class="segments lessonSteps"></div><p class="lessonCaption" aria-live="polite"></p>';
 const choice=host.querySelector(".lessonSteps"),drawing=host.querySelector(".lessonDrawing");
 choice.innerHTML=names.map((name,i)=>`<button type="button" data-step="${i}">${name}</button>`).join("");
 const rows=db.records.filter(r=>r.file.includes("confirm_10000")&&r.rounds===3&&r.distance===3&&r.basis==="Z"&&r.shots===10000&&r.decoder==="BP+OSD characterized").sort((a,b)=>a.probability-b.probability);
 function draw(){
   const g=shapes[3],coords=new Map(g.nodes.map(q=>{
     const x=q.x-3,y=q.y-3;
     return [q.id,[150+30*(x*Math.cos(yaw)-y*Math.sin(yaw)),105+19*(x*Math.sin(yaw)+y*Math.cos(yaw))-(q.type==="data"?0:10)]];
   }));
   const [fx,fy]=coords.get(14),degrees=step===0?90:270;
   const lattice=g.edges.map(([a,b])=>{const [x,y]=coords.get(a),[u,v]=coords.get(b);return `<path d="M${x},${y} L${u},${v}" stroke="#436079" stroke-width="2"/>`;}).join("")+g.nodes.map(q=>{
     const [x,y]=coords.get(q.id),c=q.id===14?"#ffd28a":({X:"#ed888a",Z:"#55cfc5",data:"#78aafd"})[q.type];
     return `<circle cx="${x}" cy="${y}" r="${q.id===14?9:6}" fill="${c}"><title>${q.type} · Q${q.id}</title></circle>`;
   }).join("");
   const arc=`M398 124 A40 40 0 ${degrees===270?1:0} 0 ${degrees===270?358:438} 84`;
   const right=step<2?`<text x="316" y="30">QB14 · native rotation</text><circle cx="398" cy="84" r="40" fill="none" stroke="#45637c"/><path class="rotationArc" d="${arc}" fill="none" stroke="#ffd28a" stroke-width="5" pathLength="1"/><circle cx="${degrees===270?358:438}" cy="84" r="5" fill="#ffd28a"/><text x="398" y="156" text-anchor="middle">${degrees}° · phase 270°</text>`:
     step===2?'<text x="310" y="42">Compiler tracks the Pauli</text><text x="310" y="82" fill="#ffd28a">Gate → later CZ gates</text><text x="310" y="122">Readout → detector parity</text>':
     '<text x="294" y="32">3-round Z memory · IQM</text>'+rows.map((r,i)=>`<text x="294" y="${61+29*i}" fill="${i?"#b7c9dc":"#ffd28a"}">${esc(r.pipeline)} · ${r.twirling?"twirled":"control"} · ${pct(r.probability)}</text>`).join("");
   drawing.innerHTML=`<svg viewBox="0 0 535 205" role="img" aria-label="${names[step]} on the distance-3 surface code" fill="#e6eff7" font-size="14">${lattice}<path d="M${fx} ${fy+12} V180 H120" fill="none" stroke="#ffd28a"/><text x="125" y="185" fill="#ffd28a">QB14 · Z ancilla</text>${right}</svg>`;
   host.querySelector(".lessonCaption").textContent=copy[step];
   choice.querySelectorAll("button").forEach((b,i)=>b.setAttribute("aria-pressed",String(i===step)));
 }
 choice.onclick=e=>{if(e.target.dataset.step!==undefined){step=+e.target.dataset.step;draw();}};
 host.querySelector("input").oninput=e=>{yaw=+e.target.value*Math.PI/180;draw();};
 draw();
}
function scene(container, distance, fixed=false){
 const data=shapes[distance];
 if(!data)return;
 const center=distance, width=730,height=365;
 const projected=data.nodes.map(q=>{
  let u=q.x-center,v=q.y-center,z=q.type==="data"?0:.6;
  let a=u*Math.cos(spin)-v*Math.sin(spin),b=u*Math.sin(spin)+v*Math.cos(spin);
  let scale=30*zoom*(5/distance);
  return {...q,px:width/2+panX+a*scale,py:height/2+panY+(b*Math.cos(tilt)-z*Math.sin(tilt))*scale,depth:b*Math.sin(tilt)+z*Math.cos(tilt)};
 });
 const qs=new Map(projected.map(q=>[q.id,q]));
 const nearby=new Set(data.edges.filter(e=>e.includes(selected)).flat());
 const hits=new Set(projected.filter(q=>nearby.has(q.id)&&q.type!=="data"&&(fault==="Y"||q.type!==fault)).map(q=>q.id));
 const color={data:"#73aaff",X:"#fb7e80",Z:"#55cfc5"};
 container.innerHTML=`<svg viewBox="0 0 ${width} ${height}" aria-label="Rotated surface code" style="cursor:grab"><defs>${Object.entries(color).map(([k,c])=>`<radialGradient id="${container.id}-${k}" cx="35%" cy="30%"><stop stop-color="#fff"/><stop offset=".38" stop-color="${c}"/><stop offset="1" stop-color="#18364e"/></radialGradient>`).join("")}</defs>${data.edges.map(([a,b],i)=>`<line x1="${qs.get(a).px}" y1="${qs.get(a).py}" x2="${qs.get(b).px}" y2="${qs.get(b).py}" stroke="${nearby.has(a)&&nearby.has(b)||frame>0&&data.layers[a+"-"+b]===frame-1?"#55cfc5":"#365975"}" stroke-width="2"/>`).join("")}${projected.sort((a,b)=>a.depth-b.depth).map(q=>`<circle data-qubit="${q.id}" tabindex="0" cx="${q.px}" cy="${q.py}" r="${q.id===selected||demoStep>=2&&hits.has(q.id)?13:9}" stroke="${demoStep&&q.id===selected?"#ffd28a":demoStep>=2&&hits.has(q.id)?"#55cfc5":"none"}" stroke-width="3" fill="url(#${container.id}-${q.type})"><title>Q${q.id} · ${q.type}</title></circle>`).join("")}</svg>`;
 if(fixed)return;
 const svg=container.querySelector("svg");
 svg.onpointerdown=e=>{
  if(e.target.dataset.qubit){selected=+e.target.dataset.qubit;demoStep=0;render();return;}
  const initial=e.clientX, initialY=e.clientY, pan=e.shiftKey;
  function up(event){
   if(pan){panX+=event.clientX-initial;panY+=event.clientY-initialY;}
   else{spin+=(event.clientX-initial)*.012;tilt=Math.max(0,Math.min(1.35,tilt+(event.clientY-initialY)*.008));}
   render();
  }
  window.addEventListener("pointerup",up,{once:true});
 };
 svg.onwheel=e=>{e.preventDefault();zoom=Math.max(.45,Math.min(2,zoom-e.deltaY*.001));render();};
 const q=qs.get(selected);
 container.insertAdjacentHTML("beforeend",`<div class="toolbar"><span class="key">Blue data · Red X checks · Turquoise Z checks · Shift-drag to pan</span><div><button id="flat">2D / 3D</button> <button id="play">${timer?"Pause":"Play"}</button> <button id="step">Next layer</button> <button id="faultStep">Advance error demo</button> <select aria-label="Injected Pauli" id="fault"><option>X</option><option>Y</option><option>Z</option></select></div></div><p class="key">Educational layout · ${q?esc(q.type==="data"?`Data qubit Q${q.id}`:`${q.type} stabilizer Q${q.id}: ${[...nearby].filter(k=>k!==q.id).map(k=>q.type+k).join(" ")}`):"Select a qubit to inspect its stabilizer."}</p>`);
  $("fault").value=fault;
 $("fault").onchange=e=>{fault=e.target.value;demoStep=0;render();};
 $("faultStep").onclick=()=>{
  if(q?.type!=="data"){selected=data.nodes.find(a=>a.type==="data").id;demoStep=0;}
  demoStep=(demoStep+1)%5;render();
 };
 if(demoStep){
  const messages=[null,`Inject ${fault} on data qubit Q${selected}.`,`Anticommuting stabilizers change sign: ${[...hits].map(q=>"Q"+q).join(", ")}.`,"The decoder uses the syndrome to infer a correction. The fault location is known here because we injected it.","For an isolated single-qubit Pauli fault, the ideal code can correct it and preserve the logical state."];
  container.insertAdjacentHTML("beforeend",`<p>${esc(messages[demoStep])}</p>`);
 }
 if(distance===3){
   container.insertAdjacentHTML("beforeend",'<details class="latticeLesson"><summary>Explore gate twirling on this patch</summary><div></div></details>');
   twirlLesson(container.lastElementChild.lastElementChild);
 }
 $("flat").onclick=()=>{tilt=tilt?0:.55;render();};
 $("step").onclick=()=>{frame=(frame+1)%5;render();};
 $("play").onclick=()=>{if(timer){clearInterval(timer);timer=0;}else timer=setInterval(()=>{frame=(frame+1)%5;render();},650);render();};
}
function describe(a){
 selectedRecord=a;
 $("shotButton").disabled=!(a?.raw&&a?.model);
 $("shotIndex").max=(a?.shots??1)-1;
 $("detail").innerHTML=a?`<strong>${pct(a.probability)}</strong> · ${n(a.failures)} failures / ${n(a.shots)} shots · 95% CI ${a.interval.map(pct).join("–")}<br>${esc(a.pipeline)} · ${esc(a.decoder)} · ${esc(a.source)}<br>Job ${esc(a.job)} · Calibration ${esc(a.calibration)}<br>Source <code>${esc(a.file)}</code>${a.audit?.swaps===0?" · ZERO SWAPs — VERIFIED":""}${a.raw?` · <a href="/api/raw?record=${encodeURIComponent(a.id)}">Download raw source</a>`:""}`:
 state.source==="IQM_HARDWARE"?"No IQM hardware measurement exists for this selected configuration.":"No simulation matches this selection. Run one in the noise lab.";
 if(a?.audit?.swap>0){
   $("detail").insertAdjacentHTML("beforeend",`<p>Routed circuit · ${n(a.audit.swap)} SWAPs · ${n(a.audit.native_operations.cz)} native CZ gates</p>`);
 }
 if(a?.routed_redecode){
   const alt=a.routed_redecode;
   $("detail").insertAdjacentHTML("beforeend",`<p><b>Same shots, routing-aware decoder</b> · ${alt.failures} / ${n(alt.shots)} failures · ${pct(alt.failures/alt.shots)} (95% CI ${alt.interval.map(pct).join("–")}). The alternative decoder includes errors on the submitted rotations and CZ gates using assumed rates. Paired exact p = ${alt.paired_exact_p.toFixed(3)}.<br><code>${esc(a.audit_file)}</code></p>`);
 }
 if(!a&&state.source==="IQM_HARDWARE"&&state.distance===5&&db.pilot){
   const pilot=db.pilot;
   const available=pilot.status==="complete";
   const status=available?"completed":pilot.status;
   $("detail").insertAdjacentHTML("beforeend",`<p><strong>Emerald pilot · ${esc(status)}</strong><br>Qiskit · Z memory · 3 rounds · Twirling off · ${n(pilot.shots)} submitted shots<br>Job <code>${esc(pilot.job_id)}</code></p><button id="pilotFilters">Select pilot settings</button> <button id="refreshPilot">Refresh data</button>`);
   $("pilotFilters").onclick=()=>{
     Object.assign(state,{pipeline:"qiskit",rounds:3,basis:"Z",twirling:false,decoder:"Any"});
     $("rounds").value=3;$("calibration").value="";$("jobFilter").value="";
     controls();render();
   };
   $("refreshPilot").onclick=async()=>{
     const button=$("refreshPilot");button.disabled=true;
     try{await reloadArchive();}
     catch(error){button.disabled=false;button.textContent="Retry refresh";}
   };
 }
}
async function reloadArchive(){
 const response=await fetch("/api/records",{cache:"no-store"});
 if(!response.ok)throw Error("Archive refresh failed");
 db=await response.json();
 controls();render();archive();
}
function render(){
 $("roundValue").value=state.rounds;
 const rows=db.records.filter(r=>same(r)&&!(
   r.source==="IQM_HARDWARE"&&r.pipeline?.toLowerCase()==="qiskit"&&r.twirling==null));
 const matches=rows.filter(r=>r.rounds===state.rounds);
 if(view==="chart"){
   $("visualization").innerHTML=chart(rows);
   $("visualization").onclick=e=>{const item=e.target.closest("[data-row]");if(item)describe(rows[+item.dataset.row]);
   if(e.target.id==="svgExport")download("logical-error.svg",new XMLSerializer().serializeToString($("chart")),"image/svg+xml");
   if(e.target.id==="pngExport")exportPng($("chart"));};
   $("visualization").onkeydown=e=>{if(e.key==="Enter"&&e.target.dataset.row)describe(rows[+e.target.dataset.row]);};
   const chartSvg=$("chart");
   if(chartSvg)enableChartNavigation(chartSvg);
 }else{ $("visualization").onclick=null;scene($("visualization"),state.distance);}
 const preferred=matches.find(a=>a.decoder==="BP+OSD characterized"&&a.shots===10000);
 describe(preferred??matches.at(-1));
 if(matches.length>1){
   const picker=document.createElement("select");
   picker.setAttribute("aria-label","Measurement at selected round");
   for(const row of matches){
     picker.add(new Option(`${row.decoder} · ${pct(row.probability)} · ${row.job??row.id}`,row.id));
   }
   picker.value=selectedRecord.id;
   picker.onchange=()=>describe(matches.find(row=>row.id===picker.value));
   $("visualization").append(picker);
 }
 $("distances").innerHTML=[3,5].map(d=>{
   const r=db.records.find(v=>v.distance===d&&v.basis==="Z"&&v.source==="IQM_HARDWARE"&&v.file.includes(d===3?"/basis_pilot/":"/routing_followup/"));
   const geom=shapes[d],points=new Map(geom.nodes.map(q=>[q.id,[12+q.x*9,12+q.y*9]]));
   const patch=geom.edges.map(([a,b])=>`<polyline points="${points.get(a)} ${points.get(b)}" fill="none" stroke="#51778b"/>`).join("")+geom.nodes.map(q=>`<circle cx="${points.get(q.id)[0]}" cy="${points.get(q.id)[1]}" r="3" fill="${q.type==="data"?"#98bfff":"#55cfc5"}"/>`).join("");
   return `<article><svg viewBox="0 0 ${24+18*d} ${24+18*d}" aria-label="Distance ${d} patch">${patch}</svg><div><h3>Distance ${d}</h3><p>${d*d} data qubits + ${d*d-1} check qubits</p><strong>${r?pct(r.probability):"Unmeasured"}</strong>${r?`<p>${r.failures} failures in ${n(r.shots)} shots<br>${r.audit.swap??r.audit.swaps} routing SWAPs</p>`:""}</div></article>`;
 }).join("");
 const matched=db.records.filter(a=>a.source==="SIMULATION"&&a.settings?.seed===51226&&a.settings?.profile==="balanced");
 $("distanceCurve").innerHTML=matched.length?chart(matched.map(a=>({...a,pipeline:"Stim d="+a.distance})),db.simulation_fits).replace(/id="chart"/g,"").replace(/<button.*$/s,""):"";
 if(db.simulation_fits){const f=db.simulation_fits;$("distanceCurve").insertAdjacentHTML("beforeend",`<p>Matched balanced-noise simulation · fitted per round ${pct(f["3"].rate)} (d=3) and ${pct(f["5"].rate)} (d=5) · suppression factor ${(f["3"].rate/f["5"].rate).toFixed(2)}×.</p>`);}
 $("pilotStatus").textContent="On the shared Emerald calibration, the smaller patch preserved the Z-memory value more often after three rounds. The distance-5 follow-up needed extra routing and exposed more qubits to noise. These jobs measure the combined effect of the code, its placement and the hardware.";
 const pilots=db.records.filter(r=>r.source==="IQM_HARDWARE"&&/\/(basis_pilot|routing_followup|routed_hardware)\//.test(r.file));
 $("pilotComparison").innerHTML=pilots.length?`<h3>Three-round IQM checks</h3><div class="tableScroll"><table><thead><tr><th>Memory</th><th>Failures / shots</th><th>Logical failure (95% CI)</th><th>SWAPs</th><th>Native CZ</th><th>Depth</th><th>Calibration ID</th></tr></thead><tbody>${pilots.map(r=>`<tr title="${esc(r.job)}"><td>d=${r.distance} · ${r.basis}</td><td>${r.failures} / ${n(r.shots)}</td><td>${pct(r.probability)} (${r.interval.map(pct).join("–")})</td><td>${r.audit.swap??r.audit.swaps}</td><td>${(r.audit.operations??r.audit.native_operations).cz}</td><td>${r.audit.depth}</td><td>${esc(r.calibration)}</td></tr>`).join("")}</tbody></table></div><p>Qiskit, twirling off, standard dynamical decoupling and correlated matching. Each interval describes shot uncertainty for one circuit. Compare calibration IDs before attributing a difference to routing.</p>`:"";
}
function enableChartNavigation(svg){
 let box=[0,0,730,360];
 function update(){svg.setAttribute("viewBox",box.join(" "));}
 svg.onwheel=e=>{
  if(!e.ctrlKey)return;
  e.preventDefault();
  const scale=Math.min(1.15,Math.max(.85,1+e.deltaY*.001));
  const width=Math.min(730,Math.max(220,box[2]*scale)),height=width*360/730;
  box=[box[0]+(box[2]-width)/2,box[1]+(box[3]-height)/2,width,height];update();
 };
 svg.onpointerdown=e=>{
  if(!e.shiftKey)return;
  const start=[e.clientX,e.clientY],factor=box[2]/svg.clientWidth;
  window.addEventListener("pointerup",up=>{box[0]-=(up.clientX-start[0])*factor;box[1]-=(up.clientY-start[1])*factor;update();},{once:true});
 };
 svg.ondblclick=()=>{box=[0,0,730,360];update();};
}
function exportPng(svg){
 const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)],{type:"image/svg+xml"}));
 const image=new Image();
 image.onload=()=>{const canvas=document.createElement("canvas");canvas.width=1460;canvas.height=720;
 canvas.getContext("2d").drawImage(image,0,0,1460,720);URL.revokeObjectURL(url);
 canvas.toBlob(blob=>download("logical-error.png",blob,"image/png"));};
 image.onerror=()=>URL.revokeObjectURL(url);
 image.src=url;
}
function download(filename,data,type){
 const url=URL.createObjectURL(new Blob([data],{type})),a=document.createElement("a");a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
const tableKeys=["id","job","distance","pipeline","basis","rounds","shots","twirling","decoder","backend","calibration","probability","interval","source","status"];
function archive(){
 const q=$("search").value.toLowerCase(),rows=db.records.filter(row=>tableKeys.some(k=>String(row[k]).toLowerCase().includes(q)));
 $("table").innerHTML=`<table><thead><tr>${tableKeys.map(k=>`<th>${esc(k)}</th>`).join("")}</tr></thead><tbody>${rows.map(o=>`<tr>${tableKeys.map(k=>`<td>${esc(k==="probability"?pct(o[k]):k==="interval"?o[k]?.map(pct).join("–"):o[k])}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
 $("csv").onclick=()=>download("experiments.csv",[tableKeys,...rows.map(a=>tableKeys.map(k=>a[k]))].map(line=>line.map(v=>'"'+String(v??"").replaceAll('"','""')+'"').join(",")).join("\r\n"),"text/csv");
}
const workflow=[
 ["Python / Stim","Define the memory","Python builds a rotated surface code and reuses the ancillas across rounds without resetting them. Stim records which measurement parities should be predictable.","native_memory.py"],
 ["Qiskit / Qrisp","Translate the circuit","Both paths translate the stabilizer schedule into instructions for IQM. Classical bit indices preserve the order needed for decoding.","stim_to_qiskit.py · twirl_memory.py"],
 ["Characterization","Measure the readout bias","In our characterized distance-3 comparison, readout measurements informed the weights used by the decoder. The calibration ID also lets us identify which jobs shared device settings.","device_noise.py / decoder_sweep.json"],
 ["Native compilation","Map gates to the chip","The compiler assigns physical qubits and emits rotations, CZ gates and measurements. The ideal payload audit checks measurement keys and parities before a job runs.","dashboard/verify_routed_payload.py"],
 ["Gate twirling","Randomize the native gates","We created seeded variants, tracked the Pauli frame and verified the ideal measurement parities. Twirled circuits and their controls shared the same logical task.","twirl_memory.py"],
 ["IQM Emerald","Execute repeated shots","We submit the native circuits, calibration ID and shot count to Resonance. The matched pilots used standard dynamical decoupling during eligible idle periods. Each shot prepares the memory and runs every stabilizer round on the QPU.","run_on_hardware.py"],
 ["Readout","Recover the syndrome","IQM returns classical measurement bits. The saved measurement keys put them in circuit order. Detector parities reveal changes across rounds and at the boundaries.","extract_syndromes.py"],
 ["Decoder","Count logical failures","The decoder predicts the logical flip from detector events. Comparing the prediction with the measured logical observable gives one success or failure per shot.","qec_analysis.py"]
];
function setupDeviceFigure(){
 const slider=$("chipRotation");
 function draw(){
   const angle=Number(slider.value)*Math.PI/180;
   const project=(x,y,z=0)=>[245+x*Math.cos(angle)-y*Math.sin(angle),149+.56*(y*Math.cos(angle)+x*Math.sin(angle))-z];
   const path=points=>points.map(p=>project(...p).join(",")).join(" ");
   function slab(x,y,w,h,z,depth,color){
     const top=[[x,y,z],[x+w,y,z],[x+w,y+h,z],[x,y+h,z]];
     const sides=top.map((a,i)=>{const b=top[(i+1)%4];return `<polygon points="${path([a,b,[b[0],b[1],z-depth],[a[0],a[1],z-depth]])}" fill="#1e4053" stroke="#457183"/>`;}).join("");
     return sides+`<polygon points="${path(top)}" fill="${color}" stroke="#85b4bc"/>`;
   }
   let body=slab(-170,-100,340,200,0,16,"#182f41");
   for(let x=-150;x<=150;x+=25)body+=`<polyline points="${path([[x,-99,0],[x,99,0]])}" stroke="#244353"/>`;
   for(let y=-75;y<=75;y+=25)body+=`<polyline points="${path([[-169,y,0],[169,y,0]])}" stroke="#244353"/>`;
   body+=slab(-130,-52,108,104,6,5,"#39968e")+slab(22,-52,108,104,6,5,"#39968e");
   body+=slab(-22,-4,20,8,6,3,"#d6bf96")+slab(2,-4,20,8,6,3,"#d6bf96")+slab(-2,-4,4,8,7,4,"#ffe6ac");
   const callout=(target,bend,end,label)=>`<polyline points="${[project(...target),bend,end].map(p=>p.join(",")).join(" ")}" fill="none" stroke="#afc8cc"/><circle cx="${project(...target)[0]}" cy="${project(...target)[1]}" r="3" fill="#fff"/><text x="${end[0]}" y="${end[1]-8}" text-anchor="middle" fill="#e3efef" font-size="14">${label}</text>`;
   $("transmon").innerHTML=`<svg viewBox="0 0 490 277" role="img" aria-label="Rotatable transmon schematic with two capacitor pads joined by a Josephson junction">${body}${callout([0,0,7],[272,58],[337,58],"Josephson junction")}${callout([-82,29,6],[126,231],[94,231],"Capacitor pad")}</svg>`;
 }
 slider.oninput=draw;draw();
}
function showRecommendation(){
 const rows=db.records.filter(r=>r.source==="IQM_HARDWARE"&&r.distance===3&&r.rounds===3&&r.basis==="Z"&&r.shots===10000&&r.decoder==="BP+OSD characterized"&&r.file.includes("confirm_10000")).sort((a,b)=>a.probability-b.probability);
 if(!rows.length)return;
 $("recommendation").innerHTML=`<p class="sectionLead">We would run the zero-SWAP distance-3 memory again. Twirled Qrisp had the lowest observed failure probability in our matched three-round Z-memory comparison. The confidence intervals overlap.</p><div class="resultsStrip">${rows.map(r=>`<div><span>${esc(r.pipeline)} / ${r.twirling?"twirled":"control"}</span><strong>${pct(r.probability)}</strong><small>${r.failures} failures in 10,000 shots</small></div>`).join("")}</div><p class="key">All four results use BP+OSD decoding with characterized readout weights.</p>`;
}
function setupWorkflow(){
 const slots=[[-129,-48],[-43,-48],[43,-48],[129,-48],[129,48],[43,48],[-43,48],[-129,48]];
 let stage=0, twirl=false;
 const diagram=$("flowDiagram"), model=$("flowScene"), angle=$("flowAngle");
 diagram.innerHTML=workflow.map(([name],i)=>`<li><button data-stage="${i}">${esc(name)}</button></li>`).join("");
 function draw(){
   const yaw=Number(angle.value)*Math.PI/180, tilt=.69;
   function point(x,y,z=0){
     const a=x*Math.cos(yaw)-y*Math.sin(yaw), b=x*Math.sin(yaw)+y*Math.cos(yaw);
     return [216+1.26*a,110+.78*b-tilt*z];
   }
   const polygon=(pts,fill,stroke)=>`<polygon points="${pts.map(p=>point(...p).join(",")).join(" ")}" fill="${fill}" stroke="${stroke}" stroke-linejoin="round"/>`;
   const segment=(a,b,color,width)=>`<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="${color}" stroke-width="${width}" stroke-linecap="round"/>`;
   let drawing=slots.slice(1).map((p,i)=>segment(point(...slots[i]),point(...p),i<stage?"#58cec2":"#375774",3)).join("");
   const order=slots.map(([x,y],i)=>({x,y,i,depth:x*Math.sin(yaw)+y*Math.cos(yaw)})).sort((a,b)=>a.depth-b.depth);
   for(const {x,y,i} of order){
     const active=i===stage, ink=active?"#75f0de":"#80b2db", edge=active?"#55cfc5":"#52779c";
     const corners=[[-30,-20],[30,-20],[30,20],[-30,20]].map(([u,v])=>[x+u,y+v]);
     let object="";
     for(let s=0;s<4;s++){
       const a=corners[s],b=corners[(s+1)%4];
       object+=polygon([[...a,0],[...b,0],[...b,13],[...a,13]],"#19334e",edge);
     }
     object+=polygon(corners.map(p=>[...p,13]),active?"#185952":"#254766",edge);
     const glyph=(a,b)=>segment(point(x+a[0],y+a[1],14),point(x+b[0],y+b[1],14),ink,1.8);
     if(i===4){
       const arc=Array.from({length:25},(_,j)=>point(x+16*Math.cos(j*Math.PI/16),y+16*Math.sin(j*Math.PI/16),16));
       object+=arc.slice(1).map((pt,j)=>segment(arc[j],pt,"#ffd28a",3)).join("");
     }else if(i===5){
       const geometry=shapes[3],lookup=new Map(geometry.nodes.map(q=>[q.id,[(q.x-3)*3.5,(q.y-3)*3.5]]));
       object+=geometry.edges.map(([a,b])=>glyph(lookup.get(a),lookup.get(b))).join("");
     }else{
       const strokes=[
         [[[-10,-8],[-18,0]],[[-18,0],[-10,8]],[[10,-8],[18,0]],[[18,0],[10,8]],[[4,-10],[-4,10]]],
         [[[-18,0],[-5,0]],[[-5,0],[8,-9]],[[-5,0],[8,9]],[[8,-9],[20,-9]],[[8,9],[20,9]]],
         [[[-18,-7],[18,-7]],[[-18,7],[18,7]],[[-5,-7],[-5,7]],[[9,-7],[9,7]]],
         [],[[[-19,7],[-10,7]],[[-10,7],[-10,-7]],[[-10,-7],[0,-7]],[[0,-7],[0,7]],[[0,7],[10,7]],[[10,7],[10,-7]],[[10,-7],[18,-7]]],
         [[[-15,0],[-5,9]],[[-5,9],[15,-10]]]
       ];
       const symbol=[0,1,2,2,2,3,4,5][i];
       object+=strokes[symbol].map(([a,b])=>glyph(a,b)).join("");
     }
     const label=point(x,y+29,-3);
     drawing+=`<g data-stage="${i}" style="cursor:pointer"><title>${esc(workflow[i][0])}</title>${object}<text x="${label[0]}" y="${label[1]}" text-anchor="middle" fill="${ink}" font-size="10">${esc(workflow[i][0])}</text></g>`;
   }
   model.innerHTML=`<svg viewBox="0 0 432 215" role="img" aria-label="Rotatable 3D model of the eight workflow stages">${drawing}</svg>`;
   const [,title,body,file]=workflow[stage];
   $("flowName").textContent=title;$("flowText").textContent=body;$("flowFile").textContent=file;
   if(stage===4 && twirl){
     $("flowName").textContent="Gate twirling before submission";
     $("flowText").textContent="In the archived distance-3 Qiskit example, the first rotation on QB14 changes from 90 degrees to 270 degrees at the same drive phase. The compiler tracks the Pauli frame across the circuit so the ideal measurement parities agree.";
     $("flowFile").textContent="Qiskit / 3 rounds / twirl seed 22112326 / job 01a200d4-e330-749d-8181-af771047036b";
   }
   $("flowTwirl").setAttribute("aria-pressed",String(twirl && stage===4));
   if(twirl && stage===4)twirlLesson(model);
   diagram.querySelectorAll("button").forEach((el,i)=>el.setAttribute("aria-pressed",String(i===stage)));
   $("flowPrev").disabled=stage===0;$("flowNext").disabled=stage===workflow.length-1;
 }
 function select(e){const node=e.target.closest("[data-stage]");if(node){stage=+node.dataset.stage;draw();}}
 $("flowTwirl").onclick=()=>{twirl=stage!==4 || !twirl;stage=4;draw();};
 diagram.onclick=select;model.onclick=select;angle.oninput=draw;
 $("flowPrev").onclick=()=>{stage--;draw();};$("flowNext").onclick=()=>{stage++;draw();};
 draw();
}
async function start(){
 const responses=await Promise.all([fetch("/api/records"),fetch("/api/geometry/3"),fetch("/api/geometry/5")]);
 [db,shapes[3],shapes[5]]=await Promise.all(responses.map(r=>r.json()));
 setupWorkflow();
 setupDeviceFigure();
 showRecommendation();
 $("metrics").innerHTML=metrics([["IQM jobs",n(db.hardware_jobs)],["Archived hardware shots",n(db.hardware_shots)],["Maximum measured rounds",Math.max(...db.records.filter(r=>r.source==="IQM_HARDWARE").map(r=>r.rounds))],["Pipelines","Qiskit / Qrisp"]]);
 controls();render();archive();
 setInterval(()=>{
   if(db.pilot&&db.pilot.status!=="complete"&&state.distance===5&&state.source==="IQM_HARDWARE"&&view==="chart"){
     reloadArchive().catch(()=>{});
   }
 },30000);
 renderTopology();
 $("shotForm").onsubmit=showShot;
 $("rounds").oninput=e=>{state.rounds=+e.target.value;render();};
 $("calibration").oninput=render;$("jobFilter").oninput=render;$("search").oninput=archive;
 $("view").onclick=()=>{view=view==="chart"?"scene":"chart";$("view").textContent=view==="chart"?"3D surface code":"Logical error chart";render();};
 const number=(name,label,value,min,max,step)=>`<div><label for="noise-${name}">${label}</label><input id="noise-${name}" required name="${name}" type="number" value="${value}" min="${min}" max="${max}" step="${step}"></div>`;
 const choice=(name,label,values)=>`<div><label for="noise-${name}">${label}</label><select id="noise-${name}" name="${name}">${values.map(v=>`<option>${v}</option>`).join("")}</select></div>`;
 $("noiseInputs").innerHTML=choice("distance","Distance",[3,5])+number("rounds","Rounds",3,1,20,1)+choice("basis","Memory basis",["Z","X"])+choice("decoder","Decoder",["plain","correlated"])+choice("profile","Noise profile",["balanced","readout","idle","phase"])+number("shots","Simulation shots",2000,1,20000,1)+number("seed","Random seed",42,0,99999999,1)+[["p","Single-qubit error"],["cz","CZ error"],["readout","Readout error"],["prep","Preparation error"],["idle","Idle error"]].map(([k,label])=>number(k,label,.003,0,.1,.0001)).join("");
 $("noise").onsubmit=async e=>{
  e.preventDefault();const button=e.submitter;button.disabled=true;$("simStatus").textContent="Running Stim simulation…";
  try{const response=await fetch("/api/simulate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))}),out=await response.json();
  if(!response.ok)throw Error(out.error);db.records.push(out);$("simStatus").textContent=`Simulation · ${n(out.failures)} / ${n(out.shots)} failures (${pct(out.probability)}).`;
  Object.assign(state,{distance:out.distance,rounds:out.rounds,source:"SIMULATION",basis:out.basis,pipeline:"stim",twirling:false,decoder:out.decoder});$("rounds").value=out.rounds;$("calibration").value="";controls();render();archive();
  }catch(error){$("simStatus").textContent=error.message;}finally{button.disabled=false;}
 };
}
function renderTopology(){
 const t=db.topology;
 if(!t?.positions){$("topologyGraphic").textContent="Topology coordinates unavailable.";return;}
 const layout=new Set(t.distances?.["3"]?.layout??[]);
 const [w,h]=[730,395];
 let turn=0, magnification=1;
 function draw(){
 const xy=t.positions.map(([x,y])=>{const dx=x-w/2,dy=y-h/2;return [w/2+(dx*Math.cos(turn)-dy*Math.sin(turn))*magnification,h/2+(dx*Math.sin(turn)+dy*Math.cos(turn))*.9*magnification];});
 $("topologyGraphic").innerHTML=`<p>${esc(t.source)} · calibration ${esc(t.calibration)} · turquoise marks the verified distance-3 patch</p><svg viewBox="0 0 ${w} ${h}">${t.edges.map(([a,b])=>`<line x1="${xy[a][0]}" y1="${xy[a][1]}" x2="${xy[b][0]}" y2="${xy[b][1]}" stroke="#426282"/>`).join("")}${xy.map(([x,y],i)=>`<g><circle cx="${x}" cy="${y}" r="5" fill="${layout.has(i)?"#55cfc5":"#7795ad"}"><title>${t.qubits[i]}</title></circle><text x="${x+6}" y="${y-4}" font-size="9" fill="#aabbd0">${t.qubits[i]}</text></g>`).join("")}</svg><p class="key">Drag to rotate the schematic. Scroll over the graph to zoom.</p>`;
 const svg=$("topologyGraphic").querySelector("svg");
 svg.onpointerdown=e=>{const x=e.clientX;window.addEventListener("pointerup",event=>{turn+=(event.clientX-x)*.008;draw();},{once:true});};
 svg.onwheel=e=>{e.preventDefault();magnification=Math.max(.5,Math.min(2.5,magnification-e.deltaY*.001));draw();};
 }
 draw();
}
async function showShot(e){
 e.preventDefault();
 const target=$("shotDetails");
 target.textContent="Converting the saved measurements to detector events...";
 try{
  const response=await fetch("/api/shot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:selectedRecord.id,index:+$("shotIndex").value})});
  const result=await response.json();if(!response.ok)throw Error(result.error);
  const fired=new Set(result.events.map(p=>p.join(",")));
  const sites=[...new Set(result.coordinates.map(q=>q.slice(0,2).join(",")))];
  const cols=Math.max(1,...result.coordinates.map(q=>q[2]??0))+1;
  const cells=result.coordinates.map((q,i)=>{const x=60+(q[2]??0)*Math.min(28,620/cols),y=24+sites.indexOf(q.slice(0,2).join(","))*11;return `<rect x="${x}" y="${y}" width="${Math.min(25,580/cols)}" height="8" fill="${fired.has(q.join(","))?"#55cfc5":"#304962"}"><title>Detector ${i} · ${q.join(", ")} · archive firing ${pct(result.rates[i])}</title></rect>`;}).join("");
  target.innerHTML=`<p>${esc(result.order)} · ${result.events.length} detectors fired · logical observable flip ${Number(result.observable)} · decoder prediction ${result.prediction==null?"unavailable":Number(result.prediction)}</p><svg viewBox="0 0 730 ${45+11*sites.length}"><text x="4" y="14" fill="#aabbd0" font-size="11">Detector sites by round</text>${cells}</svg><p>Syndrome weights by number of fired detectors · ${result.weights.map((x,i)=>`${i}: ${x}`).join(" · ")}</p>`;
 }catch(error){target.textContent=error.message;}
}
start().catch(e=>{$("detail").textContent=e.message;});









