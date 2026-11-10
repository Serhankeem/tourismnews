const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{const browser=await chromium.launch();const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8024',out=process.env.KOREAN_FIRST_OUTPUT||'/tmp/korean-first';fs.mkdirSync(out,{recursive:true});
try{for(const width of [320,390,768,1440]){
 const page=await browser.newPage({viewport:{width,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.waitForFunction(()=>!newsLoading&&window.ResearchLibrary?.database.reports.length&&window.BriefingUI?.edition);
 const news=await(await page.request.get(base+'/data/newsroom.json')).json(),reports=await(await page.request.get(base+'/data/reports.json')).json(),registry=await(await page.request.get(base+'/assets/content-localization.json')).json();
 for(const r of news.articles)assert.deepEqual(Object.keys(r).sort(),['category','keywords','published_at','source','title','url']);
 for(const r of reports.reports)assert.deepEqual(Object.keys(r).sort(),['access_type','category','keywords','published_at','publisher','report_type','title','url']);
 await page.evaluate(()=>navigate('news'));
 assert.equal(await page.locator('#news-order').inputValue(),'domestic');
 const expected=await page.evaluate(rows=>[...rows].sort((a,b)=>ContentLocale.compareNews(a,b,'domestic')),news.articles);
 assert.deepEqual(await page.locator('#news-items .news-title').allTextContents(),expected.slice(0,10).map(r=>r.title));
 for(const region of ['domestic','foreign']){
  await page.locator('[data-news-origin="'+region+'"]').click();
  const matches=await page.evaluate(({rows,region})=>rows.filter(r=>ContentLocale.newsRegion(r)===region),{rows:news.articles,region});
  assert.match(await page.locator('#news-page-total').textContent(),new RegExp('총 '+matches.length+'건'));
  await page.locator('#news-search').fill(matches[0].title);assert.equal(await page.locator('#news-items .news-title').count(),1);
  await page.locator('#news-search').fill('');
 }
 await page.locator('[data-news-origin="all"]').click();await page.locator('#news-order').selectOption('latest');
 assert.deepEqual(await page.locator('#news-items .news-title').allTextContents(),news.articles.slice(0,10).map(r=>r.title));
 await page.locator('#news-page-size').selectOption('20');assert.equal(await page.locator('#news-items .news-item').count(),Math.min(20,news.count));
 await page.locator('#news-page-buttons button[aria-label="다음 페이지"]').click();assert.ok(await page.locator('#news-page-total').textContent().then(t=>t.includes('21–')));
 await page.locator('[data-news-origin="domestic"]').click();assert.match(await page.locator('#news-page-total').textContent(),/1–/);
 await page.evaluate(()=>navigate('research'));
 for(const region of ['국내','해외']){
  await page.locator('[data-research-region="'+region+'"]').click();assert.equal(await page.locator('#research-region').inputValue(),region);
  const n=reports.reports.filter(r=>reports.publishers[r.publisher]?.region===region).length;
  assert.match(await page.locator('#research-result-count').textContent(),new RegExp('검색 결과 '+n+'건'));
 }
 await page.locator('#research-reset').click();
 for(const h of registry.headings){
  await page.locator('#research-search').fill(h.original_title);assert.equal(await page.locator('#research-results h3').count(),1);
  assert.equal(await page.locator('#research-results h3 a').textContent(),h.ko_title);
  assert.equal(await page.locator('.original-title').textContent(),'원제: '+h.original_title);
  await page.locator('#research-search').fill(h.ko_title);assert.equal(await page.locator('#research-results h3').count(),1);
  assert.match(await page.locator('.locale-badge').textContent(),/한국어 안내 표제/);
  assert.equal(await page.locator('#research-results h3 a').getAttribute('href'),h.url);
 }
 await page.locator('#research-reset').click();
 if([390,768,1440].includes(width)){
  await page.evaluate(()=>navigate('news'));await page.locator('[data-news-origin="all"]').click();await page.locator('#news-order').selectOption('domestic');await page.screenshot({path:out+'/news-domestic-'+width+'.png',animations:'disabled'});
  await page.locator('[data-news-origin="foreign"]').click();await page.screenshot({path:out+'/news-foreign-'+width+'.png',animations:'disabled'});
  await page.evaluate(()=>navigate('research'));await page.locator('[data-research-region="해외"]').click();await page.locator('#research-search').fill('OECD 관광 보고서');await page.screenshot({path:out+'/research-ko-'+width+'.png',animations:'disabled'});await page.locator('#research-reset').click();
 }
 // Withdraw and failed approval refresh must drop display text, not raw originals.
 if(registry.headings.length){
 const h=registry.headings[0];await page.locator('#research-search').fill(h.original_title);
 await page.route('**/assets/content-localization.json?*',r=>r.fulfill({json:{...registry,headings:[]}}));await page.evaluate(()=>ContentLocale.refresh());
 assert.equal(await page.locator('#research-results h3 a').textContent(),h.original_title);assert.equal(await page.locator('.locale-badge').count(),0);
 await page.route('**/assets/content-localization.json?*',r=>r.fulfill({status:503}));await page.evaluate(()=>ResearchLibrary.load());assert.equal(await page.locator('#research-results h3 a').textContent(),h.original_title);
 await page.unroute('**/assets/content-localization.json?*');await page.evaluate(()=>ResearchLibrary.load());
 assert.equal(await page.locator('#research-results h3 a').textContent(),h.ko_title);
 }
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);await page.close();
}
// Synthetic caption only in this isolated browser, using an existing allowed original.
const page=await browser.newPage();await page.goto(base);await page.waitForFunction(()=>!newsLoading&&window.BriefingUI?.edition);
const gov=await page.evaluate(()=>NEWS.find(n=>n.source==='GOV.UK · tourism'));
// Isolate the existing allowed original so newer real news cannot displace this
// caption fixture from the three-item homepage. The public DB is unchanged.
await page.evaluate(r=>{const selected=NEWS.filter(n=>n.url===r.url);NEWS.splice(0,NEWS.length,...selected);},gov);
await page.evaluate(r=>{window.originalLocale=ContentLocale;const h={kind:'news',url:r.url,publisher:r.source,published_at:r.published_at,original_title:r.title,ko_title:'visitor · 격리 검증용 안내',mode:'independent_factual_label',status:'approved',rights_status:'approved',accuracy_status:'approved',evidence_url:'https://example.org/test-only',note:'TEST ONLY',attribution:'TEST ONLY',preserved_tokens:['visitor']};window.ContentLocale=ContentLocale.create({headings:[h]});state.newsOrigin='all';state.newsOrder='latest';state.query='격리 검증용';renderNews();},gov);
assert.equal(await page.locator('#news-items .news-title').textContent(),'visitor · 격리 검증용 안내');
await page.evaluate(()=>navigate('news'));await page.locator('#news-items [data-detail]').click();assert.equal(await page.locator('#modal-title').textContent(),'visitor · 격리 검증용 안내');await page.locator('#modal-close').click();
assert.ok(await page.locator('#overview-news').textContent().then(t=>t.includes('visitor · 격리 검증용 안내')));
const current=await(await page.request.get(base+'/data/briefing.json')).json();const history=await(await page.request.get(base+'/data/briefing_archive.json')).json();
await page.route('**/data/briefing.json?*',r=>r.fulfill({json:{...current,items:[gov]}}));await page.route('**/data/briefing_archive.json?*',r=>r.fulfill({json:{...history,briefings:[{...current,briefing_date:'2026-10-01',items:[gov]}]}}));
await page.evaluate(()=>BriefingUI.load());await page.evaluate(()=>navigate('briefing'));assert.match(await page.locator('#briefing-news-list').textContent(),/격리 검증용/);
await page.locator('#briefing-edition').selectOption('2026-10-01');assert.ok(!(await page.locator('#briefing-news-list').textContent()).includes('격리 검증용'));assert.ok((await page.evaluate(()=>BriefingUI.text())).includes(gov.title));assert.ok(!(await page.evaluate(()=>BriefingUI.text())).includes('격리 검증용'));
await page.close();console.log('PASS Korean-first: four widths, verified geography independent of language, domestic/latest ordering, combined search/pagination, bilingual factual labels and original bindings, approval withdrawal/failure, six/eight fields, consistent live displays, unchanged confirmed archive');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
