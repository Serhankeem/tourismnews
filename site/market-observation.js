/* Read-only view over MacroMonitor's validated public object. No requests or writes. */
(()=>{
 const el=id=>document.getElementById(id),esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const ids=['kto_inbound','kto_outbound','kto_inbound_cn','kto_inbound_jp','kto_inbound_tw','kto_inbound_us','kto_inbound_vn'];
 const fmt=n=>n.toLocaleString('ko-KR'),pct=window.PercentageUI.html;
 const source=i=>{try{return new URL(i.source_url).protocol==='https:'?`<a class="external" href="${esc(i.source_url)}" target="_blank" rel="noopener noreferrer">${esc(i.publisher)} · 공식 출처 ↗</a>`:'';}catch(_){return '';}};
 let rows=[],status=()=> '수집 상태 미확인';
 const finality=o=>o.finality==='final'?'확정치':o.finality==='provisional'?'잠정치':'확정 여부 미표기';
 function valid(i){return ids.includes(i.id)&&i.connected&&i.frequency==='M'&&i.unit==='명'&&i.latest?.verification_status==='official_file_validated'&&Number.isSafeInteger(i.latest.value)&&i.latest.value>=0&&/^\d{4}-(0[1-9]|1[0-2])$/.test(i.latest.period)&&i.latest.comparisons&&Array.isArray(i.observations)&&i.observations.some(o=>o.period===i.latest.period&&o.value===i.latest.value);}
 function card(i,reference){
  const o=i.latest,c=o.comparisons,same=!i.country||o.period===reference;
  return `<article class="card market-observation-card" data-observation-id="${esc(i.id)}"><h4>${esc(i.name)}</h4><div class="observed-value" data-value="${o.value}">${fmt(o.value)}<small> 명</small></div><p class="macro-period">기준 ${esc(o.period)} · ${esc(finality(o))}</p>${!same?`<p class="market-mismatch">${reference?'전체 방한객과 기준월 불일치':'전체 방한객 기준월 미확인'} · 같은 기준월 비교 제외</p>`:''}<dl><div><dt>전년 동월 대비</dt><dd>${pct(c.yoy_pct)}</dd></div><div><dt>전월 대비</dt><dd>${pct(c.mom_pct)}</dd></div><div><dt>연초 누적</dt><dd>${Number.isSafeInteger(c.ytd_value)?fmt(c.ytd_value)+'명':'누락 월로 계산 생략'}</dd></div><div><dt>전년 동기 누적 대비</dt><dd>${pct(c.ytd_yoy_pct)}</dd></div></dl><p class="tiny">${esc(status(i))}<br>최종 수집 ${esc(o.last_collected_at||'미확인')}<br>공표 ${esc(o.release_published_at||'미표기')} · 정정 이력 ${i.correction_count||0}건${o.revision_status==='revised'?' · 정정 반영':''}</p>${source(i)}</article>`;
 }
 function renderChart(){
  const i=rows.find(i=>i.id===el('market-chart-metric').value),mode=el('market-chart-mode').value;
  if(!i){el('market-demand-chart').innerHTML='<p class="empty">검증된 해당 시계열이 없습니다.</p>';el('market-chart-meta').textContent='관측 불가';el('market-chart-foot').textContent='가상값이나 다른 지표로 대체하지 않습니다.';return;}
  const gaps=window.MacroMonitor.renderReadOnlyChart(el('market-demand-chart'),i,mode);
  el('market-chart-meta').textContent=`${i.name} · 최신 기준 ${i.latest.period} · 최근 12개월 · ${mode==='growth'?'전년 동월비 %':'실적 명 (축: 만 명)'} · ${status(i)}`;
  el('market-chart-foot').textContent=`${i.publisher} · ${mode==='growth'?'전년 동월 비교 자료 없음':'월 자료 누락'} ${gaps??'전체 기간 확인 필요'}개 · 결측은 × 또는 자료 없음으로 표시하며 0/보간으로 채우지 않습니다.`;
 }
 function render(db,sourceState){
  status=sourceState||status;rows=db?.mode==='verified_official_statistics'&&Array.isArray(db.indicators)?db.indicators.filter(valid):[];
  const inbound=rows.find(i=>i.id==='kto_inbound'),demand=rows.filter(i=>!i.country),countries=rows.filter(i=>i.country);
  el('market-demand-cards').innerHTML=demand.length?demand.map(i=>card(i)).join(''):'<p class="empty">검증된 관광수요 자료가 없습니다. 관측 불가.</p>';
  el('market-country-cards').innerHTML=countries.length?countries.map(i=>card(i,inbound?.latest.period)).join(''):'<p class="empty">검증된 국적별 자료가 없습니다.</p>';
  el('market-observation-status').textContent=inbound?`관광수요 관측 · 기준 ${inbound.latest.period} (현재 날짜와 다름) · ${status(inbound)}`:'관측 불가 · 검증된 방한객 자료가 없습니다. 종합 판정은 유보합니다.';
  el('home-market-observation').innerHTML=`<div class="small-label">공식 관광시장 관측</div>${inbound?`<p class="home-observed-value">방한객 전년 동월 <strong>${pct(inbound.latest.comparisons.yoy_pct)}</strong></p><p class="tiny">기준 ${esc(inbound.latest.period)} · ${fmt(inbound.latest.value)}명<br>${esc(status(inbound))}</p>${source(inbound)}`:'<p>공식 수요 관측 불가 · 검증된 자료 없음</p>'}<p class="market-withheld">시장 전체 날씨: 종합 판정 유보</p><a class="text-link" href="#weather" data-goto="weather">수요 관측 상세 →</a>`;
  renderChart();
 }
 el('market-chart-metric').addEventListener('change',renderChart);el('market-chart-mode').addEventListener('change',renderChart);
 window.addEventListener('resize',()=>{if(state.page==='weather')renderChart();});
 window.MarketObservation={render,renderChart};
})();
