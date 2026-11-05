/* Bibliographic link curation only. No PDF, image, abstract or generated prose. */
(() => {
 const section=document.getElementById('page-research');
 const state={query:'',publisher:'',region:'',type:'',category:'',sort:'newest',page:1,size:10};
 let database={reports:[],publishers:{},date_basis:{},attributions:{}},health=null,loading=false;
 const el=id=>document.getElementById(id);
 const escape=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
 const external=url=>{try{return new URL(url).protocol==='https:';}catch(_){return false;}};
 const dateText=record=>{
  const basis=database.date_basis?.[record.url];const date=record.published_at;
  if(basis?.kind==='registered')return `공식 등록일 ${date} · 발행일 미확인`;
  if(/^\d{4}$/.test(date))return `발간연도 ${date}년 · 월·일 미표기`;
  if(/^\d{4}-\d{2}$/.test(date))return `발행월 ${date}`;
  return basis?.kind==='official_page_first_publication'?`공식 공개일 ${date}`:`발행일 ${date}`;
 };
 function filtered(){
  const query=state.query.trim().toLocaleLowerCase();
  return database.reports.filter(r=>(!state.publisher||r.publisher===state.publisher)&&
   (!state.region||database.publishers[r.publisher]?.region===state.region)&&
   (!state.type||r.report_type===state.type)&&(!state.category||r.category===state.category)&&
   (!query||[r.title,r.publisher,r.report_type,r.category,...r.keywords].some(s=>s.toLocaleLowerCase().includes(query))))
   .sort((a,b)=>(state.sort==='oldest'?1:-1)*a.published_at.localeCompare(b.published_at)||a.title.localeCompare(b.title));
 }
 function card(r){
  const note=database.attributions?.[r.url];
  const attribution=note?.kogl_type?`<p class="research-attribution">출처: ${escape(r.publisher)} · ${escape(r.published_at)}${note.authors?' · 저자: '+escape(note.authors):''} · 공공누리 제${escape(note.kogl_type)}유형. 원문 이용조건은 발행기관에서 확인하세요.</p>`:'';
  const unknownAccess=r.access_type==='미확인';
  const accessLabel=unknownAccess?'열람 조건 미확인':r.access_type;
  const accessNote=unknownAccess?'<p class="research-access-note">해당 자료의 무료 열람·회원 접근·구매 여부는 원문에서 확인해야 합니다.</p>':'';
  return `<article class="research-card"><div class="research-meta"><span>${escape(r.publisher)}</span><span>${escape(dateText(r))}</span><span class="research-access">${escape(accessLabel)}</span></div>${accessNote}<h3><a href="${escape(r.url)}" target="_blank" rel="noopener noreferrer">${escape(r.title)}</a></h3><div class="research-meta"><span class="category">${escape(r.category)}</span><span>${escape(r.report_type)}</span></div><p class="research-keywords">${r.keywords.map(escape).join(' · ')}</p><a class="text-link" href="${escape(r.url)}" target="_blank" rel="noopener noreferrer">발행기관 원문 보기 ↗</a>${attribution}</article>`;
 }
 function render(){
  const count=['query','publisher','region','type','category'].filter(k=>state[k].trim()).length+(state.sort!=='newest'?1:0);
  el('research-filter-count').textContent=`적용 조건 ${count}개`;el('research-filter-summary').textContent=`${count}개 적용`;
  const reports=filtered(),pages=Math.max(1,Math.ceil(reports.length/state.size));
  state.page=Math.max(1,Math.min(state.page,pages));
  const start=(state.page-1)*state.size;
  el('research-results').innerHTML=reports.length?reports.slice(start,start+state.size).map(card).join(''):'<div class="empty">조건에 맞는 검증된 연구자료가 없습니다.</div>';
  el('research-result-count').textContent=reports.length?`검색 결과 ${reports.length}건 · ${start+1}–${Math.min(start+state.size,reports.length)}건 표시`:'검색 결과 0건';
  el('research-page-size').value=String(state.size);
  if(pages<=1){el('research-page-buttons').innerHTML='';return;}
  const numbers=new Set([1,pages]);for(let n=Math.max(1,state.page-2);n<=Math.min(pages,state.page+2);n++)numbers.add(n);
  let previous=0;const buttons=[...numbers].sort((a,b)=>a-b).map(n=>{
   const dots=previous&&n>previous+1?'<span class="news-page-ellipsis">…</span>':'';previous=n;
   return `${dots}<button class="news-page-button ${n===state.page?'selected':''}" data-report-page="${n}" ${n===state.page?'aria-current="page"':''} aria-label="연구자료 ${n}페이지">${n}</button>`;
  }).join('');
  el('research-page-buttons').innerHTML=`<button class="news-page-button" data-report-page="${state.page-1}" ${state.page===1?'disabled':''} aria-label="이전 페이지">&lt;</button>${buttons}<button class="news-page-button" data-report-page="${state.page+1}" ${state.page===pages?'disabled':''} aria-label="다음 페이지">&gt;</button>`;
 }
 function options(id,values,label){
  const node=el(id),current=node.value;
  node.innerHTML=`<option value="">${escape(label)}</option>`+[...values].map(v=>`<option value="${escape(v)}">${escape(v)}</option>`).join('');node.value=current;
 }
 function summaries(){
  el('research-count').textContent=String(database.reports.length);
  el('research-total-inline').textContent=`전체 ${database.reports.length}건`;
  el('research-recent-count').textContent=health?.new_reports_last30d??'미확인';
  el('research-auto-count').textContent=health?.automatic_reports??'미확인';
  el('research-manual-count').textContent=health?.manual_reports??'미확인';
  el('research-updated').textContent=database.generated_at?new Date(database.generated_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}):'확인 전';
  options('research-publisher',Object.keys(database.publishers),'전체 발행기관');
  const types=['종합 연구보고서','정기 시장동향','정책연구','산업·경제 분석','통계보고서','산업 브리프 / 인사이트'];
  const categories=['국제관광·인바운드','국내관광·관광소비','숙박·호텔산업','항공·교통산업','OTA·여행기술','관광정책·산업경제','MICE·비즈니스 이벤트','관광시장 전망·트렌드'];
  options('research-type',types,'전체 보고서 유형');options('research-category',categories,'전체 연구 분야');
  el('research-source-counts').innerHTML=Object.keys(database.publishers).map(name=>{
   const count=database.reports.filter(r=>r.publisher===name).length;
   return `<button data-report-publisher="${escape(name)}"><span>${escape(name)}</span><strong>${count}건</strong></button>`;
  }).join('');
  const failed=health?.sources?.filter(s=>['error','partial'].includes(s.status)).map(s=>s.publisher)||[];
  el('research-status').textContent=failed.length?`일부 출처 확인 지연: ${failed.join(', ')} · 이전에 검증한 자료는 유지합니다.`:`자동 수집 ${health?.connected_sources??'미확인'}개 기관 · 게시 자료 ${health?.publishing_sources??'미확인'}개 기관`;
 }
 async function load(){
  if(loading)return;loading=true;
  try{
   const response=await fetch('./data/reports.json?v='+Date.now(),{cache:'no-store'});
   if(!response.ok)throw new Error('reports_not_ready');
   const json=await response.json();
   if(!Array.isArray(json.reports))throw new Error('invalid_reports_db');
   const valid=json.reports.filter(r=>['title','publisher','published_at','report_type','category','url','access_type'].every(k=>typeof r[k]==='string')&&Array.isArray(r.keywords)&&r.keywords.every(k=>typeof k==='string')&&external(r.url));
   database={...json,reports:valid};
   try{const hr=await fetch('./data/reports_health.json?v='+Date.now(),{cache:'no-store'});if(hr.ok)health=await hr.json();}catch(_){}
   summaries();render();
  }catch(_){el('research-status').textContent=database.reports.length?'연구자료 갱신을 확인하지 못해 기존 목록을 유지합니다.':'연구자료 수집 결과가 아직 연결되지 않았습니다. 검증되지 않은 자료는 표시하지 않습니다.';render();}
  finally{loading=false;}
 }
 const filterDetails=el('research-filter-details'),wideFilters=matchMedia('(min-width: 769px)');
 function layoutFilters(){filterDetails.open=wideFilters.matches;el('research-source-overview').open=wideFilters.matches;}
 wideFilters.addEventListener('change',layoutFilters);layoutFilters();
 el('research-reset').addEventListener('click',()=>{
  Object.assign(state,{query:'',publisher:'',region:'',type:'',category:'',sort:'newest',page:1});
  for(const id of ['research-search','research-publisher','research-region','research-type','research-category'])el(id).value='';
  el('research-sort').value='newest';render();
 });
 el('research-search').addEventListener('input',e=>{state.query=e.target.value;state.page=1;render();});
 for(const [id,key] of [['research-publisher','publisher'],['research-region','region'],['research-type','type'],['research-category','category'],['research-sort','sort']])
  el(id).addEventListener('change',e=>{state[key]=e.target.value;state.page=1;render();});
 el('research-page-size').addEventListener('change',e=>{state.size=[10,20].includes(+e.target.value)?+e.target.value:10;state.page=1;render();});
 section.addEventListener('click',e=>{
  const page=e.target.closest('[data-report-page]');if(page&&!page.disabled){state.page=+page.dataset.reportPage;render();}
  const publisher=e.target.closest('[data-report-publisher]');if(publisher){state.publisher=publisher.dataset.reportPublisher;el('research-publisher').value=state.publisher;state.page=1;render();}
 });
 window.renderResearch=render;window.ResearchLibrary={load,state,get database(){return database;}};
 load();setInterval(load,30*60*1000);
})();
