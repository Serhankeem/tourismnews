// Only verified real publication metadata; never writes production fixtures.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const proof=require('../docs/newsroom-source-expansion-v05/comparison.json');
(async()=>{const browser=await chromium.launch({headless:true});try{
 for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010';
  await page.goto(base);await page.waitForFunction(()=>!newsLoading&&window.BriefingUI?.edition);
  const db=await(await page.request.get(base+'/data/newsroom.json')).json();
  assert.ok(db.count>=proof.after.public_news);assert.equal(db.count,db.articles.length);
  for(const expected of proof.new_articles){
   assert.deepEqual(db.articles.find(a=>a.url===expected.url),expected);
   assert.ok(expected.keywords.length);for(const word of expected.keywords)assert.ok(expected.title.includes(word));
   assert.deepEqual(Object.keys(expected).sort(),['category','keywords','published_at','source','title','url']);
   await page.evaluate(()=>navigate('news'));await page.locator('#news-search').fill(expected.title);
   assert.equal(await page.locator('#news-items .news-item').count(),1);
   assert.equal(await page.locator('#news-items .news-title').textContent(),expected.title);
  }
  assert.ok(!db.articles.some(a=>a.source==='Hotel News Resource'));
  const health=await(await page.request.get(base+'/data/health.json')).json();
  const domestic=health.discovery.quality.domestic_coverage;
  assert.equal(domestic.domestic_publishing_sources,5);assert.deepEqual(domestic.new_domestic_publishing_sources,[]);
  assert.ok(domestic.domestic_korea_direct_news_count<domestic.domestic_publisher_news_count);
  assert.ok(domestic.domestic_korea_direct_news_count>=28,'include the three title-proven Korean policy stories');
  assert.equal(domestic.domestic_news_by_media_type.general_economy,0);
  assert.equal(domestic.domestic_news_by_media_type.corporate,0);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);await page.close();
 }
 console.log('PASS v0.5: 7 real domestic-publisher additions, six fields, original dates/links, search, rights exclusion, honest domestic coverage, 390/1440px');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
