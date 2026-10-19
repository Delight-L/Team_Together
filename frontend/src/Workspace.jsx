import React, { useRef, useState } from 'react';
import { api } from './api';
import { ReviewWorkspace } from './Experience';
import { personName } from './personas.mjs';
import { showToast } from './toast';
import { useApiQuery } from './useApiQuery';
import { useTransientMessage } from './useTransientMessage';

// 업무는 사업 검토 → (업무 기록) → 보고서 순서입니다. 지역 분석은 업무 단계가 아닙니다.
const nextStep = (workflow) => workflow?.workflow_complete || workflow?.done?.includes(2)
  ? ['report', '보고서 작성']
  : ['services', '사업 매칭 검토'];
const statusOf = (workflow) => workflow.workflow_complete ? '보고서 저장 완료' : workflow.done?.includes(2) ? '보고서 대기' : '사업 검토 전';

// 사업 매칭 검토 → 업무 기록(선택) → 보고서 순서를 보여 주고, 아직 하지 않은 앞 단계로 바로 이동하게 합니다.
// 지역 분석은 참고 화면이며 업무 단계가 아닙니다. 첫 사업 검토를 저장할 때 서버가 분석 근거를 함께 기록합니다.
// workflow.done: 2 사업 검토 저장, 3 보고서 저장(0·1은 사업 검토 저장 때 자동 기록)
// recordSaved: 업무 기록(검토·후속 조치)을 저장했는지. 모르면 undefined로 두어 '선택'으로만 표시합니다.
export function WorkflowSteps({ context, workflow, current, onView, recordSaved }) {
  const steps = [
    { key: 'services', label: '사업 매칭 검토', done: workflow.done?.includes(2) },
    { key: 'records', label: '업무 기록', optional: true, done: !!recordSaved },
    { key: 'report', label: '보고서 저장', done: !!workflow.workflow_complete },
  ];
  const index = steps.findIndex(s => s.key === current);
  // 업무 기록은 선택 단계라 막힘 조건도 아니고, 사업 검토 전에도 쓸 수 있습니다. 보고서는 사업 검토 저장만 필요합니다.
  const blocker = !context.district ? { key: 'map', label: '지역 선택' }
    : steps[index]?.optional ? null : steps.slice(0, index).find(s => !s.optional && !s.done);
  return <div className={`workflow-steps ${blocker ? 'blocked' : ''}`}>
    <ol aria-label="업무 진행 단계">{steps.map((s, i) => <li key={s.key} className={`${s.done ? 'done' : ''} ${i === index ? 'current' : ''}`}>
      <span aria-hidden="true">{s.done ? '✓' : i + 1}</span><b>{s.label}</b>{s.done ? <small>완료</small> : i === index ? <small>지금 단계</small> : s.optional ? <small>선택</small> : null}
    </li>)}</ol>
    {blocker && <p role="status"><span>{blocker.key === 'map' ? '먼저 살펴볼 동을 선택해야 이 단계를 진행할 수 있습니다.' : `‘${blocker.label}’ 단계를 먼저 저장해야 이 단계를 진행할 수 있습니다.`}</span>
      <button className="primary" onClick={() => onView(blocker.key)}>{blocker.key === 'map' ? '지역 선택하러 가기' : `${blocker.label} 하러 가기`} →</button></p>}
  </div>;
}

// 업무 기록: 왼쪽은 담당자가 저장한 지역 업무 목록, 오른쪽은 선택한 업무의 검토·후속 조치 기록입니다.
// 목록에서 업무를 고르면 App의 지역·기준월이 함께 바뀌어 다른 메뉴도 같은 업무를 보게 됩니다.
export function Records({ context, workflow, user, reviewSeed, onReviewSaved, onSelect, onView }) {
  const { data, error, loading, reload } = useApiQuery('/missions');
  const items = (data?.items || []).filter(item => item.city === context.city);
  const isCurrent = (item) => item.city === context.city && item.district === context.district && item.month === context.month && (item.age || '') === (context.age || '');
  const current = items.find(isCurrent);
  // 목록보다 App이 가진 현재 업무 상태가 최신입니다(다른 탭에서 방금 저장한 내용 포함).
  const [nextView, nextLabel] = nextStep(workflow || current?.workflow);
  const [recordSaved, setRecordSaved] = useState(undefined);
  return (
    <div className="scroll-view records-layout">
      <section className="card info-card records-list" aria-label="지역별 업무 목록">
        <h2>지역별 업무</h2>
        <p className="hint">사업 검토나 검토·후속 조치를 저장한 지역·기준월이 여기에 쌓입니다.</p>
        <button className="text-button" disabled={loading} onClick={reload}>업무 목록 새로고침</button>
        {error && <p className="error" role="alert">{error}</p>}
        {loading && <p className="hint" role="status">업무 목록을 불러오고 있습니다…</p>}
        {!loading && !items.length && !error && <p className="hint">저장된 업무가 없습니다. 사업 매칭 검토에서 첫 검토를 저장하세요.</p>}
        <ul>
          {items.map((item) => (
            <li key={item.city + item.district + item.month + (item.age || '')}>
              <button className={isCurrent(item) ? 'selected' : ''} aria-current={isCurrent(item) || undefined} onClick={() => onSelect(item)}>
                <span><b>{item.district}{item.age ? ` · ${item.age}` : ''}</b><small>{item.city} · {item.month}{item.workflow.previous_rounds?.length ? ` · ${item.workflow.previous_rounds.length + 1}회차` : ''}</small></span>
                <span className={`record-status ${item.workflow.workflow_complete ? 'done' : ''}`}>{statusOf(item.workflow)}</span>
                <span className="record-progress" title="사업 검토 → 보고서 중 마친 단계 수">{(item.workflow.done || []).filter((n) => n >= 2).length}/2단계</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <div className="records-detail">
        {context.district ? <>
          <WorkflowSteps context={context} workflow={workflow || current?.workflow || {}} current="records" onView={onView} recordSaved={recordSaved} />
          <div className="records-next card">
            <span>{context.district}{context.age ? ` · ${context.age}` : ''} · {context.month}{current ? ` · ${statusOf(current.workflow)}` : loading ? ' · 업무 목록 확인 중' : error ? ' · 업무 상태 조회 실패' : ' · 아직 저장된 업무 없음'}</span>
            <button className="primary" disabled={loading || (!!error && !current)} onClick={() => onView(nextView)}>{current?.workflow?.done?.length ? `${nextLabel} 이어서 하기` : '사업 매칭 검토에서 시작하기'} →</button>
          </div>
          <ReviewWorkspace key={user.id + JSON.stringify(context) + (reviewSeed?.id || '')} context={context} user={user} onView={onView} seed={reviewSeed} onSaved={() => { reload(); onReviewSaved?.(); }} onRecord={setRecordSaved} />
        </> : <section className="card info-card empty">
          <h2>업무를 선택하세요</h2>
          <p>왼쪽 목록에서 업무를 고르거나, 지역 현황에서 살펴볼 동을 선택하면 검토·후속 조치를 기록할 수 있습니다.</p>
          <button className="text-button" onClick={() => onView('map')}>지역 선택하러 가기 →</button>
        </section>}
      </div>
    </div>
  );
}

export function Activity() {
  const { data, error, loading, reload } = useApiQuery('/activity');
  const rows = data?.activity || [];
  const [search, setSearch] = useState(''), [kind, setKind] = useState('');
  const kinds = [...new Set(rows.map(row => row.kind).filter(Boolean))];
  const shown = rows.filter(row => (!kind || row.kind === kind) &&
    [row.created_at, personName(row.actor), row.kind, row.detail, row.result].some(value => String(value || '').includes(search.trim())))
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  return (
    <div className="scroll-view">
      <section className="card info-card">
        <h2>DB1 활동 이력</h2>
        <p>기존 DB1에 저장된 데이터 반영 이력을 조회합니다.</p>
        <div className="management-toolbar">
          <label>이력 검색<input aria-label="활동 이력 검색" value={search} placeholder="담당자·내용·결과" onChange={e => setSearch(e.target.value)} /></label>
          <label>작업 종류<select aria-label="활동 종류" value={kind} onChange={e => setKind(e.target.value)}><option value="">전체</option>{kinds.map(value => <option key={value}>{value}</option>)}</select></label>
          <button className="secondary" disabled={loading} onClick={reload}>{loading ? '불러오는 중…' : '새로고침'}</button>
          {(search || kind) && <button className="text-button" onClick={() => { setSearch(''); setKind(''); }}>조건 초기화</button>}
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        {loading && <p className="hint" role="status">활동 이력을 불러오고 있습니다…</p>}
        {data && <p className="hint">전체 {rows.length}건 · 검색 결과 {shown.length}건 · 최신순</p>}
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
        {!loading && !error && rows.length > 0 && !shown.length && <p className="hint">검색 조건에 맞는 이력이 없습니다.</p>}
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
      showToast('분석 자료를 DB1에 반영했어요 · ' + result.runId);
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
      <p>
        반영한 분석 결과는 화면에서 다시 불러옵니다. 이전 버전과
        업로드 이력은 보관됩니다.
      </p>
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
      <p className="hint">CSV/XLSX · 파일당 15MB, 전체 20MB 이하 · {kind === 'monthly' ? '분석 결과 파일 1개' : '지역 배경자료 최대 5개'} · 검사 결과는 30분 동안 반영할 수 있습니다.</p>
      {files.length > 0 && <ul className="upload-files">{files.map(file => <li key={file.name}>{file.name} · {(file.size / 1_000_000).toFixed(2)}MB</li>)}</ul>}
      {publishedRun && <p className="success" role="status">DB 반영 완료 · 결과 버전 {publishedRun}</p>}
      {kind === 'structure' && <p className="hint">SKT 구조자료·등록인구·세대수·생계급여 수급자·독거노인 CSV/XLSX를 선택하세요. 65세 이상 등록인구 중 독거노인 비율은 2025년 독거노인 수와 2025년 4분기 인구를 기준으로 계산합니다.</p>}
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
