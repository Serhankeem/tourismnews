// Real public metadata only. Scenario inputs are deliberately fictional UI values.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8022';
 const out=process.env.POLISH_V10_OUTPUT||'/tmp/currentourism-polish-v10';fs.mkdirSync(out,{recursive:true});
 const evidence=[];
 try{
  for(const width of [320,390,768,1024,1440]){
   const context=await browser.newContext({viewport:{width,height:1100},hasTouch:width<=390,isMobile:width<=390,reducedMotion:'no-preference'});
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(base);await page.waitForFunction(()=>!newsLoading&&window.MacroMonitor?.database&&window.ResearchLibrary?.database?.reports?.length||(!newsLoading&&document.querySelector('#research-results .research-card')));
   const data=await(await page.request.get(base+'/data/reports.json')).json();
   const image=await page.request.get(base+'/assets/currentourism-new-airplane-logo.png');
   assert.equal(crypto.createHash('sha256').update(await image.body()).digest('hex'),'7f92affea61c57197f2b015576cb7bcaf604defb0ac270894157d8e94d070b7f');
   const logo=await page.locator('#brand-logo').boundingBox();assert.equal(logo.width,130);assert.equal(logo.height,65);
   assert.ok((await page.locator('.site-header').boundingBox()).height<=82);
   if(width<=390){await page.locator('#header-menu-toggle').click();assert.equal(await page.locator('#header-menu-toggle').getAttribute('aria-expanded'),'true');await page.keyboard.press('Escape');}
   const animations=await page.evaluate(()=>{navigate('news');return document.querySelector('#page-news').getAnimations().map(a=>({duration:a.effect.getTiming().duration,frames:a.effect.getKeyframes()}));});
   assert.ok(animations.some(a=>a.duration===200&&a.frames[0].opacity==='0'));
   await page.locator('#page-news .news-subnav a[href="#research"]').focus();
   assert.equal(await page.locator('#page-news .news-subnav a[href="#research"]').evaluate(n=>getComputedStyle(n).outlineStyle),'solid');
   await page.keyboard.press('Enter');assert.equal(await page.locator('#page-research').isVisible(),true);
   const active=page.locator('#page-research .news-subnav a[aria-current="page"]');assert.equal(await active.textContent(),'리서치');assert.ok(await active.evaluate(n=>n===document.activeElement));
   assert.equal(await active.evaluate(n=>getComputedStyle(n).backgroundColor),'rgb(23, 59, 115)');
   if(width<=390){const boxes=await page.locator('#page-research .news-subnav a').evaluateAll(ns=>ns.map(n=>n.getBoundingClientRect().width));assert.ok(Math.abs(boxes[0]-boxes[1])<1);}
   await page.goBack();assert.equal(await page.locator('#page-news').isVisible(),true);
   await page.goForward();assert.equal(await page.locator('#page-research').isVisible(),true);
   const unknown=data.reports.find(r=>r.access_type==='미확인');assert.ok(unknown);
   await page.locator('#research-search').fill(unknown.title);
   assert.equal(await page.locator('.research-access').first().textContent(),'열람 조건 미확인');
   assert.match(await page.locator('.research-access-note').first().textContent(),/무료 열람·회원 접근·구매 여부는 원문에서 확인/);
   assert.equal(data.reports.find(r=>r.url===unknown.url).access_type,'미확인');
   await page.locator('#research-reset').click();
   if(width>=768){
    const inactive=page.locator('#page-research .news-subnav a[href="#news"]');await inactive.hover();
    await page.waitForFunction(()=>getComputedStyle(document.querySelector('#page-research .news-subnav a[href="#news"]')).backgroundColor==='rgb(229, 238, 249)');
    await page.mouse.down();assert.equal(await inactive.evaluate(n=>getComputedStyle(n).filter),'brightness(0.94)');await page.mouse.up();
    await page.evaluate(()=>navigate('research'));await page.locator('.research-card').first().hover();
    await page.waitForFunction(()=>new DOMMatrix(getComputedStyle(document.querySelector('.research-card')).transform).f<=-1.9);
   }else{assert.equal(await page.evaluate(()=>matchMedia('(hover: hover)').matches),false);}
   await page.evaluate(()=>navigate('weather'));
   const cases=[['rain',[-30,-30,-30],'비'],['cloudy',[0,0,0],'흐림'],['partly',[20,10,0],'구름 조금'],['sunny',[35,35,35],'맑음']];
   for(const [tone,inputs,label] of cases){
    await page.evaluate(values=>{['s-arrivals','s-spend','s-air'].forEach((id,i)=>document.getElementById(id).value=values[i]);weather();},inputs);
    const score=Math.max(0,Math.min(100,Math.round(50+.65*inputs[0]+.4*inputs[1]+.25*inputs[2])));
    assert.equal(await page.locator('#weather-score').textContent(),String(score));
    assert.equal(await page.locator('#home-weather-score').textContent(),String(score));
    assert.equal(await page.locator('#weather-title').textContent(),label);
    assert.equal(await page.locator('#weather-icon').getAttribute('data-icon-state'),tone);
    assert.match(await page.locator('#weather-icon').getAttribute('aria-label'),/시나리오 · 가상 실험/);
    assert.equal(await page.locator('#home-weather-icon svg').innerHTML(),await page.locator('#weather-icon svg').innerHTML());
    const moving=await page.locator('#weather-icon svg *').evaluateAll(ns=>ns.filter(n=>getComputedStyle(n).animationName!=='none').map(n=>getComputedStyle(n).animationPlayState));
    assert.ok(moving.length>0&&moving.every(v=>v==='running'));
    assert.ok((await page.locator('#home-weather-icon svg *').evaluateAll(ns=>ns.map(n=>getComputedStyle(n).animationPlayState))).every(v=>v==='paused'));
    if(width===1440)await page.locator('.weather-result').screenshot({path:out+'/weather-'+tone+'.png',animations:'disabled'});
   }
   const svg=await page.locator('#weather-icon svg').innerHTML();
   await page.evaluate(()=>{document.getElementById('s-air').value=34;weather();});
   assert.equal(await page.locator('#weather-icon svg').innerHTML(),svg,'Same-tone input must reuse its SVG DOM');
   const whenPaused=await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));return getComputedStyle(document.querySelector('#weather-icon .cloud-drift')||document.querySelector('#weather-icon .sun-rays')).animationPlayState;});assert.equal(whenPaused,'paused');
   await page.evaluate(()=>{delete document.hidden;document.dispatchEvent(new Event('visibilitychange'));});
   await page.emulateMedia({reducedMotion:'reduce'});
   assert.ok((await page.locator('.weather-glyph *').evaluateAll(ns=>ns.map(n=>getComputedStyle(n).animationName))).every(n=>n==='none'));
   const reduced=await page.evaluate(()=>{navigate('macro');return document.querySelector('#page-macro').getAnimations().length;});assert.equal(reduced,0);
   await page.emulateMedia({reducedMotion:'no-preference'});
   await page.evaluate(()=>navigate('news'));await page.locator('[data-filter="항공·숙박"]').click();
   assert.equal(await page.locator('[data-filter="항공·숙박"]').getAttribute('aria-pressed'),'true');
   await page.locator('[data-filter="전체"]').click();
   const disabled=page.locator('#news-page-buttons button[aria-label="이전 페이지"]');
   assert.equal(await disabled.isDisabled(),true);assert.ok((await disabled.boundingBox()).height>=44);
   await page.evaluate(()=>navigate('overview'));
   assert.notEqual(await page.locator('.kpi').first().evaluate(n=>getComputedStyle(n).cursor),'pointer');
   await page.evaluate(()=>scrollTo(0,300));await page.waitForFunction(()=>document.querySelector('.site-header').classList.contains('is-scrolled'));
   await page.locator('.brand-home').click();assert.equal(await page.locator('#page-overview').isVisible(),true);
   if([390,768,1440].includes(width)){
    for(const route of ['overview','news','research','weather']){
     await page.evaluate(r=>navigate(r),route);
     if(route==='weather')await page.locator('#reset-weather').click();
     await page.screenshot({path:`${out}/after-${route}-${width}.png`,fullPage:route==='weather',animations:'disabled'});
    }
   }
   await page.evaluate(()=>navigate('overview'));
   await page.evaluate(async()=>{await Promise.all(document.querySelector('#page-overview').getAnimations().map(a=>a.finished));});
   await page.evaluate(()=>loadLiveNews());
   assert.equal(await page.locator('#page-overview').evaluate(n=>n.getAnimations().length),0,'Data refresh must not restart page entrance');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
   evidence.push({width,logo_width:logo.width,logo_height:logo.height,weather_states:4,keys_history:true,reduced_motion:true,errors});
   await context.close();
  }
  fs.writeFileSync(out+'/checks.json',JSON.stringify(evidence,null,2));
  console.log('PASS Polish v1.0: five widths, original 130px logo, measured header, segmented links/history/keyboard, four shared SVG states, unchanged scores, hidden/reduced motion pause, 200ms route-only entrance, access-condition label, 44px pagination, no pointer on plain KPI, real data preservation');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
