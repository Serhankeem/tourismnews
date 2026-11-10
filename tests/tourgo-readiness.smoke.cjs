/* Synthetic 69-month staging only. No actual TOURGO XLS is embedded or fetched. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),{execFileSync}=require('node:child_process');
const generated=JSON.parse(execFileSync('python',['-c',`
import sys,tempfile,json,os
from pathlib import Path
sys.path.insert(0,'tests')
from test_tourgo_readiness import synthetic69,NOW,ROOT
from src.macro import tourgo_release as r
with tempfile.TemporaryDirectory() as tmp:
 output=Path(tmp)/'staging'
 receipt=r.stage(synthetic69(),Path(os.environ.get('TOURGO_TEST_BASELINE',str(ROOT))),output,r.INITIAL_HASHES,'initial',NOW)
 print(json.dumps({'macro':json.loads((output/'pages/data/macro.json').read_text()),'health':json.loads((output/'pages/data/macro_health.json').read_text()),'count':receipt['financial_observations']}))
`],{cwd:require('node:path').resolve(__dirname,'..'),encoding:'utf8',maxBuffer:4*1024*1024}));
(async()=>{
 const browser=await chromium.launch({headless:true}),base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8039',out=process.env.TOURGO_READINESS_SHOTS||'/tmp/tourgo39/screenshots';fs.mkdirSync(out,{recursive:true});const errors=[];
 try{
  assert.equal(generated.count,138);
  for(const width of [320,390,768,1440]){
   const page=await browser.newPage({viewport:{width,height:1000}});page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base+'/#macro');await page.waitForFunction(()=>window.MacroMonitor?.database);
   const before=await page.evaluate(()=>MacroMonitor.database),score=await page.locator('#weather-score').textContent();
   assert.equal(await page.locator('#macro-kpis [data-value]').count(),2);
   await page.route('**/data/macro.json?*',r=>r.fulfill({json:generated.macro}));await page.route('**/data/macro_health.json?*',r=>r.fulfill({json:generated.health}));await page.evaluate(()=>MacroMonitor.load());
   assert.deepEqual(await page.evaluate(()=>MacroMonitor.database.indicators.filter(i=>i.unit==='명')),before.indicators.filter(i=>i.unit==='명'));
   const card=page.locator('#macro-kpis [data-macro-id="kto_tourism_receipts"]');assert.match(await card.textContent(),/10\.068\s*백만 US\$/);
   assert.match(await page.locator('#macro-kpis .macro-derived-balance').textContent(),/-3\.068\s*백만 US\$/);assert.match(await page.locator('#macro-kpis .macro-derived-balance').textContent(),/0\.012백만 US\$ 악화/);
   assert.equal(await page.locator('#macro-kpis .macro-derived-balance .percentage-change').count(),0);
   assert.equal(await card.locator('.percentage-change--positive').first().evaluate(n=>getComputedStyle(n).color),'rgb(200, 67, 77)');
   await page.locator('#macro-metric').selectOption('kto_tourism_receipts');await page.locator('#macro-range').selectOption('69');
   await page.locator('#chart-toggle-macro [data-chart="count"]').click();assert.equal(await page.locator('#chart-macro rect').count(),69);assert.match(await page.locator('#chart-macro rect title').last().textContent(),/10\.068 백만 US\$/);
   const publicRows=generated.macro.indicators.filter(i=>i.source_id==='tourgo_tourism_balance');assert.ok(publicRows.every(i=>i.observations.every(o=>!('bundle_sha256_by_kind' in o)&&!('file_sha256' in o)&&!('source_value' in o))));
   const waiting=structuredClone(generated.health);waiting.sources[0].status='manual_update_pending';waiting.sources[0].collection_state='waiting_for_manual_input';const verifiedAt=waiting.sources[0].last_successful_check;
   await page.route('**/data/macro_health.json?*',r=>r.fulfill({json:waiting}));await page.evaluate(()=>MacroMonitor.load());assert.match(await card.textContent(),/수동 갱신 대기/);
   assert.equal(await page.evaluate(()=>MacroMonitor.health.sources[0].last_successful_check),verifiedAt);assert.equal(await page.locator('#weather-score').textContent(),score);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   if([390,1440].includes(width)){
    await page.evaluate(()=>{const b=document.createElement('div');b.textContent='합성 69개월 staging · 실제 TOURGO 수치 아님 · 운영 미활성';b.style='padding:12px;background:#fff2b3;color:#663900;font-weight:700;text-align:center';document.body.prepend(b);window.scrollTo(0,0);});await page.waitForTimeout(350);await page.screenshot({path:`${out}/synthetic-readiness-${width}.png`,fullPage:true});
   }
   await page.evaluate(()=>navigate('overview'));assert.match(await page.locator('#home-macro-kpis [data-macro-id="kto_tourism_receipts"]').textContent(),/10\.068/);assert.match(await page.locator('#home-macro-kpis .macro-derived-balance').textContent(),/적자/);
   await page.close();
  }
  assert.deepEqual(errors,[]);console.log('PASS readiness UI: synthetic 69 months/138 financial records, 483 visitor records retained, exact amounts/deficit/absolute changes, pending manual update without freshness inflation, public metadata isolation, 4 widths, Overview and Scenario Lab preserved');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
