const clickNav=require('./navigation-helper.cjs');
// Real public data, UI navigation, truthful freshness, desktop/mobile. No collector mutation.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const crypto=require('node:crypto');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010';
 const dir=process.env.HOME_SCREENSHOTS||'/tmp/currentourism-home';fs.mkdirSync(dir,{recursive:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const news=await(await page.request.get(base+'/data/newsroom.json')).json();
  const reports=await(await page.request.get(base+'/data/reports.json')).json();
  await page.goto(base);await page.waitForFunction(()=>!newsLoading&&NEWS.length>0&&window.MacroMonitor?.database?.indicators.length>0);
  const originalLogo=await page.request.get(base+'/assets/currentourism-new-airplane-logo.png?v=7f92affea61c5719');
  assert.equal(originalLogo.status(),200);
  assert.equal(crypto.createHash('sha256').update(await originalLogo.body()).digest('hex'),'7f92affea61c57197f2b015576cb7bcaf604defb0ac270894157d8e94d070b7f','Browser-served logo must match new airplane original bytes');
  await page.locator('#brand-logo').waitFor({state:'visible'});
  assert.equal(await page.locator('#brand-fallback').isVisible(),false);
  async function checkLogoRatio(target){
   const size=await target.locator('#brand-logo').evaluate(img=>({w:img.naturalWidth,h:img.naturalHeight,rect:img.getBoundingClientRect().toJSON()}));
   assert.equal(size.w,1774);assert.equal(size.h,887);
   assert.ok(Math.abs(size.rect.width/size.rect.height-size.w/size.h)<0.01,'Preserve original logo ratio');
  }
  await checkLogoRatio(page);
  assert.equal(await page.locator('.sidebar').count(),0);
  assert.equal(await page.locator('.primary-navigation a').count(),6);
  assert.deepEqual(await page.locator('.primary-navigation a').evaluateAll(a=>a.map(x=>x.dataset.nav)),['weather','news','briefing','research','macro','about']);
  assert.equal(await page.title(),'여행기류 currentourism — 관광산업 인텔리전스');
  const rect=await page.locator('.overview-hero').evaluate(el=>[...el.children].map(n=>({x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y,w:n.getBoundingClientRect().width})));
  assert.equal(rect[0].y,rect[1].y);assert.ok(rect[0].w>rect[1].w);
  assert.equal(await page.locator('#overview-news .home-news-item').count(),3);
  for(const a of await page.locator('#overview-news h3 a').evaluateAll(nodes=>nodes.map(a=>({title:a.textContent,url:a.getAttribute('href')}))))assert.ok(news.articles.some(n=>n.title===a.title&&n.url===a.url));
  assert.equal(await page.locator('#overview-news img,#overview-news .news-desc').count(),0);
  const ordered=await page.locator('#page-overview').evaluate(el=>['.overview-hero','.kpi-grid','.dashboard-lower'].map(s=>el.querySelector(s).getBoundingClientRect().top));assert.ok(ordered[0]<ordered[1]&&ordered[1]<ordered[2]);
  assert.match(await page.locator('.weather-panel').textContent(),/시뮬레이션/);
  await page.screenshot({path:dir+'/home-desktop.png',fullPage:true});
  await page.locator('.brand-home').screenshot({path:dir+'/brand-header.png'});
  for(const route of ['weather','news','briefing','research','macro','about']){
   await clickNav(page,route);
   assert.equal(await page.locator('#page-'+route).isVisible(),true);
   assert.equal(await page.locator(`.primary-navigation [data-nav="${route}"]`).getAttribute('aria-current'),'page');
   await page.locator('.brand-home').click();assert.equal(await page.locator('#page-overview').isVisible(),true);
  }
  await clickNav(page,'weather');
  const before=await page.locator('#weather-score').textContent();
  await page.locator('#s-spend').fill('-30');await page.locator('#s-spend').dispatchEvent('input');
  assert.notEqual(await page.locator('#weather-score').textContent(),before);
  assert.equal(await page.locator('#home-weather-score').textContent(),await page.locator('#weather-score').textContent());
  await page.locator('#reset-weather').click();assert.equal(await page.locator('#weather-score').textContent(),before);
  await clickNav(page,'macro');
  await page.locator('#chart-toggle-macro [data-chart="growth"]').click();assert.match(await page.locator('#chart-macro svg').getAttribute('aria-label'),/전년 동월비/);
  await page.locator('#chart-toggle-macro [data-chart="count"]').click();const macro=await page.evaluate(()=>MacroMonitor.database.indicators.find(i=>i.id==='kto_inbound'));const [my,mm]=macro.latest_period.split('-').map(Number);const cutoff=new Date(Date.UTC(my,mm-36,1)).toISOString().slice(0,7);assert.equal(await page.locator('#chart-macro svg rect').count(),macro.observations.filter(o=>o.period>=cutoff).length);
  await page.goto(base+'/#research');await page.waitForFunction(()=>window.ResearchLibrary?.database.reports.length>0);
  assert.equal(await page.locator('#page-research').isVisible(),true);assert.equal(await page.locator('#research-count').textContent(),String(reports.count));
  assert.equal(await page.locator('.primary-navigation [data-nav="research"]').getAttribute('aria-current'),'page');
  await page.locator('#page-research .news-subnav [data-goto="news"]').click();assert.equal(await page.locator('#page-news').isVisible(),true);
  await page.goBack();assert.equal(await page.locator('#page-research').isVisible(),true);
  await page.goto(base+'/#sources');await page.waitForFunction(()=>document.querySelectorAll('#about-research-sources .source-status-row').length===Object.keys(ResearchLibrary.database.publishers).length);
  assert.equal(await page.locator('#page-about').isVisible(),true);assert.equal(await page.locator('#data-sources').isVisible(),true);
  assert.match(await page.locator('#about-research-sources').textContent(),/공개 등록 65건/);
  assert.match(await page.locator('#about-research-sources').textContent(),/미연결/);
  assert.equal(await page.locator('#data-sources a[href="https://know.tour.go.kr/main/main.do"]').count(),1);
  for(const heading of ['About Us','프로젝트 목적','운영 원칙','Data Sources','Non-commercial Policy'])assert.ok(await page.getByRole('heading',{name:heading,exact:true}).count());
  await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:dir+'/about-desktop.png',fullPage:true});
  // Old issue dates must remain old; empty/error states cannot fabricate news.
  await page.evaluate(()=>{NEWS.forEach(n=>n.published_at='2020-01-01T00:00:00+09:00');renderHomeNews();});
  assert.match(await page.locator('#home-news-freshness').textContent(),/최근 24시간 발행 뉴스가 없습니다/);
  await page.evaluate(()=>{NEWS.splice(0);renderHomeNews();});assert.equal(await page.locator('#overview-news h3').count(),0);assert.match(await page.locator('#home-news-freshness').textContent(),/게시 가능한 뉴스 데이터가 없습니다/);
  await clickNav(page,'about');
  await page.locator('.brand-home').focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('#page-overview').isVisible(),true,'Keyboard logo link returns home');
  const mobile=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});mobile.on('pageerror',e=>errors.push(e.message));
  await mobile.goto(base);await mobile.waitForFunction(()=>!newsLoading&&NEWS.length>0);
  await mobile.locator('#brand-logo').waitFor({state:'visible'});await checkLogoRatio(mobile);
  assert.equal(await mobile.locator('.primary-navigation').isVisible(),false);
  await mobile.locator('#header-menu-toggle').click();
  const toggle=mobile.locator('#news-menu-toggle');await toggle.click();assert.equal(await toggle.getAttribute('aria-expanded'),'true');
  await mobile.keyboard.press('Escape');assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.equal(await toggle.evaluate(el=>document.activeElement===el),true);
  for(const route of ['weather','news','briefing','research','macro','about']){
   await clickNav(mobile,route);assert.equal(await mobile.locator('#page-'+route).isVisible(),true);assert.equal(await toggle.getAttribute('aria-expanded'),'false');
   assert.equal(await mobile.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,route+' must fit mobile');
   await mobile.locator('#brand-logo').click();assert.equal(await mobile.locator('#page-overview').isVisible(),true);
  }
  const mrect=await mobile.locator('.overview-hero').evaluate(el=>[...el.children].map(n=>n.getBoundingClientRect().top));assert.ok(mrect[0]<mrect[1]);
  await mobile.screenshot({path:dir+'/home-mobile.png',fullPage:true});
  await mobile.locator('.home-research-link a').click();assert.equal(await mobile.locator('#page-research').isVisible(),true);
  assert.equal(await mobile.locator('#research-results .research-card').count(),10);
  await mobile.goto(base+'/#about');await mobile.waitForFunction(()=>document.querySelectorAll('#about-research-sources .source-status-row').length===Object.keys(ResearchLibrary.database.publishers).length);
  await mobile.screenshot({path:dir+'/about-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: real home metadata/order/freshness, desktop/mobile four-group navigation, home logo link, keyboard menu, deep links/history, About dynamic source status, chart, weather/reset, Research preservation; no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
