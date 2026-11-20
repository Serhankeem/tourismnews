const assert=require('node:assert/strict');
module.exports=async function assertSharedModel(page){
 await page.waitForFunction(()=>window.MarketSignalUI?.result);
 const r=await page.evaluate(()=>MarketSignalUI.result);
 assert.equal(r.model_version,'model-signal-v1.0.0');
 assert.equal(await page.locator('#s-arrivals,#s-spend,#s-air,#reset-weather').count(),0);
 assert.equal(await page.locator('#home-weather-score').textContent(),await page.locator('#weather-score').textContent());
 assert.equal(await page.locator('#weather-score').textContent(),r.status==='observed'?r.score_display:'—');
 assert.deepEqual(r.source_indicator_ids,['kto_inbound','kto_tourism_receipts']);
};
