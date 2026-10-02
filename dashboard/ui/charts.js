// ============================================================
// 파트 3. 위험도 추이 그래프
// ============================================================
// 여기만 바꾸면 같은 데이터로 꺾은선 / 영역 / 막대를 연습할 수 있습니다.
// 기본 그래프는 'line'입니다. 다른 종류는 'area' 또는 'bar'로 바꾸세요.
const TREND_CHART_TYPE = "line";

function chartSVG(series, labels, description) {
  // SVG 그림 크기와 안쪽 여백을 설정합니다.
  const W = 600,
    H = 220,
    L = 34,
    R = 12,
    T = 12,
    B = 26;
  const values = series.flatMap((item) => item.v).filter(Number.isFinite);
  let min = Math.floor(Math.min(...values, TH[0]) / 10) * 10;
  const max = Math.ceil(Math.max(...values, TH[2] + 2) / 10) * 10;
  if (max - min < 30) min = max - 30;

  // 데이터 값 → 그림 좌표. y 좌표는 아래로 커지므로 점수와 반대로 계산합니다.
  const X = (index) =>
    L + (labels.length === 1 ? 0 : (index * (W - L - R)) / (labels.length - 1));
  const Y = (value) => T + ((max - value) * (H - T - B)) / (max - min);
  let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${description}">`;

  // 세로축 숫자와 가로 눈금선.
  for (let value = min; value <= max; value += 10) {
    svg += `<line class="gl" x1="${L}" x2="${W - R}" y1="${Y(value)}" y2="${Y(value)}"/><text x="${L - 6}" y="${Y(value) + 4}" text-anchor="end">${value}</text>`;
  }

  // 위험·심각 기준선을 점선으로 표시합니다.
  [
    [TH[1], "--b2", "위험"],
    [TH[2], "--b3", "심각"],
  ].forEach(([value, color, name]) => {
    if (value > min && value < max) {
      svg += `<line class="thl" x1="${L}" x2="${W - R}" y1="${Y(value)}" y2="${Y(value)}" stroke="var(${color})"/><text x="${W - R}" y="${Y(value) - 3}" text-anchor="end" style="fill:var(${color})">${name} ${value}↑</text>`;
    }
  });

  const step = Math.ceil(labels.length / 6);
  labels.forEach((label, index) => {
    if (index % step === 0 || index === labels.length - 1) {
      svg += `<text x="${X(index)}" y="${H - 8}" text-anchor="middle">${label}</text>`;
    }
  });

  // 지역 평균과 선택 동을 각각 그립니다. 결측 날짜에서는 선을 끊습니다.
  series.forEach((item, seriesIndex) => {
    let path = "",
      connected = false;
    const groups = [];
    let group = [];
    item.v.forEach((value, index) => {
      if (!Number.isFinite(value)) {
        connected = false;
        if (group.length) groups.push(group);
        group = [];
        return;
      }
      path += `${connected ? "L" : "M"}${X(index).toFixed(1)} ${Y(value).toFixed(1)}`;
      connected = true;
      group.push([index, value]);
      if (TREND_CHART_TYPE === "bar") {
        const width = Math.min(
          16,
          (W - L - R) / Math.max(labels.length, 1) / (series.length + 1),
        );
        const x = X(index) + (seriesIndex - (series.length - 1) / 2) * width;
        svg += `<rect x="${x - width / 2}" y="${Y(value)}" width="${width}" height="${Y(min) - Y(value)}" fill="${item.c}"/>`;
      }
    });
    if (group.length) groups.push(group);
    if (TREND_CHART_TYPE === "area") {
      groups.forEach((points) => {
        const first = points[0][0],
          last = points[points.length - 1][0];
        const outline =
          "M" +
          points
            .map(([i, v]) => `${X(i).toFixed(1)} ${Y(v).toFixed(1)}`)
            .join("L");
        svg += `<path d="${outline}L${X(last)} ${Y(min)}L${X(first)} ${Y(min)}Z" fill="${item.c}" opacity="0.15"/>`;
      });
    }
    if (TREND_CHART_TYPE !== "bar") {
      svg += `<path d="${path}" fill="none" stroke="${item.c}" stroke-width="${item.w}" stroke-linejoin="round" stroke-linecap="round"/>`;
      const index = item.v.length - 1;
      if (Number.isFinite(item.v[index])) {
        svg += `<circle cx="${X(index)}" cy="${Y(item.v[index])}" r="${item.w + 1.5}" fill="${item.c}"><title>${item.name} ${f1(item.v[index])}</title></circle>`;
      }
    }
  });
  return svg + "</svg>";
}
