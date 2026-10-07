import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api, query, number } from './api';
import { Icon, Bomi, RegionMap, EvidenceTable, Trend, ChatPanel } from './components';
import { Missions, Activity, Upload } from './Workspace';
import { Briefing, RegionalOverview, summarizeRegions } from './Briefing';
import { SupportDialog, ReviewWorkspace, Comparison, ReportQuality } from './Experience';

const menus = [
  ['dashboard', '종합 현황'],
  ['map', '지역 현황'],
  ['chart', '지역 분석'],
  ['compare', '지역·기간 비교'],
  ['followup', '검토·후속 조치'],
  ['missions', '업무 현황'],
  ['services', '사업 매칭 검토'],
  ['report', '보고서 작성'],
  ['data', '데이터 안내'],
];
const titles = {
  compare: '여러 지역과 월별 변화를 비교하세요',
  followup: '검토 의견과 실제 조치를 이어서 기록하세요',
  dashboard: '우리 지역의 작은 변화를 발견하세요',
  map: '지역별 변화 한눈에 살펴보기',
  chart: '변화의 근거를 자세히 살펴봐요',
  services: '필요한 지원으로 연결하는 첫걸음',
  report: '검토 결과를 보고서로 정리하세요',
  data: '분석 데이터와 실행 정보',
  chat: '보미와 함께하는 분석 공간',
  missions: '지역별 업무를 이어서 진행하세요',
  activity: '자료 반영 이력을 확인하세요',
};

// 컴포넌트는 화면의 한 조각을 만드는 함수입니다. JSX는 HTML과 비슷하지만,
// class 대신 className, onclick 대신 onClick을 사용합니다.
// onLogin은 부모 App이 전달한 함수이며 로그인 후 user 상태를 갱신합니다.
function Login({ onLogin }) {
  const [id, setId] = useState('gangnam01'),
    [password, setPassword] = useState('demo1234'),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      onLogin((await api('/login', { id, password })).user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <section className="login-hero">
        <img className="brand-logo" src="/brand/welfind_logo.png" alt="WELFIND 복지탐정" />
        <span className="eyebrow">지역의 작은 변화를 발견하는 파트너</span>
        <h1>
          더 따뜻한 복지,
          <br />
          보미와 함께 시작해요.
        </h1>
        <p>
          변화를 발견하고, 근거를 살펴보고,
          <br />
          우리 지역에 필요한 지원으로 연결합니다.
        </p>
        <Bomi />
        <span className="hero-note">
          발견하기 <Icon name="arrow" /> 분석하기 <Icon name="arrow" /> 연결하기
        </span>
      </section>
      <section className="login-form">
        <form onSubmit={submit}>
          <span className="eyebrow">WELFIND WORKSPACE</span>
          <h2>반갑습니다, 담당자님</h2>
          <p>시연 계정으로 업무 공간에 접속하세요.</p>
          <label>
            아이디
            <input
              value={id}
              onChange={(e) => setId(e.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            비밀번호
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="primary wide" disabled={busy}>
            {busy ? '접속 중…' : '업무 공간 시작하기'}
            <Icon name="arrow" />
          </button>
          <div className="demo-accounts">
            <span>시연 계정 선택</span>
            {[
              ['강남구', 'gangnam01', 'demo1234'],
              ['춘천시', 'chuncheon01', 'demo1234'],
              ['관리자', 'admin', 'admin1234'],
            ].map(([label, value, pw]) => (
              <button
                type="button"
                key={value}
                onClick={() => {
                  setId(value);
                  setPassword(pw);
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <small>시연용 로그인입니다. 실제 서비스 인증은 별도 구성이 필요합니다.</small>
        </form>
      </section>
    </div>
  );
}

// App은 지도·상세·챗봇이 공유하는 상태를 관리하는 최상위 컴포넌트입니다.
// useState: 값이 바뀌면 React가 관련 화면을 다시 그립니다.
// useEffect: 로그인/선택 지역 변경 시 서버 조회 같은 작업을 실행합니다.
// useMemo: 지정한 값이 바뀔 때만 필터링 결과/객체를 다시 만듭니다.
export default function App() {
  const [user, setUser] = useState(null),
    [checking, setChecking] = useState(true),
    [data, setData] = useState(null),
    [error, setError] = useState('');
  const [supportOpen, setSupportOpen] = useState(false),
    [view, setView] = useState('dashboard'),
    [city, setCity] = useState('강남구'),
    [month, setMonth] = useState(''),
    [district, setDistrict] = useState('');
  // 메뉴 접힘 상태도 React가 관리합니다. 화면 내용/선택 지역은 그대로 유지됩니다.
  const [navCollapsed, setNavCollapsed] = useState(() => window.innerWidth <= 1100);
  const previousChatView = useRef('dashboard');
  const originalWorkspace = useRef(null);
  const pendingWorkspace = useRef(null);
  const [workflow, setWorkflow] = useState({}),
    [reportSeed, setReportSeed] = useState(null),
    [reviewSeed, setReviewSeed] = useState(null),
    [notice, setNotice] = useState(''),
    [chatOpen, setChatOpen] = useState(() => window.innerWidth >= 1500),
    [busy, setBusy] = useState(false),
    [trialError, setTrialError] = useState('');
  useEffect(() => {
    api('/session')
      .then((d) => setUser(d.user))
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);
  useEffect(() => {
    if (!user) return;
    setReportSeed(null);
    setReviewSeed(null);
    let active = true;
    setData(null);
    setError('');
    api('/dashboard')
      .then((d) => {
        if (active) {
          const target = pendingWorkspace.current;
          pendingWorkspace.current = null;
          const nextCity = target?.city && d.geometry[target.city] ? target.city : user.admin ? '강남구' : user.org;
          const nextMonth = d.months.includes(target?.month) ? target.month : d.months.at(-1) || '';
          const nextDistrict = d.geometry[nextCity]?.units.some(u => u.n === target?.district) ? target.district : '';
          setData(d);
          setCity(nextCity);
          setMonth(nextMonth);
          setDistrict(nextDistrict);
          if (target) {
            setView(target.view || 'dashboard');
            setChatOpen(!!target.chatOpen);
          }
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [user]);
  // 지역/월을 단일 context로 관리해 지도와 챗봇이 같은 지역을 보도록 합니다.
  const context = useMemo(() => ({ city, district, month }), [city, district, month]);
  const latestContext = useRef(context);
  latestContext.current = context;
  const rows = useMemo(
    () => (data?.assessment || []).filter((r) => city === '강남구' && r['기준연월'] === month),
    [data, city, month],
  );
  const selectedRows = rows.filter((r) => r['행정동명'] === district);
  useEffect(() => {
    setWorkflow({});
    setNotice('');
    if (!district) return;
    let active = true;
    api('/workflow?' + query(context))
      .then((d) => active && setWorkflow(d))
      .catch((e) => active && setNotice(e.message));
    return () => {
      active = false;
    };
  }, [context, user?.id]);
  // 저장 공통 처리: 중복 클릭 방지 → 서버 저장 → 최신 업무 상태 반영.
  // 실제 저장 성공 여부와 단계 검증은 Python API 결과로 판단합니다.
  async function mutate(path, extra = {}) {
    setBusy(true);
    setNotice('');
    try {
      const result = await api(path, { ...context, ...extra });
      // 저장 중 지역을 바꿨다면 이전 지역의 상태를 새 지역 화면에 덮어쓰지 않습니다.
      if (latestContext.current === context) {
        setWorkflow(result);
        setNotice('저장했습니다.');
      }
      return result;
    } catch (e) {
      if (latestContext.current === context) setNotice(e.message);
      return null;
    } finally {
      setBusy(false);
    }
  }
  async function switchTrial(mode) {
    if (busy) return false;
    setBusy(true); setTrialError('');
    try {
      const result = await api('/trial/' + mode, {});
      if (mode === 'start') {
        if (!user.trial) originalWorkspace.current = { ...context, view, chatOpen };
        const trialCity = result.user.org;
        const candidates = summarizeRegions(data.assessment, data.geometry[trialCity], trialCity, month, data.months);
        const first = candidates.find(r => r.count > 0) || candidates.find(r => r.rows.length);
        pendingWorkspace.current = { city: trialCity, month, district: first?.name || '', view: first ? 'chart' : 'dashboard', chatOpen: false };
      } else {
        pendingWorkspace.current = originalWorkspace.current || { city: result.user.org, month, view: 'dashboard' };
        originalWorkspace.current = null;
      }
      setWorkflow({}); setNotice(''); setUser(result.user);
      return true;
    } catch (e) {
      setTrialError(e.message);
      return false;
    } finally { setBusy(false); }
  }
  function expandChat() {
    if (view !== 'chat') previousChatView.current = view;
    setChatOpen(true);
    setView('chat');
  }
  function collapseChat() {
    setChatOpen(true);
    setView(previousChatView.current);
  }
  function closeChat() {
    setChatOpen(false);
    if (view === 'chat') setView(previousChatView.current);
  }
  async function logout() {
    await api('/logout', {});
    setUser(null);
    setData(null);
    setView('dashboard');
    setSupportOpen(false);
    originalWorkspace.current = null;
    pendingWorkspace.current = null;
  }
  const regions = useMemo(() => summarizeRegions(
    data?.assessment || [], data?.geometry[city], city, month, data?.months || [],
  ), [data, city, month]);
  if (checking) return <div className="loading">복지탐정 업무 공간을 준비하고 있습니다…</div>;
  if (!user) return <Login onLogin={setUser} />;
  const select = (name) => setDistrict(name);
  const start = async () => {
    if (await mutate('/workflow/start')) setView('chart');
  };
  const briefingProps = {
    regions,
    assessment: data?.assessment || [],
    city,
    month,
    geometry: data?.geometry[city],
    selected: district,
    onSelect: select,
    onStart: start,
    onChat: () => setChatOpen(true),
    busy,
    months: data?.months || [],
  };

  return (
    <div
      className={`app-shell ${chatOpen || view === 'chat' ? 'with-chat' : ''} ${view === 'chat' ? 'chat-view' : ''} ${navCollapsed ? 'nav-collapsed' : ''} ${view === 'dashboard' ? 'briefing-shell' : ''}`}
    >
      <nav className="sidebar" aria-label="주 메뉴">
        <button
          className="logo-toggle"
          onClick={() => setNavCollapsed((v) => !v)}
          aria-label={navCollapsed ? '왼쪽 메뉴 펼치기' : '왼쪽 메뉴 접기'}
          aria-expanded={!navCollapsed}
          title={navCollapsed ? '메뉴 펼치기' : '메뉴 접기'}
        >
          <img
            className={navCollapsed ? 'bomi-face' : 'brand-logo'}
            src={navCollapsed ? '/brand/bomi-face.png' : '/brand/welfind_logo.png'}
            alt={navCollapsed ? '보미 얼굴' : 'WELFIND 복지탐정'}
          />
        </button>
        <div className="workspace-tag">
          <span className="online-dot" />
          복지정책 업무 공간
        </div>
        <span className="nav-label">WORKSPACE</span>
        {menus.map(([key, label]) => (
          <button
            key={key}
            className={view === key ? 'active' : ''}
            onClick={() => setView(key)}
            aria-label={label}
            aria-current={view === key ? 'page' : undefined}
          >
            <Icon name={key === 'compare' ? 'chart' : key === 'followup' ? 'missions' : key} />
            <span>{label}</span>
          </button>
        ))}
        {user.admin && (
          <button
            className={view === 'activity' ? 'active' : ''}
            onClick={() => setView('activity')}
            aria-label="활동 이력"
          >
            <Icon name="report" />
            <span>활동 이력</span>
          </button>
        )}
        <span className="nav-label assistant-nav">ASSISTANT</span>
        <button
          className={view === 'chat' ? 'active' : ''}
          aria-label="보미 챗봇"
          onClick={expandChat}
        >
          <Icon name="chat" />
          <span>보미 챗봇</span>
          <span className="new-tag">AI</span>
        </button>
        <div className="sidebar-bottom">
          <div className="user-avatar">{user.admin ? 'A' : user.org.slice(0, 1)}</div>
          <div>
            <b>{user.admin ? '전체 관리자' : user.org + ' 담당자'}</b>
            <small>{user.account_id || user.id}</small>
          </div>
          <button disabled={busy} onClick={logout} aria-label="로그아웃">
            <Icon name="logout" size={18} />
          </button>
        </div>
      </nav>
      <div className="main-wrap">
        <header className="topbar">
          <span>
            복지정책과 <span className="separator">/</span>{' '}
            {menus.find((m) => m[0] === view)?.[1] || '보미 챗봇'}
          </span>
          <div>
            <button className="text-button support-trigger" disabled={!data} onClick={() => setSupportOpen(true)}>이용 안내{user.trial ? ' · 체험 중' : ''}</button>
            {user.trial && <button className="text-button" disabled={busy || !data} onClick={async () => { if (!await switchTrial('end')) setSupportOpen(true); }}>체험 종료</button>}
            <span className="connected">
              <span className="online-dot" />
              {data ? '분석 결과 연결' : '분석 결과 확인 중'}
            </span>
            <button
              className="icon-button"
              onClick={() => view === 'chat' ? closeChat() : setChatOpen(v => !v)}
              aria-label="챗봇 표시 전환"
            >
              <Icon name="chat" />
            </button>
          </div>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">WELFIND · {city}</span>
              <h1>
                {view === 'dashboard' ? (
                  <>
                    {user.admin ? '담당자' : city + ' 담당자'}님,
                    <br />
                    이번 달 <em>복지 미션</em>을 확인하세요.
                  </>
                ) : (
                  titles[view]
                )}
              </h1>
              <p>데이터에서 발견한 변화, 더 세심한 지역 돌봄으로 이어집니다.</p>
            </div>
            <div className="filters">
              <label>
                지역
                <select
                  value={city}
                  onChange={(e) => {
                    setCity(e.target.value);
                    setDistrict('');
                  }}
                >
                  {Object.keys(data?.geometry || { [city]: {} }).map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label>
                기준월
                <select value={month} onChange={(e) => setMonth(e.target.value)}>
                  {data?.months
                    .slice()
                    .reverse()
                    .map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                </select>
              </label>
            </div>
          </div>
          {error ? (
            <div className="error" role="alert">
              {error}
              <p>분석 자료를 연결하지 못했습니다. 다시 연결한 뒤에도 문제가 계속되면 관리자에게 문의하세요.</p>
              {user.admin && <p>관리자 확인: 분석 결과 파일과 서버 로그를 확인하세요.</p>}
              <button onClick={() => setUser({ ...user })}>다시 연결</button>
            </div>
          ) : !data ? (
            <div className="loading">분석 결과를 읽고 있습니다…</div>
          ) : (
            <>
              {notice && (
                <div className="notice" role="status">
                  {notice}
                  <button
                    className="icon-button"
                    onClick={() => setNotice('')}
                    aria-label="알림 닫기"
                  >
                    <Icon name="close" size={15} />
                  </button>
                </div>
              )}
              {!rows.length && <div className="notice" role="status">{city} · {month}의 분석 자료가 없습니다. 지역 또는 기준월을 확인해 주세요.</div>}
              {view === 'compare' && <Comparison key={city} data={data} context={context} />}
              {view === 'followup' && (district ? <ReviewWorkspace key={JSON.stringify(context) + (reviewSeed?.id || "")} context={context} onView={setView} seed={reviewSeed} /> : <div className="empty">지도나 지역 분석에서 동을 먼저 선택하세요.<button className="text-button" onClick={() => setView('map')}>지역 선택하기 →</button></div>)}
              {view === 'dashboard' && <Briefing {...briefingProps} />}
              {view === 'map' && <RegionalOverview {...briefingProps} />}
              {view === 'chart' && (
                <div className="scroll-view">
                  <section className="card analysis-card">
                    <header>
                      <h2>지역 분석 근거</h2>
                      <select
                        aria-label="분석 지역 선택"
                        value={district}
                        onChange={(e) => select(e.target.value)}
                      >
                        <option value="">행정동 선택</option>
                        {data.geometry[city]?.units.map((u) => (
                          <option key={u.n}>{u.n}</option>
                        ))}
                      </select>
                    </header>
                    {selectedRows.length ? (
                      <>
                        <div className="analysis-title">
                          <h2>{district}</h2>
                          <span className="pill">{month} · 분석 결과</span>
                        </div>
                        <EvidenceTable rows={selectedRows} />
                        <p className="hint">{selectedRows.filter(r => r.is_risk_signal).length}개 지표가 후보 기준에 해당합니다. 전월 증가한 지표도 지역 전체의 공통 흐름과 과거 이력을 반영하면 후보가 될 수 있습니다. 후보는 지표 묶음을 함께 확인한 결과입니다.</p>
                        <p className="hint">
                          지역 전체의 공통 흐름을 제외한 변화 참고값:{' '}
                          {selectedRows
                            .map((r) => `${r.metric_label} ${number(r.relative_change_pp)}`)
                            .join(' · ')}
                        </p>
                        <div className="workflow-actions">
                          <button
                            className="primary"
                            disabled={busy || workflow.workflow_complete}
                            onClick={() => mutate('/workflow/start')}
                          >
                            분석 확인 저장
                          </button>
                          <button
                            className="secondary"
                            disabled={
                              busy || !workflow.done?.includes(0) || workflow.workflow_complete
                            }
                            onClick={() => mutate('/workflow/confirm')}
                          >
                            근거 검토 완료
                          </button>
                          <button
                            className="text-button"
                            disabled={!workflow.done?.includes(1)}
                            onClick={() => setView('services')}
                          >
                            사업 매칭 검토
                            <Icon name="arrow" size={17} />
                          </button>
                        </div>
                        <p className="hint">
                          {workflow.done?.includes(1)
                            ? '근거 검토 완료 · 사업 매칭 검토로 이동하세요'
                            : workflow.done?.includes(0)
                              ? '분석 확인 완료 · 근거 검토를 진행하세요'
                              : '분석 확인을 저장하면 업무 기록이 시작됩니다.'}
                        </p>
                      </>
                    ) : (
                      <div className="empty">
                        분석할 지역을 선택하세요. 실제 자료가 없는 지역은 분석하지 않습니다.
                      </div>
                    )}
                  </section>
                  {selectedRows.length > 0 &&
                    selectedRows.map((r) => (
                      <section className="card trend-card" key={r.metric_label}>
                        <header>
                          <h2>{r.metric_label} · 최근 분석월 추이</h2>
                          <span>전월 변화율 (%)</span>
                        </header>
                        <Trend
                          assessment={data.assessment.filter(r => r['기준연월'] <= month)}
                          district={district}
                          metric={r.metric_label}
                        />
                      </section>
                    ))}
                  <p className="hint">
                    지역 집계자료의 변화이며 개인의 고립 여부를 판정하지 않습니다. 계절·행사·집계
                    정의 변화는 추가 확인이 필요합니다.
                  </p>
                </div>
              )}
              {view === 'services' && (
                <Services
                  key={JSON.stringify(context)}
                  context={context}
                  workflow={workflow}
                  mutate={mutate}
                  busy={busy}
                />
              )}
              {view === 'report' && (
                <Report
                  key={JSON.stringify(context)}
                  context={context}
                  workflow={workflow}
                  user={user}
                  mutate={mutate}
                  busy={busy}
                  seed={reportSeed}
                  onSaved={() => { if (latestContext.current === context) setReportSeed(null); }}
                />
              )}
              {view === 'data' && (
                <div className="scroll-view">
                  {user.admin && <Upload />}
                  <section className="card info-card">
                    <span className="eyebrow">DATA PROVENANCE</span>
                    <h2>실제 분석 결과를 사용합니다</h2>
                    <dl>
                      <dt>분석 소스</dt>
                      <dd>{data.source}</dd>
                      <dt>분석 규칙</dt>
                      <dd>analysis2-v11 · 공통 변화 제거 후 Robust Z</dd>
                      <dt>기간</dt>
                      <dd>
                        {data.months[0]} ~ {data.months.at(-1)}
                      </dd>
                      <dt>근거 행</dt>
                      <dd>{data.assessment.length.toLocaleString()}개</dd>
                      <dt>현재 결과 버전</dt>
                      <dd>{data.runId}</dd>
                    </dl>
                    <p>
                      전화·문자 또는 평일·휴일 이동의 Robust Z가 모두 -2.0 이하일 때 지표 묶음을
                      후보로 표시합니다. 최소 12회 과거 이력이 필요합니다.
                    </p>
                    <p>
                      춘천시의 실제 Analysis2 결과는 연결되지 않았습니다. 강남구 결과를 다른 지역의
                      데이터로 표시하지 않습니다.
                    </p>
                    <p>
                      CSV는 Git에서 제외됩니다. 팀원 PC와 시연 PC에 분석 결과 파일을 별도로 전달해야
                      합니다.
                    </p>
                  </section>
                </div>
              )}
              {view === 'missions' && (
                <Missions
                  onResume={(item) => {
                    setCity(item.city);
                    setDistrict(item.district);
                    setMonth(item.month);
                    setView(
                      item.workflow.workflow_complete
                        ? 'report'
                        : item.workflow.done?.includes(2)
                          ? 'report'
                          : item.workflow.done?.includes(1)
                            ? 'services'
                            : 'chart',
                    );
                  }}
                />
              )}
              {view === 'activity' && user.admin && <Activity />}
              {view === 'chat' && (
                <div className="chat-context-view">
                  <span className="eyebrow">CONNECTED ANALYSIS</span>
                  <h2>선택 지역과 대화를 연결하세요</h2>
                  <p>지도에서 선택한 동과 기준월을 보미가 함께 참고합니다.</p>
                  <select
                    aria-label="챗봇 분석 지역"
                    value={district}
                    onChange={(e) => select(e.target.value)}
                  >
                    <option value="">행정동 선택</option>
                    {data.geometry[city]?.units.map((u) => (
                      <option key={u.n}>{u.n}</option>
                    ))}
                  </select>
                  {district && (
                    <>
                      <h3>
                        {district} · {month}
                      </h3>
                      <EvidenceTable rows={selectedRows} />
                      <button className="primary" onClick={() => setView('chart')}>
                        분석 근거 살펴보기
                        <Icon name="arrow" />
                      </button>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </main>
        <footer className="app-footer">
          <span>WELFIND · 복지탐정</span>
          <span>지역의 변화를 발견하고, 필요한 지원으로 연결합니다.</span>
        </footer>
      </div>
      {data && supportOpen && <SupportDialog onClose={() => setSupportOpen(false)} data={data} context={context} rows={selectedRows} workflow={workflow} onView={setView} onSelect={select} regions={regions} user={user} onTrial={switchTrial} busy={busy} trialError={trialError} page={view} />}
      {data && (
        <ChatPanel
          key={user.id}
          visible={chatOpen || view === 'chat'}
          context={context}
          hasEvidence={selectedRows.length > 0}
          expanded={view === 'chat'}
          onClose={closeChat}
          onExpand={view === 'chat' ? collapseChat : expandChat}
          onAction={(a) => {
            if (a.district) select(a.district);
            if (a.reportDraft) setReportSeed(a.reportDraft);
            if (a.reviewNote) setReviewSeed({ id: Date.now(), context: { ...context }, text: a.reviewNote });
            setView(a.view === 'analysis' ? 'chart' : a.view);
          }}
        />
      )}
    </div>
  );
}

// 실제 DB2 사업을 조회한 뒤 serviceKey를 서버에 보내 검토 기록을 저장합니다.
// .env의 DB 설정이 틀리면 조회 오류를 표시하며 가짜 사업으로 대체하지 않습니다.
function Services({ context, workflow, mutate, busy }) {
  const [matches, setMatches] = useState([]),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(false),
    [loaded, setLoaded] = useState(false),
    [pageSize, setPageSize] = useState(5),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState(''),
    [reviewDrafts, setReviewDrafts] = useState({});
  const pageCount = Math.max(1, Math.ceil(matches.length / pageSize));
  const pageStart = (page - 1) * pageSize;
  const visibleMatches = matches.slice(pageStart, pageStart + pageSize);
  function changePage(nextPage) {
    setPage(nextPage);
    setSelected('');
  }
  function updateReview(key, field, value) {
    setReviewDrafts((previous) => ({
      ...previous,
      [key]: { decision: '보류', note: '', ...previous[key], [field]: value },
    }));
  }
  const pagination = (
    <div className="service-pagination" aria-label="사업 목록 페이지">
      <button className="secondary" disabled={busy || loading || page === 1} onClick={() => changePage(page - 1)}>이전</button>
      <span aria-live="polite">{page} / {pageCount} 페이지</span>
      <button className="secondary" disabled={busy || loading || page === pageCount} onClick={() => changePage(page + 1)}>다음</button>
    </div>
  );
  async function load() {
    setLoading(true);
    setError('');
    setSelected('');
    try {
      setMatches((await api('/services?' + query(context))).matches);
      setLoaded(true);
      setPage(1);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="scroll-view">
      <section className="card info-card">
        <span className="eyebrow">SERVICE REVIEW</span>
        <h2>{context.district || '지역 선택 필요'} · 사업 매칭 검토</h2>
        <p>
          정기 수집된 지자체 복지사업에서 선택 지역과 같은 시·도의 지역 미지정 자료를 검토 후보로 조회합니다.
          게시 지역이 이용 자격을 뜻하지는 않습니다. 지원 대상과 접수 가능 여부는 운영기관에 확인하세요.
        </p>
        <button
          className="primary"
          onClick={load}
          disabled={busy || loading || !workflow.done?.includes(1)}
        >
          {loading ? 'DB2 조회 중…' : '관련 사업 조회'}
        </button>
        {!workflow.done?.includes(1) && (
          <p className="hint">지역 분석 화면에서 분석 확인과 근거 검토를 먼저 저장하세요.</p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {matches.length > 0 && (
          <div className="service-list-toolbar">
            <label className="service-page-size">
              표시 개수
              <select aria-label="페이지당 사업 개수" value={pageSize} disabled={busy || loading}
                onChange={(e) => { setPageSize(Number(e.target.value)); changePage(1); }}>
                {[5, 10, 15].map((size) => <option key={size} value={size}>{size}개씩</option>)}
              </select>
            </label>
            <span className="service-result-count">총 {matches.length}개 · {pageStart + 1}–{Math.min(pageStart + pageSize, matches.length)}개 표시</span>
            {pagination}
          </div>
        )}
        {visibleMatches.map((m) => {
          const review = reviewDrafts[m.key] || { decision: '보류', note: '' };
          return (
          <article className={`service-card ${selected === m.key ? 'chosen' : ''}`} key={m.key}>
            <h3>{m.service.name}</h3>
            {m.service.source_id === 'local_welfare_api' && (
              <>
                <small>게시 지역: {m.service.province} · {m.service.district && m.service.district !== '-' ? m.service.district : '시·군·구 미지정'} / 이용 가능 지역은 별도 확인</small>
                {m.service.detail_pending && <p className="hint">{m.service.detail_checked_at ? '상세 재확인 대기 · 이전에 수집한 상세정보입니다.' : '상세 수집 대기 · 현재 목록 정보만 제공됩니다.'}</p>}
                <p>시행기간: {m.service.effective_start || '시작일 미확인'} ~ {m.service.effective_end || '종료일 미확인'}</p>
              </>
            )}
            <p>{m.service.target_text || m.service.description || '사업 대상 정보 확인 필요'}</p>
            <p>{m.service.eligibility_text || '이용 조건 확인 필요'}</p>
            <p>{m.service.support_text || m.service.summary}</p>
            {m.service.application_text && <p>신청 방법: {m.service.application_text}</p>}
            {/^https?:\/\//i.test(m.service.source_url || '') && (
              <a className="text-button" href={m.service.source_url} target="_blank" rel="noopener noreferrer">사업 안내 원문 확인 →</a>
            )}
            <small>
              매칭 근거: {m.reasons.length
                ? m.reasons
                    .map(
                      (r) =>
                        `${r.category} · ${r.metrics.join(', ')} → ${r.service_terms.join(', ')}`,
                    )
                    .join(' / ')
                : '지표와 직접 연결되는 키워드 근거 없음'}
            </small>
            <details><summary>적합성·추가 확인 조건</summary><p>게시 지역은 이용 자격을 의미하지 않습니다. 선택 지역 {context.city} {context.district}의 주민이 이용 가능한지 확인하세요.</p><ul><li>지원 대상: {m.service.target_text || '운영기관 확인 필요'}</li><li>이용 조건: {m.service.eligibility_text || '운영기관 확인 필요'}</li><li>신청 방법: {m.service.application_text || '운영기관 확인 필요'}</li><li>현재 접수 여부·정원·거주 요건을 운영기관에 확인하세요.</li></ul></details>
            <button
              className="secondary"
              disabled={busy || loading || workflow.workflow_complete}
              aria-expanded={selected === m.key}
              aria-controls={selected === m.key ? 'service-review-form' : undefined}
              onClick={() => setSelected(selected === m.key ? '' : m.key)}
            >
              {selected === m.key ? '검토 입력 닫기' : '이 사업 검토'}
            </button>
            {selected === m.key && (
              <div className="review-form service-inline-review" id="service-review-form" role="group" aria-label={`${m.service.name} 검토 입력`}>
                <b>{m.service.name} · 검토 기록</b>
                <label>
                  검토 결과
                  <select value={review.decision} disabled={busy} onChange={(e) => updateReview(m.key, 'decision', e.target.value)}>
                    {['적합', '보류', '부적합'].map((decision) => <option key={decision}>{decision}</option>)}
                  </select>
                </label>
                <label>
                  검토 근거
                  <textarea value={review.note} disabled={busy} onChange={(e) => updateReview(m.key, 'note', e.target.value)}
                    placeholder="사업 조건과 지역 근거를 함께 기록하세요." />
                </label>
                <button className="primary" disabled={busy || !review.note.trim() || workflow.workflow_complete}
                  onClick={async () => {
                    const result = await mutate('/workflow/review', { serviceKey: m.key, ...review });
                    if (result) setSelected('');
                  }}>
                  {busy ? '저장 중…' : '사업 검토 기록 저장'}
                </button>
              </div>
            )}
          </article>
          );
        })}
        {matches.length > 0 && <div className="service-list-footer">{pagination}</div>}
        {!loading && !error && !matches.length && (
          <p className="hint">{loaded ? '선택 지역의 검토 후보가 없습니다. 수집 범위와 시행기간을 확인하세요.' : '관련 사업 조회를 눌러 수집된 사업을 확인하세요.'}</p>
        )}
      </section>
      <section className="card info-card">
        <h2>저장된 사업 검토 기록</h2>
        {workflow.reviews?.length ? (
          workflow.reviews.map((r, i) => (
            <article className="service-card" key={i}>
              <b>
                {r.name} · {r.decision}
              </b>
              <p>{r.note}</p>
            </article>
          ))
        ) : (
          <p className="hint">저장된 기록이 없습니다.</p>
        )}
      </section>
    </div>
  );
}

// Word 문서 생성은 Python build_report(), 단계/해시 검증은 mission_store.py가 처리합니다.
function Report({ context, workflow, user, mutate, busy, seed, onSaved }) {
  const [author, setAuthor] = useState(user.account_id || user.id),
    [department, setDepartment] = useState(context.city + ' 복지정책과'),
    [contact, setContact] = useState(''),
    [content, setContent] = useState(null),
    [confirmed, setConfirmed] = useState(false),
    [draft, setDraft] = useState(null),
    [draftBusy, setDraftBusy] = useState(false),
    [error, setError] = useState('');
  useEffect(() => {
    setDraft(null);
    setConfirmed(false);
  }, [author, department, contact, content]);
  const reviewKey = JSON.stringify(workflow.reviews || []);
  useEffect(() => {
    setContent(null);
    setConfirmed(false);
    setDraft(null);
  }, [reviewKey]);
  useEffect(() => {
    if (seed && JSON.stringify(seed.review_snapshot || []) === reviewKey &&
      ['city', 'district', 'month'].every((k) => seed.context?.[k] === context[k])) {
      setContent(seed);
      setDraft(null);
      setConfirmed(false);
    }
  }, [seed, reviewKey]);
  async function generate() {
    setDraftBusy(true);
    setError('');
    try {
      setContent(await api('/report/content', context));
    } catch (e) {
      setError(e.message);
    } finally {
      setDraftBusy(false);
    }
  }
  async function preview() {
    setDraftBusy(true);
    setConfirmed(false);
    setDraft(null);
    setError('');
    try {
      setDraft(await api('/report/preview', { ...context, author, department, contact,
        content, review_id: content.review_id }));
    } catch (e) {
      setError(e.message);
    } finally {
      setDraftBusy(false);
    }
  }
  async function save() {
    const result = await mutate('/report', { token: draft.token, confirmed });
    if (result) {
      setContent(null);
      setDraft(null);
      setConfirmed(false);
      setError('');
      onSaved();
    }
  }
  return (
    <div className="scroll-view">
      <section className="card info-card">
        <span className="eyebrow">REVIEW REPORT</span>
        <h2>{context.district || '지역 선택 필요'} · 복지서비스 연계 검토보고</h2>
        {workflow.workflow_complete && (
          <>
            <p>최종 보고서가 저장되었습니다. 같은 지역의 보고서를 다시 작성할 수 있습니다. 이전 저장본은 이력으로 보관됩니다.</p>
            <a className="primary download" href={'/api/report?' + query(context)}>
              저장된 Word 보고서 내려받기
              <Icon name="arrow" />
            </a>
          </>
        )}
        <>
            <p>지역 분석과 사업 검토를 바탕으로 복지서비스 연계·추진을 제안하는 약식보고서를 작성합니다. 기본 분량은 1~2쪽을 목표로 하며, 입력 내용에 따라 늘어날 수 있습니다.</p>
            <p className="hint">약식보고서 표준서식 · 검토 요지 → 지역 현황 → 서비스 제안 → 향후 조치</p>
            {!workflow.done?.includes(2) && (
              <p className="hint">사업 매칭 검토 기록을 먼저 저장하세요.</p>
            )}
            <div className="report-form">
              <label>
                작성 부서
                <input value={department} maxLength={100} disabled={draftBusy || busy} onChange={(e) => setDepartment(e.target.value)} />
              </label>
              <label>
                작성자
                <input value={author} maxLength={60} disabled={draftBusy || busy} onChange={(e) => setAuthor(e.target.value)} />
              </label>
              <label className="full">
                연락처 (선택)
                <input value={contact} maxLength={80} disabled={draftBusy || busy} onChange={(e) => setContact(e.target.value)} />
              </label>
            </div>
            <button className="secondary" disabled={busy || draftBusy || !workflow.done?.includes(2)} onClick={generate}>
              {draftBusy ? '생성 중…' : content ? '저장된 근거로 초안 다시 만들기' : '보고서 에이전트로 초안 만들기'}
            </button>
            {content && (
              <div className="report-form report-editor">
                <p className="hint full">{content.mode} · 제안 내용과 확인할 조건을 검토해 수정하세요. 초안 재생성 시 편집 내용이 바뀝니다.</p>
                {[
                  ['title', '보고서 제목', 80], ['summary', '검토 요지', 350],
                  ['situation', '지역 현황', 900], ['proposal', '복지서비스 연계·추진 제안', 1200],
                  ['next_steps', '향후 조치 및 담당자 의견', 600],
                ].map(([key, label, limit]) => (
                  <label className="full" key={key}>
                    {label}
                    <textarea rows={key === 'title' ? 2 : 4} maxLength={limit} disabled={draftBusy || busy} value={content[key]}
                      onChange={(e) => setContent((prev) => ({ ...prev, [key]: e.target.value }))} />
                    <small>{content[key].length} / {limit}자</small>
                  </label>
                ))}
              </div>
            )}
            <ReportQuality content={content} workflow={workflow} />
            {error && <p className="error">{error}</p>}
            <button
              className="secondary"
              disabled={
                busy ||
                draftBusy ||
                !workflow.done?.includes(2) ||
                !content || ![author, department, ...['title', 'summary', 'situation', 'proposal', 'next_steps'].map((k) => content?.[k] || '')].every((s) => s.trim())
              }
              onClick={preview}
            >
              {draftBusy ? '생성 중…' : '편집한 내용으로 Word 파일 생성'}
            </button>
            {draft && (
              <a
                className="text-button"
                href={'/api/report/draft?' + query({ ...context, token: draft.token })}
              >
                생성된 보고서 내려받아 확인 →
              </a>
            )}
            <label className="confirmation">
              <input
                type="checkbox"
                disabled={!draft}
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />{' '}
              분석 근거·사업 검토 내역·최종 의견을 확인했습니다.
            </label>
            <button
              className="primary"
              disabled={
                busy ||
                !workflow.done?.includes(2) ||
                !confirmed ||
                !draft ||
                draftBusy || !content || ![author, department].every((s) => s.trim())
              }
              onClick={save}
            >
              확인한 최종 보고서 저장
            </button>
        </>
      </section>
    </div>
  );
}
