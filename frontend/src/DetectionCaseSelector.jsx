import React from 'react';
import './detection-case-selector.css';

export default function DetectionCaseSelector({items, selected, onSelect, disabled=false, loading=false}) {
  const current=items.find(item => item.district===selected?.district && item.age===selected?.age);
  const key=item => `${item.code || item.district}/${item.age}`;
  return <label className="detection-case-selector">
    <span>탐지 사례 {items.length}건</span>
    <select aria-label="탐지 사례 선택" value={current ? key(current) : ''} disabled={disabled || loading || !items.length}
      onChange={event => {const item=items.find(item => key(item)===event.target.value);if(item) onSelect(item);}}>
      {!current && <option value="">{loading ? '사례 확인 중…' : items.length ? '행정동 · 연령대 선택' : '선택한 월의 탐지 사례 없음'}</option>}
      {items.map(item => <option key={key(item)} value={key(item)}>{item.district} · {item.age}</option>)}
    </select>
  </label>;
}
