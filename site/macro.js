/* Official Macro JSON only. Never imports values into the Market Weather simulator. */
(() => {
 const el=id=>document.getElementById(id),esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
 const core=[['kto_inbound','방한 외래관광객 수'],['kto_outbound','국민 해외관광객 수'],['kto_tourism_receipts','관광수입'],['kto_tourism_expenditure','관광지출']];
 let db=null,health=null,loading=false,failed=false,healthUnknown=false,metric='kto_inbound',range=36;
 const fmt=n=>Number(n).toLocaleString('ko-KR'),pct=n=>n==null?'비교 자료 없음':`${n>=0?'+':''}${Number(n).toFixed(2)}%`;
 const money=i=>i?.value_kind==='money_nonnegative'&&i?.unit==='US$';
 const number=(value,i)=>{if(!money(i))return fmt(value);const digits=String(value).padStart(7,'0'),fraction=digits.slice(-6).replace(/0+$/,'');return fmt(Number(digits.slice(0,-6)))+(fraction?'.'+fraction:'');};
 const unit=i=>money(i)?'백만 US$':i?.unit||'단위 미검증';
 const chartUnit=i=>money(i)?'실적 백만 US$ (원장 US$)':'실적 명 (축: 만 명)';
 const date=s=>s?new Date(s).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}):'미확인';
 const safeUrl=s=>{try{return new URL(s).protocol==='https:'?s:'';}catch(_){return '';}};
 const link=(url,label)=>safeUrl(url)?`<a class="external macro-source" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`:'';
 const finality=o=>o?.finality==='provisional'?'잠정':o?.finality==='final'?'확정':'공표치 · 확정 여부 미표기';
 const item=id=>db?.indicators.find(i=>i.id===id);
 function sourceState(i){
  if(!i?.connected)return '미연동';
  if(failed)return '자료 수집 실패 · 이전 검증값 유지';
  if(healthUnknown)return '수집 상태 확인 실패 · 기준기간 확인 필요';
  const source=health?.sources?.find(s=>s.id===i.source_id);
  if(source?.status==='error'||(health?.status==='failed'&&!source))return '자료 수집 실패 · 이전 검증값 유지';
  if(source?.status==='not_connected')return '자동 수집 미연결 · 이전 검증값';
  if(source?.status==='partial')return '일부 월 누락 · 이전 검증값 유지';
  if(!source?.last_successful_check||Date.now()-Date.parse(source.last_successful_check)>48*3600000)return '갱신 지연 · 마지막 검증값';
  const [y,m]=i.latest.period.split('-').map(Number),nextDue=new Date(Date.UTC(y,m+2,0,15));
  if(!money(i)&&Date.now()>=nextDue.getTime())return '최신 공표 미확인 · 갱신 지연';
  return money(i)?'공식 API 연동':'공식 파일 연동';
 }
 function card(id,name){
  const i=item(id),o=i?.latest,s=sourceState(i);
  if(!o)return `<article class="card kpi macro-kpi" data-macro-id="${id}"><span class="label">${esc(name)}</span><div class="value macro-unavailable">미연동</div><div class="note">${esc(failed?'공식 통계 DB 수집 실패':i?.reason||'공식 자료 확인 전')}</div>${link(i?.source_url,'공식 출처')}</article>`;
  return `<article class="card kpi macro-kpi" data-macro-id="${id}"><span class="label">${esc(name)}</span><div class="value" data-value="${o.value}">${number(o.value,i)}<span>${esc(unit(i))}</span></div><div class="macro-period">기준 ${esc(o.period)} · 월간 실적</div>${money(i)?`<div class="tiny">전월 대비 ${pct(o.comparisons.mom_pct)}<br>전년 동월비 ${pct(o.comparisons.yoy_pct)}</div>`:o.comparisons.yoy_pct==null?'':`<span class="delta">전년 동월비 ${pct(o.comparisons.yoy_pct)}</span>`}<div class="note">${esc(finality(o))}${o.revision_status==='revised'?' · 정정 감지':''}<br>${esc(s)}${money(i)?`<br>최근 확인 ${esc(date(o.last_collected_at))}<br>공표일 ${esc(o.release_published_at?date(o.release_published_at):'API 미제공')} · 월별 공표 시차 있음`:''}</div>${link(i.source_url,esc(i.publisher))}</article>`;
 }
 function monthly(start,end){const out=[];let [y,m]=start.split('-').map(Number);while(`${y}-${String(m).padStart(2,'0')}`<=end){out.push(`${y}-${String(m).padStart(2,'0')}`);if(++m>12){m=1;y++;}}return out;}
 function chart(container,i,limit,growthMode=state.chart==='growth'){
  if(!i?.observations.length){container.innerHTML='<div class="empty">검증된 월별 통계가 없습니다.</div>';return;}
  const periods=monthly(i.first_period,i.latest_period),chosen=periods.slice(-Math.min(limit,periods.length)),lookup=new Map(i.observations.map(o=>[o.period,o]));
  const growth=growthMode;
  const rows=chosen.map(period=>{const o=lookup.get(period),prior=lookup.get(`${Number(period.slice(0,4))-1}${period.slice(4)}`);return {period,value:growth?(o&&prior&&prior.value!==0?(o.value/prior.value-1)*100:null):o?.value??null};});
  const vals=rows.filter(o=>o.value!==null).map(o=>o.value);
  if(!vals.length){container.innerHTML='<div class="empty">전년 동월 자료가 없어 증감률을 계산하지 않습니다.</div>';return rows.length;}
  const w=Math.max(280,Math.min(900,container.clientWidth||640)),h=250,left=money(i)?74:52,right=14,top=28,bottom=42,pw=w-left-right,ph=h-top-bottom;
  const low=Math.min(0,...vals),hi=Math.max(1,...vals),span=(hi-low)*1.12,max=low+span;
  const y=v=>top+ph*(1-(v-low)/(max-low)),baseline=y(0),bar=Math.max(2,Math.min(36,pw/rows.length*.58));
  const ticks=Array.from({length:5},(_,n)=>low+(max-low)*n/4).map(v=>`<line x1="${left}" y1="${y(v)}" x2="${w-right}" y2="${y(v)}" stroke="#DFE5ED" stroke-dasharray="4 5"/><text x="${left-8}" y="${y(v)+4}" text-anchor="end" fill="#52647A" font-size="12">${growth?fmt(Math.round(v))+'%':money(i)?Number(v/1000000).toLocaleString('ko-KR',{maximumFractionDigits:2}):fmt(Math.round(v/10000))+'만'}</text>`).join('');
  const stride=Math.max(1,Math.ceil(rows.length/Math.max(2,Math.floor(pw/64))));
  const bars=rows.map((o,n)=>{const x=left+pw*(n+.5)/rows.length,label=(n%stride===0||n===rows.length-1)&&!(n!==rows.length-1&&rows.length-1-n<stride*.6),year=o.period.slice(2).replace('-','.');
   const shape=o.value===null?`<text x="${x}" y="${top+ph-8}" font-size="12" text-anchor="middle" class="macro-series-gap">×<title>${esc(o.period)}: ${growth?'전년 비교 자료 없음':'월 자료 누락'}</title></text>`:`<rect data-period="${o.period}" data-value="${o.value}" x="${x-bar/2}" y="${Math.min(y(o.value),baseline)}" width="${bar}" height="${Math.max(.8,Math.abs(y(o.value)-baseline))}" rx="2" fill="${n===rows.length-1?'#F47735':'#173B73'}"><title>${o.period}: ${growth?pct(o.value):number(o.value,i)+' '+unit(i)}</title></rect>`;
   return shape+(label?`<text x="${x}" y="${h-14}" font-size="12" fill="#52647A" text-anchor="middle">${year}</text>`:'');
  }).join('');
  container.innerHTML=`<svg role="img" aria-label="${esc(i.name)} ${chosen[0]}~${chosen.at(-1)} ${growth?'전년 동월비':'월간 실적'}; 누락은 × 표시" viewBox="0 0 ${w} ${h}"><title>${esc(i.name)} · ${growth?'단위 %':money(i)?'단위 백만 US$ (원장 US$)':'단위 명 (축: 만 명)'}</title>${ticks}${bars}</svg>`;
  return rows.filter(o=>o.value===null).length;
 }
 function renderCharts(){
  const inbound=item('kto_inbound'),selected=item(metric)||inbound;
  chart(el('chart-overview'),inbound,12);const gaps=chart(el('chart-macro'),selected,range);
  document.querySelectorAll('[data-chart]').forEach(b=>b.classList.toggle('sel',b.dataset.chart===state.chart));
  if(inbound?.latest){
   el('home-inbound-meta').textContent=`${inbound.first_period}~${inbound.latest_period} 중 최근 12개월 · ${inbound.publisher} · ${state.chart==='growth'?'전년 동월비 %':'실적 명 (축: 만 명)'}`;
   el('home-inbound-foot').textContent=`공표 파일 ${date(inbound.latest.release_published_at)} · 최종 수집 ${date(inbound.latest.last_collected_at)} · ${finality(inbound.latest)} · ${sourceState(inbound)}. 월간 실적만 표시하며 누락 월을 0으로 채우지 않습니다.`;
  }
  if(selected?.latest){
   const o=selected.latest,c=o.comparisons;
   el('macro-chart-meta').textContent=`${selected.name} · ${selected.first_period}~${selected.latest_period} · ${selected.months}개월 확보 · ${state.chart==='growth'?'전년 동월비 %':chartUnit(selected)} · ${sourceState(selected)}`;
   el('macro-comparisons').innerHTML=`<div>전월 대비 (${c.mom_base_period})<strong>${pct(c.mom_pct)}</strong></div><div>전년 동월 대비 (${c.yoy_base_period})<strong>${pct(c.yoy_pct)}</strong></div><div>연초 누적 (${c.ytd_range.join('~')})<strong>${c.ytd_value==null?(money(selected)?'검증 가능한 누적 비교 자료 없음':'누락 월로 계산 생략'):number(c.ytd_value,selected)+' '+esc(unit(selected))}</strong></div><div>전년 동기 누적 대비<strong>${pct(c.ytd_yoy_pct)}</strong></div>`;
   el('macro-chart-foot').innerHTML=`${link(selected.source_url,money(selected)?'ECOS 공식 API 안내':'공식 공표문')}<br>공표 자료 ${esc(o.release_published_at?date(o.release_published_at):'API 공표일 미제공 (조회시각과 구분)')} · 최종 수집 ${esc(date(o.last_collected_at))}<br>${esc(finality(o))} · 조회 범위의 ${state.chart==='growth'?'비교 자료 없음':'누락 월'} ${gaps??0}개 · 0이나 보간값으로 채우지 않습니다.`;
  }
 }
 function render(){
  const markup=core.map(([id,name])=>card(id,name)).join('');el('home-macro-kpis').innerHTML=markup;el('macro-kpis').innerHTML=markup;
  const connected=db?.indicators.filter(i=>i.connected)||[],primary=connected.filter(i=>i.priority===1);
  const warning=failed||healthUnknown||connected.some(i=>!['공식 파일 연동','공식 API 연동'].includes(sourceState(i)));
  const text=connected.length?`핵심 월간 ${primary.length}/4개 연동 · 국적별 ${connected.filter(i=>i.country).length}개 · 기준 ${item('kto_inbound')?.latest_period||'미확인'}${core.slice(2).filter(([id])=>item(id)?.connected).map(([id,name])=>` · ${name} 기준 ${item(id).latest_period}`).join('')} · ${failed?'새 DB 확인 실패, 이전 검증값 보존':healthUnknown?'수집 상태 확인 실패':sourceState(item('kto_inbound'))}`:'검증된 공식 통계 데이터가 없습니다. 미연동 상태이며 정적 예시를 실시간 수치로 표시하지 않습니다.';
  for(const id of ['macro-status','home-macro-status']){el(id).textContent=text;el(id).classList.toggle('is-delayed',warning);}
  if(db){
   el('macro-metric').innerHTML=connected.map(i=>`<option value="${i.id}">${esc(i.name)}</option>`).join('')||'<option>연동 지표 없음</option>';
   if(!connected.some(i=>i.id===metric))metric=connected[0]?.id||'kto_inbound';el('macro-metric').value=metric;
   const current=item(metric),n=current?.latest?monthly(current.first_period,current.latest_period).length:0;el('macro-range').innerHTML=[12,36].filter(x=>x<=n).map(x=>`<option value="${x}">최근 ${x}개월</option>`).join('')+(n?`<option value="${n}">전체 (${n}개월)</option>`:'<option value="0">자료 없음</option>');
   if(![...el('macro-range').options].some(o=>Number(o.value)===range))range=n;el('macro-range').value=String(range);
   el('macro-registry').innerHTML=db.indicators.map(i=>`<div class="source-row macro-registry-row"><div class="macro-registry-heading"><b>${esc(i.name)}</b><span class="pill ${i.connected?'':'amber'}">${esc(sourceState(i))}</span></div><p>${esc(i.publisher)} · ${i.frequency==='A'?'연간':'월간'} · ${esc(unit(i))}${money(i)?' (원장 US$)':''}<br>최신 기준 ${esc(i.latest_period||'미연동')} · 최종 수집 ${esc(date(i.latest?.last_collected_at))}</p><details><summary>정의·집계 기준</summary>${esc(i.definition)}${!i.connected?'<p>'+esc(i.reason||'자료 경로 확인 필요')+'</p>':''}</details>${link(i.source_url,'공식 출처')}</div>`).join('');
  }
  renderCharts();
  window.DataObservation?.render(db,health,failed||healthUnknown);
  window.MarketObservation?.render(db, sourceState);
 }
 async function load(){
  if(loading)return;loading=true;
  try{
   const r=await fetch('./data/macro.json?v='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('macro_not_available');const candidate=await r.json();
   if(candidate.schema_version!==1||candidate.mode!=='verified_official_statistics'||!Array.isArray(candidate.indicators)||candidate.indicators.some(i=>!Array.isArray(i.observations)||(i.connected&&(!i.latest?.comparisons||!i.observations.some(o=>o.period===i.latest.period&&o.value===i.latest.value)))||i.observations.some(o=>!Number.isSafeInteger(o.value)||o.value<0||(money(i)?(!['kto_tourism_receipts','kto_tourism_expenditure'].includes(i.id)||i.source_id!=='ecos_general_travel'||o.unit!=='US$'||o.verification_status!=='official_api_validated'||o.collection_method!=='official_ecos_api'||i.display_unit!=='백만 US$'||i.display_divisor!==1000000):(o.verification_status!=='official_file_validated'||i.unit!=='명')))))throw Error('macro_invalid');
   db=candidate;failed=false;healthUnknown=false;
   try{const h=await fetch('./data/macro_health.json?v='+Date.now(),{cache:'no-store'});if(!h.ok)throw Error();health=await h.json();}catch(_){healthUnknown=true;}
  }catch(_){failed=true;}
  finally{loading=false;render();}
 }
 el('macro-metric').addEventListener('change',e=>{metric=e.target.value;render();});el('macro-range').addEventListener('change',e=>{range=Number(e.target.value);renderCharts();});
 window.MacroMonitor={load,renderCharts,render,renderReadOnlyChart:(container,indicator,mode)=>chart(container,indicator,12,mode==='growth'),get database(){return db;},get health(){return health;}};
 load();setInterval(load,300000);
})();
