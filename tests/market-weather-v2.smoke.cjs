// All mutations stay in isolated browser memory. Never writes production JSON.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true}),base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010',dir=process.env.WEATHER_OUTPUT||'/tmp/currentourism-pr12';fs.mkdirSync(dir,{recursive:true});
 try{
  for(const width of [320,390,768,1440]){
   const page=await browser.newPage({viewport:{width,height:1100},reducedMotion:'reduce'}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   let macroRequests=0;page.on('request',r=>{if(/\/data\/macro.json/.test(r.url()))macroRequests++;});
   await page.goto(base);await page.waitForFunction(()=>MacroMonitor?.database&&document.querySelectorAll('[data-observation-id]').length===7);
   const db=await page.evaluate(()=>MacroMonitor.database),inbound=db.indicators.find(i=>i.id==='kto_inbound');
   assert.equal(macroRequests,1,'Observation must share the Macro request');
   assert.match(await page.locator('#home-market-observation').textContent(),new RegExp(inbound.latest.period));
   assert.match(await page.locator('#home-market-observation').textContent(),new RegExp(inbound.latest.comparisons.yoy_pct.toFixed(2).replace('.','\\.')));
   assert.match(await page.locator('#home-market-observation').textContent(),/종합 판정 유보/);
   assert.equal(await page.locator('#home-market-observation [data-weather]').count(),0);
   for(const route of ['overview','weather']){
    await page.evaluate(r=>navigate(r),route);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),width+'/'+route);
    if([390,1440].includes(width))await page.screenshot({path:`${dir}/after-${route}-${width}.png`,fullPage:true});
   }
   for(const i of db.indicators.filter(i=>i.connected)){
    const card=page.locator(`[data-observation-id="${i.id}"]`);assert.equal(await card.locator('[data-value]').getAttribute('data-value'),String(i.latest.value));
    assert.match(await card.textContent(),new RegExp(i.latest.period));assert.equal(await card.locator('a').getAttribute('href'),i.source_url);
   }
   assert.equal(await page.locator('#market-country-cards [data-observation-id]').count(),5);
   assert.equal(await page.locator('#market-demand-chart rect').count(),12);
   const originalScore=await page.locator('#weather-score').textContent();
   await page.locator('#market-chart-metric').selectOption('kto_outbound');assert.match(await page.locator('#market-demand-chart svg').getAttribute('aria-label'),/국민 해외/);
   await page.locator('#market-chart-mode').selectOption('growth');assert.match(await page.locator('#market-demand-chart svg').getAttribute('aria-label'),/전년 동월비/);assert.equal(await page.locator('#weather-score').textContent(),originalScore);
   // Forecast and observation controls are independent.
   const observedBefore=await page.locator('#market-demand-cards').textContent(),neutral=await page.locator('.market-observation-card').first().evaluate(e=>getComputedStyle(e).backgroundColor);
   const colors=new Set();
   for(const [value,tone,score] of [[-30,'rain','11'],[0,'cloudy','50'],[15,'partly','70'],[35,'sunny','96']]){
    await page.evaluate(v=>{for(const id of ['s-arrivals','s-spend','s-air'])document.getElementById(id).value=v;weather();},value);
    assert.equal(await page.locator('#weather-score').textContent(),score);assert.equal(await page.locator('.weather-result').getAttribute('data-weather'),tone);colors.add(await page.locator('.weather-result').evaluate(e=>getComputedStyle(e).backgroundColor));
    assert.equal(await page.locator('#market-demand-cards').textContent(),observedBefore);assert.equal(await page.locator('.market-observation-card').first().evaluate(e=>getComputedStyle(e).backgroundColor),neutral);
   }
   assert.equal(colors.size,4);await page.locator('#reset-weather').click();assert.equal(await page.locator('#weather-score').textContent(),'68');
   await page.locator('#s-arrivals').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#s-arrivals').inputValue(),'22');await page.locator('#reset-weather').click();
   const formula=page.locator('.scenario-formula');assert.equal(await formula.evaluate(e=>e.open),false);await formula.locator('summary').focus();await page.keyboard.press('Enter');assert.equal(await formula.evaluate(e=>e.open),true);
   // One missing month and no previous-year denominators: never fill with zero.
   await page.evaluate(()=>{const i=MacroMonitor.database.indicators.find(i=>i.id==='kto_inbound');i.observations=i.observations.filter(o=>o.period!=='2026-08');MacroMonitor.render();});
   await page.locator('#market-chart-metric').selectOption('kto_inbound');await page.locator('#market-chart-mode').selectOption('count');assert.equal(await page.locator('#market-demand-chart .macro-series-gap').count(),1);assert.equal(await page.locator('#market-demand-chart rect').count(),11);
   await page.evaluate(()=>{const i=MacroMonitor.database.indicators.find(i=>i.id==='kto_inbound');i.observations=i.observations.filter(o=>!o.period.startsWith('2025'));i.latest.comparisons.yoy_pct=null;MacroMonitor.render();});
   await page.locator('#market-chart-mode').selectOption('growth');assert.match(await page.locator('#market-demand-chart').textContent(),/전년 동월 자료가 없어/);assert.match(await page.locator('#market-chart-foot').textContent(),/12개/);const gap=page.locator('[data-observation-id="kto_inbound"] .percentage-change--missing').first();assert.equal(await gap.textContent(),'—');assert.equal(await gap.getAttribute('aria-label'),'비교 자료 없음');
   await page.evaluate(()=>MacroMonitor.load());
   // Corrected official data reflected everywhere, without touching scenario inputs.
   await page.evaluate(()=>{const i=MacroMonitor.database.indicators.find(i=>i.id==='kto_inbound');i.latest.value=1234567;i.observations.find(o=>o.period===i.latest.period).value=1234567;i.latest.revision_status='revised';i.correction_count=1;MacroMonitor.render();});
   for(const selector of ['#home-macro-kpis [data-macro-id="kto_inbound"] [data-value]','[data-observation-id="kto_inbound"] [data-value]'])assert.equal(await page.locator(selector).getAttribute('data-value'),'1234567');
   assert.match(await page.locator('#home-market-observation').textContent(),/1,234,567/);assert.match(await page.locator('[data-observation-id="kto_inbound"]').textContent(),/정정 반영/);assert.equal(await page.locator('#weather-score').textContent(),'68');
   await page.evaluate(()=>{const i=MacroMonitor.database.indicators.find(i=>i.id==='kto_outbound');i.latest={...i.latest,period:'2026-10'};i.latest_period='2026-10';i.observations.push({...i.latest});i.months++;MacroMonitor.render();});assert.match(await page.locator('[data-observation-id="kto_outbound"]').textContent(),/2026-10/);assert.match(await page.locator('#home-market-observation').textContent(),/2026-09/);assert.equal(await page.locator('#weather-score').textContent(),'68');
   await page.evaluate(()=>{const i=MacroMonitor.database.indicators.find(i=>i.id==='kto_inbound_cn');i.latest.period='2026-08';i.observations.find(o=>o.period==='2026-08').value=i.latest.value;MacroMonitor.render();});assert.match(await page.locator('[data-observation-id="kto_inbound_cn"]').textContent(),/기준월 불일치/);
   await page.evaluate(()=>MacroMonitor.load());
   await page.route('**/data/macro_health.json?*',r=>r.fulfill({json:{status:'ok',sources:[{id:'kto_monthly_statistics',status:'ok',last_successful_check:'2020-01-01T00:00:00+09:00'}]}}));await page.evaluate(()=>MacroMonitor.load());assert.match(await page.locator('#market-observation-status').textContent(),/갱신 지연/);await page.unroute('**/data/macro_health.json?*');
   await page.route('**/data/macro.json?*',r=>r.fulfill({status:503}));await page.evaluate(()=>MacroMonitor.load());assert.match(await page.locator('#market-observation-status').textContent(),/실패.*이전 검증값/);assert.equal(await page.locator('[data-observation-id="kto_inbound"] [data-value]').getAttribute('data-value'),String(inbound.latest.value));
   await page.evaluate(()=>MarketObservation.render({mode:'verified_official_statistics',indicators:[{id:'kto_tourism_receipts',connected:true,latest:{value:999999999}}]},()=> '공식 파일 연동'));assert.equal(await page.locator('[data-observation-id]').count(),0);assert.match(await page.locator('#market-demand-cards').textContent(),/관측 불가/);assert.doesNotMatch(await page.locator('#home-market-observation').textContent(),/999,999,999/);assert.equal(await page.locator('#weather-score').textContent(),'68');
   assert.deepEqual(errors,[]);await page.close();
  }
  const empty=await browser.newPage();await empty.route('**/data/macro.json?*',r=>r.fulfill({status:503}));await empty.goto(base);await empty.waitForFunction(()=>document.getElementById('market-observation-status').textContent.includes('관측 불가'));assert.match(await empty.locator('#home-market-observation').textContent(),/검증된 자료 없음/);await empty.close();
  console.log('PASS Weather v2: shared official values/source/month, 12-month chart/missing/comparisons, corrections/delay/failures/financial exclusion, scenario isolation/colors/keyboard/reset, four widths');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
