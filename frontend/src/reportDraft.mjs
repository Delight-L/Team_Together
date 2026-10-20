// 초안 수정 버튼을 누른 경우 기존 임시 초안보다 전달된 초안을 우선합니다.
export function importReportDraft(local, seed, context) {
  if (!seed || local.seedId === JSON.stringify(seed) ||
    !['city', 'district', 'month', 'age'].every(key => (seed.context?.[key] || '') === (context[key] || ''))) return null;
  return { ...local, previousContent: local.content, content: seed,
    selection: seed.selection ?? null, seedId: JSON.stringify(seed) };
}
