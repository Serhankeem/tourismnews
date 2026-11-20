const assertSharedModel=require('./model-ui-helper.cjs');
// SYNTHETIC release only; real r2 is never loaded or publicly staged.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.MONTHLY_TEST_URL||'http://127.0.0.1:8060';
const empty=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8061';
const output=process.env.MONTHLY_TEST_OUTPUT||'/tmp/currentourism-step19';
(async()=>{fs.mkdirSync(output,{recursive:true,mode:0o700});const browser=await chromium.launch({headless:true});
try{
 for(const width of [320,390,768,1440]){
  const page=await browser.newPage({viewport:{width,height:1100}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto(base+'/#weather');await page.waitForSelector('.monthly-title');
  assert.equal(await page.locator('.monthly-title').textContent(),'합성 월간 원고');
  assert.match(await page.locator('.monthly-notice').textContent(),/종합 판정 보류/);
  assert.equal(await page.locator('.monthly-metrics section').count(),2);
  assert.equal(await page.locator('#monthly-article>section').count(),5);
  assert.equal(await page.locator('#monthly-article a[href^="https:"]').count(),2);
  assert.equal(await page.locator('#weather-legacy').isVisible(),false);
  await page.locator('#monthly-edition').focus();await page.keyboard.press('ArrowDown');
  await page.locator('[data-weather-mode="simulator"]').focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('#weather-legacy').isVisible(),true);
  assert.equal(await page.locator('#weather-monthly').isVisible(),false);
  await assertSharedModel(page);
  await page.goBack();assert.equal(await page.locator('#weather-monthly').isVisible(),true);
  await page.goForward();assert.equal(await page.locator('#weather-legacy').isVisible(),true);
  await page.locator('[data-weather-mode="monthly"]').click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.ok(requests.every(u=>!/(diagnostic-private|manuscript|editorial-approval|authority|operator-trust)/.test(u)));
  const axePath=process.env.AXE_PATH;
  if(axePath){await page.addScriptTag({path:axePath});const result=await page.evaluate(()=>axe.run(document.querySelector('#page-weather'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));assert.deepEqual(result.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),[]);}
  if([390,1440].includes(width))await page.screenshot({path:output+'/synthetic-monthly-'+width+'.png',fullPage:true});
  assert.deepEqual(errors,[]);await page.close();
 }
 const page=await browser.newPage();
 await page.goto(empty+'/#weather');await page.waitForFunction(()=>document.querySelector('#monthly-state').textContent==='아직 발행된 월간 진단 없음');
 assert.equal(await page.locator('#monthly-article').textContent(),'');assert.equal(await page.locator('#monthly-picker').isVisible(),false);
 // Each malformed/expired response must leave an empty reader, not a fallback article.
 const pair=await Promise.all(['index','archive'].map(async name=>await (await page.request.get(base+'/data/market_weather_'+name+'.json')).json()));
 const cases=[
  ([i,a])=>i.latest='missing',
  ([i,a])=>i.entries[0].content_sha256='0'.repeat(64),
  ([i,a])=>i.entries[0].not_after='2020-01-01T00:00:00+09:00',
  ([i,a])=>a.contents[i.latest].publication_approved=true,
  ([i,a])=>a.contents[i.latest].metrics.ecos_fx={value:1},
  ([i,a])=>a.contents[i.latest].article.sections[0].markdown='<img src=x onerror=alert(1)>',
 ];
 for(const change of cases){const data=structuredClone(pair);change(data);
  await page.route('**/data/market_weather_index.json',r=>r.fulfill({json:data[0]}));
  await page.route('**/data/market_weather_archive.json',r=>r.fulfill({json:data[1]}));
  await page.goto(empty+'/#weather');await page.waitForTimeout(100);
  assert.equal(await page.locator('.monthly-title').count(),0);assert.equal(await page.locator('#monthly-article').textContent(),'');
  await page.unrouteAll();
 }
 await page.close();console.log('PASS monthly: Gate-generated synthetic pair; two metrics/five prose sections/source links; four widths; keyboard/history/model; no private requests; absent/invalid/expired/extra-field/unapproved-axis/tampered-content blocked; axe WCAG 2 A/AA+2.1 AA if AXE_PATH set');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
