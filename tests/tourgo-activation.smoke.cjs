/* User-supplied September anchors in an explicitly SYNTHETIC 69-month fixture.
   Neither official XLS bytes nor an operating publication are used here. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),{execFileSync}=require('node:child_process');
const fixture=JSON.parse(execFileSync('python',['-c',`
import sys,tempfile,json,os
from pathlib import Path
sys.path.insert(0,'tests')
from test_tourgo_readiness import synthetic69,NOW,ROOT
from src.macro import tourgo_release as r
ledger=synthetic69()
for n,period in enumerate(sorted(ledger['series']['receipts'])):
 values=dict(receipts=1500000+n*10000,expenditure=1700000+n*12000)
 values['balance']=values['receipts']-values['expenditure']
 for kind,value in values.items():ledger['series'][kind][period]['value']=value
for kind,value in dict(receipts=2460800,expenditure=2958800,balance=-498000).items():ledger['series'][kind]['2026-09']['value']=value
with tempfile.TemporaryDirectory() as tmp:
 out=Path(tmp)/'staging'
 r.stage(ledger,Path(os.environ.get('TOURGO_TEST_BASELINE',str(ROOT))),out,r.INITIAL_HASHES,'initial',NOW)
 print(json.dumps({'macro':json.loads((out/'pages/data/macro.json').read_text()),'health':json.loads((out/'pages/data/macro_health.json').read_text())}))
`],{cwd:require('node:path').resolve(__dirname,'..'),encoding:'utf8',maxBuffer:4*1024*1024}));
(async()=>{
 const browser=await chromium.launch({headless:true}),base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8041',shots=process.env.TOURGO_ACTIVATION_SHOTS||'/tmp/tourgo40/screenshots';fs.mkdirSync(shots,{recursive:true});const errors=[];
 try{
 for(const width of [320,390,768,1440]){
  const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/#macro');await page.waitForFunction(()=>window.MacroMonitor?.database);
  const before=await page.evaluate(()=>MacroMonitor.database.indicators.filter(i=>i.unit==='명'));
  await page.route('**/data/macro.json?*',r=>r.fulfill({json:fixture.macro}));
  const waiting=structuredClone(fixture.health),source=waiting.sources.find(s=>s.id==='tourgo_tourism_balance');source.status='manual_update_pending';source.collection_state='waiting_for_manual_input';
  await page.route('**/data/macro_health.json?*',r=>r.fulfill({json:waiting}));await page.evaluate(()=>MacroMonitor.load());
  assert.deepEqual(await page.evaluate(()=>MacroMonitor.database.indicators.filter(i=>i.unit==='명')),before);
  for(const [id,value] of [['kto_tourism_receipts','2,460.8'],['kto_tourism_expenditure','2,958.8']]){
   const card=page.locator(`#macro-kpis [data-macro-id="${id}"]`);assert.ok((await card.textContent()).includes(value));assert.match(await card.textContent(),/백만 US\$|2026-09/);assert.match(await card.textContent(),/수동 갱신 대기/);
   await page.locator('#macro-metric').selectOption(id);await page.locator('#macro-range').selectOption('69');await page.locator('#chart-toggle-macro [data-chart="count"]').click();assert.equal(await page.locator('#chart-macro rect').count(),69);
  }
  const balance=page.locator('#macro-kpis .macro-derived-balance');assert.match(await balance.textContent(),/-498\s*백만 US\$/);assert.equal(await balance.locator('.percentage-change').count(),0);
  assert.match(await page.locator('#macro-chart-foot').textContent(),/한국문화관광연구원|관광지식정보시스템/);
  await page.evaluate(()=>navigate('overview'));assert.match(await page.locator('#home-macro-kpis').textContent(),/2,460\.8/);assert.match(await page.locator('#home-macro-kpis').textContent(),/적자/);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  if([390,1440].includes(width)){
   await page.evaluate(()=>{let b=document.createElement('div');b.textContent='합성 69개월 · 제공된 기대값 표시 테스트 · 실제 원본 검증 아님 · 운영 미활성';b.style='padding:12px;background:#fff2b3;color:#663900;font-weight:bold;text-align:center';document.body.prepend(b);navigate('macro');window.scrollTo(0,0);});
   await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(300);
   await page.screenshot({path:`${shots}/synthetic-activation-${width}.png`,fullPage:true});
  }
  await page.close();
 }
 assert.deepEqual(errors,[]);console.log('PASS synthetic activation UI: supplied anchors 2460.8 / 2958.8 / -498 million USD, 69-month charts, source/period/comparisons, waiting state, KTO preserved, four widths; actual originals NOT validated');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
