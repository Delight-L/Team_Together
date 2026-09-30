// 데이터 계산과 새 컴포넌트의 JavaScript 문법을 검사합니다. 브라우저 제어 도구가 아닙니다.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const assert = require('assert/strict');
const boot = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const ui = path.join(__dirname, 'ui');
const csvContext = vm.createContext({BOOT:boot});
vm.runInContext(fs.readFileSync(path.join(ui,'data.js'),'utf8'), csvContext);
const original = fs.readFileSync(path.join(__dirname,'isolation-dashboard_260921.html'),'utf8');
const originalContext = vm.createContext({});
vm.runInContext(original.slice(original.indexOf('const GEO='), original.indexOf('/* ===== UI ===== */')), originalContext);

// 현재 값뿐 아니라 일별 비교·월평균·가중치 변경이 원본 공식과 같은지 확인합니다.
let checked = 0;
for (const [city, geometry] of Object.entries(boot.geometry)) {
    for (const unit of geometry.units) {
        for (const [mode, period] of [['day','2026-09-20'],['day','2026-09-13'],['month','2026-09'],['month','2026-08']]) {
            for (const weights of [[25,25,20,15,15],[40,5,20,30,10]]) {
                const code = `scoreAt(${JSON.stringify(city)},${JSON.stringify(unit.n)},${JSON.stringify(mode)},${JSON.stringify(period)},${JSON.stringify(weights)})`;
                const actual = vm.runInContext(code,csvContext);
                const expected = vm.runInContext(code,originalContext);
                assert(Math.abs(actual-expected)<1e-10,`${city} ${unit.n} ${period}`);
                checked++;
            }
        }
    }
}
assert.equal(vm.runInContext("scoreAt('강남구','역삼1동','day','1900-01-01',DEFW)",csvContext),null);
// 함수로 구성해 구문만 검사합니다. 화면 이벤트를 실행하지 않습니다.
new Function(fs.readFileSync(path.join(ui,'data.js'),'utf8') + fs.readFileSync(path.join(ui,'charts.js'),'utf8') + fs.readFileSync(path.join(ui,'dashboard.js'),'utf8'));
console.log(JSON.stringify({calculationComparisons:checked,syntax:'PASS',missingData:'PASS'}));
