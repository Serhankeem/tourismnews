const assertSharedModel=require('./model-ui-helper.cjs');
// Current approved operating data only. No fabricated stats or writes.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
  const browser=await chromium.launch({headless:true}),base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8045';
  try{
    for(const width of [320,390,768,1440]){
      const page=await browser.newPage({viewport:{width,height:1100}}),errors=[];
      page.on('pageerror',e=>errors.push(e.message));await page.goto(base);
      await page.waitForFunction(()=>MacroMonitor?.database&&document.querySelector('#market-demand-chart svg'));
      const db=await page.evaluate(()=>MacroMonitor.database),connected=db.indicators.filter(i=>i.connected);
      assert.equal(connected.length,9);assert.equal(connected.reduce((n,i)=>n+i.observations.length,0),621);
      assert.ok(connected.every(i=>i.id.startsWith('kto_')));
      for(const id of ['kto_inbound','kto_outbound','kto_tourism_receipts','kto_tourism_expenditure']){
        const i=db.indicators.find(i=>i.id===id);
        assert.equal(await page.locator(`#macro-kpis [data-macro-id="${id}"] [data-value]`).getAttribute('data-value'),String(i.latest.value));
      }
      // Financial series remain in Macro, not the population observation cards.
      for(const i of connected.filter(i=>i.unit==='명'))assert.equal(await page.locator(`[data-observation-id="${i.id}"] [data-value]`).getAttribute('data-value'),String(i.latest.value));
      assert.equal(await page.locator('[data-observation-id="kto_tourism_receipts"]').count(),0);
      const score=await page.locator('#weather-score').textContent();
      await page.evaluate(()=>navigate('macro'));assert.equal(await page.locator('#chart-macro rect').count(),36);
      await page.locator('#macro-range').selectOption('12');assert.equal(await page.locator('#chart-macro rect').count(),12);
      const original=await page.locator('#macro-kpis [data-value]').evaluateAll(ns=>ns.map(n=>n.dataset.value));
      await page.route('**/data/macro.json?*',r=>r.fulfill({status:503}));await page.evaluate(()=>MacroMonitor.load());
      assert.deepEqual(await page.locator('#macro-kpis [data-value]').evaluateAll(ns=>ns.map(n=>n.dataset.value)),original);
      assert.match(await page.locator('#macro-status').textContent(),/이전 검증값 보존/);
      await page.unroute('**/data/macro.json?*');await page.evaluate(()=>MacroMonitor.load());
      await page.evaluate(()=>navigate('weather-simulator'));await assertSharedModel(page);
      await page.locator('.model-details summary').focus();await page.keyboard.press('Enter');assert.equal(await page.locator('.model-details').evaluate(e=>e.open),true);
      assert.equal(await page.locator('.review-bar').count(),0);assert.equal(await page.locator('script[src*="monthly.js"]').count(),0);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('PASS: current public Macro 9 connected/621 exact observations; four core cards; financial separation; chart/failure preservation; shared model/no manual controls; four widths; no Preview assets');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
