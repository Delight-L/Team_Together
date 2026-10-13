import React, { lazy, Suspense } from 'react';

// 지도 라이브러리는 로그인 후 지도 화면을 열 때 불러옵니다.
// 입체(ReliefMap)는 WebGL을 쓸 수 없을 때 VectorMap 내부의 대체 지도로만 사용합니다.
const VectorMap = lazy(() => import('./VectorMap'));

export function MissionMap(props) {
  return <div className={`mission-map-switchable ${props.flat ? '' : 'single-overview'}`}>
    <Suspense fallback={<div className="empty" role="status">지역 지도를 준비하고 있습니다…</div>}>
      <VectorMap {...props} />
    </Suspense>
  </div>;
}
