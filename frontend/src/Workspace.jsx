import React, { useRef, useState } from 'react';
import { api } from './api';
import { personName } from './personas.mjs';
import { useApiQuery } from './useApiQuery';
import { useTransientMessage } from './useTransientMessage';

// 사업 매칭 검토와 보고서 저장의 진행 상황을 보여 줍니다. 사업 검토는 선택이라 보고서를 막지 않습니다(구상 보고서).
// 지역 분석은 참고 화면이며 업무 단계가 아닙니다. 첫 사업 검토나 보고서를 저장할 때 서버가 분석 근거를 함께 기록합니다.
// workflow.done: 2 사업 검토 저장, 3 보고서 저장(0·1은 처음 저장할 때 자동 기록)
export function WorkflowSteps({ context, workflow, current, onView }) {
  const steps = [
    { key: 'services', label: '사업 매칭 검토', optional: true, done: workflow.done?.includes(2) },
    { key: 'report', label: '보고서 저장', done: !!workflow.workflow_complete },
  ];
  const index = steps.findIndex((s) => s.key === current);
  // 순서 제약이 없으므로 막힘 조건은 동 선택 하나뿐입니다.
  const blocker = !context.district ? { key: 'map', label: '지역 선택' } : null;
  return (
    <div className={`workflow-steps ${blocker ? 'blocked' : ''}`}>
      <ol aria-label="업무 진행 단계">
        {steps.map((s, i) => (
          <li key={s.key} className={`${s.done ? 'done' : ''} ${i === index ? 'current' : ''}`}>
            <span aria-hidden="true">{s.done ? '✓' : i + 1}</span>
            <b>{s.label}</b>
            {s.done ? (
              <small>완료</small>
            ) : i === index ? (
              <small>지금 단계</small>
            ) : s.optional ? (
              <small>선택</small>
            ) : null}
          </li>
        ))}
      </ol>
      {blocker && (
        <p role="status">
          <span>
            {blocker.key === 'map'
              ? '먼저 살펴볼 동을 선택해야 이 단계를 진행할 수 있습니다.'
              : `‘${blocker.label}’ 단계를 먼저 저장해야 이 단계를 진행할 수 있습니다.`}
          </span>
          <button className="primary" onClick={() => onView(blocker.key)}>
            {blocker.key === 'map' ? '지역 선택하러 가기' : `${blocker.label} 하러 가기`} →
          </button>
        </p>
      )}
    </div>
  );
}

export function Activity() {
  const { data, error, loading, reload } = useApiQuery('/activity');
  const rows = data?.activity || [];
  const [search, setSearch] = useState(''),
    [kind, setKind] = useState('');
  const kinds = [...new Set(rows.map((row) => row.kind).filter(Boolean))];
  const shown = rows
    .filter(
      (row) =>
        (!kind || row.kind === kind) &&
        [row.created_at, personName(row.actor), row.kind, row.detail, row.result].some((value) =>
          String(value || '').includes(search.trim()),
        ),
    )
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  return (
    <div className="scroll-view">
      <section className="card info-card">
        <h2>DB1 활동 이력</h2>
        <p>기존 DB1에 저장된 데이터 반영 이력을 조회합니다.</p>
        <div className="management-toolbar">
          <label>
            이력 검색
            <input
              aria-label="활동 이력 검색"
              value={search}
              placeholder="담당자·내용·결과"
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <label>
            작업 종류
            <select aria-label="활동 종류" value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="">전체</option>
              {kinds.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <button className="secondary" disabled={loading} onClick={reload}>
            {loading ? '불러오는 중…' : '새로고침'}
          </button>
          {(search || kind) && (
            <button
              className="text-button"
              onClick={() => {
                setSearch('');
                setKind('');
              }}
            >
              조건 초기화
            </button>
          )}
        </div>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {loading && (
          <p className="hint" role="status">
            활동 이력을 불러오고 있습니다…
          </p>
        )}
        {data && (
          <p className="hint">
            전체 {rows.length}건 · 검색 결과 {shown.length}건 · 최신순
          </p>
        )}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>시각</th>
                <th>담당자</th>
                <th>종류</th>
                <th>내용</th>
                <th>결과</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r, i) => (
                <tr key={i}>
                  <td>{r.created_at}</td>
                  <td>{personName(r.actor)}</td>
                  <td>{r.kind}</td>
                  <td>{r.detail}</td>
                  <td>{r.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!loading && !error && !rows.length && <p className="hint">저장된 활동 이력이 없습니다.</p>}
        {!loading && !error && rows.length > 0 && !shown.length && (
          <p className="hint">검색 조건에 맞는 이력이 없습니다.</p>
        )}
      </section>
    </div>
  );
}

// FileReader는 파일을 브라우저에서 읽는 API입니다.
// base64로 인코딩해 Python에 전달하며, 파일 내용이나 검사 결과를 Git에 넣지 않습니다.
const encodeFile = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, content: reader.result.split(',')[1] });
    reader.onerror = () => reject(new Error('파일을 읽지 못했습니다.'));
    reader.readAsDataURL(file);
  });
export function Upload({ onPublished }) {
  const fileInput = useRef(null);
  const [kind, setKind] = useState('monthly'),
    [files, setFiles] = useState([]),
    [prepared, setPrepared] = useState(null),
    [busy, setBusy] = useState(false),
    [publishedRun, setPublishedRun] = useTransientMessage();
  const [notice, setNotice] = useTransientMessage();
  async function validate() {
    setBusy(true);
    setNotice('');
    setPrepared(null);
    try {
      if (!files.length) throw new Error('파일을 선택하세요.');
      if (
        files.some((f) => f.size > 15_000_000) ||
        files.reduce((sum, f) => sum + f.size, 0) > 20_000_000
      )
        throw new Error('파일당 15MB, 전체 20MB 이하로 선택하세요.');
      setPrepared(
        await api('/upload/validate', { kind, files: await Promise.all(files.map(encodeFile)) }),
      );
    } catch (e) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function publish() {
    setBusy(true);
    try {
      const result = await api('/upload/publish', { token: prepared.token });
      setNotice('');
      setPrepared(null);
      setPublishedRun(result.runId);
      setFiles([]);
      if (fileInput.current) fileInput.current.value = '';
      onPublished?.();
    } catch (e) {
      setNotice(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card info-card">
      <span className="eyebrow">ADMIN DATA MANAGEMENT</span>
      <h2>데이터 검사와 DB1 반영</h2>
      <p>검사 → 미리보기 → DB1 반영 순서로 진행합니다. 기존 버전은 보관됩니다.</p>
      <p>반영한 분석 결과는 화면에서 다시 불러옵니다. 이전 버전과 업로드 이력은 보관됩니다.</p>
      <div className="review-form">
        <label>
          자료 종류
          <select
            value={kind}
            disabled={busy}
            onChange={(e) => {
              setKind(e.target.value);
              setPrepared(null);
              setFiles([]);
              setNotice('');
              if (fileInput.current) fileInput.current.value = '';
            }}
          >
            <option value="monthly">동별 통화·문자·이동 분석 결과 (CSV/Excel)</option>
            <option value="structure">2025년 하반기 지역 배경자료 5종 · 독거노인 포함</option>
          </select>
        </label>
        <label>
          파일 선택
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.xlsx"
            multiple={kind === 'structure'}
            disabled={busy}
            onChange={(e) => {
              setFiles(Array.from(e.target.files));
              setPrepared(null);
              setNotice('');
            }}
          />
        </label>
        <button className="primary" disabled={busy || !files.length} onClick={validate}>
          {busy ? '처리 중…' : '업로드 자료 검사 및 분석'}
        </button>
      </div>
      <p className="hint">
        CSV/XLSX · 파일당 15MB, 전체 20MB 이하 ·{' '}
        {kind === 'monthly' ? '분석 결과 파일 1개' : '지역 배경자료 최대 5개'} · 검사 결과는 30분
        동안 반영할 수 있습니다.
      </p>
      {files.length > 0 && (
        <ul className="upload-files">
          {files.map((file) => (
            <li key={file.name}>
              {file.name} · {(file.size / 1_000_000).toFixed(2)}MB
            </li>
          ))}
        </ul>
      )}
      {publishedRun && (
        <p className="success" role="status">
          DB 반영 완료 · 결과 버전 {publishedRun}
        </p>
      )}
      {kind === 'structure' && (
        <p className="hint">
          SKT 구조자료·등록인구·세대수·생계급여 수급자·독거노인 CSV/XLSX를 선택하세요. 65세 이상
          등록인구 중 독거노인 비율은 2025년 독거노인 수와 2025년 4분기 인구를 기준으로 계산합니다.
        </p>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {prepared && (
        <>
          <h3 className="upload-summary">
            검사 완료 · {prepared.period} · {prepared.rows.toLocaleString()}행
          </h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {Object.keys(prepared.preview[0] || {}).map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {prepared.preview.map((r, i) => (
                  <tr key={i}>
                    {Object.entries(r).map(([k, v]) => (
                      <td key={k}>{String(v ?? '—')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <button className="primary" disabled={busy} onClick={publish}>
            검사한 결과를 DB1에 반영
          </button>
        </>
      )}
    </section>
  );
}
