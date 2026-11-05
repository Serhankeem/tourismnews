// Synthetic captions; never shipped in the runtime asset or operational DB.
const assert=require('node:assert/strict'),{create}=require('../site/content-locale.js');
const record={title:'OECD Tourism 2026',publisher:'OECD',published_at:'2026-06-30',url:'https://example.org/2026',category:'관광정책',keywords:['관광']};
const heading={kind:'research',url:record.url,publisher:'OECD',published_at:record.published_at,original_title:record.title,ko_title:'OECD 관광 보고서 2026',mode:'independent_factual_label',status:'approved',rights_status:'approved',accuracy_status:'approved',preserved_tokens:['OECD'],note:'fixture',attribution:'fixture',evidence_url:'https://example.org/license'};
let api=create({headings:[heading]});assert.equal(api.heading(record,'research').title,heading.ko_title);assert.equal(api.searchable(record,'research','OECD Tourism'),true);assert.equal(api.searchable(record,'research','관광 보고서'),true);
for(const change of [{status:'review'},{status:'withdrawn'},{rights_status:'review'},{accuracy_status:'review'},{ko_title:'OECD 관광 보고서 2099'},{ko_title:'다른기관 관광 2026'},{published_at:'2025-06-30'},{publisher:'Unknown'},{original_title:'Different 2026'},{preserved_tokens:'OECD'},{evidence_url:'javascript:alert(1)'},{ko_title:{bad:true}}]){
 api=create({headings:[{...heading,...change}]});assert.equal(api.heading(record,'research').localized,false,JSON.stringify(change));
}
assert.equal(create({headings:[heading,heading]}).heading(record,'research').localized,false);
assert.equal(create({headings:[heading]}).heading(record,'research',false).localized,false);
const publishers=[{name:'Korean registered publisher',country:'KR',domains:['kr.example.org']},{name:'Foreign registered publisher',country:'GB',domains:['foreign.example.org']}];
api=create({news_publishers:publishers});
const domestic={source:publishers[0].name,url:'https://kr.example.org/a',title:'English language title',published_at:'2026-10-01T00:00:00Z'};
const foreign={source:publishers[1].name,url:'https://foreign.example.org/a',title:'한국어 제목이어도 해외 발행처',published_at:'2026-11-01T00:00:00Z'};
assert.equal(api.newsRegion(domestic),'domestic');assert.equal(api.newsRegion(foreign),'foreign');
for(const x of [{...domestic,source:'Unknown'},{...domestic,url:'https://kr.example.org.evil/a'},{...domestic,url:'https://kr.example.org@evil.example.org/a'}])assert.equal(api.newsRegion(x),'unknown');
assert.deepEqual([foreign,domestic].sort((a,b)=>api.compareNews(a,b,'domestic')),[domestic,foreign]);
assert.deepEqual([domestic,foreign].sort((a,b)=>api.compareNews(a,b,'latest')),[foreign,domestic]);
console.log('PASS locale unit: dual-language search, no language-based country inference, immutable original, exact binding, invalid year/entity/date, review/withdraw/duplicates, domestic-first vs chronological');
