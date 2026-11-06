/* Live snapshot for screenshots. Boundary rates are synthetic browser memory only. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8035',out=process.env.PERCENTAGE_SHOTS||'/tmp/percentage-ui';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true});const errors=[];
 try{
  const ctx=await browser.newContext();const original=await(await ctx.request.get(base+'/data/macro.json')).json();
  for(const width of [320,390,768,1440]){
   const page=await browser.newPage({viewport:{width,height:1000}});page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base+'/#macro');await page.waitForFunction(()=>window.MacroMonitor?.database);await page.waitForTimeout(350);
   assert.deepEqual(await page.evaluate(()=>MacroMonitor.database),original,'Rendering must not mutate the live payload');
   assert.equal(await page.locator('#macro-kpis [data-value]').count(),2);assert.equal(await page.locator('.macro-unavailable .percentage-change').count(),0);
   if([390,1440].includes(width))await page.screenshot({path:`${out}/after-macro-${width}.png`,fullPage:true});
   await page.evaluate(()=>navigate('weather'));await page.waitForTimeout(350);
   const order=await page.locator('#market-country-cards [data-observation-id]').evaluateAll(ns=>ns.map(n=>n.dataset.observationId));
   assert.deepEqual(order,original.indicators.filter(i=>i.connected&&i.country).map(i=>i.id));
   if([390,1440].includes(width))await page.screenshot({path:`${out}/after-weather-${width}.png`,fullPage:true});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   const score=await page.locator('#weather-score').textContent();
   // Explicit UI fixtures; no raw count, JSON file, API or source permission changes.
   await page.evaluate(()=>{
    const db=MacroMonitor.database;const i=db.indicators.find(i=>i.id==='kto_inbound');
    Object.assign(i.latest.comparisons,{yoy_pct:21.1,mom_pct:-8.4,ytd_yoy_pct:-0});
    const countries=db.indicators.filter(i=>i.connected&&i.country);
    [21.1,' -8.40% ',-0,null,'<img src=x onerror=alert(1)>'].forEach((v,n)=>countries[n].latest.comparisons.yoy_pct=v);
    MacroMonitor.render();
   });
   for(const [id,state,color,text] of [[order[0],'positive','rgb(200, 67, 77)','21.10%'],[order[1],'negative','rgb(40, 100, 173)','8.40%'],[order[2],'neutral','rgb(113, 128, 150)','0.00%']]){
    const item=page.locator(`[data-observation-id="${id}"] dd .percentage-change`).first();
    assert.match(await item.getAttribute('class'),new RegExp('--'+state));assert.equal(await item.evaluate(n=>getComputedStyle(n).color),color);assert.match(await item.textContent(),new RegExp(text.replace('.','\\.')));
   }
   const missing=page.locator(`[data-observation-id="${order[3]}"] dd .percentage-change`).first();assert.equal(await missing.textContent(),'—');assert.match(await missing.getAttribute('class'),/--missing/);assert.equal(await page.locator('#market-country-cards img').count(),0);
   await page.evaluate(()=>navigate('macro'));await page.waitForTimeout(350);
   assert.equal(await page.locator('#macro-comparisons .percentage-change--positive').count(),1);
   assert.equal(await page.locator('#macro-comparisons .percentage-change--negative').count(),1);
   assert.equal(await page.locator('#macro-comparisons .percentage-change--neutral').count(),1);
   assert.equal(await page.locator('#home-macro-kpis [data-macro-id="kto_inbound"] .percentage-change--positive').count(),1);
   assert.ok(await page.locator('#data-observation .percentage-change--negative').count());
   assert.equal(await page.locator('#macro-kpis .value .percentage-change').count(),0);
   await page.locator('#chart-toggle-macro [data-chart="growth"]').click();
   const bars=await page.locator('#chart-macro rect').evaluateAll(ns=>ns.map(n=>({value:Number(n.dataset.value),color:getComputedStyle(n).fill,title:n.querySelector('title').textContent})));
   for(const b of bars){assert.equal(b.color,b.value>0?'rgb(200, 67, 77)':b.value<0?'rgb(40, 100, 173)':'rgb(113, 128, 150)');assert.ok(!b.title.includes('<span'));}
   await page.locator('#chart-toggle-macro [data-chart="count"]').click();
   assert.equal(await page.locator('#chart-macro [class^="percentage-bar"]').count(),0);
   assert.equal(await page.locator('#weather-score').textContent(),score);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   assert.equal(await page.locator('.percentage-change').evaluateAll(ns=>ns.some(n=>n.getBoundingClientRect().width>n.parentElement.getBoundingClientRect().width+1)),false);
   await page.close();
  }
  assert.deepEqual(errors,[]);console.log('PASS percentage UI: signs/zero/missing/XSS, exact colors in all rate components, chart growth-only colors, real snapshot preservation, four widths and simulation unchanged');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
