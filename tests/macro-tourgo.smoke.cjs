/* Every TOURGO amount here is synthetic, created through the Python adapter.
 * Interception is confined to browser memory; operational JSON never changes.
 */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),{execFileSync}=require('node:child_process');
const generated=JSON.parse(execFileSync('python',['-c',`
import sys,json,tempfile
sys.path.insert(0,'tests')
from test_macro_tourgo import config,ledger,NOW
from src.macro.engine import collect
from pathlib import Path
v=dict(receipts={'2025-08':1234567,'2026-07':1400001,'2026-08':1500123},expenditure={'2025-08':1300000,'2026-07':1600000,'2026-08':1800123},balance={'2025-08':-65433,'2026-07':-199999,'2026-08':-300000})
with tempfile.TemporaryDirectory() as tmp:
 collect(config(),Path(tmp)/'data',Path(tmp)/'state',now=NOW,force=True,tourgo_ledger=ledger(v))
 print((Path(tmp)/'data/macro.json').read_text())
`],{cwd:require('node:path').resolve(__dirname,'..'),encoding:'utf8'}));
(async()=>{
 const browser=await chromium.launch({headless:true}),base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8037',out=process.env.TOURGO_SHOTS||'/tmp/tourgo37/screenshots';fs.mkdirSync(out,{recursive:true});const errors=[],external=[];
 try{
  for(const width of [320,390,768,1440]){
   const page=await browser.newPage({viewport:{width,height:1000}});page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/know\.tour\.go\.kr|ecos\.bok\.or\.kr/.test(r.url()))external.push(r.url());});
   await page.goto(base+'/#macro');await page.waitForFunction(()=>window.MacroMonitor?.database);
   const real=await page.evaluate(()=>MacroMonitor.database),originalVisitors=real.indicators.filter(i=>i.unit==='명');
   assert.equal(await page.locator('#macro-kpis [data-value]').count(),2);assert.equal(await page.locator('.macro-derived-balance').count(),0);
   if([390,1440].includes(width)){await page.waitForTimeout(350);await page.screenshot({path:`${out}/default-unconnected-${width}.png`,fullPage:true});}
   const score=await page.locator('#weather-score').textContent();
   const fixture=structuredClone(real);fixture.indicators=fixture.indicators.map(i=>generated.indicators.find(g=>g.id===i.id)||i);fixture.tourism_balance=generated.tourism_balance;
   await page.route('**/data/macro.json?*',r=>r.fulfill({json:fixture}));
   await page.route('**/data/macro_health.json?*',r=>r.fulfill({json:{status:'ok',sources:[{id:'kto_monthly_statistics',status:'ok',last_successful_check:new Date().toISOString()},{id:'tourgo_tourism_balance',status:'ok',collection_state:'manual_import_validated',last_successful_check:new Date().toISOString()}]}}));
   await page.evaluate(()=>MacroMonitor.load());
   const card=page.locator('#macro-kpis [data-macro-id="kto_tourism_receipts"]');
   assert.match(await card.textContent(),/1,500\.123\s*백만 US\$/);assert.match(await card.textContent(),/확정 여부 미표기/);assert.match(await card.textContent(),/공식 파일 수동 입력/);assert.match(await card.textContent(),/공표일 파일에 미표기/);
   assert.equal(await card.locator('a').getAttribute('href'),'https://know.tour.go.kr/stat/koreaTourIncomeDis19Re.do');assert.match(await card.textContent(),/자료: 한국문화관광연구원/);
   const balance=page.locator('#macro-kpis .macro-derived-balance');assert.match(await balance.textContent(),/-300\s*백만 US\$/);assert.match(await balance.textContent(),/적자/);assert.match(await balance.textContent(),/234\.567백만 US\$ 악화/);assert.match(await balance.textContent(),/원본과 차감 계산값 일치/);assert.equal(await balance.locator('.percentage-change').count(),0);
   assert.equal(await card.locator('.percentage-change--positive').first().evaluate(n=>getComputedStyle(n).color),'rgb(200, 67, 77)');
   await page.locator('#macro-metric').selectOption('kto_tourism_receipts');assert.match(await page.locator('#chart-macro rect title').last().textContent(),/1,500\.123 백만 US\$/);
   assert.equal(await page.locator('#macro-comparisons .percentage-change--missing').count(),1);assert.match(await page.locator('#macro-chart-foot').textContent(),/TOURGO/);
   await page.locator('#chart-toggle-macro [data-chart="growth"]').click();assert.match(await page.locator('#chart-macro svg > title').textContent(),/단위 %/);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.equal(await page.locator('#weather-score').textContent(),score);assert.deepEqual(await page.evaluate(()=>MacroMonitor.database.indicators.filter(i=>i.unit==='명')),originalVisitors);
   if([390,1440].includes(width)){
    await page.evaluate(()=>{const b=document.createElement('div');b.textContent='합성 테스트 데이터 · 실제 TOURGO 통계 아님 · UI 검증 전용';b.style='padding:12px;background:#fff2b3;color:#663900;text-align:center;font-weight:700';document.body.prepend(b);window.scrollTo(0,0);});await page.waitForTimeout(350);await page.screenshot({path:`${out}/synthetic-tourgo-only-${width}.png`,fullPage:true});
   }
   for(const mode of ['synthetic','wrong_unit','identity','ecos_mix','hash']){
    const invalid=structuredClone(fixture),r=invalid.indicators.find(i=>i.id==='kto_tourism_receipts');
    if(mode==='synthetic')r.observations[0].data_origin='synthetic_test';if(mode==='wrong_unit')r.observations[0].source_unit='백만 US$';if(mode==='identity')r.observations[0].official_balance_value+=1;if(mode==='ecos_mix')r.source_id='ecos_general_travel';if(mode==='hash')r.observations[0].file_sha256='0'.repeat(64);
    await page.route('**/data/macro.json?*',r=>r.fulfill({json:invalid}));await page.evaluate(()=>MacroMonitor.load());assert.match(await page.locator('#macro-status').textContent(),/이전 검증값 보존/);assert.match(await card.textContent(),/1,500\.123/);
   }
   await page.close();
  }
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);console.log('PASS TOURGO UI: gated default, adapter-generated synthetic path, exact USD/million scale, signed official balance/absolute changes, provenance rejection, 4 widths, unchanged visitors/Scenario Lab, no API calls');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
