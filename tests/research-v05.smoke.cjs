// Uses actual expanded public metadata only. No synthetic records or DB writes.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),clickNav=require('./navigation-helper.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true}),base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010',dir=process.env.RESEARCH_V05_SCREENSHOTS||'/tmp/currentourism-research-v05';fs.mkdirSync(dir,{recursive:true});
 try{
  for(const width of [390,1440]){
   const page=await browser.newPage({viewport:{width,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   const snapshot=await(await page.request.get(base+'/data/reports.json')).json();
   await page.goto(base+'/#research');await page.waitForFunction(()=>ResearchLibrary?.database.reports.length>0);
   assert.equal(Number(await page.locator('#research-count').textContent()),snapshot.count);
   const details=page.locator('#research-filter-details');if(!await details.evaluate(e=>e.open))await details.locator('summary').click();
   for(const publisher of ['OECD','한국교통연구원']){
    await page.locator('#research-publisher').selectOption(publisher);
    const actual=snapshot.reports.filter(r=>r.publisher===publisher);assert.ok(actual.length>0);
    assert.equal(await page.locator('#research-results .research-card').count(),actual.length);
    const titles=await page.locator('#research-results h3 a').evaluateAll(nodes=>nodes.map(n=>({title:n.textContent,url:n.href})));
    for(const row of titles)assert.ok(actual.some(r=>r.title===row.title&&r.url===row.url));
    if(publisher==='한국교통연구원')assert.match(await page.locator('#research-results').textContent(),/공공누리 제4유형.*저자|저자:.*공공누리 제4유형/s);
   }
   await page.locator('#research-reset').click();
   for(const category of ['MICE·비즈니스 이벤트','항공·교통산업','숙박·호텔산업']){
    await page.locator('#research-category').selectOption(category);const actual=snapshot.reports.filter(r=>r.category===category);assert.ok(actual.length>0);assert.equal(await page.locator('#research-results .research-card').count(),Math.min(10,actual.length));
    if(category==='MICE·비즈니스 이벤트')assert.match(await page.locator('#research-results').textContent(),/발간연도 2024년 · 월·일 미표기/);
   }
   await page.locator('#research-category').selectOption('항공·교통산업');
   if(width===390)await details.locator('summary').click();
   if(await page.locator('#research-source-overview').evaluate(e=>e.open))await page.locator('#research-source-overview>summary').click();
   await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:`${dir}/aviation-${width}.png`});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.equal(await page.locator('#research-results img').count(),0);
   await page.locator('#research-reset').click();await page.screenshot({path:`${dir}/overview-${width}.png`});
   await clickNav(page,'weather');assert.ok(await page.locator('#market-demand-chart svg').isVisible());
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS Research v0.5: real new publishers, MICE/aviation/hotel filters, original links/dates/attribution, no images, desktop/mobile and Weather preservation');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
