// Real DB, no data writes. Tests navigation and filter disclosure behavior.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),clickNav=require('./navigation-helper.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true}),base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010',dir=process.env.NAV_OUTPUT||'/tmp/currentourism-nav21';fs.mkdirSync(dir,{recursive:true});
 try{
  for(const width of [320,390,768,1024,1440]){
   const page=await browser.newPage({viewport:{width,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base);await page.waitForFunction(()=>!newsLoading&&ResearchLibrary?.database.reports.length>0);
   const top=page.locator('.primary-navigation>a,.primary-navigation>.news-nav>button'),toggle=page.locator('#news-menu-toggle');
   assert.deepEqual((await top.allTextContents()).map(t=>t.trim()),['오늘의 관광 날씨는?','뉴스 ▾','관광지표','소개']);const compact=await page.locator('#header-menu-toggle').isVisible();
   if(compact){assert.equal(await page.locator('.primary-navigation').isVisible(),false);await page.locator('#header-menu-toggle').click();}
   for(const n of await top.all()){assert.ok(await n.isVisible());const r=await n.boundingBox();assert.ok(r.height>=44&&r.x>=0&&r.x+r.width<=width);}
   assert.equal(await toggle.getAttribute('aria-controls'),'news-submenu');assert.equal(await toggle.getAttribute('aria-expanded'),'false');
   if([390,1440].includes(width))await page.screenshot({path:`${dir}/navigation-closed-${width}.png`});
   await toggle.focus();await page.keyboard.press('Space');assert.equal(await toggle.getAttribute('aria-expanded'),'true');
   assert.deepEqual((await page.locator('#news-submenu a').allTextContents()).map(s=>s.trim()),['뉴스','데일리 브리핑','리서치']);
   if([390,1440].includes(width))await page.screenshot({path:`${dir}/navigation-open-${width}.png`});
   const box=await page.locator('#news-submenu').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width);for(const link of await page.locator('#news-submenu a').all())assert.ok(await link.evaluate(n=>{const r=n.getBoundingClientRect();return n.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}),'All dropdown links must be above content and unclipped');
   await page.keyboard.press('Tab');assert.equal(await page.locator('#news-submenu a').first().evaluate(e=>e===document.activeElement),true);await page.keyboard.press('Escape');assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.ok(await toggle.evaluate(e=>e===document.activeElement));
   await page.keyboard.press('Enter');await page.locator('.brand-home').click();assert.equal(await toggle.getAttribute('aria-expanded'),'false');
   for(const route of ['weather','news','briefing','research','macro','about']){
    await clickNav(page,route);assert.equal(await page.locator('#page-'+route).isVisible(),true);assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.equal(await page.locator(`[data-nav="${route}"]`).getAttribute('aria-current'),'page');
    if(['news','briefing','research'].includes(route))assert.ok(await toggle.evaluate(e=>e.classList.contains('active')));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   }
   await clickNav(page,'news');await clickNav(page,'research');await page.goBack();assert.ok(await page.locator('#page-news').isVisible());await page.goForward();assert.ok(await page.locator('#page-research').isVisible());
   await page.goto(base+'/#briefing');await page.waitForFunction(()=>state.page==='briefing');assert.ok(await toggle.evaluate(e=>e.classList.contains('active')));
   await page.goto(base+'/#research');await page.waitForFunction(()=>ResearchLibrary?.database.reports.length>0);
   const details=page.locator('#research-filter-details');assert.equal(await details.evaluate(e=>e.open),width>768);
   if(width<=768)await details.locator('summary').click();
   const r=await page.evaluate(()=>ResearchLibrary.database.reports.find(r=>r.region==='국내')||ResearchLibrary.database.reports[0]);
   await page.locator('#research-publisher').selectOption(r.publisher);await page.locator('#research-type').selectOption(r.report_type);await page.locator('#research-category').selectOption(r.category);
   const expected=await page.evaluate(()=>{const s=ResearchLibrary.state;return ResearchLibrary.database.reports.filter(r=>r.publisher===s.publisher&&r.report_type===s.type&&r.category===s.category).length;});assert.ok(expected>0);assert.match(await page.locator('#research-result-count').textContent(),new RegExp(`검색 결과 ${expected}건`));assert.match(await page.locator('#research-filter-count').textContent(),/3개/);
   if(width<=768){await details.locator('summary').click();assert.equal(await details.evaluate(e=>e.open),false);assert.equal(await page.locator('#research-publisher').inputValue(),r.publisher);await details.locator('summary').focus();await page.keyboard.press('Enter');assert.equal(await details.evaluate(e=>e.open),true);}
   await page.locator('#research-reset').click();assert.equal(await page.locator('#research-publisher').inputValue(),'');assert.match(await page.locator('#research-filter-count').textContent(),/0개/);
   await page.locator('#research-search').fill('관광');assert.match(await page.locator('#research-filter-count').textContent(),/1개/);await page.locator('#research-reset').click();
   await page.locator('#research-page-size').selectOption('20');assert.equal(await page.locator('#research-results .research-card').count(),20);
   await page.locator('#research-page-buttons [aria-label="다음 페이지"]').click();assert.equal(await page.evaluate(()=>ResearchLibrary.state.page),2);
   await page.locator('#research-reset').click();assert.equal(await page.evaluate(()=>ResearchLibrary.state.page),1);assert.equal(await page.locator('#research-page-size').inputValue(),'20');
   if(width<=768&&await details.evaluate(e=>e.open))await details.locator('summary').click();
   // A compact statistics disclosure keeps results near the search panel.
   if(await page.locator('#research-source-overview').evaluate(e=>e.open))await page.locator('#research-source-overview>summary').click();
   await page.evaluate(()=>scrollTo(0,0));
   if([390,1440].includes(width))await page.screenshot({path:`${dir}/research-${width}.png`});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   const style=await page.locator('#research-search').evaluate(e=>({bg:getComputedStyle(e).backgroundColor,size:parseFloat(getComputedStyle(e).fontSize)}));assert.equal(style.bg,'rgb(255, 255, 255)');assert.ok(style.size>=16);
   await page.locator('#research-source-overview>summary').click();assert.equal(await page.locator('#research-source-counts button').count(),Object.keys(await page.evaluate(()=>ResearchLibrary.database.publishers)).length);
   await page.locator('.site-footer [data-goto="sources"]').click();const target=await page.locator('#data-sources').boundingBox(),header=await page.locator('.site-header').boundingBox();assert.ok(target.y>=header.height,'Sticky header must not obscure anchor');
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS nav/research v2.1: 4 top-level menus with content-fit compact disclosure, disclosure/keyboard/history/hash, 5 widths, compound filters/counts/persistence/reset/pagination, stats/anchors; no JS errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
