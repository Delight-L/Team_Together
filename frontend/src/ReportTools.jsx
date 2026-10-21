import React from 'react';
import { query } from './api';
import './report-tools.css';

export function ReportMaterials({ material, selection, onChange, disabled }) {
  if (!material) return null;
  const chosen = selection || {
    metrics: material.metrics,
    services: material.services.map((s) => s.key),
  };
  function toggle(type, key, checked) {
    onChange({
      ...chosen,
      [type]: checked ? [...chosen[type], key] : chosen[type].filter((k) => k !== key),
    });
  }
  return (
    <fieldset className="report-materials" disabled={disabled}>
      <legend>초안에 포함할 근거</legend>
      <p className="hint">
        선택은 새로 만드는 초안에 적용됩니다. 저장된 검토 기록은 그대로 보관됩니다.
      </p>
      <div className="report-material-columns">
        <div>
          <h4>분석 지표</h4>
          {material.metrics.map((label) => (
            <label key={label}>
              <input
                type="checkbox"
                checked={chosen.metrics.includes(label)}
                onChange={(e) => toggle('metrics', label, e.target.checked)}
              />
              {label}
            </label>
          ))}
        </div>
        <div>
          <h4>사업별 최신 검토</h4>
          {material.services.length ? (
            material.services.map((item) => (
              <label key={item.key}>
                <input
                  type="checkbox"
                  checked={chosen.services.includes(item.key)}
                  onChange={(e) => toggle('services', item.key, e.target.checked)}
                />
                <span>
                  {item.name} · {item.decision}
                </span>
              </label>
            ))
          ) : (
            <p className="hint">
              저장된 사업 검토가 없습니다. 구상·제안 내용을 직접 작성할 수 있습니다.
            </p>
          )}
        </div>
      </div>
      <p className="hint">
        지표 {chosen.metrics.length}개 · 사업 {chosen.services.length}개 선택 · 긴 내용은 보고서
        분량에 맞춰 요약됩니다.
      </p>
    </fieldset>
  );
}

export function ReportHistory({ versions, loading, error, context, onCopy, disabled }) {
  return (
    <details className="report-history">
      <summary>저장 이력{versions.length > 0 ? ` · ${versions.length}건` : ''}</summary>
      {loading && <p role="status">저장 이력을 불러오는 중…</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {!loading && !error && !versions.length && (
        <p className="hint">아직 저장한 보고서가 없습니다.</p>
      )}
      {versions.map((item) => (
        <article key={item.revision}>
          <div>
            <strong>
              {item.revision}차 · {item.title || '저장된 보고서'}
            </strong>
            <small>
              {item.created_at} · {item.department} · {item.author}
            </small>
          </div>
          <div className="form-actions">
            <a
              className="secondary"
              href={'/api/report?' + query({ ...context, revision: item.revision })}
            >
              Word 내려받기
            </a>
            <button
              className="secondary"
              disabled={disabled || !item.content}
              onClick={() => onCopy(item)}
            >
              복사해 이어쓰기
            </button>
          </div>
          {!item.content && (
            <p className="hint">이전 형식으로 저장된 문서는 Word 파일로 확인할 수 있습니다.</p>
          )}
        </article>
      ))}
    </details>
  );
}

export function ReportReadingPreview({ content, author, department, contact, month, fields }) {
  return (
    <details className="report-reading-preview" open>
      <summary>본문 미리보기</summary>
      <p className="hint">
        현재 입력한 내용을 읽기 형태로 보여줍니다. 페이지 나눔과 최종 서식은 Word 파일에서
        확인하세요.
      </p>
      <article className="report-paper" aria-label="보고서 본문 미리보기">
        <h2>{content.title}</h2>
        <p className="report-paper-meta">
          {month} 기준 · {department} · {author}
          {contact && ` · ${contact}`}
        </p>
        {fields
          .filter((f) => f.key !== 'title')
          .map((field) => (
            <section key={field.key}>
              <h3>{field.label}</h3>
              <p>{content[field.key]}</p>
            </section>
          ))}
      </article>
    </details>
  );
}
