/* Display only: no fetching, statistical calculation, approval or data mutation. */
((root)=>{
 'use strict';
 function parse(raw){
  if(typeof raw==='number')return Number.isFinite(raw)?raw:null;
  if(typeof raw!=='string')return null;
  const value=raw.trim().replace(/^−/,'-');
  if(!/^[+-]?\s*(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)\s*%?$/.test(value))return null;
  const n=Number(value.replace(/[,\s%]/g,''));return Number.isFinite(n)?n:null;
 }
 function describe(raw){
  const value=parse(raw);
  if(value===null)return {value:null,state:'missing',icon:'—',number:'',label:'비교 자료 없음',text:'—'};
  const state=value===0?'neutral':value>0?'positive':'negative';
  const icon={positive:'▲',negative:'▼',neutral:'—'}[state];
  const number=(value>0?'+':'')+(value===0?'0.00':value.toFixed(2))+'%';
  return {value,state,icon,number,label:{positive:'증가',negative:'감소',neutral:'보합'}[state],text:icon+' '+number};
 }
 function html(raw){
  const d=describe(raw);
  if(d.state==='missing')return '<span class="percentage-change percentage-change--missing" title="비교 자료 없음" aria-label="비교 자료 없음">—</span>';
  // Only fixed enum strings and Number.toFixed output enter markup.
  return `<span class="percentage-change percentage-change--${d.state}" data-change-value="${d.value}"><span aria-hidden="true">${d.icon}</span><span class="percentage-sr-only">${d.label}</span> ${d.number}</span>`;
 }
 const api=Object.freeze({parse,describe,html,text:raw=>describe(raw).text});
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.PercentageUI=api;
})(typeof window==='undefined'?globalThis:window);
