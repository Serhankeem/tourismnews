const assert=require('node:assert/strict'),p=require('../site/percentage.js');
for(const [raw,state,text] of [[21.1,'positive','▲ +21.10%'],[-8.4,'negative','▼ -8.40%'],[0,'neutral','— 0.00%'],[-0,'neutral','— 0.00%'],['-0.00%','neutral','— 0.00%'],[' + 21.10 % ','positive','▲ +21.10%'],['−8.40%','negative','▼ -8.40%'],['1,234.50 %','positive','▲ +1234.50%'],['.25','positive','▲ +0.25%']]){
 assert.equal(p.describe(raw).state,state);assert.equal(p.text(raw),text);
}
for(const raw of [null,undefined,'','   ',NaN,Infinity,-Infinity,true,false,[],{},'NaN','미발표','미연동','1,23%','1 2%','--2%','12%%','0x10','1e2','2<script>','<img src=x onerror=alert(1)>']){
 assert.equal(p.parse(raw),null);assert.equal(p.text(raw),'—');assert.ok(!/--(?:positive|negative|neutral)/.test(p.html(raw)));
 assert.ok(!p.html(raw).includes('<img'));
}
assert.equal(p.describe(-0.001).state,'negative','Direction is determined before rounding');
assert.equal(p.text(-0.001),'▼ -0.00%');assert.equal(p.text(1.235),'▲ +1.24%');
assert.match(p.html(21.1),/aria-hidden="true"/);assert.match(p.html(-8.4),/감소/);assert.match(p.html(0),/보합/);
console.log('PASS percentage parsing, rounding, signed zero, actual numeric direction, missing/invalid/XSS and accessibility');
