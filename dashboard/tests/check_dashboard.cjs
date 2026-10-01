// 데이터 계산과 새 컴포넌트의 JavaScript 문법을 검사합니다. 브라우저 제어 도구가 아닙니다.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert/strict');
const boot = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const ui = path.join(__dirname, '..', 'ui');
const csvContext = vm.createContext({BOOT:boot});
vm.runInContext(fs.readFileSync(path.join(ui,'data.js'),'utf8'), csvContext);
// CSV의 일별 값과 월평균을 기준으로 가중 점수를 확인합니다.
const monthly = new Map();
const cases = [];
for (const [date, city, district, ...factors] of boot.riskRows) {
    cases.push({city, district, mode:'day', period:date, factors});
    const month = date.slice(0, 7);
    const key = JSON.stringify([city, district, month]);
    if (!monthly.has(key)) monthly.set(key, {city, district, mode:'month', period:month, sum:factors.map(() => 0), count:0});
    const group = monthly.get(key);
    factors.forEach((value, index) => { group.sum[index] += value; });
    group.count++;
}
for (const group of monthly.values()) {
    cases.push({...group, factors:group.sum.map(value => value / group.count)});
}
let checked = 0;
for (const {city, district, mode, period, factors} of cases) {
    for (const weights of [boot.weights, [40,5,20,30,10]]) {
        const code = `scoreAt(${JSON.stringify(city)},${JSON.stringify(district)},${JSON.stringify(mode)},${JSON.stringify(period)},${JSON.stringify(weights)})`;
        const actual = vm.runInContext(code, csvContext);
        const expected = factors.reduce((sum, value, index) => sum + value * weights[index], 0) / weights.reduce((sum, value) => sum + value, 0);
        assert(actual !== null && Math.abs(actual - expected) < 1e-10, `${city} ${district} ${period}`);
        checked++;
    }
}
assert(checked > 0, '검증할 위험 요인 자료가 없습니다.');
assert.equal(vm.runInContext("scoreAt('__missing__','__missing__','day',BOOT.endDate,DEFW)", csvContext), null);
assert.equal(vm.runInContext("scoreOf([10,20,30,40,50],[0,0,0,0,0])", csvContext), null);
// 함수로 구성해 구문만 검사합니다. 화면 이벤트를 실행하지 않습니다.
new Function(fs.readFileSync(path.join(ui,'data.js'),'utf8') + fs.readFileSync(path.join(ui,'charts.js'),'utf8') + fs.readFileSync(path.join(ui,'responses.js'),'utf8') + fs.readFileSync(path.join(ui,'workspace.js'),'utf8') + fs.readFileSync(path.join(ui,'dashboard.js'),'utf8'));
console.log(JSON.stringify({calculationChecks:checked,syntax:'PASS',missingData:'PASS'}));

// 집계 누락·판단 기준·필터·집단별 조치 상태 검증.
const responseContext = vm.createContext({
 BOOT:{groupSignals:JSON.parse(fs.readFileSync(path.join(__dirname,'../data/group_signals.json'),'utf8'))},
 S:{city:'강남구'}, listen:()=>{},
 prevMonth:month=>{const [y,m]=month.split('-').map(Number);return new Date(Date.UTC(y,m-2,1)).toISOString().slice(0,7)},
 esc:value=>String(value).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))
});
vm.runInContext(fs.readFileSync(path.join(ui,'responses.js'),'utf8'),responseContext);
const run=code=>vm.runInContext(code,responseContext);
assert.equal(run('changeRate(80,100)'),-20);
assert.equal(run('changeRate(5,0)'),null);
assert.equal(run('changeRate(null,100)'),null);
assert.equal(run('R.month'),'2026-08');
assert.equal(run("responseRows().filter(r=>r.priority==='우선 확인').length"),1);
assert.equal(run("responseRows().filter(r=>r.priority==='판단 보류').length"),2);
assert.equal(run("responseRows().every(r=>r.city==='강남구')"),true);
assert(run('viewUsers()').includes('사회참여·교류 프로그램'));
assert(run('viewActions()').includes('프로그램 연계 검토'));
run("R.gender='여성';R.age='20대'");
assert.equal(run('filteredResponses().length'),1);
run("R.district='없는동'");
assert(run('viewUsers()').includes('조건에 맞는 집단이 없습니다'));
run("R.district=R.gender=R.age='전체';R.month='2026-09'");
assert.equal(run("responseRows().every(r=>r.priority==='판단 보류' && r.reason==='월 집계 미완료')"),true);
assert.equal(run('responseRows().flatMap(recommendations).length'),0);
run("R.month='2026-07'");
assert.equal(run("responseRows().every(r=>r.reason==='전월 자료 없음')"),true);
run("R.month='2026-08';R.statuses[responseRows()[0].key]='검토 중'");
assert.equal(run('responseStatus(responseRows()[0])'),'검토 중');
run("S.city='춘천시'");
assert.equal(run("responseRows().every(r=>r.city==='춘천시')"),true);
assert.equal(run('responseStatus(responseRows()[0])'),'미확인');
console.log('PASS: group signals, missing/partial months, filters, service gating, city-scoped status');
