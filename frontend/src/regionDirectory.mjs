// 목록과 분석 화면의 초기 선택에 같은 정렬 기준을 적용합니다.
export function candidateFirst(a, b) {
  const count = b.count - a.count;
  if (count) return count;
  const difference = (a.minZ ?? Infinity) - (b.minZ ?? Infinity);
  return (Number.isNaN(difference) ? 0 : difference) || a.name.localeCompare(b.name, 'ko');
}
