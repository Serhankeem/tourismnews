/* Public six-field metadata only. Selected edition drives both display and copy. */
(()=>{
 const el=id=>document.getElementById(id),esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 let current=null,history=[],edition=null,lastError=false,collectionFailed=false,collectionHealth=null,blockedHashes=new Set(),rightsUnavailable=false;
 const safe=s=>{try{return ['https:','http:'].includes(new URL(s).protocol);}catch(_){return false;}};
 async function checked(b){if(!b||!Array.isArray(b.items)||b.mode!=='live_rss')throw Error();const valid=b.items.filter(n=>['title','source','published_at','category','url'].every(k=>typeof n[k]==='string')&&Array.isArray(n.keywords)&&n.keywords.every(k=>typeof k==='string')&&safe(n.url));const permitted=await Promise.all(valid.map(async n=>{const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(n.url)))).map(v=>v.toString(16).padStart(2,'0')).join('');return blockedHashes.has(hash)?null:n;}));return {...b,items:permitted.filter(Boolean).slice(0,5),rights_hidden_count:(b.rights_hidden_count||0)+valid.length-permitted.filter(Boolean).length};}
 function render(){
  if(rightsUnavailable){edition=null;CURRENT_BRIEFING=null;el('briefing-state').textContent='권리 상태 확인 불가';el('briefing-news-list').textContent='권리 검토 상태를 확인할 때까지 브리핑 표시를 보류합니다.';return;}
  const key=el('briefing-edition').value;
  edition=key==='current'?current:history.find(b=>b.briefing_date===key);
  CURRENT_BRIEFING=edition;
  if(!edition){el('briefing-state').textContent='데이터 확인 불가';el('briefing-news-list').textContent='검증된 브리핑을 불러오지 못했습니다.';return;}
  const age=Date.now()-Date.parse(edition.generated_at),past=key!=='current';
  const empty=edition.rights_hidden_count?'권리 검토 중인 항목은 표시·복사에서 제외했습니다. 확정 기록 원본은 보존됩니다.':edition.status==='no_eligible_recent_articles'?'최근 발행 뉴스는 있으나 브리핑 선정 기준 미충족':edition.status==='no_recent_articles'?'최근 24시간 신규 뉴스 없음':'선정 내역 확인 필요';
  const generationFailed=lastError||collectionHealth?.briefing?.status==='failed';
  const partial=collectionHealth?.status==='partial'||edition.collection?.status==='partial';
  el('briefing-state').textContent=(generationFailed?'브리핑 생성/갱신 실패 · 이전 기록 유지 · ':'')+(collectionFailed?'뉴스 수집 실패 · 후보 확보 불완전 · ':partial?'일부 출처 수집 실패 · 후보 확보 불완전 · ':'')+(past?'과거 브리프':age>86400000?'이전 생성 후보 · 최신 수집 확인 필요':edition.items.length?'주요 뉴스 후보':empty)+(edition.rights_hidden_count?` · 권리 검토 제외 ${edition.rights_hidden_count}건`:'');
  el('briefing-dates').textContent=`생성 ${edition.generated_at} · 마지막 수집 성공 ${edition.last_successful_fetch||'기존 기록에 미기재'} · 뉴스 DB 최근 수집 성공 ${collectionHealth?.last_successful_fetch||'미확인'} · 실제 발송 안 함`;
  el('briefing-news-list').innerHTML=edition.items.length?edition.items.map((n,i)=>`<article class="news-item"><div class="news-meta"><span class="category">${esc(n.category)}</span><span>${esc(n.source)}</span><time datetime="${esc(n.published_at)}">발행 ${esc(n.published_at)}</time></div><h2 class="news-title"><span class="briefing-number">${i+1}.</span> <a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">${esc(n.title)} ↗</a></h2><p class="tiny">${(n.keywords||[]).map(esc).join(' · ')}</p></article>`).join(''):`<p class="briefing-empty">${edition.rights_hidden_count?empty:past?'이 날짜의 확정 브리프는 비어 있습니다. 이후 적격 기사는 현재 후보에서 확인하세요.':empty+'.'} ${history.length?'지난 브리프는 날짜 메뉴에서 확인할 수 있습니다.':'아직 보관된 지난 브리프가 없습니다. 보관 시작 이후의 기록만 표시합니다.'}</p>`;
 }
 async function load(){
  try{const r=await fetch('./data/publication_visibility.json?v='+Date.now(),{cache:'no-store'});if(r.ok){const d=await r.json();if(!Array.isArray(d.blocked_url_hashes)||!d.blocked_url_hashes.every(v=>/^[a-f0-9]{64}$/.test(v)))throw Error();blockedHashes=new Set(d.blocked_url_hashes);}else if(r.status!==404||blockedHashes.size)throw Error();rightsUnavailable=false;}catch(_){rightsUnavailable=true;render();return;}
  try{if(current)current=await checked(current);history=await Promise.all(history.map(checked));if(current||history.length)render();}catch(_){rightsUnavailable=true;render();return;}

  try{const r=await fetch('./data/briefing.json?v='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error();current=await checked(await r.json());lastError=false;}catch(_){lastError=true;}
  try{const r=await fetch('./data/briefing_archive.json?v='+Date.now(),{cache:'no-store'});if(r.ok){const a=await r.json();if(a.mode==='live_rss'&&Array.isArray(a.briefings))history=(await Promise.all(a.briefings.map(checked))).sort((a,b)=>b.briefing_date.localeCompare(a.briefing_date));}}catch(_){}
  try{const h=await fetch('./data/health.json?v='+Date.now(),{cache:'no-store'});if(h.ok){collectionHealth=await h.json();collectionFailed=collectionHealth.status==='failed';}}catch(_){}
  const selected=el('briefing-edition').value;
  el('briefing-edition').innerHTML='<option value="current">현재 후보</option>'+history.map(b=>`<option value="${esc(b.briefing_date)}">${esc(b.briefing_date)} · ${b.items.length}건 · 보관 브리프</option>`).join('');
  if([...el('briefing-edition').options].some(o=>o.value===selected))el('briefing-edition').value=selected;
  render();
 }
 function text(){return edition?.items.length?['[여행기류 · 브리핑 후보]',`생성: ${edition.generated_at}`,`마지막 수집 성공: ${edition.last_successful_fetch||'미기재'}`,...edition.items.map((n,i)=>`${i+1}. ${n.title}\n${n.source} · ${n.published_at}\n${n.category} · ${(n.keywords||[]).join(' · ')}\n${n.url}`),'메타데이터 링크 모음 · 실제 발송 안 함'].join('\n\n'):'복사할 뉴스가 없습니다. 현재 선택한 브리프는 비어 있거나 확인할 수 없습니다.';}
 function copy(){const value=text();if(navigator.clipboard&&window.isSecureContext)navigator.clipboard.writeText(value).catch(()=>window.prompt('브리프 복사',value));else window.prompt('브리프 복사',value);}
 el('briefing-edition').addEventListener('change',render);
 window.BriefingUI={load,render,copy,text,get edition(){return edition;}};load();setInterval(load,300000);
})();
