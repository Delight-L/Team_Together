// 원본 HTML의 샘플 값을 CSV/JSON으로 옮기는 일회성 도구입니다.
// Streamlit을 실행할 때는 이 파일이나 원본 HTML이 필요하지 않습니다.
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const html = fs.readFileSync(
  path.join(__dirname, "isolation-dashboard_260921.html"),
  "utf8",
);
const start = html.indexOf("const GEO=");
const end = html.indexOf("/* ===== UI ===== */");
if (start < 0 || end < start)
  throw new Error("원본 데이터 구간을 찾지 못했습니다.");
const context = vm.createContext({});
// 화면 코드 대신 확인된 지도 상수와 샘플 계산 함수만 실행합니다.
vm.runInContext(html.slice(start, end), context, { timeout: 10000 });
const result = vm.runInContext(
  `(() => {
  const rows = [];
  for (let d=toD('2025-08-01'); d<=END; d++) {
    for (const city of Object.keys(GEO)) {
      for (const unit of GEO[city].units) {
        rows.push([fmtD(d), city, unit.n, ...fac(city, unit.n, d)]);
      }
    }
  }
  return {geo:GEO, rows};
})()`,
  context,
  { timeout: 20000 },
);
const peopleStart = html.indexOf("const PEOPLE=");
const peopleEnd = html.indexOf("function viewUsers()");
vm.runInContext(html.slice(peopleStart, peopleEnd), context);
const people = vm.runInContext(
  `Object.keys(GEO).flatMap(city => people(city).map((p,i) => [city+'-'+String(i+1).padStart(3,'0'), city,p.name,p.age,p.u,p.s,p.why.join(' / '),p.st,p.last]))`,
  context,
);
const dataDir = path.join(__dirname, "data");
fs.mkdirSync(dataDir, { recursive: true });
const csv = (rows) =>
  "\uFEFF" +
  rows
    .map((row) =>
      row
        .map((value) => '"' + String(value).replaceAll('"', '""') + '"')
        .join(","),
    )
    .join("\n");
fs.writeFileSync(
  path.join(dataDir, "risk_factors.csv"),
  csv([
    ["date", "city", "district", "flow", "card", "single", "elder", "welfare"],
    ...result.rows,
  ]),
);
fs.writeFileSync(
  path.join(dataDir, "people.csv"),
  csv([
    [
      "person_id",
      "city",
      "name",
      "age",
      "district",
      "risk_score",
      "reason",
      "status",
      "last_contact",
    ],
    ...people,
  ]),
);
fs.writeFileSync(
  path.join(dataDir, "map_boundaries.json"),
  JSON.stringify(result.geo, null, 2),
);
console.log(
  JSON.stringify({
    riskRows: result.rows.length,
    people: people.length,
    cities: Object.keys(result.geo),
  }),
);
