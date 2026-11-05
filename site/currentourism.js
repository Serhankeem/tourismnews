function contentHeading(record,kind,allow=true){return window.ContentLocale?.heading(record,kind,allow)||{title:record.title,localized:false};}
function contentTitleNote(record,kind,allow=true){
 const h=contentHeading(record,kind,allow);if(!h.localized)return '';
 return `<div class="localized-title-note"><span class="locale-badge">한국어 안내 표제</span><p class="original-title" lang="en">원제: ${escapeHtml(record.title)}</p><details><summary>표제 근거·이용 안내</summary><p>${escapeHtml(h.note)}</p><p>${escapeHtml(h.attribution)}</p><a href="${escapeHtml(h.evidence_url)}" target="_blank" rel="noopener noreferrer">이용조건 ↗</a></details></div>`;
}
function publisherRegionLabel(n){return ({domestic:'국내 발행처',foreign:'해외 발행처',unknown:'발행처 구분 미확인'})[ContentLocale.newsRegion(n)];}
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
 label.textContent=NEWS.length?(recent.length?`최근 24시간 발행 ${recent.length}건 · 전체 최신순 · 원문 발행일 기준`:'최근 24시간 발행 뉴스가 없습니다. 아래는 수록된 최근 기사이며 오늘 발행한 뉴스가 아닙니다.'):'게시 가능한 뉴스 데이터가 없습니다. 수집 상태를 확인해 주세요.';
 document.getElementById('overview-news').innerHTML=NEWS.length?ordered.slice(0,3).map(n=>`<article class="home-news-item"><div class="news-meta"><span class="category">${escapeHtml(n.category)}</span><span>${escapeHtml(n.source)}</span><span class="publisher-region">${publisherRegionLabel(n)}</span><time datetime="${escapeHtml(n.published_at)}">${escapeHtml(n.date)}</time></div><h3><a href="${escapeHtml(n.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(contentHeading(n,'news').title)}</a></h3>${contentTitleNote(n,'news')}<p class="news-keywords">${n.keywords.map(escapeHtml).join(' · ')}</p></article>`).join(''):'<div class="empty">실제 수집 결과가 아직 없습니다.</div>';
}
// Static vector artwork shared by both Scenario Lab views; no model inputs.
const WeatherMotion=(()=>{
 const sun='<g fill="none" stroke="#F47735" stroke-width="3" stroke-linecap="round"><circle class="sun-halo" cx="35" cy="31" r="24" fill="#F47735" stroke="none" opacity=".25"/><g class="sun-rays"><path d="M35 4v6M35 52v6M8 31h6M56 31h6M16 12l4 4M50 46l4 4M16 50l4-4M50 16l4-4"/></g><circle cx="35" cy="31" r="14" fill="#F47735" stroke="none"/></g>';
 const cloud=(cls,x,y)=>`<g transform="translate(${x} ${y})"><path class="${cls}" d="M25 55h43c16 0 17-23 2-25-1-17-26-20-31-4-15-5-25 10-18 20-9 0-9 9 4 9z" fill="#E1EAF6" stroke="#173B73" stroke-width="2.5"/></g>`;
 const labels={sunny:'맑음',partly:'구름 조금',cloudy:'흐림',rain:'비'};
 function render(tone){
  const art=tone==='sunny'?sun:tone==='partly'?sun+cloud('cloud-drift',0,7):
   tone==='cloudy'?cloud('cloud-back',-9,-10)+cloud('cloud-drift',4,7):
   cloud('cloud-drift',0,-3)+'<g stroke="#173B73" stroke-width="3" stroke-linecap="round"><path class="rain-drop" d="M30 60l-3 6"/><path class="rain-drop" d="M49 60l-3 6"/><path class="rain-drop" d="M68 60l-3 6"/></g>';
  for(const id of ['weather-icon','home-weather-icon']){
   const node=document.getElementById(id);if(!node)continue;
   if(node.dataset.iconState!==tone||!node.querySelector('svg')){
    node.innerHTML=`<svg class="weather-glyph" viewBox="0 0 96 80" aria-hidden="true" focusable="false">${art}</svg>`;
    node.dataset.iconState=tone;
   }
   node.removeAttribute('aria-hidden');node.setAttribute('role','img');node.setAttribute('aria-label',`시나리오 · 가상 실험: ${labels[tone]}`);
  }
 }
 return {render};
})();
let pageEntrance;
const motionPreference=matchMedia('(prefers-reduced-motion: reduce)');
window.polishPageTransition=(page,changed)=>{
 if(!changed)return;
 pageEntrance?.cancel();
 if(!motionPreference.matches)pageEntrance=document.getElementById('page-'+page).animate(
  [{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'translateY(0)'}],
  {duration:200,easing:'ease-out'});
};
motionPreference.addEventListener('change',()=>{if(motionPreference.matches)pageEntrance?.cancel();});
const pauseWeatherMotion=()=>document.documentElement.dataset.motionPaused=String(document.hidden);
document.addEventListener('visibilitychange',pauseWeatherMotion);pauseWeatherMotion();

function syncHomeWeather(){
 const title=document.getElementById('weather-title').textContent;
 const tone=({'비':'rain','흐림':'cloudy','구름 조금':'partly','맑음':'sunny'})[title]||'cloudy';
 document.querySelectorAll('.weather-panel,.weather-result').forEach(card=>card.dataset.weather=tone);

 WeatherMotion.render(tone);
 for(const key of ['title','score'])document.getElementById('home-weather-'+key).textContent=document.getElementById('weather-'+key).textContent;
}
document.addEventListener('DOMContentLoaded',()=>{
 const button=document.getElementById('news-menu-toggle'),panel=document.getElementById('news-submenu'),group=button.closest('.news-nav');
 const header=document.querySelector('.site-header'),inner=header.querySelector('.header-inner'),nav=document.getElementById('primary-navigation'),menu=document.getElementById('header-menu-toggle');
 function closeNews(returnFocus=false){const inside=panel.contains(document.activeElement);panel.hidden=true;button.setAttribute('aria-expanded','false');if(returnFocus||inside)button.focus();}
 function openNews(){panel.hidden=false;button.setAttribute('aria-expanded','true');}
 function closeNavigation(returnFocus=false){
  const inside=nav.contains(document.activeElement);closeNews();nav.classList.remove('is-open');menu.setAttribute('aria-expanded','false');
  if(header.dataset.compact==='true'&&(returnFocus||inside))menu.focus();
 }
 function openNavigation(){nav.classList.add('is-open');menu.setAttribute('aria-expanded','true');}
 window.closeNewsMenu=closeNews;window.closeNavigation=closeNavigation;
 menu.addEventListener('click',()=>menu.getAttribute('aria-expanded')==='true'?closeNavigation():openNavigation());
 menu.addEventListener('keydown',event=>{if(event.key==='ArrowDown'){event.preventDefault();openNavigation();nav.querySelector('a').focus();}});
 button.addEventListener('click',()=>panel.hidden?openNews():closeNews());
 button.addEventListener('keydown',event=>{if(event.key==='ArrowDown'){event.preventDefault();openNews();panel.querySelector('a').focus();}});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'){
  if(!panel.hidden){event.preventDefault();closeNews(true);}
  else if(menu.getAttribute('aria-expanded')==='true'){event.preventDefault();closeNavigation(true);}
 }});
 document.addEventListener('click',event=>{if(!group.contains(event.target))closeNews();if(!header.contains(event.target))closeNavigation();});
 header.addEventListener('focusout',event=>{if(event.relatedTarget&&!header.contains(event.relatedTarget))closeNavigation();});
 group.addEventListener('focusout',event=>{if(event.relatedTarget&&!group.contains(event.relatedTarget))closeNews();});
 function sizeHeader(){
  // Measure the same links in their desktop style, synchronously and without
  // paint/focus changes. No viewport breakpoint decides whether they fit.
  header.dataset.measuring='true';
  const style=getComputedStyle(inner),available=inner.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight);
  const required=header.querySelector('.brand-home').getBoundingClientRect().width+parseFloat(style.columnGap)+nav.getBoundingClientRect().width;
  delete header.dataset.measuring;
  const compact=required>available;
  if(header.dataset.compact!==String(compact)){
   const active=document.activeElement;header.dataset.compact=String(compact);closeNavigation();
   if(compact&&nav.contains(active))menu.focus();
   else if(!compact&&active===menu)nav.querySelector('a').focus();
  }
  document.documentElement.style.setProperty('--site-header-height',header.getBoundingClientRect().height+'px');
 }
 let scrolled;
 const scrollHeader=()=>{const next=scrollY>8;if(next!==scrolled){header.classList.toggle('is-scrolled',next);scrolled=next;}};
 window.addEventListener('scroll',scrollHeader,{passive:true});scrollHeader();
 const headerObserver=new ResizeObserver(sizeHeader);headerObserver.observe(inner);headerObserver.observe(nav);window.addEventListener('resize',sizeHeader);document.fonts.ready.then(sizeHeader);sizeHeader();
 const logo=document.getElementById('brand-logo'),fallback=document.getElementById('brand-fallback');
 function showLogo(){if(logo.naturalWidth){logo.hidden=false;fallback.hidden=true;}}
 logo.addEventListener('load',showLogo);logo.addEventListener('error',()=>{logo.hidden=true;fallback.hidden=false;});showLogo();
 window.addEventListener('content-locale-updated',()=>{
  if(state.page==='research')window.renderResearch?.();
  else if(state.page==='news'||state.page==='overview')renderNews();
  else if(state.page==='briefing')window.BriefingUI?.render();
  const modal=document.getElementById('modal-layer');
  if(modal.classList.contains('open')&&modal.dataset.newsId){
   if(NEWS.some(n=>n.id===modal.dataset.newsId))openDetail(modal.dataset.newsId);
   else modal.classList.remove('open');
  }
 });
 document.querySelectorAll('[data-news-origin]').forEach(b=>b.addEventListener('click',()=>{state.newsOrigin=b.dataset.newsOrigin;state.newsPage=1;renderNews();}));
 document.getElementById('news-order').addEventListener('change',e=>{state.newsOrder=e.target.value;state.newsPage=1;renderNews();});
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
