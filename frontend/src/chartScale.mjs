// 선 그래프 세로축 범위: 0부터 그리면 90~95처럼 좁은 변화가 평평하게 보이므로 자료 범위에 맞춥니다.
// 값이 모두 0 이상이면 아래쪽은 0 밑으로 내려가지 않게 합니다.

function niceStep(raw) {
  const power = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / power;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * power;
}

export function fitDomain(values, { pad = 0.15 } = {}) {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return { low: 0, high: 1, ticks: [0, 0.5, 1], fromZero: true };
  let min = Math.min(...finite), max = Math.max(...finite);
  // 값이 하나뿐이거나 모두 같으면 위아래로 조금 벌려 선이 가운데 오게 합니다.
  const spread = max - min || Math.abs(max) * 0.1 || 1;
  min -= spread * pad;
  max += spread * pad;
  if (Math.min(...finite) >= 0) min = Math.max(0, min);
  // 눈금 세 개(아래·가운데·위)가 읽기 쉬운 숫자가 되도록 간격을 맞춥니다.
  const step = niceStep((max - min) / 2);
  const low = Math.floor(min / step) * step;
  const high = Math.max(low + 2 * step, Math.ceil(max / step) * step);
  const mid = (low + high) / 2;
  return { low, high, ticks: [low, mid, high], fromZero: low === 0 };
}
