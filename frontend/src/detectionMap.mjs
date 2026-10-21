export const DETECTION_METHODS = {
  absolute: { label: '자체 과거 비교', color: '#eab308' },
  local: { label: '공통 변화 제거 후 비교', color: '#14b8a6' },
  both: { label: '두 비교 모두', color: '#f36e7b' },
};

// Classify each age/domain first. Never combine independent cases into a both-method signal.
export function detectionMapRegions(regions, tracking, month) {
  if (!tracking?.available) return regions;
  return regions.map((region) => {
    const events = tracking.events.filter(
      (e) => e.district === region.name && e.signalMonth === month,
    );
    const cases = events.flatMap((e) =>
      ['communication', 'mobility'].flatMap((domain) => {
        const signal = e.signals[domain] || {};
        const method =
          signal.absolute && signal.local
            ? 'both'
            : signal.absolute
              ? 'absolute'
              : signal.local
                ? 'local'
                : null;
        return method ? [{ age: e.age, domain, method }] : [];
      }),
    );
    const methods = Object.keys(DETECTION_METHODS).filter((m) => cases.some((c) => c.method === m));
    return {
      ...region,
      count: events.length,
      detectionMode: true,
      detectionMethods: methods,
      detectionCases: cases,
    };
  });
}

export function detectionDescription(region) {
  return (region.detectionCases || [])
    .map(
      (c) =>
        `${c.age} ${c.domain === 'communication' ? '통신' : '이동'} · ${DETECTION_METHODS[c.method].label}`,
    )
    .join(' / ');
}

export function detectionMethodsForAge(region, age) {
  return Object.keys(DETECTION_METHODS).filter((method) =>
    (region?.detectionCases || []).some((item) => item.age === age && item.method === method),
  );
}
