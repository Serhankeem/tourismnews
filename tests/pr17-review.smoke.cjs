// Public real data only. No collection or public DB writes.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const baseline=require('../docs/newsroom-source-expansion-v04/comparison.json');
(async()=>{const browser=await chromium.launch({headless:true});try{for(const width of [390,1440]){
 const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010';await page.goto(base);await page.waitForFunction(()=>!newsLoading&&window.BriefingUI?.edition);
 const db=await(await page.request.get(base+'/data/newsroom.json')).json();assert.equal(db.count,db.articles.length);
 for(const original of baseline.new_articles){
  const row=db.articles.find(a=>a.url===original.url);
  if(original.source==='Hotel News Resource'){assert.equal(row,undefined);await page.evaluate(()=>navigate('news'));await page.locator('#news-search').fill(original.title);assert.equal(await page.locator('#news-items .news-item').count(),0);continue;}
  assert.ok(row);assert.ok(row.keywords.length>0);
  assert.deepEqual(Object.keys(row).sort(),['category','keywords','published_at','source','title','url']);
  for(const k of row.keywords)assert.ok(row.title.includes(k));
  for(const field of ['title','source','published_at','url','category'])assert.equal(row[field],original[field]);
  await page.evaluate(()=>navigate('news'));await page.locator('#news-search').fill(row.title);
  assert.equal(await page.locator('#news-items .news-keywords').textContent(),row.keywords.join(' · '));
 }
 await page.locator('#news-search').fill('');await page.evaluate(()=>navigate('briefing'));
 const briefing=await(await page.request.get(base+'/data/briefing.json')).json();
 assert.ok(!briefing.items.some(a=>a.source==='Hotel News Resource'));
 assert.ok(!(await page.locator('#briefing-news-list').textContent()).includes('IHG Opens Kimpton'));
 assert.deepEqual(errors,[]);await page.close();
}console.log('PASS PR17 review: approved literal keywords and held-source exclusion, unchanged five fields, public count, six public fields, current briefing rights exclusion, 390/1440px');}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
