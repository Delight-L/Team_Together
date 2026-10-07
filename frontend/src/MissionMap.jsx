import React, { lazy, Suspense, useState } from 'react';
import { ReliefMap } from './ReliefMap';

// 지도 라이브러리는 로그인 후 지도 화면을 열 때 불러옵니다.
const VectorMap = lazy(() => import('./VectorMap'));

export function MissionMap(props) {
  const [mode, setMode] = useState('road');
  return <div className={`mission-map-switchable ${props.flat ? '' : 'single-overview'}`}>
    {props.flat && <div className="map-view-toggle" role="group" aria-label="지도 표현 방식">
      <button aria-pressed={mode === 'relief'} onClick={() => setMode('relief')}>입체</button>
      <button aria-pressed={mode === 'road'} onClick={() => setMode('road')}>도로</button>
    </div>}
    {props.flat && mode === 'relief' ? <ReliefMap {...props} /> :
      <Suspense fallback={<div className="empty" role="status">지역 지도를 준비하고 있습니다…</div>}>
        <VectorMap {...props} />
      </Suspense>}
  </div>;
}
