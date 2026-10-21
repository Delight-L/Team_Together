import React from 'react';
import { serviceCardContent } from './serviceCandidate.mjs';
import './service-candidate.css';

export default function ServiceCandidate({
  match,
  context,
  selected,
  disabled,
  onReview,
  fromChat,
}) {
  const service = match.service;
  const content = serviceCardContent(service);
  const reasons = match.reasons || [];
  const checks = (match.additional_checks || []).filter(
    (text) => !text.startsWith('이용 가능 지역·현재 접수 여부'),
  );
  const conditions = checks.length ? checks : ['운영 장소 · 이용 절차 · 접수 여부'];
  return (
    <div className="service-candidate">
      <div className="candidate-heading">
        <h3>
          {service.name}
          {fromChat && <small className="service-chat-badge"> · 보미 안내</small>}
        </h3>
        {match.sector && <span className="candidate-sector">{match.sector}</span>}
        {match.match_label && (
          <span
            className={`candidate-status ${match.match_level !== 'age_area' ? 'conditional' : ''}`}
          >
            {match.match_label}
          </span>
        )}
      </div>
      <p className="candidate-introduction">{content.introduction}</p>
      <dl className="candidate-facts">
        <div>
          <dt>지원 대상</dt>
          <dd>{content.target}</dd>
        </div>
        <div>
          <dt>확인할 조건</dt>
          <dd>
            {conditions.slice(0, 2).join(' · ')}
            {conditions.length > 2 && <span> 외 {conditions.length - 2}개 조건</span>}
          </dd>
        </div>
      </dl>
      <div className="candidate-connection">
        <b>조회 기준</b>
        <p>{match.criteria_summary || '지역·연령 조건과 세부 이용 자격을 확인하세요.'}</p>
      </div>
      {match.benefit_notes?.length > 0 && (
        <ul className="candidate-benefit-notes">
          {match.benefit_notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      <div className="candidate-actions">
        <details className="candidate-details">
          <summary>상세 내용 보기</summary>
          <div className="candidate-detail-content">
            <p className="candidate-qualification">
              지원 필요·이용 자격이 확정된 결과는 아닙니다. 요약에서 생략된 세부 조건을 확인하세요.
            </p>
            {service.detail_pending && (
              <p>
                {service.detail_checked_at
                  ? '상세 재확인 대기 · 이전에 수집한 상세정보입니다.'
                  : '상세 수집 대기 · 현재 목록 정보만 제공됩니다.'}
              </p>
            )}
            <dl>
              {content.details.map((item) => (
                <div key={item.labels.join('/')}>
                  <dt>{item.labels.join(' · ')}</dt>
                  <dd>{item.text}</dd>
                </div>
              ))}
            </dl>
            <h4>대상·이용 조건 원문</h4>
            {reasons.map((reason) => (
              <div className="candidate-reason" key={reason.category}>
                <b>{reason.category}</b>
                <p>{reason.check_question}</p>
                {[...new Set((reason.purpose_evidence || []).map((item) => item.excerpt))]
                  .slice(0, 2)
                  .map((text) => (
                    <blockquote key={text}>{text}</blockquote>
                  ))}
              </div>
            ))}
            <h4>이용 전 확인</h4>
            {checks.length > 0 && (
              <ul>
                {checks.map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
            )}
            <p>
              게시 지역:{' '}
              {[
                service.province,
                service.district && service.district !== '-' ? service.district : '시·군·구 미지정',
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
            <p>
              선택 지역 {context.city} {context.district} 주민의 이용 가능 여부와 현재 접수
              여부·정원을 운영기관에 확인하세요.
            </p>
            <p>
              시행기간: {service.effective_start || '시작일 미확인'} ~{' '}
              {service.effective_end === '9999-12-31'
                ? '종료일 미지정'
                : service.effective_end || '종료일 미확인'}
            </p>
          </div>
        </details>
        {/^https?:\/\//i.test(service.source_url || '') && (
          <a href={service.source_url} target="_blank" rel="noopener noreferrer">
            사업 원문 보기 ↗
          </a>
        )}
        <button
          className="primary"
          disabled={disabled}
          aria-expanded={selected}
          aria-controls={selected ? 'service-review-form' : undefined}
          onClick={onReview}
        >
          {selected ? '검토 입력 닫기' : '이 사업 검토 →'}
        </button>
      </div>
    </div>
  );
}
