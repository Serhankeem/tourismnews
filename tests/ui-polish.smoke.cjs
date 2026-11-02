const clickNav=require('./navigation-helper.cjs');
/* Design-only responsive/accessibility regression using the real public databases.
   Optional AXE_SCRIPT_PATH points to a local axe-core browser bundle (not shipped). */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const base=process.env.TOURISM_TEST_URL||'http://127.0.0.1:8010';
 const dir=process.env.POLISH_OUTPUT||'/tmp/currentourism-polish';fs.mkdirSync(dir,{recursive:true});
 const axeScript=process.env.AXE_SCRIPT_PATH;
 function contrast(fg,bg){
  const luminance=color=>{const rgb=color.match(/[0-9a-f]{2}/gi).map(x=>parseInt(x,16)/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4);return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];};
  const a=luminance(fg),b=luminance(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
 }
 assert.ok(contrast('#52647A','#FFFFFF')>=4.5,'SVG axis contrast on white');
 assert.ok(contrast('#1B477B','#FFFFFF')>=4.5,'SVG value contrast on white');
 const results=[],errors=[];
 try{
  for(const width of [1440,1024,768,390]){
   const page=await browser.newPage({viewport:{width,height:1000},isMobile:width===390});
   page.on('pageerror',e=>errors.push(e.message));
   for(const route of ['overview','news','research','briefing','macro','weather','about']){
    await page.goto(base+'/#'+route);await page.waitForFunction(()=>!newsLoading&&window.ResearchLibrary?.database.reports.length>0&&window.MacroMonitor?.database?.indicators.length>0);
    if(route==='about')await page.waitForFunction(()=>document.querySelectorAll('#about-research-sources .source-status-row').length===Object.keys(ResearchLibrary.database.publishers).length);
    assert.equal(await page.locator('#page-'+route).isVisible(),true);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}/${route}: horizontal overflow`);
    const logo=await page.locator('#brand-logo').evaluate(i=>({loaded:i.naturalWidth>0,ratio:i.getBoundingClientRect().width/i.getBoundingClientRect().height,natural:i.naturalWidth/i.naturalHeight}));assert.ok(logo.loaded);assert.ok(Math.abs(logo.ratio-logo.natural)<.01);
    const active=route==='overview'?null:route==='research'?'research':route;
    if(active)assert.equal(await page.locator(`.primary-navigation [data-nav="${active}"]`).getAttribute('aria-current'),'page');
    const touched=await page.locator('#page-'+route+' button:visible, #page-'+route+' select:visible').evaluateAll(nodes=>nodes.filter(n=>!n.disabled&&n.getBoundingClientRect().height<39).map(n=>({text:n.textContent.trim().slice(0,40),height:n.getBoundingClientRect().height})));
    assert.deepEqual(touched,[],`${width}/${route}: compact touch control`);
    if(route==='overview'||route==='macro'){
     const selector=route==='overview'?'#chart-overview':'#chart-macro';
     const chart=await page.locator(selector+' svg').evaluate(svg=>({viewWidth:svg.viewBox.baseVal.width,renderWidth:svg.getBoundingClientRect().width,labels:[...svg.querySelectorAll('text')].map(n=>({text:n.textContent,rendered:parseFloat(n.getAttribute('font-size'))*svg.getBoundingClientRect().width/svg.viewBox.baseVal.width}))}));
     assert.ok(chart.labels.every(n=>n.rendered>=11.5),`${width}/${route}: unreadable chart labels`);
     const official=await page.evaluate(()=>MacroMonitor.database.indicators.find(i=>i.id==='kto_inbound'));const plotted=await page.locator(selector+' svg rect').evaluateAll(nodes=>nodes.map(n=>({period:n.dataset.period,value:Number(n.dataset.value)})));assert.ok(plotted.length>3,'Official monthly history replaces the legacy three points');for(const p of plotted)assert.ok(official.observations.some(o=>o.period===p.period&&o.value===p.value),'Only actual observed months/values');
    }
    if(route==='news'||route==='research'){
     const input=page.locator(route==='news'?'#news-search':'#research-search');
     await input.focus();const outline=await input.evaluate(n=>({width:getComputedStyle(n).outlineWidth,style:getComputedStyle(n).outlineStyle}));assert.equal(outline.style,'solid');assert.ok(parseFloat(outline.width)>=3);
     await page.keyboard.press('Tab');assert.notEqual(await page.evaluate(()=>document.activeElement.tagName),'BODY');await page.evaluate(()=>document.activeElement.blur());
    }
    let accessibility={tool:'not run (AXE_SCRIPT_PATH absent)',violations:[],manualChecks:[]};
    if(axeScript){await page.addScriptTag({path:axeScript});accessibility=await page.evaluate(async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return {tool:'axe-core '+axe.version,violations:r.violations.map(v=>({id:v.id,targets:v.nodes.map(n=>n.target)})),manualChecks:r.incomplete.map(v=>({id:v.id,nodes:v.nodes.length}))};});assert.deepEqual(accessibility.violations,[],`${width}/${route}: axe violations`);}
    assert.equal(await page.locator('#kakao-channel-cta').evaluate(n=>{const target=document.getElementById(n.getAttribute('aria-controls'));return !!target?.querySelector('[role="dialog"]');}),true,'Hidden popup relationship exists in DOM');
    results.push({width,route,overflow:false,accessibility});
    if((width===1024||width===768)&&['overview','news','research'].includes(route))await page.screenshot({path:`${dir}/${route}-${width}.png`,fullPage:true});
   }
   // Native range labels/keyboard and unchanged simulator computation.
   await page.goto(base+'/#weather');await page.waitForFunction(()=>!newsLoading);
   const slider=page.getByLabel('관광소비 증감률 (가정)',{exact:true});
   const oldValue=Number(await slider.inputValue());await slider.focus();await page.keyboard.press('ArrowRight');assert.equal(Number(await slider.inputValue()),oldValue+1);
   const expected=await page.evaluate(()=>Math.max(0,Math.min(100,Math.round(50+.65*Number(document.getElementById('s-arrivals').value)+.4*Number(document.getElementById('s-spend').value)+.25*Number(document.getElementById('s-air').value)))));
   assert.equal(Number(await page.locator('#weather-score').textContent()),expected);
   await page.locator('#reset-weather').click();assert.equal(Number(await slider.inputValue()),oldValue);
   // Long real titles, not fabricated fixture articles.
   const db=await(await page.request.get(base+'/data/reports.json')).json();
   const longest=db.reports.reduce((a,b)=>a.title.length>b.title.length?a:b);
   await page.goto(base+'/#research');await page.waitForFunction(()=>window.ResearchLibrary?.database.reports.length>0);
   await page.locator('#research-search').fill(longest.title);assert.equal(await page.locator('#research-results h3').count(),1);assert.equal((await page.locator('#research-results h3').textContent()).trim(),longest.title);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'Long English title must wrap');
   if(width<=1024){
    const toggle=page.locator('#news-menu-toggle');await toggle.click();assert.equal(await toggle.getAttribute('aria-expanded'),'true');await page.keyboard.press('Escape');assert.equal(await toggle.getAttribute('aria-expanded'),'false');assert.equal(await toggle.evaluate(n=>document.activeElement===n),true);
    await toggle.click();await clickNav(page,'about');assert.equal(await toggle.getAttribute('aria-expanded'),'false');
    await page.locator('#brand-logo').click();assert.equal(await page.locator('#page-overview').isVisible(),true);
   }
   await page.emulateMedia({reducedMotion:'reduce'});await page.locator('#brand-logo').focus();assert.equal(await page.locator('#brand-logo').evaluate(n=>getComputedStyle(n).animationName),'none');
   await page.close();
  }
  assert.deepEqual(errors,[]);
  fs.writeFileSync(dir+'/responsive-accessibility.json',JSON.stringify({pages:results.length,widths:[1440,1024,768,390],jsErrors:errors,results},null,2)+'\n');
  console.log(`PASS: ${results.length} page/width combinations; layout, original logo, 40px+ controls, keyboard/focus, readable real chart labels, long real report title, unchanged weather calculation, reduced motion${axeScript?'; axe WCAG A/AA automatic violations 0':''}`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
