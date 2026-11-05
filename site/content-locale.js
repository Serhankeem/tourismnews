/* Presentation only: originals and server publication/rights gates stay authoritative. */
((root)=>{
 function create(registry={}){
  const rows=registry.headings||[],index=new Map(),duplicates=new Set();
  for(const row of rows){const key=row.kind+'\n'+row.url;if(index.has(key))duplicates.add(key);index.set(key,row);}
  const numbers=s=>String(s).match(/\d+(?:[.,]\d+)*/g)||[];
  function heading(record,kind,allow=true){
   const original={title:record.title,localized:false};if(!allow)return original;
   const key=kind+'\n'+record.url,h=index.get(key);
   if(!h||duplicates.has(key)||h.status!=='approved'||h.rights_status!=='approved'||h.accuracy_status!=='approved'
     ||h.mode!=='independent_factual_label'||h.original_title!==record.title||h.published_at!==record.published_at
     ||h.publisher!==(record.source||record.publisher)||typeof h.evidence_url!=='string'||!h.evidence_url.startsWith('https://')||!h.note||!h.attribution
     ||typeof h.ko_title!=='string'
     ||!/[가-힣]/.test(h.ko_title||'')||JSON.stringify(numbers(h.original_title))!==JSON.stringify(numbers(h.ko_title))
     ||!Array.isArray(h.preserved_tokens)||!h.preserved_tokens.length||h.preserved_tokens.some(t=>typeof t!=='string'||!h.original_title.includes(t)||!h.ko_title.includes(t)))return original;
   return {title:h.ko_title,localized:true,original:record.title,note:h.note,attribution:h.attribution,evidence_url:h.evidence_url};
  }
  function newsRegion(n){
   try{const u=new URL(n.url);if(u.username||u.password)return 'unknown';
    const candidates=(registry.news_publishers||[]).filter(p=>p.name===n.source&&p.domains.includes(u.hostname));
    const countries=new Set(candidates.map(p=>p.country));if(countries.size!==1)return 'unknown';
    const country=[...countries][0];return country==='KR'?'domestic':/^[A-Z]{2}$/.test(country)?'foreign':'unknown';
   }catch(_){return 'unknown';}
  }
  function compareNews(a,b,mode='domestic'){
   const priority={domestic:0,foreign:1,unknown:2};
   const group=mode==='domestic'?priority[newsRegion(a)]-priority[newsRegion(b)]:0;
   if(group)return group;
   return typeof root.compareNewsPublication==='function'?root.compareNewsPublication(a,b):
    Date.parse(b.published_at)-Date.parse(a.published_at)||String(a.url).localeCompare(String(b.url));
  }
  function searchable(record,kind,q){
   const h=heading(record,kind);
   return [record.title,h.localized?h.title:'',record.source||record.publisher,record.category,record.report_type,...record.keywords||[]]
    .filter(v=>typeof v==='string').some(v=>v.toLocaleLowerCase().includes(q.trim().toLocaleLowerCase()));
  }
  return Object.freeze({heading,newsRegion,compareNews,searchable,create});
 }
 let current=create({}),publishers=[],pending=null;
 async function refresh(){
  if(pending)return pending;
  pending=(async()=>{
   try{const response=await fetch('./assets/content-localization.json?v='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error();
    const text=await response.text();if(text.length>200000)throw Error();const data=JSON.parse(text);
    if(data.schema_version!==1||!Array.isArray(data.news_publishers)||!Array.isArray(data.headings))throw Error();
    publishers=data.news_publishers;current=create(data);
   }catch(_){current=create({news_publishers:publishers,headings:[]});} // Original titles, never stale approval fallback.
  })();
  try{await pending;}finally{pending=null;}
  if(typeof root.dispatchEvent==='function')root.dispatchEvent(new Event('content-locale-updated'));
 }
 root.ContentLocale=Object.freeze({create,refresh,
  heading:(...args)=>current.heading(...args),newsRegion:(...args)=>current.newsRegion(...args),
  compareNews:(...args)=>current.compareNews(...args),searchable:(...args)=>current.searchable(...args)});
 if(typeof module!=='undefined')module.exports={create};
})(globalThis);
