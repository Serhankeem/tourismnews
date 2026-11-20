const assertSharedModel=require('./model-ui-helper.cjs');
// Approved public snapshot only. No actual monthly manuscript or release.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
const nav=require('./navigation-helper.cjs');
const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8065';
const out=process.env.NAV195_OUTPUT||'/tmp/weather-navigation-195';
async function scan(page){if(!process.env.AXE_PATH)return;
 await page.addScriptTag({path:process.env.AXE_PATH});const violations=await page.evaluate(async()=>{
  const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)}));
 });assert.deepEqual(violations,[]);
}
(async()=>{fs.mkdirSync(out,{recursive:true,mode:0o700});const browser=await chromium.launch({headless:true});
try{for(const width of [320,390,768,1024,1440]){
 const page=await browser.newPage({viewport:{width,height:1100},hasTouch:width<=768,isMobile:width<=390,reducedMotion:'reduce'}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/#weather');
 await page.waitForFunction(()=>MacroMonitor?.database&&document.querySelector('.site-header').hasAttribute('data-compact'));
 const menu=page.locator('#header-menu-toggle'),weather=page.locator('#weather-menu-toggle'),news=page.locator('#news-menu-toggle');
 const compact=await menu.isVisible();
 if(compact){await menu.focus();await page.keyboard.press('Enter');}
 assert.match(await weather.textContent(),/한국 관광의 날씨는\?/);
 assert.deepEqual(await page.locator('#weather-submenu a').allTextContents(),['월간 진단','관광시장 모델 · 공식 관측','Macro Monitor 상세']);
 await weather.focus();await page.keyboard.press('Space');assert.equal(await weather.getAttribute('aria-expanded'),'true');
 await scan(page);
 if([390,1440].includes(width))await page.screenshot({path:out+'/dropdown-'+width+'.png'});
 await page.keyboard.press('Tab');assert.equal(await page.locator('#weather-submenu a').first().evaluate(n=>n===document.activeElement),true);
 await page.keyboard.press('Escape');assert.equal(await weather.getAttribute('aria-expanded'),'false');assert.ok(await weather.evaluate(n=>n===document.activeElement));
 await weather.focus();await page.keyboard.press('ArrowDown');assert.equal(await weather.getAttribute('aria-expanded'),'true');
 for(let n=0;n<3;n++)await page.keyboard.press('Tab');
 assert.equal(await weather.getAttribute('aria-expanded'),'false');assert.ok(await news.evaluate(n=>n===document.activeElement));
 await weather.focus();await page.keyboard.press('Enter');assert.equal(await weather.getAttribute('aria-expanded'),'true');
 if(compact)await news.tap();else await news.click();assert.equal(await weather.getAttribute('aria-expanded'),'false');assert.equal(await news.getAttribute('aria-expanded'),'true');
 await scan(page);
 await page.mouse.click(width-8,Math.min(900,(await page.locator('.site-header').boundingBox()).height+650));assert.equal(await news.getAttribute('aria-expanded'),'false');
 if(compact)assert.equal(await menu.getAttribute('aria-expanded'),'false');
 for(const route of ['weather','weather-simulator','macro']){
  await nav(page,route);const screen=page.locator(route==='macro'?'#page-macro':'#page-weather');
  assert.equal(await screen.isVisible(),true);
  assert.equal(await screen.locator('.weather-modes a[aria-current="page"]').getAttribute('href'),'#'+route);
  assert.equal(await page.locator('#weather-submenu a[aria-current="page"]').getAttribute('href'),'#'+route);
  assert.equal(await weather.getAttribute('aria-current'),'true');
  assert.equal(await page.locator('#weather-monthly').isVisible(),route==='weather');
  assert.equal(await page.locator('#weather-legacy').isVisible(),route==='weather-simulator');
  assert.equal(await screen.locator('h1').textContent(),route==='weather'?'월간 진단':route==='weather-simulator'?'관광시장 모델 · 공식 관측':'Macro Monitor');
  if(route==='weather'){const response=await page.request.get(base+'/data/market_weather_index.json');if(response.ok())await page.locator('.monthly-title').waitFor();else assert.equal(await page.locator('#monthly-state').textContent(),'아직 발행된 월간 진단 없음');}
  if(route==='weather-simulator'){
   await assertSharedModel(page);
  }
  if(route==='macro'){
   const db=await page.evaluate(()=>MacroMonitor.database);assert.equal(db.indicators.filter(i=>i.connected).reduce((n,i)=>n+i.observations.length,0),621);
   assert.equal(await page.locator('#page-macro').count(),1);assert.ok(await page.locator('#chart-macro svg').count());
   await nav(page,'weather');if(compact)await menu.click();await weather.click();await page.locator('#weather-submenu a[href="#macro"]').click();assert.equal(await page.locator('#page-macro').isVisible(),true);
  }
  await scan(page);
  if([390,1440].includes(width))await page.screenshot({path:out+'/'+route+'-'+width+'.png',fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.reload();assert.equal(await screen.isVisible(),true);
 }
 await page.goto(base+'/#weather-simulator');assert.equal(await page.locator('#weather-legacy').isVisible(),true);
 await page.locator('#page-weather .weather-modes a[href="#weather"]').click();assert.equal(await page.locator('#weather-monthly').isVisible(),true);
 await page.goBack();assert.equal(await page.locator('#weather-legacy').isVisible(),true);await page.goForward();assert.equal(await page.locator('#weather-monthly').isVisible(),true);
 for(const route of ['weather','weather-simulator','macro']){await page.goto(base+'/#'+route);await page.reload();assert.equal(await page.locator('#'+(route==='macro'?'page-macro':route==='weather'?'weather-monthly':'weather-legacy')).isVisible(),true);}
 await nav(page,'news');assert.equal(await weather.getAttribute('aria-current'),null);assert.equal(await news.getAttribute('aria-current'),'true');
 assert.deepEqual(errors,[]);await page.close();
}console.log('PASS Step 19.5: five widths; both disclosures/native Enter+Space/ArrowDown/Escape/Tab/outside click/mobile; all weather routes/direct/reload/history/active states; monthly reader; 621 Macro; shared model/no manual controls; WCAG 2 A/AA+2.1 AA if AXE_PATH supplied');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
