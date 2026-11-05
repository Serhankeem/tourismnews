// Read-only real Pages composition; no article/permission fixture injection.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  for(const width of [390,1440]){
   const page=await browser.newPage({viewport:{width,height:1000}}),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010';
   await page.goto(base+'/#news');await page.waitForFunction(()=>!newsLoading&&NEWS.length>0);
   const get=async name=>(await page.request.get(base+'/data/'+name+'.json')).json();
   const news=await get('newsroom'),health=await get('health');
   assert.equal(news.count,news.articles.length);
   for(const article of news.articles){
    assert.deepEqual(Object.keys(article).sort(),['category','keywords','published_at','source','title','url']);
    assert.notEqual(article.source,'Hotel News Resource');
   }
   const q=health.discovery.quality.domestic_coverage,d=q.publisher_diversity;
   assert.equal(d.domestic_publishers,Object.keys(d.news_by_publisher).length);
   assert.equal(Object.values(d.news_by_publisher).reduce((a,b)=>a+b,0),q.domestic_publisher_news_count);
   assert.equal(d.domestic_news_last7d,q.domestic_publisher_news_last7d);
   assert.equal(d.korea_direct_news_last7d,q.domestic_korea_direct_news_last7d);
   assert.equal(d.provenance.independent_reporting_verified,0);
   assert.ok(d.domestic_top3_publisher_share<=1);
   for(const row of health.discovery.sources){
    if(row.status!=='ok'){assert.equal(row.news_conversion_last7d,null);continue;}
    const c=row.news_conversion_last7d;
    assert.ok(c.industry_candidates<=c.observed_unique);
    assert.ok(c.approved_candidates<=c.industry_candidates);
    assert.ok(c.public_observed_candidates<=c.industry_candidates);
    assert.ok(c.new_public_candidates<=c.public_observed_candidates);
    if(row.publication_policy.status==='review'){
     assert.equal(c.approved_candidates,0);assert.equal(c.public_observed_candidates,0);
    }
   }
   const visible=await page.locator('#news-items .news-item').count();assert.ok(visible>0&&visible<=10);
   assert.equal((await get('reports')).count,135);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('PASS v0.6: six public fields, publisher grouping and current-cohort conversion, review/failure distinction, no independent-reporting claim, HNR blocked, Research preserved, 390/1440px');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
