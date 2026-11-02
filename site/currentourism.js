/* UI only: reads the existing public Newsroom and Research views; no collector writes. */
function newsPublicationTime(n){
 const raw=n.published_at||'';
 if(n.publication_time_verified_for_news===false)return -Infinity;
 const value=/^\d{4}-\d{2}-\d{2}$/.test(raw)?Date.parse(raw+'T00:00:00+09:00'):
  /T\d{2}:\d{2}.*(?:Z|[+-]\d{2}:?\d{2})$/.test(raw)?Date.parse(raw):NaN;
 return Number.isFinite(value)?value:-Infinity;
}
function compareNewsPublication(a,b){
 const x=newsPublicationTime(a),y=newsPublicationTime(b);
 if(x!==y)return x>y?-1:1;
 const left=a.url||'',right=b.url||'';
 return left<right?-1:left>right?1:0;
}
function renderHomeNews(){
 const now=Date.now(),recent=NEWS.filter(n=>{const age=now-Date.parse(n.published_at);return Number.isFinite(age)&&age>=0&&age<=86400000;});
 const label=document.getElementById('home-news-freshness');
 const ordered=[...NEWS].sort(compareNewsPublication);
 label.textContent=NEWS.length?(recent.length?`최근 24시간 발행 ${recent.length}건 · 원문 발행일 최신순`:'최근 24시간 발행 뉴스가 없습니다. 아래는 수록된 최근 기사이며 오늘 발행한 뉴스가 아닙니다.'):'게시 가능한 뉴스 데이터가 없습니다. 수집 상태를 확인해 주세요.';
 document.getElementById('overview-news').innerHTML=NEWS.length?ordered.slice(0,3).map(n=>`<article class="home-news-item"><div class="news-meta"><span class="category">${escapeHtml(n.category)}</span><span>${escapeHtml(n.source)}</span><time datetime="${escapeHtml(n.published_at)}">${escapeHtml(n.date)}</time></div><h3><a href="${escapeHtml(n.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(n.title)}</a></h3><p class="news-keywords">${n.keywords.map(escapeHtml).join(' · ')}</p></article>`).join(''):'<div class="empty">실제 수집 결과가 아직 없습니다.</div>';
}
function syncHomeWeather(){
 const title=document.getElementById('weather-title').textContent;
 const tone=({'비':'rain','흐림':'cloudy','구름 조금':'partly','맑음':'sunny'})[title]||'cloudy';
 document.querySelectorAll('.weather-panel,.weather-result').forEach(card=>card.dataset.weather=tone);

 for(const key of ['title','icon','score'])document.getElementById('home-weather-'+key).textContent=document.getElementById('weather-'+key).textContent;
}
document.addEventListener('DOMContentLoaded',()=>{
 const button=document.getElementById('news-menu-toggle'),panel=document.getElementById('news-submenu'),group=button.closest('.news-nav');
 function close(returnFocus=false){const inside=panel.contains(document.activeElement);panel.hidden=true;button.setAttribute('aria-expanded','false');if(returnFocus||inside)button.focus();}
 function open(){panel.hidden=false;button.setAttribute('aria-expanded','true');}
 window.closeNewsMenu=close;
 button.addEventListener('click',()=>panel.hidden?open():close());
 button.addEventListener('keydown',event=>{if(event.key==='ArrowDown'){event.preventDefault();open();panel.querySelector('a').focus();}});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!panel.hidden){event.preventDefault();close(true);}});
 document.addEventListener('click',event=>{if(!group.contains(event.target))close();});
 group.addEventListener('focusout',event=>{if(event.relatedTarget&&!group.contains(event.relatedTarget))close();});
 const header=document.querySelector('.site-header');
 const sizeHeader=()=>document.documentElement.style.setProperty('--site-header-height',header.getBoundingClientRect().height+'px');
 new ResizeObserver(sizeHeader).observe(header);sizeHeader();
 const logo=document.getElementById('brand-logo'),fallback=document.getElementById('brand-fallback');
 function showLogo(){if(logo.naturalWidth){logo.hidden=false;fallback.hidden=true;}}
 logo.addEventListener('load',showLogo);logo.addEventListener('error',()=>{logo.hidden=true;fallback.hidden=false;});showLogo();
 syncHomeWeather();loadAboutSources();
});
async function loadAboutSources(){
 const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
 const statuses={ok:'최근 수집 성공',error:'최근 접근 실패',disabled:'미연결 · 검토 대상',not_due:'연결 · 다음 주기 대기',partial:'일부 검증 실패'};
 const row=(name,url,label)=>`<div class="source-status-row"><div><b>${esc(name)}</b><small>${esc(label)}</small></div>${/^https?:\/\//.test(url||'')?`<a class="external" href="${esc(url)}" target="_blank" rel="noopener noreferrer">공식 출처 ↗</a>`:''}</div>`;
 await Promise.all([
  (async()=>{try{const response=await fetch('./data/health.json');if(!response.ok)throw Error();const db=await response.json();document.getElementById('about-news-sources').innerHTML=(db.sources||[]).map(s=>row(s.name,s.url,(statuses[s.status]||'상태 확인 필요')+(s.id==='kosis_recent'?' · 통계 별도 보관':s.id.startsWith('sec_')?' · 기업공시 별도 보관':''))).join('');}catch(_){document.getElementById('about-news-sources').textContent='최신 실행 상태를 불러오지 못했습니다. 위 공식 출처 링크를 이용해 주세요.';}})(),
  (async()=>{try{const [r,h]=await Promise.all([fetch('./data/reports.json'),fetch('./data/reports_health.json')]);if(!r.ok||!h.ok)throw Error();const db=await r.json(),health=await h.json();const rows=health.sources||[];const holds={kto:'허용된 발간물 경로·접근 확인 필요',mckinsey:'자동 접근 및 활용 조건 확인 필요',untourism:'접근 제한 · 공식 수신 경로 확인 필요',iata:'자동 수집 제한 · 별도 허락 필요',wttc:'공개 플랫폼 활용 범위 확인 필요'};document.getElementById('about-research-sources').innerHTML=rows.map(s=>{const publisher=s.publisher||s.name||s.id;const info=db.publishers?.[publisher]||{};const count=db.reports.filter(r=>r.publisher===publisher).length;return row(publisher,info.homepage||s.url||'',`${!['blocked','disabled'].includes(s.status)?'목록 발견 연결':'조사 대상 · 미연결'} · 공개 등록 ${count}건${s.reason?' · '+(holds[s.id]||'접근 또는 이용조건 확인 필요'):''}`);}).join('')||'기관별 연결 상태 확인이 필요합니다.';}catch(_){document.getElementById('about-research-sources').textContent='Research 연결 상태를 불러오지 못했습니다. 리서치 탭에서 발행기관과 원문을 확인해 주세요.';}})()
 ]);
}

// Dismiss only the banner, without changing channel setup or message delivery.
document.addEventListener('DOMContentLoaded',()=>{
 const banner=document.getElementById('kakao-banner');
 try{banner.hidden=localStorage.getItem('currentourism.kakao.dismissed')==='true';}catch(_){}
 document.getElementById('kakao-banner-close').addEventListener('click',()=>{
  banner.hidden=true;
  try{localStorage.setItem('currentourism.kakao.dismissed','true');}catch(_){}
  document.querySelector('.brand-home')?.focus();
 });
});
