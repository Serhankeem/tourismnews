// Real held metadata is used only in browser route fixtures, never public DB writes.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),{createHash}=require('node:crypto');
const proof=require('../docs/newsroom-source-expansion-v04/comparison.json');
(async()=>{const browser=await chromium.launch({headless:true});try{for(const width of [390,1440]){
 const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010';await page.goto(base);await page.waitForFunction(()=>!newsLoading&&window.BriefingUI?.edition);
 const blocked=proof.new_articles.filter(a=>a.source==='Hotel News Resource');
 const manifest=await(await page.request.get(base+'/data/publication_visibility.json')).json();
 assert.equal(manifest.blocked_url_hashes.length,3);
 for(const row of blocked)assert.ok(manifest.blocked_url_hashes.includes(createHash('sha256').update(row.url).digest('hex')));
 for(const file of ['news','newsroom','briefing']){
  const data=await(await page.request.get(base+'/data/'+file+'.json')).json();
  for(const row of data.articles||data.items)assert.ok(!blocked.some(b=>b.url===row.url));
 }
 const db=await(await page.request.get(base+'/data/newsroom.json')).json();assert.equal(db.count,47);
 const allowed=db.articles.find(a=>a.source==='Hospitality Net');assert.ok(allowed?.keywords.length);
 await page.route('**/data/newsroom.json?*',r=>r.fulfill({status:404}));await page.evaluate(()=>loadLiveNews());
 assert.ok(await page.evaluate(urls=>NEWS.every(n=>!urls.includes(n.url)),blocked.map(a=>a.url)));
 const originalHistory=await(await page.request.get(base+'/data/briefing_archive.json')).text();
 const current=await(await page.request.get(base+'/data/briefing.json')).json();
 const fixture={...current,briefing_date:'2026-11-03',items:[blocked[0],allowed],status:'candidates_ready'};
 const history={schema_version:1,mode:'live_rss',briefings:[fixture]};
 await page.route('**/data/briefing.json?*',r=>r.fulfill({json:fixture}));await page.route('**/data/briefing_archive.json?*',r=>r.fulfill({json:history}));
 await page.evaluate(()=>navigate('briefing'));await page.evaluate(()=>BriefingUI.load());
 assert.equal(await page.locator('#briefing-news-list .news-item').count(),1);
 assert.ok(!(await page.evaluate(()=>BriefingUI.text())).includes(blocked[0].url));
 await page.locator('#briefing-edition').selectOption('2026-11-03');
 assert.equal(await page.locator('#briefing-news-list .news-item').count(),1);assert.match(await page.locator('#briefing-state').textContent(),/권리 검토 제외/);
 assert.equal(fixture.items.length,2);assert.equal(await(await page.request.get(base+'/data/briefing_archive.json')).text(),originalHistory);
 // A formerly allowed cached edition must be filtered even when data refresh fails.
 await page.route('**/data/publication_visibility.json?*',r=>r.fulfill({json:{blocked_url_hashes:[]}}));
 await page.evaluate(()=>BriefingUI.load());assert.equal(await page.locator('#briefing-news-list .news-item').count(),2);
 await page.route('**/data/publication_visibility.json?*',r=>r.fulfill({json:manifest}));
 await page.route('**/data/briefing.json?*',r=>r.fulfill({status:503}));await page.route('**/data/briefing_archive.json?*',r=>r.fulfill({status:503}));
 await page.evaluate(()=>BriefingUI.load());assert.equal(await page.locator('#briefing-news-list .news-item').count(),1);
 assert.ok(!(await page.evaluate(()=>BriefingUI.text())).includes(blocked[0].title));
 await page.route('**/data/publication_visibility.json?*',r=>r.fulfill({status:503}));await page.evaluate(()=>BriefingUI.load());
 assert.match(await page.locator('#briefing-state').textContent(),/권리 상태 확인 불가/);assert.equal(await page.locator('#briefing-news-list .news-item').count(),0);
 // Confirmed original history can recover after approval without rewriting it.
 await page.route('**/data/publication_visibility.json?*',r=>r.fulfill({json:{blocked_url_hashes:[]}}));
 await page.route('**/data/briefing.json?*',r=>r.fulfill({json:fixture}));await page.route('**/data/briefing_archive.json?*',r=>r.fulfill({json:history}));
 await page.evaluate(()=>BriefingUI.load());assert.equal(await page.locator('#briefing-news-list .news-item').count(),2);
 assert.deepEqual(errors,[]);await page.close();
}console.log('PASS visibility gate: real 3 held URLs absent from public views/fallback, preserved approved keywords, historical display/copy filtered, immutable file, cached-data failure closed, approved restoration, 390/1440px');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
