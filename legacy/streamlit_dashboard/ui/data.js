// 파트 1. Python에서 읽은 CSV와 설정을 화면 데이터로 연결합니다.
// BOOT.riskRows: [날짜, 지자체, 행정동, 요인1, 요인2, ...]
const GEO = BOOT.geometry;
// 아래 짧은 이름은 기존 화면과 공유합니다.
// FN=요인 이름, FS=짧은 이름, FC=색, DEFW=기본 가중치, TH=기준 점수.
const DAY = 86400000; // 하루를 밀리초로 나타낸 값입니다.
const toD = (value) => Math.round(Date.parse(value + "T00:00:00Z") / DAY);
const fmtD = (value) => new Date(value * DAY).toISOString().slice(0, 10);
const END = toD(BOOT.endDate);
const MIN_DAY = Math.max(toD(BOOT.startDate), END - 365);
const FN = BOOT.factorNames;
const FS = BOOT.factorShortNames;
const FC = BOOT.factorColors;
const DEFW = BOOT.weights;
const TH = BOOT.thresholds;
const BN = ["양호", "주의", "위험", "심각"];
const MONTHS = BOOT.months.slice(-12);
// 단계 번호: 자료 없음=-1, 양호=0, 주의=1, 위험=2, 심각=3.
function bandOf(value) {
  if (!Number.isFinite(value)) return -1;
  if (value < TH[0]) return 0;
  if (value < TH[1]) return 1;
  if (value < TH[2]) return 2;
  return 3;
}

const FACTOR_ROWS = new Map();
for (const row of BOOT.riskRows) {
  const key = row[1] + "|" + row[2] + "|" + toD(row[0]);
  FACTOR_ROWS.set(key, row.slice(3));
}

// 파트 2. 일별 / 월별 요인과 가중 평균. 자료 없는 날짜를 0점으로 만들지 않습니다.
function fac(city, district, day) {
  return (
    FACTOR_ROWS.get(city + "|" + district + "|" + day) || FN.map(() => null)
  );
}

function scoreOf(factors, weights) {
  for (const value of factors) {
    if (!Number.isFinite(value)) return null;
  }
  let total = 0;
  for (const weight of weights) total += weight;
  if (total <= 0) return null;
  // 위험도 = (요인1×가중치1 + ... + 요인5×가중치5) / 가중치 합계
  let weightedSum = 0;
  for (let index = 0; index < factors.length; index++) {
    weightedSum += factors[index] * weights[index];
  }
  return weightedSum / total;
}

function monthRange(month) {
  const [year, number] = month.split("-").map(Number);
  return [
    Date.UTC(year, number - 1, 1) / DAY,
    Math.min(END, Date.UTC(year, number, 0) / DAY),
  ];
}

const MONTH_CACHE = new Map();
function monthF(city, district, month) {
  const key = city + "|" + district + "|" + month;
  if (MONTH_CACHE.has(key)) return MONTH_CACHE.get(key);
  const [start, end] = monthRange(month);
  const sum = FN.map(() => 0);
  let count = 0;
  for (let day = start; day <= end; day++) {
    const values = fac(city, district, day);
    if (values.some((value) => !Number.isFinite(value))) continue;
    values.forEach((value, index) => {
      sum[index] += value;
    });
    count++;
  }
  let mean = FN.map(() => null);
  if (count > 0) mean = sum.map((value) => value / count);
  MONTH_CACHE.set(key, mean);
  return mean;
}

function prevMonth(month) {
  const [year, number] = month.split("-").map(Number);
  return new Date(Date.UTC(year, number - 2, 1)).toISOString().slice(0, 7);
}
function factorsAt(city, district, mode, period) {
  if (mode === "day") return fac(city, district, toD(period));
  return monthF(city, district, period);
}
function scoreAt(city, district, mode, period, weights) {
  return scoreOf(factorsAt(city, district, mode, period), weights);
}
function prevScore(city, district, mode, period, weights) {
  let previousFactors;
  if (mode === "day") {
    previousFactors = fac(city, district, toD(period) - 7);
  } else {
    previousFactors = monthF(city, district, prevMonth(period));
  }
  return scoreOf(previousFactors, weights);
}
