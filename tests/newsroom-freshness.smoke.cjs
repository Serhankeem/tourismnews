// Real public snapshot first; edge/status fixtures are browser-only.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true});try{
const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010';
for(const width of [320,390,1440]){
 const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.waitForFunction(()=>!newsLoading&&window.BriefingUI?.edition);
 const snapshot=await(await page.request.get(base+'/data/newsroom.json')).json();
 const chronological=[...snapshot.articles].sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at)||(a.url<b.url?-1:a.url>b.url?1:0));
 assert.deepEqual(snapshot.articles,chronological);assert.match(chronological[0].published_at,/2026-11-02/);
 assert.deepEqual(await page.locator('#overview-news h3 a').allTextContents(),chronological.slice(0,3).map(a=>a.title));
 // Unordered six-field payload must still sort in the browser; no editorial fields.
 await page.route('**/data/newsroom.json?*',r=>r.fulfill({json:{...snapshot,articles:[...snapshot.articles].reverse()}}));
 await page.evaluate(()=>loadLiveNews());await page.evaluate(()=>navigate('news'));
 assert.equal(await page.locator('#news-items .news-title').first().textContent(),chronological[0].title);
 assert.deepEqual(await page.evaluate(()=>NEWS.map(a=>a.published_at)),chronological.map(a=>a.published_at));
 await page.evaluate(()=>navigate('briefing'));
 assert.match(await page.locator('#briefing-state').textContent(),/주요 뉴스 후보/);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.match(await page.locator('#briefing-state').textContent(),/일부 출처 수집 실패/);
 const current=await(await page.request.get(base+'/data/briefing.json')).json();
 for(const [status,expected] of [['no_recent_articles',/신규 뉴스 없음/],['no_eligible_recent_articles',/선정 기준 미충족/]]){
  await page.route('**/data/briefing.json?*',r=>r.fulfill({json:{...current,status,generated_at:new Date().toISOString(),items:[]}}));
  await page.evaluate(()=>BriefingUI.load());assert.match(await page.locator('#briefing-state').textContent(),expected);
 }
 await page.route('**/data/health.json?*',r=>r.fulfill({json:{status:'ok',briefing:{status:'failed'}}}));
 await page.evaluate(()=>BriefingUI.load());assert.match(await page.locator('#briefing-state').textContent(),/브리핑 생성\/갱신 실패/);
 await page.route('**/data/briefing.json?*',r=>r.fulfill({status:503}));await page.evaluate(()=>BriefingUI.load());
 assert.match(await page.locator('#briefing-state').textContent(),/이전 기록 유지/);
 // Same instant with different zones ties by URL; date-only stays unmodified.
 const sorted=await page.evaluate(()=>[{url:'b',published_at:'2026-11-02T01:00:00+09:00'},{url:'a',published_at:'2026-11-01T16:00:00Z'},{url:'c',published_at:'2026-11-02'}].sort(compareNewsPublication).map(a=>a.url));
 assert.deepEqual(sorted,['a','b','c']);assert.deepEqual(errors,[]);await page.close();
}
console.log('PASS: real Nov 2 first, home three, reversed six-field browser payload, exact original dates, time-zone ties, partial coverage and three empty/failure reasons at PC/mobile widths');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
