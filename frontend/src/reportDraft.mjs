// 초안 수정 버튼을 누른 경우 기존 임시 초안보다 전달된 초안을 우선합니다.
export function importReportDraft(local, seed, context) {
  if (!seed) return null;
  const seedId = JSON.stringify(seed);
  if (local.seedId === seedId) return null;

  // 다른 지역·기간·연령의 초안이 현재 화면에 섞이지 않게 합니다.
  const sameContext = ['city', 'district', 'month', 'age'].every(
    (key) => (seed.context?.[key] || '') === (context[key] || ''),
  );
  if (!sameContext) {
    return null;
  }
  return {
    ...local,
    previousContent: local.content,
    content: seed,
    selection: seed.selection ?? null,
    seedId,
  };
}
