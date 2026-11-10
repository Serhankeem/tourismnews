const clickNav=require('./navigation-helper.cjs');
// Optional browser regression: requires Playwright + Chromium and a local server.
// TOURISM_TEST_URL=http://127.0.0.1:8001 node tests/newsroom.smoke.cjs
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({headless:true});
 try {
  const page = await browser.newPage();
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const base=process.env.TOURISM_TEST_URL || 'http://127.0.0.1:8001';
  const archiveResponse=await page.request.get(base+'/data/archive.json');
  assert.equal(archiveResponse.status(),404,'Internal canonical archive must not be deployed');
  const snapshot=await (await page.request.get(base+'/data/newsroom.json')).json();
  const expectedCount=snapshot.articles.length;
  assert.ok(expectedCount>0,'Browser smoke requires a nonempty real or fixture snapshot');
  const selected=snapshot.articles[0];
  const fields=['category','keywords','published_at','source','title','url'];
  for(const a of snapshot.articles)assert.deepEqual(Object.keys(a).sort(),fields);
  const archiveSnapshot={...snapshot,articles:[...snapshot.articles,{...selected,title:'EXCLUDED SEC FILING',record_type:'regulatory_filing'},{...selected,title:'EXCLUDED KOSIS',source_id:'kosis_recent',record_type:'statistical_release'}]};
  await page.goto(base);
  await page.waitForFunction(()=>!newsLoading);
  assert.equal(await page.locator('#rss-health-chip').textContent(),'PARTIAL FETCH');
  await clickNav(page,'news');
  await page.locator('[data-news-origin="all"]').click();await page.locator('#news-order').selectOption('latest');
  assert.equal(await page.locator('#news-items .news-item').count(),Math.min(10,expectedCount));
  assert.match(await page.locator('#news-page-total').textContent(),new RegExp('총 '+expectedCount+'건'));
  await page.locator('#news-search').fill(selected.title);
  assert.equal(await page.locator('#news-items .news-item').count(),1);
  await page.locator('#news-items [data-detail]').click();
  assert.equal(await page.locator('#modal-title').textContent(),selected.title);
  const selectedCategory=await page.evaluate(c=>normalizeCategory(c),selected.category);
  assert.equal(await page.locator('#modal-category').textContent(),selectedCategory);
  assert.equal(await page.locator('#modal-keywords').textContent(),selected.keywords.join(' · '));
  assert.equal(await page.locator('#modal-impact,#modal-content,#news-items .news-desc,#overview-news .news-desc').count(),0);
  assert.equal(await page.locator('#modal-url').getAttribute('href'),selected.url);
  await page.locator('#modal-close').click();
  await page.locator('#news-items [data-bookmark]').click();
  // IDs remain stable when a collection refresh changes ordering.
  await page.route('**/data/newsroom.json?*',async route=>{
   const response=await route.fetch();const data=await response.json();
   data.articles.reverse();await route.fulfill({json:data});
  });
  await page.evaluate(()=>loadLiveNews());
  assert.match(await page.locator('#news-items [data-bookmark]').textContent(),/저장됨/);
  await page.locator('#news-search').fill('');
  await page.locator('[data-filter="'+selectedCategory+'"]').click();
  assert.ok(await page.locator('#news-items .news-item').count()>0);
  await page.locator('[data-filter="저장"]').click();
  assert.equal(await page.locator('#news-items .news-item').count(),1);
  await page.route('**/data/health.json?*',route=>route.fulfill({json:{
   status:'failed',checked_at:'2026-10-26T13:30:00+09:00',successful_sources:0,
   source_count:4,sources:[{name:'시험 장애',status:'error'}]
  }}));
  await page.evaluate(()=>loadLiveNews());
  assert.equal(await page.locator('#rss-health-chip').textContent(),'FETCH FAILED');
  await page.locator('[data-filter="전체"]').click();
  assert.equal(await page.locator('#news-items .news-item').count(),Math.min(10,expectedCount));
  assert.match(await page.locator('#news-page-total').textContent(),new RegExp('총 '+expectedCount+'건'));
  await clickNav(page,'briefing');
  const briefing=await (await page.request.get(base+'/data/briefing.json')).json();
  const expectedBriefing=briefing.items.length?/주요 뉴스 후보|이전 생성 후보/:briefing.status==='no_eligible_recent_articles'?/선정 기준 미충족|이전 생성 후보/:/신규 뉴스 없음|이전 생성 후보/;
  assert.match(await page.locator('#briefing-state').textContent(),expectedBriefing);
  // Compatibility: old categories still work with new filter buttons.
  await page.unroute('**/data/newsroom.json?*');
  const inverse={'관광정책':'정책','인바운드':'수요','여행산업':'산업','문화·트렌드':'지역','경제·시장':'리서치'};
  await page.route('**/data/newsroom.json?*',route=>route.fulfill({status:404,body:'not found'}));
  await page.route('**/data/news.json?*',route=>route.fulfill({json:{...archiveSnapshot,articles:archiveSnapshot.articles.map(a=>({...a,category:inverse[a.category]||a.category,record_type:a.source_id==='kosis_recent'?undefined:a.record_type}))}}));
  await page.evaluate(()=>loadLiveNews());
  await clickNav(page,'news');
  await page.locator('[data-filter="'+selectedCategory+'"]').click();
  assert.ok(await page.locator('#news-items .news-item').count()>0);
  await page.locator('[data-filter="전체"]').click();
  assert.equal(await page.locator('#news-items .news-item').count(),Math.min(10,expectedCount));
  assert.match(await page.locator('#news-page-total').textContent(),new RegExp('총 '+expectedCount+'건'));
  for(const filing of archiveSnapshot.articles.filter(a=>(a.record_type||'news')!=='news'||a.archived_only)){
   assert.equal(await page.locator('#news-items').getByText(filing.title,{exact:true}).count(),0);
  }
  assert.equal(await page.locator('#news-items .news-title').first().textContent(),snapshot.articles[0].title);
  // Main already paginates 10/20. Verify all original links across all pages,
  // rather than incorrectly expecting every row to be visible at once.
  const seenLinks=new Map();
  for(let n=1;n<=Math.ceil(expectedCount/10);n++){
   if(n>1)await page.locator('[data-news-page="'+n+'"][aria-label="'+n+'페이지"]').click();
   const links=await page.locator('#news-items .news-title').evaluateAll(nodes=>nodes.map(a=>[a.getAttribute('href'),a.textContent]));
   for(const [url,title] of links){assert.ok(snapshot.articles.some(a=>a.url===url&&a.title===title));seenLinks.set(url,title);}
   for(const filing of archiveSnapshot.articles.filter(a=>(a.record_type||'news')!=='news'||a.archived_only)){
    assert.equal(await page.locator('#news-items').getByText(filing.title,{exact:true}).count(),0);
   }
  }
  assert.equal(seenLinks.size,expectedCount);
  assert.equal(await page.locator('#news-items img').count(),0);
  assert.deepEqual(errors,[]);
  console.log('PASS: live articles, search, detail, stable bookmark, partial/all-failure status, preservation, briefing and legacy fallback, six-field link curation, all-page pagination/link coverage, filing/statistics exclusion and internal archive isolation; no JS errors');
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
