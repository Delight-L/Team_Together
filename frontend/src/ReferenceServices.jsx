import React, { useState } from 'react';

const PAGE = 5;

function regionName(service) {
  const district = service.district && service.district !== '-' ? service.district : '시·군·구 미지정';
  return `${service.province || '시·도 미확인'} · ${district}`;
}

// 다른 지역 참고 사례 목록입니다. 검토 저장 버튼 없이 사업 내용과 원문 링크만 보여 줍니다.
// items: [{ service, terms }] — terms는 사업 내용에서 찾은 관련어입니다.
export function ReferenceServiceList({ items }) {
  const [shown, setShown] = useState(PAGE);
  return <>
    <ul className="reference-list">
      {items.slice(0, shown).map(({ service, terms }) => (
        <li key={service.service_id}>
          <span className="reference-region">{regionName(service)}</span>
          <b>{service.name}</b>
          {(service.support_text || service.summary) && <p>{service.support_text || service.summary}</p>}
          <small>관련어: {terms.join(', ') || '없음'}{service.detail_pending ? ' · 상세 수집 대기' : ''}</small>
          {/^https?:\/\//i.test(service.source_url || '') && (
            <a className="text-button" href={service.source_url} target="_blank" rel="noopener noreferrer">사업 안내 원문 확인 →</a>
          )}
        </li>
      ))}
    </ul>
    {items.length > shown && (
      <button className="secondary reference-more" onClick={() => setShown(shown + PAGE)}>
        더 보기 ({shown}/{items.length})
      </button>
    )}
  </>;
}
