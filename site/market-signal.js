/* One calculation feeds BOTH home and detail; no separate fetch or public output. */
(()=>{
 const el=id=>document.getElementById(id),esc=v=>String(v??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const names={kto_inbound:'방한 외래관광객 수',kto_tourism_receipts:'일반여행수입 · 명목 US$'};
 const weather={rain:'비',cloudy:'흐림',partly:'구름 조금',sunny:'맑음'};
 const reasons={verified_database_required:'검증된 공식 통계를 확인할 수 없습니다.',series_not_connected:'두 핵심 계열이 모두 연결되지 않았습니다.',latest_period_unavailable:'최신 기준월을 확인할 수 없습니다.',latest_period_mismatch:'두 핵심 계열의 최신 기준월이 다릅니다.',insufficient_reference_history:'39개월 연속 원값과 24개월 참조 분포가 필요합니다.',missing_observation:'필수 월의 관측치가 누락됐습니다.',zero_yoy_denominator:'전년 같은 월의 비교 분모가 0입니다.',degenerate_reference_distribution:'참조 분포에 변동이 없어 상대 위치를 판단하지 않습니다.',tourgo_scope_exceeded:'현재 허용된 TOURGO 기간을 벗어났습니다.',stale_reference_period:'통계 기준월이 모델의 허용 시차를 넘었습니다.',future_or_incomplete_month:'완료되지 않은 월은 계산하지 않습니다.',backtest_failed:'회고 계산의 검증 조건을 충족하지 못했습니다.',macro_load_failed:'새 공식 데이터 확인에 실패해 모델 판정을 유보합니다.'};
 const pct=s=>{const n=Number(s);return Number.isFinite(n)?(n>0?'+':'')+n.toFixed(2)+'%':'비교 자료 없음';};
 const fixed=s=>Number(s).toFixed(2);
 let result=null;
 function analysisMonth(){const parts=new Intl.DateTimeFormat('en',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit'}).formatToParts(new Date());return parts.find(p=>p.type==='year').value+'-'+parts.find(p=>p.type==='month').value;}
 function render(db,context={}){
  const model=window.MarketSignalModel;
  result=model.run(context.failed?null:db,{as_of_period:analysisMonth()});
  if(context.failed)result={...result,reason:'macro_load_failed'};
  const ready=result.status==='observed',title=ready?weather[result.weather]:'모델 판정 유보',score=ready?result.score_display:'—';
  for(const prefix of ['','home-']){el(prefix+'weather-title').textContent=title;el(prefix+'weather-score').textContent=score;}
  el('weather-description').textContent=ready?'방한 수요·일반여행수입의 평활 성장률을 과거 분포와 비교한 자체 부분 신호입니다. 관광시장 전체의 경기 판정이 아닙니다.':(reasons[result.reason]||'입력의 정의·단위·출처·비교 수치를 검증하지 못했습니다.');
  el('home-weather-description').textContent=ready?'과거 대비 상대 성장 신호입니다. 시장 전체의 경기 수준이나 미래 예측이 아닙니다.':el('weather-description').textContent;
  const reference=`기준 ${result.reference_period||'미확인'} · ${result.model_version}`;
  el('model-reference').textContent=reference;el('home-model-reference').textContent=reference;
  const status=el('model-signal-status');status.textContent=ready?'공식 관측 기반 부분 신호 · 실험 모델':el('weather-description').textContent;status.dataset.status=result.status;status.dataset.reason=result.reason||'';
  document.querySelectorAll('.weather-panel,.weather-result').forEach(n=>n.dataset.weather=ready?result.weather:'withheld');
  window.WeatherMotion?.render(ready?result.weather:'withheld');
  el('model-window').innerHTML=ready?`<div><dt>참조 분포</dt><dd>${esc(result.axes[0].reference_from)}~${esc(result.axes[0].reference_through)} · 24개월</dd></div><div><dt>사용 원값</dt><dd>${esc(result.axes[0].input_from)}~${esc(result.reference_period)} · 39개월/계열</dd></div><div><dt>가중치</dt><dd>방한 수요 50% · 일반여행수입 50%</dd></div>`:'';
  el('model-evidence').innerHTML=ready?result.axes.map(a=>`<article class="card model-axis" data-model-id="${esc(a.indicator_id)}"><h4>${names[a.indicator_id]}</h4><p class="model-raw-value" data-value="${a.value}">${a.value.toLocaleString('ko-KR')} <small>${esc(a.unit)}</small></p><dl><div><dt>전년 동월 대비</dt><dd>${pct(a.yoy_pct)}</dd></div><div><dt>최근 3개월 평균 YoY</dt><dd>${pct(a.smoothed_yoy_pct)}</dd></div><div><dt>과거 분포 내 상대 위치</dt><dd>${fixed(a.percentile)} / 100</dd></div><div><dt>합산 점수 기여도</dt><dd>${fixed(a.contribution)}점 · 50% 가중</dd></div></dl><p>기준 ${esc(result.reference_period)} · ${a.finality==='final'?'확정':a.finality==='provisional'?'잠정':'확정 여부 미표기'}<br>수집 ${esc(a.last_collected_at||'미확인')} · 원공표 ${esc(a.original_publication_at||'미확인')}</p><a class="external" href="${esc(a.source_url)}" target="_blank" rel="noopener noreferrer">${esc(a.publisher)} 공식 원자료</a></article>`).join(''):'<p class="empty">누락값을 0·추정값·가상 초기값으로 채우지 않습니다. 공식 관측은 아래에서 별도로 확인할 수 있습니다.</p>';
  const audit=result.backtest||{};el('model-audit').textContent=`현재 수정 빈티지 회고 검증: 평가 ${audit.evaluated_months||0}개월, 계산 ${audit.scored_months||0}개월, 유보 ${audit.withheld_months||0}개월. 미래 월 제외 검증 오류 ${audit.invariant_failures||0}건. 이는 예측 정확도나 과거 발행 시점 재현의 증명이 아닙니다.`;
  const warnings=new Set(result.axes.flatMap(a=>a.warnings));
  el('model-warnings').textContent=[warnings.has('pandemic_baseline_in_reference')?'비교에 코로나19 기저가 포함됩니다.':'',warnings.has('ties_can_be_revision_sensitive')?'동률 참조값이 있어 작은 정정도 상대 위치를 바꿀 수 있습니다.':'',warnings.has('outside_reference_range')?'평활 성장률이 참조 분포 범위 밖에 있습니다.':'',warnings.has('revised_input_vintage')?'정정된 원값이 포함됩니다.':'',context.healthUnknown?'수집 상태 확인이 제한됩니다.':'','항공·고용·내국인 카드소비·산업 활동은 모델에 포함되지 않습니다.'].filter(Boolean).join(' ');
 }
 window.MarketSignalUI={render,get result(){return result;}};
 render(null);
})();
