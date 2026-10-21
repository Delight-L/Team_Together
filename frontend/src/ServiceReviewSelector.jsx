import React from 'react';
import { reviewCaseKey, reviewMonthGroups } from './serviceReview.mjs';

const monthLabel = (month) => `${Number(month.slice(5))}월`;
export default function ServiceReviewSelector({
  items,
  selected,
  filter,
  onFilter,
  onSelect,
  busy,
  loading,
  unlistedLabel,
}) {
  const groups = reviewMonthGroups(items);
  const visible = filter === 'all' ? items : items.filter((item) => item.signalMonth === filter);
  return (
    <div className="service-review-picker">
      <div className="service-review-filters" role="group" aria-label="탐지월별 검토 사례">
        <button
          type="button"
          className={filter === 'all' ? 'active' : ''}
          aria-pressed={filter === 'all'}
          disabled={busy || loading}
          onClick={() => onFilter('all')}
        >
          전체 {items.length}건
        </button>
        {groups.map((group) => (
          <button
            type="button"
            key={group.month}
            className={filter === group.month ? 'active' : ''}
            aria-pressed={filter === group.month}
            disabled={busy || loading}
            onClick={() => onFilter(group.month)}
          >
            {monthLabel(group.month)} {group.lifecycle === 'new' ? '신규' : '탐지 · 추적 중'}{' '}
            {group.count}건
          </button>
        ))}
      </div>
      <label className="service-review-select">
        <span>검토 사례 {items.length}건</span>
        <select
          aria-label="검토 사례 선택"
          value={selected ? reviewCaseKey(selected) : ''}
          disabled={busy || loading || !visible.length}
          onChange={(event) => {
            const item = visible.find((item) => reviewCaseKey(item) === event.target.value);
            if (item) onSelect(item);
          }}
        >
          {!selected && (
            <option value="">
              {loading ? '사례 확인 중…' : unlistedLabel || '검토할 탐지 사례 없음'}
            </option>
          )}
          {visible.map((item) => (
            <option key={reviewCaseKey(item)} value={reviewCaseKey(item)}>
              {item.district} · {item.age} | {monthLabel(item.signalMonth)} 탐지 ·{' '}
              {item.lifecycle === 'new' ? '신규' : '추적 중'}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
