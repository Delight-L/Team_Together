import React, { useEffect, useState } from 'react';
import { api } from './api';

// 기존 SQLite 기록에서 로그인한 담당자의 업무만 조회합니다.
// onResume은 App에서 받은 함수로 지역/월/화면을 한 번에 바꿉니다.
export function Missions({ onResume }) {
  const [items, setItems] = useState([]),
    [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    api('/missions')
      .then((d) => active && setItems(d.items))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, []);
  return (
    <div className="scroll-view">
      <section className="card info-card">
        <h2>지역별 업무 현황</h2>
        <p>담당자별로 저장된 지역·기준월 업무를 이어서 진행합니다.</p>
        {error && <p className="error">{error}</p>}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>지역</th>
                <th>기준월</th>
                <th>진행</th>
                <th>상태</th>
                <th>업무</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={i}>
                  <td>
                    {item.city} · {item.district}
                  </td>
                  <td>{item.month}</td>
                  <td>{(item.workflow.done || []).filter((n) => n > 0).length}/3</td>
                  <td>
                    {item.workflow.workflow_complete
                      ? '업무 완료'
                      : item.workflow.done?.includes(2)
                        ? '보고서 대기'
                        : '분석·검토 중'}
                  </td>
                  <td>
                    <button className="text-button" onClick={() => onResume(item)}>
                      이어서 보기 →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!items.length && !error && (
          <p className="hint">저장된 업무가 없습니다. 지역 분석에서 분석 확인을 저장하세요.</p>
        )}
      </section>
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
