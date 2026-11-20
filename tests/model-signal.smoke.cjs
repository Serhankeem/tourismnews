// Pinned, already published Macro + VOL.01 only. No writes to public data or APIs.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8090',out=process.env.MODEL_SCREENSHOTS||'/tmp/model-signal-review';
const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
(async()=>{fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({headless:true});
try{
 for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.clock.install({time:new Date('2026-11-20T08:30:00Z')});await page.goto(base+'/#weather-simulator');
  await page.waitForFunction(()=>window.MarketSignalUI?.result?.status==='observed');
  const result=await page.evaluate(()=>MarketSignalUI.result);assert.equal(result.model_version,'model-signal-v1.0.0');assert.equal(result.reference_period,'2026-09');
  assert.equal(await page.locator('#weather-score').textContent(),result.score_display);assert.equal(await page.locator('#home-weather-score').textContent(),result.score_display);
  assert.equal(await page.locator('#s-arrivals,#s-spend,#s-air,#reset-weather').count(),0);
  assert.equal(await page.locator('#weather-page-title').textContent(),'관광시장 모델 · 공식 관측');
  assert.equal(await page.locator('.model-axis').count(),2);assert.ok(await page.locator('#market-demand-chart svg').count());
  for(const axis of result.axes)assert.equal(await page.locator(`[data-model-id="${axis.indicator_id}"] [data-value]`).getAttribute('data-value'),String(axis.value));
  for(const a of await page.locator('#model-evidence a').all()){assert.match(await a.getAttribute('href'),/^https:\/\/(datalab.visitkorea.or.kr|know.tour.go.kr)\//);assert.equal(await a.getAttribute('target'),'_blank');}
  await page.locator('.model-details summary').focus();await page.keyboard.press('Enter');assert.ok(await page.locator('.model-details').evaluate(n=>n.open));
  if(process.env.AXE_PATH){await page.addScriptTag({path:process.env.AXE_PATH});const violations=await page.evaluate(async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}));});assert.deepEqual(violations,[]);}
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(await page.locator('#kakao-banner-close').isVisible())await page.locator('#kakao-banner-close').click();await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(100);await page.screenshot({path:out+'/model-'+width+'.png',fullPage:true});
  await page.locator('.brand-home').click();assert.equal(await page.locator('#home-weather-score').textContent(),await page.locator('#weather-score').textContent());await page.screenshot({path:out+'/home-'+width+'.png',fullPage:true});
  await page.evaluate(()=>navigate('weather-simulator'));await page.reload();await page.waitForFunction(()=>MarketSignalUI?.result?.status==='observed');assert.equal(await page.locator('#weather-score').textContent(),result.score_display);
  await page.locator('#page-weather .weather-modes a[href="#weather"]').click();await page.waitForSelector('.monthly-title');
  const [index,archive]=await Promise.all(['index','archive'].map(async name=>(await page.request.get(base+'/data/market_weather_'+name+'.json')).json()));
  const article=archive.contents[index.latest];assert.equal(crypto.createHash('sha256').update(canonical(article)).digest('hex'),index.entries[0].content_sha256);
  assert.equal(index.entries[0].content_sha256,'f0ab5238755ecba0d22144fabbf5c3de6cabd1884bcdd1ac5e64af9aa9d846c0');assert.equal(await page.locator('#monthly-article>section').count(),5);
  await page.goBack();assert.equal(await page.locator('#weather-legacy').isVisible(),true);assert.deepEqual(errors,[]);await page.close();
 }
 for(const kind of ['missing','disconnected','month_mismatch','tampered','load_failed']){
  const page=await browser.newPage();await page.clock.install({time:new Date('2026-11-20T08:30:00Z')});
  const original=await(await page.request.get(base+'/data/macro.json')).json();
  await page.route('**/data/macro.json*',route=>{if(kind==='load_failed')return route.fulfill({status:503,body:'unavailable'});const d=structuredClone(original),a=d.indicators.find(i=>i.id==='kto_inbound'),b=d.indicators.find(i=>i.id==='kto_tourism_receipts');if(kind==='missing')a.observations=a.observations.filter(o=>o.period!=='2025-09');if(kind==='disconnected')b.connected=false;if(kind==='month_mismatch')b.latest.period='2026-08';if(kind==='tampered')a.latest.value+=100;return route.fulfill({json:d});});
  await page.goto(base+'/#weather-simulator');await page.waitForTimeout(600);
  assert.equal(await page.locator('#weather-score').textContent(),'—');assert.equal(await page.locator('#home-weather-score').textContent(),'—');assert.equal(await page.locator('#weather-title').textContent(),'모델 판정 유보');assert.equal(await page.locator('.model-axis').count(),0);await page.close();
 }
 console.log('PASS Model Signal: pinned real public replay, home/detail single result, 390/1440, sources/keyboard/axe, reload/history, missing/disconnected/mismatch/tamper/failure withholding, frozen VOL.01 hash unchanged');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
