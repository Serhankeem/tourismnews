// Layout-only regression. All figures are read from existing public data.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),nav=require('./navigation-helper.cjs');
(async()=>{const browser=await chromium.launch({headless:true}),base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010';
const dir=process.env.HEADER_WEATHER_OUTPUT||'/tmp/currentourism-header-weather-v22';fs.mkdirSync(dir,{recursive:true});
try{for(const width of [320,390,768,1024,1280,1440]){
 const page=await browser.newPage({viewport:{width,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.waitForFunction(()=>!newsLoading&&MacroMonitor?.database&&document.querySelector('.site-header').hasAttribute('data-compact'));
 const menu=page.locator('#header-menu-toggle'),news=page.locator('#news-menu-toggle');
 assert.equal(await menu.isVisible(),width<768);assert.equal(await menu.getAttribute('aria-controls'),'primary-navigation');assert.equal(await menu.getAttribute('aria-expanded'),'false');
 const logo=await page.locator('.brand-home').boundingBox(),header=await page.locator('.site-header').boundingBox();
 assert.ok(logo.x<header.x+Math.max(50,(width-1280)/2+50));assert.ok(header.height<=82);
 if(width<768){
  assert.equal(await page.locator('#primary-navigation').isVisible(),false);
  await menu.focus();await page.keyboard.press('Space');assert.equal(await menu.getAttribute('aria-expanded'),'true');
  await news.focus();await page.keyboard.press('Enter');assert.equal(await news.getAttribute('aria-expanded'),'true');
  for(const a of await page.locator('#news-submenu a').all())assert.ok(await a.isVisible());
  await news.focus();await page.keyboard.press('ArrowDown');await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));assert.ok(await page.locator('#news-submenu a').first().evaluate(e=>e===document.activeElement));
  if(width===390){await page.screenshot({path:dir+'/menu-open-390.png'});}
  await page.keyboard.press('Escape');assert.equal(await news.getAttribute('aria-expanded'),'false');assert.equal(await menu.getAttribute('aria-expanded'),'true');
  await page.keyboard.press('Escape');assert.equal(await menu.getAttribute('aria-expanded'),'false');assert.ok(await menu.evaluate(e=>e===document.activeElement));
  await menu.click();await page.locator('.brand-home').click();assert.equal(await menu.getAttribute('aria-expanded'),'false');
  await menu.click();await page.mouse.click(width-10,500);assert.equal(await menu.getAttribute('aria-expanded'),'false');
  await menu.focus();await page.keyboard.press('ArrowDown');assert.ok(await page.locator('[data-nav="weather"]').evaluate(e=>e===document.activeElement));
  await page.keyboard.press('Tab');assert.ok(await news.evaluate(e=>e===document.activeElement));
  await page.keyboard.press('Escape');
  if(width===390)await page.screenshot({path:dir+'/menu-closed-390.png'});
 }else{
  const boxes=await page.locator('.primary-navigation>a,.news-menu-toggle').evaluateAll(ns=>ns.map(n=>n.getBoundingClientRect().toJSON()));
  assert.ok(boxes.every(b=>b.y===boxes[0].y&&b.x>logo.x+logo.width&&b.right<=width));assert.ok(logo.y+logo.height>boxes[0].y&&logo.y<boxes[0].bottom);
  await news.focus();await page.keyboard.press('Space');assert.equal(await news.getAttribute('aria-expanded'),'true');await page.keyboard.press('Tab');assert.ok(await page.locator('#news-submenu a').first().evaluate(e=>e===document.activeElement));await page.keyboard.press('Escape');assert.equal(await news.getAttribute('aria-expanded'),'false');
  if([1024,1440].includes(width))await page.screenshot({path:`${dir}/header-${width}.png`,clip:{x:0,y:0,width,height:180}});
 }
 for(const route of ['news','briefing','research','macro','about','weather']){
  await nav(page,route);assert.equal(await page.locator('#page-'+route).isVisible(),true);assert.equal(await menu.getAttribute('aria-expanded'),'false');assert.equal(await news.getAttribute('aria-expanded'),'false');
 }
 await nav(page,'news');await nav(page,'research');await page.goBack();assert.ok(await page.locator('#page-news').isVisible());await page.goForward();assert.ok(await page.locator('#page-research').isVisible());
 await page.goto(base+'/#weather');await page.waitForFunction(()=>MacroMonitor?.database&&document.querySelector('#market-demand-chart svg'));
 assert.equal(await page.evaluate(()=>scrollY),0);
 const sequence=await page.locator('#page-weather>section').evaluateAll(ns=>ns.map(n=>n.className));assert.deepEqual(sequence,['scenario-section','market-observation-section']);
 const scenario=await page.locator('.scenario-section').boundingBox(),observation=await page.locator('.market-observation-section').boundingBox();
 assert.ok(scenario.y>=header.height);assert.ok(scenario.y+scenario.height<=observation.y);assert.ok(scenario.y<500);
 const original=await page.locator('#weather-score').textContent();await page.locator('#s-arrivals').focus();await page.keyboard.press('ArrowRight');
 assert.notEqual(await page.locator('#weather-score').textContent(),original);assert.equal(await page.locator('#home-weather-score').textContent(),await page.locator('#weather-score').textContent());
 await page.locator('#reset-weather').click();assert.equal(await page.locator('#weather-score').textContent(),original);
 await page.locator('.brand-home').click();
 assert.deepEqual(await page.locator('.market-home-card').evaluate(n=>[...n.children].map(c=>c.id||c.className)),['weather-panel scenario-preview','home-market-observation']);
 assert.match(await page.locator('.scenario-preview').textContent(),/시뮬레이션 · 실제 관광시장 종합지수 아님/);
 await page.locator('.scenario-preview [data-goto="weather"]').click();assert.equal(await page.evaluate(()=>scrollY),0);
 assert.ok(await page.locator('#market-demand-chart svg').count());assert.ok(await page.locator('#market-country-cards .market-observation-card').count());
 if([390,1440].includes(width)){
  await page.screenshot({path:`${dir}/weather-${width}.png`,fullPage:true});
  await page.locator('.brand-home').click();await page.screenshot({path:`${dir}/home-${width}.png`,fullPage:true});
 }
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);await page.close();
}
// At the same viewport, increased actual text size must trigger compact mode.
const page=await browser.newPage({viewport:{width:768,height:1000}});await page.goto(base);await page.waitForFunction(()=>!newsLoading);
assert.equal(await page.locator('#header-menu-toggle').isVisible(),false);
await page.addStyleTag({content:'.primary-navigation>a,.news-menu-toggle{font-size:30px!important}'});
await page.waitForFunction(()=>document.querySelector('.site-header').dataset.compact==='true');assert.ok(await page.locator('#header-menu-toggle').isVisible());
await page.setViewportSize({width:1440,height:1000});await page.waitForFunction(()=>document.querySelector('.site-header').dataset.compact==='false');
assert.equal(await page.locator('#header-menu-toggle').getAttribute('aria-expanded'),'false');await page.close();
console.log('PASS header/weather v2.2: 6 widths, measured fit/text scaling, compact menu/native keys/ARIA/external/Escape, all routes/history, DOM order, scenario first on hash/home entry, sliders/reset/shared values, retained real charts/country cards');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
