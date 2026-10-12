import React, { useEffect, useState } from 'react';
import { api } from './api';
import { ReviewWorkspace } from './Experience';

const nextStep = (workflow) => workflow?.workflow_complete || workflow?.done?.includes(2)
  ? ['report', '보고서 작성']
  : workflow?.done?.includes(1) ? ['services', '사업 매칭 검토'] : ['chart', '지역 분석'];
const statusOf = (workflow) => workflow.workflow_complete ? '업무 완료' : workflow.done?.includes(2) ? '보고서 대기' : '분석·검토 중';

// 업무 기록: 왼쪽은 담당자가 저장한 지역 업무 목록, 오른쪽은 선택한 업무의 검토·후속 조치 기록입니다.
// 목록에서 업무를 고르면 App의 지역·기준월이 함께 바뀌어 다른 메뉴도 같은 업무를 보게 됩니다.
export function Records({ context, user, reviewSeed, onReviewSaved, onSelect, onView }) {
  const [items, setItems] = useState([]),
    [error, setError] = useState(''),
    [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let active = true;
    api('/missions')
      .then((d) => active && setItems(d.items))
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoaded(true));
    return () => {
      active = false;
    };
  }, []);
  const isCurrent = (item) => item.city === context.city && item.district === context.district && item.month === context.month;
  const current = items.find(isCurrent);
  const [nextView, nextLabel] = nextStep(current?.workflow);
  return (
    <div className="scroll-view records-layout">
      <section className="card info-card records-list" aria-label="지역별 업무 목록">
        <h2>지역별 업무</h2>
        <p className="hint">분석 확인을 저장한 지역·기준월이 여기에 쌓입니다.</p>
        {error && <p className="error" role="alert">{error}</p>}
        {!loaded && !error && <p className="hint" role="status">업무 목록을 불러오고 있습니다…</p>}
        {loaded && !items.length && !error && <p className="hint">저장된 업무가 없습니다. 지역 분석에서 분석 확인을 저장하세요.</p>}
        <ul>
          {items.map((item) => (
            <li key={item.city + item.district + item.month}>
              <button className={isCurrent(item) ? 'selected' : ''} aria-current={isCurrent(item) || undefined} onClick={() => onSelect(item)}>
                <span><b>{item.district}</b><small>{item.city} · {item.month}</small></span>
                <span className={`record-status ${item.workflow.workflow_complete ? 'done' : ''}`}>{statusOf(item.workflow)}</span>
                <span className="record-progress" title="근거 검토 → 사업 검토 → 보고서 중 마친 단계 수">{(item.workflow.done || []).filter((n) => n > 0).length}/3단계</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <div className="records-detail">
        {context.district ? <>
          <div className="records-next card">
            <span>{context.district} · {context.month}{current ? ` · ${statusOf(current.workflow)}` : ' · 아직 저장된 업무 없음'}</span>
            <button className="primary" onClick={() => onView(nextView)}>{current ? `${nextLabel} 이어서 하기` : '지역 분석에서 시작하기'} →</button>
          </div>
          <ReviewWorkspace key={user.id + JSON.stringify(context) + (reviewSeed?.id || '')} context={context} user={user} onView={onView} seed={reviewSeed} onSaved={onReviewSaved} />
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
  const [rows, setRows] = useState([]),
    [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api('/activity')
      .then((d) => active && setRows(d.activity))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, []);
  return (
    <div className="scroll-view">
      <section className="card info-card">
        <h2>DB1 활동 이력</h2>
        <p>기존 DB1에 저장된 데이터 반영 이력을 조회합니다.</p>
        {error && <p className="error">{error}</p>}
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
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.created_at}</td>
                  <td>{r.actor}</td>
                  <td>{r.kind}</td>
                  <td>{r.detail}</td>
                  <td>{r.result}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!rows.length && !error && <p className="hint">저장된 활동 이력이 없습니다.</p>}
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
export function Upload() {
  const [kind, setKind] = useState('monthly'),
    [files, setFiles] = useState([]),
    [prepared, setPrepared] = useState(null),
    [notice, setNotice] = useState(''),
    [busy, setBusy] = useState(false);
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
      setNotice('DB1 반영 완료 · ' + result.runId);
      setPrepared(null);
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
        현재 화면은 저장소의 Analysis2 CSV를 읽습니다. DB1 반영만으로 화면의 CSV가 교체되지는
        않습니다.
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
            }}
          >
            <option value="monthly">Analysis2 탐지 결과 CSV 또는 Excel</option>
            <option value="structure">지역 구조자료 원본 5종</option>
          </select>
        </label>
        <label>
          파일 선택
          <input
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
