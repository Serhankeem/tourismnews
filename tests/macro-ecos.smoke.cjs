/* SYNTHETIC financial API schema in intercepted browser memory only.
 * No real ECOS tourism data has been obtained; never save this as public JSON.
 */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8026',dir=process.env.ECOS_SCREENSHOTS||'/tmp/macro-ecos-v06';fs.mkdirSync(dir,{recursive:true});
 const errors=[],apiRequests=[];
 try{
  const context=await browser.newContext();const raw=await(await context.request.get(base+'/data/macro.json')).json();
  const original7=raw.indicators.filter(i=>i.connected);assert.equal(original7.length,7);assert.ok(original7.every(i=>i.unit==='명'));
  const fixture=structuredClone(raw),now=new Date().toISOString(),financial=['kto_tourism_receipts','kto_tourism_expenditure'];
  for(const [n,id] of financial.entries()){
   const i=fixture.indicators.find(i=>i.id===id);Object.assign(i,{source_id:'ecos_general_travel',connected:true,enabled:true,value_kind:'money_nonnegative',unit:'US$',display_unit:'백만 US$',display_divisor:1000000,publisher:'한국은행 ECOS',source_url:'https://ecos.bok.or.kr/api/',first_period:'2025-08',latest_period:'2026-08',months:13});
   i.observations=Array.from({length:13},(_,index)=>{const date=new Date(Date.UTC(2025,7+index,1)),period=date.toISOString().slice(0,7);return {period,value:(n+1)*1000000+123456+index*100000,unit:'US$',frequency:'M',verification_status:'official_api_validated',collection_method:'official_ecos_api',source_unit:'백만달러',finality:'not_stated',release_published_at:null,original_publication_at:null,first_collected_at:now,last_collected_at:now,revision_status:'original'};});
   i.latest={...i.observations.at(-1),comparisons:{mom_pct:4.5,yoy_pct:10,ytd_value:null,ytd_yoy_pct:null,mom_base_period:'2026-07',yoy_base_period:'2025-08',ytd_range:['2026-01','2026-08']}};
  }
  for(const width of [320,390,768,1440]){
   const page=await browser.newPage({viewport:{width,height:1000}});page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(new URL(r.url()).hostname==='ecos.bok.or.kr')apiRequests.push(r.url());});
   await page.goto(base+'/#macro');await page.waitForFunction(()=>window.MacroMonitor?.database);
   assert.equal(await page.locator('#macro-kpis [data-value]').count(),2,'Real unconnected financial cards must stay unconnected');
   assert.equal(await page.locator('#macro-kpis').getByText('미연동',{exact:true}).count(),2);
   const originals=await page.evaluate(()=>MacroMonitor.database.indicators.filter(i=>i.connected));assert.deepEqual(originals,original7);
   if(width===390||width===1440){await page.waitForTimeout(350);await page.screenshot({path:`${dir}/real-macro-${width}.png`,fullPage:true});await page.evaluate(()=>navigate('overview'));await page.waitForTimeout(350);await page.screenshot({path:`${dir}/real-home-${width}.png`,fullPage:true});}
   const before=await page.locator('#weather-score').textContent();
   await page.route('**/data/macro.json?*',r=>r.fulfill({json:fixture}));
   await page.route('**/data/macro_health.json?*',r=>r.fulfill({json:{status:'ok',sources:[{id:'kto_monthly_statistics',status:'ok',last_successful_check:now},{id:'ecos_general_travel',status:'ok',last_successful_check:now,collection_state:'new_data'}]}}));
   await page.evaluate(()=>MacroMonitor.load());
   assert.equal(await page.locator('#home-macro-kpis [data-value]').count(),4);
   assert.deepEqual(await page.evaluate(()=>MacroMonitor.database.indicators.filter(i=>i.unit==='명')),fixture.indicators.filter(i=>i.unit==='명'));
   const moneyCard=page.locator('#home-macro-kpis [data-macro-id="kto_tourism_receipts"]');
   assert.match(await moneyCard.textContent(),/2\.323456\s*백만 US\$/);assert.match(await moneyCard.textContent(),/2026-08/);
   assert.match(await moneyCard.textContent(),/전월 대비/);assert.match(await moneyCard.textContent(),/전년 동월비/);assert.match(await moneyCard.textContent(),/확정 여부 미표기/);
   assert.match(await moneyCard.textContent(),/최근 확인/);assert.match(await moneyCard.textContent(),/공표일 API 미제공/);
   assert.match(await page.locator('#home-macro-status').textContent(),/관광수입 기준 2026-08/);
   assert.equal(await page.locator('#weather-score').textContent(),before);
   await page.evaluate(()=>navigate('macro'));await page.locator('#macro-metric').selectOption(financial[0]);await page.locator('#macro-range').selectOption('12');
   assert.match(await page.locator('#macro-chart-meta').textContent(),/백만 US\$/);
   assert.match(await page.locator('#chart-macro svg > title').textContent(),/백만 US\$/);
   assert.equal(await page.locator('#chart-macro').getByText(/만$/).count(),0,'Money axis must not use person units');
   assert.match(await page.locator('#chart-macro rect title').last().textContent(),/2\.323456 백만 US\$/);
   assert.match(await page.locator('#macro-chart-foot').textContent(),/공표일 미제공/);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   if(width===390||width===1440){
    await page.evaluate(()=>{const b=document.createElement('div');b.textContent='합성 테스트 데이터 · 실제 ECOS 통계 아님 · UI 검증 전용';b.style='position:fixed;top:0;left:0;right:0;padding:10px;background:#fff2b3;color:#6d3600;z-index:999999;text-align:center;font-weight:700';b.id='synthetic-only-notice';document.body.append(b);});
    await page.waitForTimeout(350);await page.screenshot({path:`${dir}/synthetic-ui-only-macro-${width}.png`,fullPage:true});
    await page.locator('#synthetic-only-notice').evaluate(n=>n.remove());
   }
   await page.locator('#chart-toggle-macro [data-chart="growth"]').click();assert.match(await page.locator('#chart-macro svg > title').textContent(),/단위 %/);
   await page.locator('#chart-toggle-macro [data-chart="count"]').click();await page.locator('#macro-metric').selectOption('kto_inbound');assert.match(await page.locator('#chart-macro svg > title').textContent(),/만 명/);
   // One provider error is not an error in the other provider's data.
   await page.route('**/data/macro_health.json?*',r=>r.fulfill({json:{status:'partial',sources:[{id:'kto_monthly_statistics',status:'ok',last_successful_check:now},{id:'ecos_general_travel',status:'error',collection_state:'authentication_required'}]}}));
   await page.evaluate(()=>MacroMonitor.load());assert.match(await page.locator('#macro-kpis [data-macro-id="kto_tourism_receipts"]').textContent(),/자료 수집 실패/);
   assert.doesNotMatch(await page.locator('#macro-kpis [data-macro-id="kto_inbound"]').textContent(),/자료 수집 실패/);
   assert.equal(await page.locator('#weather-score').textContent(),before);
   // Invalid financial schema cannot replace the last validated snapshot.
   const invalid=structuredClone(fixture);invalid.indicators.find(i=>i.id===financial[0]).observations[0].value=-1;
   await page.route('**/data/macro.json?*',r=>r.fulfill({json:invalid}));await page.evaluate(()=>MacroMonitor.load());
   assert.equal(await page.locator('#macro-kpis [data-value]').count(),4);assert.match(await page.locator('#macro-status').textContent(),/이전 검증값 보존/);
   await page.evaluate(()=>{const i=MacroMonitor.database.indicators.find(i=>i.id==='kto_tourism_receipts');i.latest.value=Number.MAX_SAFE_INTEGER;MacroMonitor.render();});
   assert.match(await page.locator('#macro-kpis [data-macro-id="kto_tourism_receipts"] .value').textContent(),/9,007,199,254\.740991/,'Exact USD precision survives display conversion at the safe-integer boundary');
   await page.close();
  }
  assert.deepEqual(apiRequests,[],'No client-side ECOS call or API key');assert.deepEqual(errors,[]);
  console.log('PASS ECOS monetary UI: 4 widths, actual unconnected state, separate synthetic amounts, exact million USD display, periods/source/finality/check time, financial axis/tooltips, 7 visitor series, per-provider failures, retained values and unchanged Scenario Lab');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
