/* Only allowlisted validated visitor statistics; no news input or financial values. */
(()=>{
 const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const fmt=n=>n.toLocaleString('ko-KR'),pct=window.PercentageUI.html;
 function render(db,health,failed=false){
  const card=document.getElementById('data-observation');if(!card)return;
  const allowed=new Set(['kto_inbound','kto_outbound','kto_inbound_cn','kto_inbound_jp','kto_inbound_tw','kto_inbound_us','kto_inbound_vn']);
  const rows=db?.mode==='verified_official_statistics'?db.indicators.filter(i=>allowed.has(i.id)&&i.connected&&i.unit==='명'&&i.frequency==='M'&&i.latest?.verification_status==='official_file_validated'&&i.latest.comparisons&&Number.isSafeInteger(i.latest.value)&&i.latest.value>=0&&/^\d{4}-\d{2}$/.test(i.latest.period)&&i.observations.some(o=>o.period===i.latest.period&&o.value===i.latest.value)):[];
  if(!rows.length){card.innerHTML='<div class="tag">DATA OBSERVATION</div><h3>공식 통계 관찰 불가</h3><p>검증된 방문객 자료가 없거나 불완전합니다. 미연동 값과 관광수지 승인 대기 자료를 사용하지 않습니다.</p>';return;}
  const inbound=rows.find(i=>i.id==='kto_inbound'),focus=inbound||rows[0];
  const sources=health?.sources||[];const error=failed||health?.status==='failed'||sources.some(s=>s.id==='kto_monthly_statistics'&&['error','partial'].includes(s.status));
  const facts=rows.filter(i=>!i.country).map(i=>{const c=i.latest.comparisons||{};return `<li><strong>${esc(i.name)} · ${esc(i.latest.period)}</strong><br>${fmt(i.latest.value)}명 · 전년 동월 ${pct(c.yoy_pct)} · 전월 ${pct(c.mom_pct)}<br>연초 누적 ${Number.isSafeInteger(c.ytd_value)?fmt(c.ytd_value)+'명':'누락 월로 계산 생략'} · 전년 동기 ${pct(c.ytd_yoy_pct)}</li>`;}).join('');
  const countries=rows.filter(i=>i.country&&i.latest.period===focus.latest.period).map(i=>`${esc(i.country)} ${fmt(i.latest.value)}명`).join(' · ');
  const url=String(focus.source_url||'');
  card.innerHTML=`<div class="tag">DATA OBSERVATION · 자동 통계 관찰</div><h3>${esc(focus.latest.period)} 관광수요 실적</h3><p class="observation-status">${error?'수집/검증 실패 · 마지막 검증값 유지':health?'공식 공개 통계 기반':'수집 상태 미확인 · 기준월 확인 필요'}</p><ul class="observation-facts">${facts}</ul>${countries?`<p><strong>같은 기준월 국적별 방한객</strong><br>${countries}</p>`:''}<p class="tiny">${esc(focus.publisher)} · 공표 ${esc(focus.latest.release_published_at||'미표기')}<br>최종 수집 ${esc(focus.latest.last_collected_at||'미확인')} · ${focus.latest.finality==='provisional'?'잠정치':focus.latest.finality==='final'?'확정치':'확정 여부 미표기'} · 정정 이력 ${focus.correction_count||0}건</p><p><strong>해석 시 주의</strong><br>입출국 건수의 변화가 관광수입·1인당 소비·지역 소비의 증가를 입증하지는 않습니다. 미연동 금융·소비 지표로 성과를 단정하지 않습니다.</p><p class="tiny">Analyst’s Note · 승인된 편집 의견 없음. 위 내용은 공식 수치의 자동 관찰이며 전망이나 분석가 의견이 아닙니다.</p>${/^https:\/\//.test(url)?`<a class="external" href="${esc(url)}" target="_blank" rel="noopener noreferrer">공식 출처 ↗</a>`:''} <a class="text-link" href="#macro" data-goto="macro">Macro Monitor 상세 →</a>`;
 }
 window.DataObservation={render};
})();
