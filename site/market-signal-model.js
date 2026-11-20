/* Pure, deterministic current-vintage research model. No fetch, DOM or writes. */
(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.MarketSignalModel=factory();})(globalThis,()=>{
 'use strict';
 const VERSION='model-signal-v1.0.0',IDS=['kto_inbound','kto_tourism_receipts'];
 const METHOD=Object.freeze({yoy:'100*(x[t]/x[t-12]-1)',smoothing_months:3,reference_months:24,
  percentile:'100*(strictly_lower+0.5*equal)/24; reference excludes target month',weights:Object.freeze([0.5,0.5]),
  weather_cutoffs:Object.freeze([25,50,75]),max_lag_months:3,mode:'retrospective_current_vintage',seasonal_adjustment:false,
  scope:'inbound_demand_and_nominal_general_travel_receipts_only'});
 const CONTRACT=[
  {source:'kto_monthly_statistics',unit:'명',publisher:'한국관광공사',verification:'official_file_validated',method:'official_public_xlsx',
   definition:'전체 외국인 입국자 중 관광객으로 볼 수 없는 일부 체류자격을 제외하고 재외국민 입국자를 포함한 한국관광통계 공표치. 승무원 포함. 순수 관광목적 입국자나 Foreign Visitors 행만의 합계와 다름.'},
  {source:'tourgo_tourism_balance',unit:'US$',publisher:'한국문화관광연구원 관광지식정보시스템(TOURGO)',verification:'official_tourgo_file_validated',method:'operator_supplied_official_excel_export',
   definition:'TOURGO 관광수입(일반여행수입); 유학연수를 포함한 전체 여행수지와 구분. 원본 천 US$, Macro 원장 US$.'}
 ];
 const month=p=>typeof p==='string'&&/^(19|20)\d\d-(0[1-9]|1[0-2])$/.test(p);
 const add=(p,n)=>{const [y,m]=p.split('-').map(Number),d=new Date(Date.UTC(y,m-1+n,1));return d.getUTCFullYear()+'-'+String(d.getUTCMonth()+1).padStart(2,'0');};
 const distance=(a,b)=>(Number(a.slice(0,4))-Number(b.slice(0,4)))*12+Number(a.slice(5))-Number(b.slice(5));
 const need=(ok,code)=>{if(!ok)throw Error(code);};
 const gcd=(a,b)=>{a=a<0n?-a:a;while(b){[a,b]=[b,a%b];}return a||1n;};
 const frac=(n,d=1n)=>{need(d>0n,'invalid_denominator');const g=gcd(n,d);return {n:n/g,d:d/g};};
 const sum=(a,b)=>frac(a.n*b.d+b.n*a.d,a.d*b.d),scale=(a,n,d=1n)=>frac(a.n*n,a.d*d);
 const compare=(a,b)=>a.n*b.d<b.n*a.d?-1:a.n*b.d>b.n*a.d?1:0;
 function decimal(a,places=6){const factor=10n**BigInt(places),negative=a.n<0n,n=negative?-a.n:a.n,q=(n*factor*2n+a.d)/(2n*a.d),s=q.toString().padStart(places+1,'0');return (negative&&q?'−':'')+(places?s.slice(0,-places)+'.'+s.slice(-places):s);}
 const ascii=a=>decimal(a).replace('−','-');
 const number=a=>Number(a.n)/Number(a.d);
 function official(url,financial=false){try{const u=new URL(url);return !u.username&&!u.password&&u.protocol==='https:'&&(financial?url==='https://know.tour.go.kr/stat/koreaTourIncomeDis19Re.do':u.hostname==='datalab.visitkorea.or.kr'&&u.pathname==='/site/portal/ex/bbs/View.do');}catch{return false;}}
 function rows(i,c,target,current){
  need(i&&i.enabled===true&&i.connected===true,'series_not_connected');
  need(i.source_id===c.source&&i.unit===c.unit&&i.publisher===c.publisher&&i.definition===c.definition&&i.frequency==='M'&&!i.country&&official(i.source_url,c.unit==='US$'),'indicator_contract_mismatch');
  need(Array.isArray(i.observations),'observations_invalid');
  const start=add(target,-38),map=new Map();let first=null;
  for(const o of i.observations){
   need(o&&month(o.period),'observation_period_invalid');if(o.period>target)continue;
   if(first===null||o.period<first)first=o.period;
   if(o.period<start)continue;
   need(!map.has(o.period),'duplicate_period');
   need(Number.isSafeInteger(o.value)&&o.value>=0&&o.unit===c.unit&&o.frequency==='M'&&o.publisher===c.publisher&&o.verification_status===c.verification&&o.collection_method===c.method&&official(o.source_url,c.unit==='US$')&&['not_stated','provisional','final'].includes(o.finality)&&(!('definition' in o)||o.definition===c.definition),'observation_contract_mismatch');
   if(c.unit==='US$')need(o.period>='2021-01'&&o.period<='2026-09','tourgo_scope_exceeded');
   else need(o.rights==='KOGL-0'&&/^[a-f0-9]{64}$/.test(o.file_sha256||''),'official_file_evidence_missing');
   map.set(o.period,o);
  }
  need(first!==null&&start>=first,'insufficient_reference_history');
  for(let n=-38;n<=0;n++)need(map.has(add(target,n)),'missing_observation');
  if(current){const saved=map.get(target),latest=i.latest;
   need(latest&&['period','value','unit','frequency','publisher','source_url','verification_status','collection_method'].every(k=>latest[k]===saved[k]),'latest_observation_mismatch');
   const base=map.get(add(target,-12)).value;
   need(base>0,'zero_yoy_denominator');
   const pct=frac(100n*(BigInt(saved.value)-BigInt(base)),BigInt(base));
   need(latest.comparisons?.reference_period===target&&latest.comparisons?.yoy_base_period===add(target,-12)&&typeof latest.comparisons?.yoy_pct==='number'&&latest.comparisons.yoy_pct===Number(decimal(pct,2).replace('−','-')),'supplied_yoy_mismatch');
  }
  return map;
 }
 function axis(i,c,target,current){
  const map=rows(i,c,target,current),growth=new Map();
  for(let n=-26;n<=0;n++){const p=add(target,n),a=map.get(p).value,b=map.get(add(p,-12)).value;need(b>0,'zero_yoy_denominator');growth.set(p,frac(100n*(BigInt(a)-BigInt(b)),BigInt(b)));}
  const smooth=p=>scale(sum(sum(growth.get(p),growth.get(add(p,-1))),growth.get(add(p,-2))),1n,3n);
  const value=smooth(target),reference=Array.from({length:24},(_,n)=>smooth(add(target,n-24))),sorted=[...reference].sort(compare);
  need(compare(sorted[0],sorted[23])!==0,'degenerate_reference_distribution');
  const lower=reference.filter(v=>compare(v,value)<0).length,ties=reference.filter(v=>compare(v,value)===0).length;
  const position=frac(BigInt(100*(2*lower+ties)),48n),warnings=[];
  if(add(target,-38)<='2022-12')warnings.push('pandemic_baseline_in_reference');
  if(ties)warnings.push('ties_can_be_revision_sensitive');
  if(compare(value,sorted[0])<0||compare(value,sorted[23])>0)warnings.push('outside_reference_range');
  if([...map.values()].some(o=>o.revision_status==='revised'))warnings.push('revised_input_vintage');
  return {rank:position,data:{indicator_id:i.id,value:map.get(target).value,unit:c.unit,yoy_pct:ascii(growth.get(target)),smoothed_yoy_pct:ascii(value),percentile:ascii(position),contribution:ascii(scale(position,1n,2n)),
   source_url:map.get(target).source_url,publisher:c.publisher,definition:c.definition,finality:map.get(target).finality,
   last_collected_at:map.get(target).last_collected_at||null,original_publication_at:map.get(target).original_publication_at||null,
   reference_from:add(target,-24),reference_through:add(target,-1),input_from:add(target,-38),input_through:target,reference_count:24,tie_count:ties,warnings}};
 }
 function withheld(period,reason){return {model_version:VERSION,reference_period:period||null,source_indicator_ids:[...IDS],methodology:METHOD,status:'withheld',reason,score:null,score_display:null,weather:null,axes:[],warnings:['experimental_partial_signal','retrospective_current_vintage','not_an_official_index_or_forecast','nominal_usd_not_real_consumption']};}
 function evaluate(db,options={}){
  let target=options.reference_period||null;
  try{
   need(db?.schema_version===1&&db.mode==='verified_official_statistics'&&Array.isArray(db.indicators),'verified_database_required');
   const series=IDS.map(id=>{const a=db.indicators.filter(i=>i.id===id);need(a.length===1,'indicator_identity_invalid');return a[0];});
   const current=!target;
   if(current){need(series.every(i=>month(i.latest?.period)),'latest_period_unavailable');need(series[0].latest.period===series[1].latest.period,'latest_period_mismatch');target=series[0].latest.period;}
   need(month(target),'target_period_invalid');
   const asOf=options.as_of_period||db.generated_at?.slice(0,7);need(month(asOf),'analysis_month_required');
   need(target<asOf,'future_or_incomplete_month');need(distance(asOf,target)<=METHOD.max_lag_months,'stale_reference_period');
   const axes=series.map((i,n)=>axis(i,CONTRACT[n],target,current)),score=scale(sum(axes[0].rank,axes[1].rank),1n,2n);
   const tone=compare(score,frac(25n))<0?'rain':compare(score,frac(50n))<0?'cloudy':compare(score,frac(75n))<0?'partly':'sunny';
   return {...withheld(target,null),status:'observed',score:number(score),score_display:decimal(score,2),score_exact:ascii(score),weather:tone,axes:axes.map(a=>a.data)};
  }catch(e){return withheld(target,SAFE.has(e.message)?e.message:'input_contract_invalid');}
 }
 const SAFE=new Set(['invalid_denominator','series_not_connected','indicator_contract_mismatch','observations_invalid','observation_period_invalid','duplicate_period','observation_contract_mismatch','tourgo_scope_exceeded','official_file_evidence_missing','insufficient_reference_history','missing_observation','latest_observation_mismatch','zero_yoy_denominator','supplied_yoy_mismatch','degenerate_reference_distribution','verified_database_required','indicator_identity_invalid','latest_period_unavailable','latest_period_mismatch','target_period_invalid','analysis_month_required','future_or_incomplete_month','stale_reference_period']);
 function walkForward(db,end){
  const periods=[...new Set((db?.indicators?.find(i=>i.id===IDS[0])?.observations||[]).map(o=>o.period).filter(p=>month(p)&&(!end||p<=end)))].sort(),points=[];
  let failures=0;
  for(const period of periods){
   const options={reference_period:period,as_of_period:add(period,1)},result=evaluate(db,options);
   const prefix={...db,indicators:db.indicators.filter(i=>IDS.includes(i.id)).map(i=>{const observations=i.observations.filter(o=>month(o.period)&&o.period<=period);return {...i,observations,latest:observations.at(-1)||null};})};
   const match=JSON.stringify(result)===JSON.stringify(evaluate(prefix,options));
   if(!match||(result.status==='observed'&&(!Number.isFinite(result.score)||result.score<0||result.score>100)))failures++;
   points.push({reference_period:period,status:result.status,reason:result.reason,score:result.score,weather:result.weather,future_prefix_match:match,axes:result.axes});
  }
  return {mode:'retrospective_current_vintage',historical_as_of_verified:false,prediction_accuracy_measured:false,evaluated_months:points.length,scored_months:points.filter(p=>p.status==='observed').length,withheld_months:points.filter(p=>p.status!=='observed').length,invariant_failures:failures,points};
 }
 function run(db,options={}){
  const result=evaluate(db,options);let backtest;
  try{backtest=walkForward(db,result.reference_period||undefined);}catch{return {...withheld(result.reference_period,'backtest_failed'),backtest:{invariant_failures:1}};}
  if(backtest.invariant_failures)return {...withheld(result.reference_period,'backtest_failed'),backtest};
  return {...result,backtest};
 }
 return Object.freeze({VERSION,IDS:Object.freeze(IDS),METHOD,CONTRACT:Object.freeze(CONTRACT.map(Object.freeze)),evaluate,walkForward,run,addMonth:add});
});
