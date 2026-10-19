import { useDraft } from './useDraft';
import { draftKey, clearDrafts, hasDrafts } from './draftStore.mjs';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api, query, number } from './api';
import { Icon, Bomi, EvidenceTable, Trend } from './components';
import BomiChat from './BomiChat';
import AISettings from './AISettings';
import { Records, Activity, Upload } from './Workspace';
import { RegionalOverview, summarizeRegions, exampleQuestion } from './Briefing';
import { DataDialog, Comparison, ReportQuality } from './Experience';
import GuideTour from './GuideTour';
import GroupDashboard from './GroupDashboard';
import RegionAnalysis from './RegionAnalysis';
import { normalizeAgeNames } from './ageSignals.mjs';
import { userName } from './personas.mjs';

const menus = [
  ['dashboard', '종합 현황'],
  ['map', '지역 현황'],
  ['chart', '지역 분석'],
  ['services', '사업 매칭 검토'],
  ['records', '업무 기록'],
  ['report', '보고서 작성'],
];
// 예전 메뉴 이름으로 이동을 요청해도 합쳐진 메뉴의 해당 탭으로 연결합니다.
const legacyViews = { compare: ['chart', 'compare'], followup: ['records'], missions: ['records'] };
const adminMenus = [['data', '데이터 관리'], ['activity', '활동 이력'], ['ai', 'AI 설정']];
// 메뉴마다 서로 다른 아이콘을 써서 메뉴를 접었을 때도 구분되게 합니다.
const menuIcons = { records: 'clipboard', activity: 'history' };
const subtitles = {
  map: '지도에서 지역을 고르고, 탐지 이후 변화를 추적합니다.',
  chart: '지역 유형과 소비 변화, 주민들의 사회적 연결을 함께 살펴봅니다.',
  records: '진행 중인 지역 업무를 고르고, 검토 의견과 후속 조치를 기록합니다.',
  services: '확인한 필요에 맞는 복지사업을 찾아 조건을 검토합니다.',
  report: '분석과 사업 검토 결과를 보고서 초안으로 정리합니다.',
  data: '새 분석 자료를 검사한 뒤 반영합니다.',
  activity: '자료가 언제 어떻게 반영됐는지 확인합니다.',
  ai: '외부 AI의 사용 범위를 설정하세요.',
  chat: '선택한 지역을 바탕으로 보미가 복지사업과 담당 기관을 안내합니다.',
};
const titles = {
  dashboard: '우리 지역의 작은 변화를 발견하세요',
  map: '지역별 변화 한눈에 살펴보기',
  chart: '지역별 생활 특성 살펴보기',
  services: '필요한 지원으로 연결하는 첫걸음',
  report: '검토 결과를 보고서로 정리하세요',
  data: '자료를 검사하고 반영하세요',
  chat: '보미에게 질문 · 복지사업 안내',
  records: '지역별 업무와 후속 조치를 이어서 기록하세요',
  activity: '자료 반영 이력을 확인하세요',
};

// 컴포넌트는 화면의 한 조각을 만드는 함수입니다. JSX는 HTML과 비슷하지만,
// class 대신 className, onclick 대신 onClick을 사용합니다.
// onLogin은 부모 App이 전달한 함수이며 로그인 후 user 상태를 갱신합니다.
function Login({ onLogin, sessionNotice = '' }) {
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
        {/* 로고는 문서 흐름에 두고, 소개 문구는 남는 높이의 가운데에 둡니다. 화면 높이가 낮아도 로고와 겹치지 않습니다. */}
        <div className="login-hero-body">
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
        </div>
      </section>
      <section className="login-form">
        <form onSubmit={submit}>
          <span className="eyebrow">WELFIND WORKSPACE</span>
          <h2>반갑습니다, 담당자님</h2>
          <p>시연 계정으로 업무 공간에 접속하세요.</p>
          {sessionNotice && <p className="error" role="status">{sessionNotice}</p>}
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
    [error, setError] = useState(''),
    [sessionNotice, setSessionNotice] = useState('');
  function openSupport() { setSupportOpen(true); }
  // 단계별 안내: 계정마다 처음 로그인할 때 한 번 자동으로 열고, 상단 ? 버튼으로 다시 볼 수 있습니다.
  const [tourOpen, setTourOpen] = useState(false);
  const tourKey = user ? 'welfind-guide-seen-v1:' + (user.account_id || user.id) : '';
  function openTour() { go('dashboard'); setTourOpen(true); }
  function closeTour() { setTourOpen(false); try { localStorage.setItem(tourKey, '1'); } catch { /* 저장이 막힌 브라우저는 다음 접속 때 다시 안내합니다. */ } }
  const [supportOpen, setSupportOpen] = useState(false),
    [view, setView] = useState('dashboard'),
    [city, setCity] = useState('강남구'),
    [month, setMonth] = useState(''),
    [district, setDistrict] = useState(''), [age, setAge] = useState('');
  // 메뉴 접힘 상태도 React가 관리합니다. 화면 내용/선택 지역은 그대로 유지됩니다.
  const [navCollapsed, setNavCollapsed] = useState(() => window.innerWidth <= 1100);
  const [analysisTab, setAnalysisTab] = useState('evidence');
  const [chatScreenScope, setChatScreenScope] = useState(null);
  // 모든 화면 이동은 go를 거칩니다. 좁은 화면에서는 이동 후 메뉴를 접어 본문을 가리지 않게 합니다.
  function go(target) {
    const [next, tab] = legacyViews[target] || [target];
    if (next === 'chart') setAnalysisTab(tab || 'evidence');
    setView(next);
    if (window.innerWidth <= 760) setNavCollapsed(true);
  }
  const [workflow, setWorkflow] = useState({}),
    [reportSeed, setReportSeed] = useState(null),
    [reviewSeed, setReviewSeed] = useState(null),
    [notice, setNotice] = useState(''),
    [busy, setBusy] = useState(false);
  const [chatDraft, setChatDraft] = useState(null);
  const [chatGroup, setChatGroup] = useState(null);
  useEffect(() => {
    api('/session')
      .then((d) => setUser(d.user))
      .catch(() => {})
      .finally(() => setChecking(false));
  }, []);
  useEffect(() => {
    const returnToLogin = () => {
      clearDrafts();
      setUser(null);
      setData(null);
      setSessionNotice('서버가 다시 시작되어 로그인 세션이 초기화되었습니다. 다시 로그인해 주세요.');
    };
    window.addEventListener('welfind-session-expired', returnToLogin);
    return () => window.removeEventListener('welfind-session-expired', returnToLogin);
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
          // 관리자는 강남구, 담당자는 소속 지역의 가장 최근 기준월로 시작합니다.
          setData(normalizeAgeNames(d));
          setCity(user.admin ? '강남구' : user.org);
          setMonth(d.months.at(-1) || '');
          setDistrict('');
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [user]);
  // 지역/월을 단일 context로 관리해 지도와 챗봇이 같은 지역을 보도록 합니다.
  const context = useMemo(() => ({ city, district, month, ...(age ? {age} : {}) }), [city, district, month, age]);
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
  function expandChat() {
    document.querySelector('.bomi-chat textarea')?.focus();
  }
  async function logout() {
    if (hasDrafts() && !window.confirm('로그아웃하면 임시 보관 중인 작성 내용이 삭제됩니다. 로그아웃할까요?')) return;
    await api('/logout', {});
    clearDrafts();
    setUser(null);
    setData(null);
    setView('dashboard');
    setSupportOpen(false);
  }
  const regions = useMemo(() => summarizeRegions(
    data?.assessment || [], data?.geometry[city], city, month, data?.months || [],
  ), [data, city, month]);
  const dashboardAnalysis = useMemo(() => data && ({ assessment: data.assessment, geometry: data.geometry[city], months: data.months, analysisScope:data.analysisScope, ageDetections:data.ageDetections }), [data, city]);
  useEffect(() => {
    if (!data || !tourKey || view !== 'dashboard') return;
    let seen = false;
    try { seen = localStorage.getItem(tourKey) === '1'; } catch { /* 저장소를 읽을 수 없으면 안내를 보여 줍니다. */ }
    if (!seen) setTourOpen(true);
  }, [data, tourKey]);
  // 동을 고르지 않고 지역 분석을 열면 확인 후보가 가장 많은 동을 먼저 보여 줍니다.
  useEffect(() => {
    if (view !== 'chart' || district) return;
    const top = regions.find(r => r.count > 0) || regions.find(r => r.rows.length);
    if (top) setDistrict(top.name);
  }, [view, regions]);
  if (checking) return <div className="loading">복지탐정 업무 공간을 준비하고 있습니다…</div>;
  if (!user) return <Login onLogin={(nextUser) => { setSessionNotice(''); setUser(nextUser); }} sessionNotice={sessionNotice} />;
  const select = (name) => setDistrict(name);
  const start = async () => {
    if (await mutate('/workflow/start')) go('chart');
  };
  const briefingProps = {
    regions,
    assessment: data?.assessment || [],
    age, onAgeChange:setAge, onMonthChange:setMonth,
    city,
    month,
    geometry: data?.geometry[city],
    selected: district,
    onSelect: select,
    onStart: start,
    // 지역 상세의 «보미와 근거 살펴보기»: 그 동 기준으로 채팅을 맞추고 예시 질문을 입력란에 넣어 둡니다.
    onChat: (region) => {
      if (!region?.name) { expandChat(); return; }
      setDistrict(region.name);
      setChatDraft({ id: Date.now(), contextKey: JSON.stringify({ city, district: region.name, month }), question: exampleQuestion(region), guide: true });
    },
    onInspect: (name) => { setDistrict(name); go('chart'); },
    onAsk: (name, question) => {
      setDistrict(name);
      setChatDraft({ id: Date.now(), contextKey: JSON.stringify({ city, district: name, month }), question });
      expandChat();
    },
    busy,
    months: data?.months || [],
  };

  return (
    <div
      className={`app-shell unified-shell with-chat ${navCollapsed ? 'nav-collapsed' : ''} ${view === 'dashboard' ? 'briefing-shell group-shell' : view === 'chart' ? 'region-insights-shell' : view === 'map' ? 'followup-shell' : ''}`}
    >
      <button className="panel-handle menu-handle" onClick={() => setNavCollapsed(v => !v)} aria-label={navCollapsed ? '왼쪽 메뉴 펼치기' : '왼쪽 메뉴 접기'} aria-expanded={!navCollapsed} title={navCollapsed ? '메뉴 펼치기' : '메뉴 접기'}>{navCollapsed ? '›' : '‹'}</button>
      <nav className="sidebar" aria-label="주 메뉴">
        <button
          className="logo-toggle"
          onClick={() => setNavCollapsed((v) => !v)}
          aria-label={navCollapsed ? '왼쪽 메뉴 펼치기' : '왼쪽 메뉴 접기'}
          aria-expanded={!navCollapsed}
          title={navCollapsed ? '메뉴 펼치기' : '메뉴 접기'}
        >
          {!navCollapsed ? <span className="gd-brand"><img src="/brand/bomi-face.png" alt=""/><span><b>복지탐정</b><small>WELFIND</small></span></span> : <img
            className={navCollapsed ? 'bomi-face' : 'brand-logo'}
            src={navCollapsed ? '/brand/bomi-face.png' : '/brand/welfind_logo.png'}
            alt={navCollapsed ? '보미 얼굴' : 'WELFIND 복지탐정'}
          />}
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
            onClick={() => go(key)}
            aria-label={label}
            title={navCollapsed ? label : undefined}
            aria-current={view === key ? 'page' : undefined}
          >
            <Icon name={menuIcons[key] || key} />
            <span>{label}</span>
          </button>
        ))}
        {user.admin && <><span className="nav-label">관리</span>{adminMenus.map(([key, label]) => <button key={key} className={view === key ? 'active' : ''} onClick={() => go(key)} aria-label={label} aria-current={view === key ? 'page' : undefined}><Icon name={menuIcons[key] || key} /><span>{label}</span></button>)}</>}
        <span className="nav-label assistant-nav">ASSISTANT</span>
        <button
          className={view === 'chat' ? 'active' : ''}
          aria-label="보미에게 질문"
          onClick={expandChat}
        >
          <Icon name="chat" />
          <span>보미에게 질문</span>
          <span className="new-tag">AI</span>
        </button>
        <div className="sidebar-bottom">
          <div className="user-avatar">{user.admin ? 'A' : user.org.slice(0, 1)}</div>
          <div>
            <b>{user.admin ? '전체 관리자' : user.org + ' 담당자'}</b>
            <small>{userName(user)} 님</small>
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
            {[...menus, ...adminMenus].find((m) => m[0] === view)?.[1] || '보미에게 질문'}
          </span>
          <div>
            <button className="icon-button guide-trigger" disabled={!data} onClick={openTour} aria-label="사용 안내 다시 보기" title="사용 안내 다시 보기"><Icon name="help" size={18} /></button>
            <span className="connected">
              <span className="online-dot" />
              {data ? `분석 자료 ${data.months?.at(-1) || ''}까지 반영` : '분석 자료 확인 중'}
            </span>
            {view !== 'dashboard' && <button
              className="icon-button"
              onClick={expandChat}
              aria-label="보미 질문 입력하기"
              title="보미에게 질문"
            >
              <Icon name="chat" /><span className="topbar-chat-label">보미</span>
            </button>}
          </div>
        </header>
        <main className="main-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">WELFIND · {city}</span>
              <h1>
                {view === 'dashboard' ? (
                  <>
                    지역의 변화를 발견하고, <em>필요한 복지로 연결합니다</em>
                  </>
                ) : (
                  titles[view]
                )}
              </h1>
              <p>{view === 'dashboard' ? '복지 담당자가 지역의 사회적 고립 위험 신호와 생활 여건을 살펴보고, 필요한 지원을 검토하도록 돕습니다.' : subtitles[view]}</p>
            </div>
            <div className={`heading-tools ${view === 'dashboard' ? 'case-heading-tools' : ''}`}>
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
              {view === 'dashboard' && <div id="group-period-slot" />}
              {view === 'chart' && <div id="region-period-slot" />}{view === 'map' && <div id="followup-period-slot" />}{view !== 'dashboard' && view !== 'chart' && view !== 'map' && <label>
                기준월
                <select value={month} onChange={(e) => setMonth(e.target.value)}>
                  {data?.months
                    .slice()
                    .reverse()
                    .map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                </select>
              </label>}
            </div>
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
              {!rows.length && view !== 'dashboard' && <div className="notice" role="status">{city} · {month}의 분석 자료가 없습니다. 지역 또는 기준월을 확인해 주세요.</div>}
              {view === 'records' && <Records
                key={user.id + city}
                context={context}
                user={user}
                reviewSeed={reviewSeed}
                onReviewSaved={() => setReviewSeed(null)}
                onSelect={(item) => { setCity(item.city); setDistrict(item.district); setMonth(item.month); }}
                onView={go}
              />}
              {view === 'dashboard' && <GroupDashboard key={user.id + ':' + city} city={city} month={month} user={user} analysis={dashboardAnalysis} onActiveGroup={setChatGroup} onMonthChange={setMonth} />}
              {view === 'map' && <RegionalOverview {...briefingProps} />}
              {view === 'chart' && <div className="scroll-view"><RegionAnalysis city={city} district={district} onSelect={setDistrict} age={age} onAgeChange={setAge}/></div>}
              {view === 'services' && (
                <Services
                  key={user.id + JSON.stringify(context)}
                  context={context}
                  workflow={workflow}
                  user={user}
                  mutate={mutate}
                  busy={busy}
                  onView={go}
                />
              )}
              {view === 'report' && (
                <Report
                  key={user.id + JSON.stringify(context)}
                  context={context}
                  workflow={workflow}
                  user={user}
                  mutate={mutate}
                  busy={busy}
                  seed={reportSeed}
                  onView={go}
                  onSaved={() => { if (latestContext.current === context) setReportSeed(null); }}
                />
              )}
              {view === 'data' && user.admin && <div className="scroll-view"><Upload /><div className="data-source-strip"><span>분석 출처와 판단 기준은 데이터 기준에서 확인할 수 있습니다.</span><button className="text-button" onClick={() => openSupport()}>데이터 기준 보기</button></div></div>}
              {view === 'activity' && user.admin && <Activity />}
              {view === 'ai' && user.admin && <AISettings />}
              {view === 'chat' && (
                <div className="chat-context-view">
                  <span className="eyebrow">CONNECTED ANALYSIS</span>
                  <h2>선택 지역과 대화를 연결하세요</h2>
                  <p>선택한 지역을 보미의 검색 맥락에 반영합니다. 기준월은 분석 자료의 기준이며 사업 운영 시점과는 다릅니다.</p>
                  <select
                    aria-label="챗봇 분석 지역"
                    value={district}
                    onChange={(e) => select(e.target.value)}
                  >
                    <option value="">읍·면·동 선택</option>
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
      {data && supportOpen && <DataDialog onClose={() => setSupportOpen(false)} data={data} context={context} rows={selectedRows} user={user} />}
      {data && tourOpen && <GuideTour onClose={closeTour} />}
      {data && (

        <BomiChat
          key={user.id}
          layout="panel"
          draft={chatDraft}
          onAction={(action) => {
            // 보고서 작성 에이전트의 초안은 보고서 탭의 편집 칸으로 넘깁니다.
            // 그룹 화면에서 요청한 경우 앱의 선택 동이 비어 있으므로 초안의 지역·기준월로 맞춥니다.
            const target = action.reportDraft?.context;
            if (target) { setCity(target.city); setMonth(target.month); setDistrict(target.district); }
            if (action.reportDraft) setReportSeed(action.reportDraft);
            if (action.view) go(action.view);
          }}
          visible={true}
          context={view === 'dashboard' && chatGroup ? {city: chatGroup.city, district: chatGroup.district, month: chatGroup.month, age: chatGroup.age, sex: chatGroup.sex} : {
            ...context,
            ...(view === 'chart' && analysisTab === 'compare' && chatScreenScope ? { screen: chatScreenScope } : {}),
            ...(view === 'chart' && analysisTab === 'evidence' && district && selectedRows.length ? {
              screen: { kind: 'evidence', from: month, to: month, districts: [district],
                metrics: selectedRows.map(row => row.metric_label) },
            } : {}),
          }}
          group={view === 'dashboard' ? chatGroup : undefined}
        />

      )}
    </div>
  );
}

// 실제 DB2 사업을 조회한 뒤 serviceKey를 서버에 보내 검토 기록을 저장합니다.
// .env의 DB 설정이 틀리면 조회 오류를 표시하며 가짜 사업으로 대체하지 않습니다.
// 분석 확인 → 사업 검토 → 보고서 순서를 보여 주고, 아직 하지 않은 앞 단계로 바로 이동하게 합니다.
// workflow.done: 0 분석 확인 저장, 1 근거 검토 완료, 2 사업 검토 저장
export function WorkflowSteps({ context, workflow, current, onView }) {
  const steps = [
    { key: 'chart', label: '분석 확인·근거 검토', done: workflow.done?.includes(0) && workflow.done?.includes(1) },
    { key: 'services', label: '사업 매칭 검토', done: workflow.done?.includes(2) },
    { key: 'report', label: '보고서 저장', done: !!workflow.workflow_complete },
  ];
  const index = steps.findIndex(s => s.key === current);
  // 사업 매칭 검토는 지역 분석 화면을 거치지 않아도 진행할 수 있습니다(검토 저장 때 앞 단계를 함께 기록).
  const blocker = !context.district ? { key: 'map', label: '지역 선택' } : current === 'services' ? null : steps.slice(0, index).find(s => !s.done);
  // 보고서 화면에는 자체 작성 단계가 있으므로, 앞 단계가 막혔을 때만 업무 단계를 보여 줍니다.
  if (current === 'report' && !blocker) return null;
  return <div className={`workflow-steps ${blocker ? 'blocked' : ''}`}>
    <ol aria-label="업무 진행 단계">{steps.map((s, i) => <li key={s.key} className={`${s.done ? 'done' : ''} ${i === index ? 'current' : ''}`}>
      <span aria-hidden="true">{s.done ? '✓' : i + 1}</span><b>{s.label}</b>{s.done ? <small>완료</small> : i === index ? <small>지금 단계</small> : null}
    </li>)}</ol>
    {blocker && <p role="status"><span>{blocker.key === 'map' ? '먼저 살펴볼 동을 선택해야 이 단계를 진행할 수 있습니다.' : `‘${blocker.label}’ 단계를 먼저 저장해야 이 단계를 진행할 수 있습니다.`}</span>
      <button className="primary" onClick={() => onView(blocker.key)}>{blocker.key === 'map' ? '지역 선택하러 가기' : `${blocker.label} 하러 가기`} →</button></p>}
  </div>;
}

export function Services({ context, workflow, mutate, busy, user, onView }) {
  const [matches, setMatches] = useState([]),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(false),
    [loaded, setLoaded] = useState(false),
    [pageSize, setPageSize] = useState(5),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState('');
  const [reviewDrafts, setReviewDrafts, clearReviewDrafts, storageFailed] = useDraft(draftKey(user, context, 'services'), {});
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
      <section className="card info-card service-review-workspace">
        <WorkflowSteps context={context} workflow={workflow} current="services" onView={onView} />
        <span className="eyebrow">SERVICE REVIEW</span>
        <h2>{context.district || '지역 선택 필요'} · 사업 매칭 검토</h2>
        <p className="hint">{storageFailed ? '브라우저 임시 보관에 실패했습니다. 새로고침하기 전에 검토 기록을 저장하세요.' : '작성 중인 검토 내용은 이 탭에서 임시 보관됩니다. 다시 방문하면 관련 사업을 조회해 이어서 작성하세요. 로그아웃하면 임시 내용은 삭제됩니다.'}</p>
        <p>
          정기 수집된 지자체 복지사업에서 선택 지역과 같은 시·도의 지역 미지정 자료를 검토 후보로 조회합니다.
          게시 지역이 이용 자격을 뜻하지는 않습니다. 지원 대상과 접수 가능 여부는 운영기관에 확인하세요.
        </p>
        <button
          className="primary"
          onClick={load}
          disabled={busy || loading || !context.district}
        >
          {loading ? '사업을 찾는 중…' : '관련 사업 조회'}
        </button>
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
                    // 서버는 분석 확인 → 근거 검토 → 사업 검토 순서를 요구하므로, 아직 기록되지 않은 앞 단계를 먼저 저장합니다.
                    let done = workflow.done || [];
                    if (!done.includes(0)) done = (await mutate('/workflow/start'))?.done;
                    if (done && !done.includes(1)) done = (await mutate('/workflow/confirm'))?.done;
                    if (!done) return;
                    const result = await mutate('/workflow/review', { serviceKey: m.key, ...review });
                    if (result) {
                      const remaining = { ...reviewDrafts }; delete remaining[m.key];
                      if (Object.keys(remaining).length) setReviewDrafts(remaining); else clearReviewDrafts();
                      setSelected('');
                    }
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
export function Report({ context, workflow, user, mutate, busy, seed, onSaved, onView }) {
  const initial = { author: userName(user), department: context.city + ' 복지정책과', contact: '', content: null, seedId: null };
  const [localDraft, setLocalDraft, clearLocalDraft, storageFailed] = useDraft(draftKey(user, context, 'report'), initial);
  const { author, department, contact, content } = localDraft;
  const [step, setStep] = useState(() => localDraft.content ? 2 : 1);
  const setAuthor = author => setLocalDraft(prev => ({ ...prev, author }));
  const setDepartment = department => setLocalDraft(prev => ({ ...prev, department }));
  const setContact = contact => setLocalDraft(prev => ({ ...prev, contact }));
  const setContent = content => setLocalDraft(prev => ({ ...prev, content: typeof content === 'function' ? content(prev.content) : content }));
  useEffect(() => {
    // 이미 임시 저장된 초안의 기본 계정명도 바꾸되, 직접 입력한 작성자는 유지합니다.
    if (localDraft.author === user.id || localDraft.author === user.account_id) {
      setLocalDraft(prev => ({ ...prev, author: userName(user) }));
    }
  }, [localDraft.author, user.id, user.account_id, user.name]);
  const [confirmed, setConfirmed] = useState(false),
    [draft, setDraft] = useState(null),
    [draftBusy, setDraftBusy] = useState(false),
    [error, setError] = useState('');
  // AI 문장 다듬기: AI 연결이 있을 때만 고를 수 있고, 저장된 근거와 대조를 통과한 문장만 씁니다.
  const [aiAvailable, setAiAvailable] = useState(false), [useAi, setUseAi] = useState(true);
  useEffect(() => { let live = true; api('/chat/config').then(d => live && setAiAvailable(!!d.aiAvailable)).catch(() => {}); return () => { live = false; }; }, []);
  useEffect(() => {
    setDraft(null);
    setConfirmed(false);
  }, [author, department, contact, content]);
  const reviewKey = JSON.stringify(workflow.reviews || []);
  useEffect(() => {
    setConfirmed(false);
    setDraft(null);
  }, [reviewKey]);
  useEffect(() => {
    if (!content && seed && localDraft.seedId !== JSON.stringify(seed) && JSON.stringify(seed.review_snapshot || []) === reviewKey &&
      ['city', 'district', 'month'].every((k) => seed.context?.[k] === context[k])) {
      setLocalDraft(prev => ({ ...prev, content: seed, seedId: JSON.stringify(seed) }));
      setStep(2);
      setDraft(null);
      setConfirmed(false);
    }
  }, [seed, reviewKey]);
  const staleContent = content && JSON.stringify(content.review_snapshot || []) !== reviewKey;
  async function generate() {
    if (content && !window.confirm('현재 편집 내용을 새 초안으로 바꿀까요? 기존 편집 내용은 사라집니다.')) return;
    setDraftBusy(true);
    setError('');
    try {
      setContent(await api('/report/content', { ...context, ai: aiAvailable && useAi }));
      setStep(2);
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
      setStep(3);
    } catch (e) {
      setError(e.message);
    } finally {
      setDraftBusy(false);
    }
  }
  async function save() {
    const result = await mutate('/report', { token: draft.token, confirmed });
    if (result) {
      clearLocalDraft({ ...initial, seedId: seed ? JSON.stringify(seed) : null });
      setDraft(null);
      setConfirmed(false);
      setError('');
      setStep(1);
      onSaved();
    }
  }
  const working = busy || draftBusy;
  const canCreateFile = workflow.done?.includes(2) && content && !staleContent &&
    [author, department, ...['title', 'summary', 'situation', 'proposal', 'next_steps'].map(k => content?.[k] || '')].every(value => value.trim());
  return <div className="scroll-view"><section className="card info-card report-workspace">
    <WorkflowSteps context={context} workflow={workflow} current="report" onView={onView} />
    <div className="workspace-heading"><div><span className="eyebrow">검토보고서</span><h2>{context.district || '지역 선택 필요'} · 복지서비스 연계 검토보고</h2><p className="hint">{context.month} · 초안을 다듬고 Word 파일을 확인한 뒤 저장하세요.</p></div></div>
    {workflow.workflow_complete && <div className="saved-report"><span>최종 보고서가 저장되어 있습니다. 새로 작성해도 이전 저장본은 이력에 남습니다.</span><a className="text-button" href={'/api/report?' + query(context)}>저장된 Word 보고서 내려받기 →</a></div>}
    <ol className="report-steps" aria-label="보고서 작업 순서">{['초안 준비', '내용 수정', '파일 확인·저장'].map((label, i) => <li key={label} className={step === i + 1 ? 'current' : ''}><button aria-current={step === i + 1 ? 'step' : undefined} disabled={working || (i > 0 && !content) || (i === 2 && !draft)} onClick={() => setStep(i + 1)}><span>{i + 1}</span>{label}</button></li>)}</ol>
    <p className="hint draft-caption">{storageFailed ? '브라우저 임시 보관에 실패했습니다. 새로고침 전에 내용을 복사해 두세요.' : '작성 내용은 이 탭에 임시 보관됩니다. 로그아웃 전에 저장해 주세요.'}</p>
    {staleContent && <p className="notice">사업 검토 근거가 달라졌습니다. 편집한 내용은 남아 있습니다. 필요한 문장을 복사해 둔 뒤 ‘초안 준비’에서 최신 근거로 다시 만들어 주세요.</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {step === 1 && <section className="report-stage" aria-label="초안 준비">
      <h3>작성 정보를 확인해 주세요.</h3><p className="hint">저장된 지역 분석과 사업 검토로 1~2쪽 분량의 초안을 만듭니다.</p>
      <div className="report-form">
        <label>작성 부서<input value={department} maxLength={100} disabled={working} onChange={e => setDepartment(e.target.value)} /></label>
        <label>작성자<input value={author} maxLength={60} disabled={working} onChange={e => setAuthor(e.target.value)} /></label>
        <label className="full">연락처 (선택)<input value={contact} maxLength={80} disabled={working} onChange={e => setContact(e.target.value)} /></label>
      </div>
      <label className="confirmation"><input type="checkbox" disabled={working || !aiAvailable} checked={aiAvailable && useAi} onChange={e => setUseAi(e.target.checked)} />
        AI로 문장 다듬기{aiAvailable ? ' · 전송 시 외부 AI 사용, 저장된 근거와 대조를 통과한 문장만 사용' : ' · 연결 설정 필요'}</label>
      <div className="form-actions">
        {!content ? <button className="primary" disabled={working || !workflow.done?.includes(2)} onClick={generate}>{draftBusy ? '초안 만드는 중…' : '보고서 초안 만들기'}</button> : <button className="primary" disabled={working} onClick={() => setStep(2)}>작성 중인 초안 이어서 수정</button>}
      </div>
      {content && <div className="regenerate-section"><span className="hint">최신 근거로 다시 만들면 편집한 내용이 바뀝니다.</span><button className="text-button" disabled={working || !workflow.done?.includes(2)} onClick={generate}>{draftBusy ? '초안 만드는 중…' : '저장된 근거로 초안 다시 만들기'}</button></div>}
    </section>}
    {step === 2 && content && <section className="report-stage" aria-label="내용 수정">
      <h3>보고서 내용을 검토하고 다듬어 주세요.</h3><p className="hint">검토 요지 → 지역 현황 → 서비스 제안 → 향후 조치 순서입니다.{content.mode ? ` · ${content.mode}` : ''}</p>
      {content.notice && <p className="notice">{content.notice}</p>}
      <div className="report-form report-editor">{[['title', '보고서 제목', 80], ['summary', '검토 요지', 350], ['situation', '지역 현황', 900], ['proposal', '복지서비스 연계·추진 제안', 1200], ['next_steps', '향후 조치 및 담당자 의견', 600]].map(([key, label, limit]) => <label className="full" key={key}>{label}<textarea aria-label={label} rows={key === 'title' ? 2 : 4} maxLength={limit} disabled={working} value={content[key]} onChange={e => setContent(prev => ({ ...prev, [key]: e.target.value }))} /><small>{content[key].length} / {limit}자</small></label>)}</div>
      <ReportQuality content={content} workflow={workflow} />
      {!canCreateFile && !staleContent && <p className="hint">작성자·부서와 보고서의 모든 항목을 입력하면 Word 파일을 만들 수 있습니다.</p>}
      <div className="form-actions"><button className="primary" disabled={working || !canCreateFile} onClick={preview}>{draftBusy ? 'Word 파일 만드는 중…' : 'Word 파일 만들고 확인하기'}</button><button className="secondary" disabled={working} onClick={() => setStep(1)}>작성 정보 수정</button></div>
    </section>}
    {step === 3 && content && <section className="report-stage" aria-label="파일 확인·저장">
      <h3>파일을 내려받아 확인한 뒤 저장해 주세요.</h3><p className="hint">내용을 다시 수정하면 Word 파일도 새로 만들어야 합니다.</p>
      {draft ? <div className="report-file"><span><strong>{content.title}</strong><small>Word 문서 · 현재 편집 내용으로 생성</small></span><a className="secondary" href={'/api/report/draft?' + query({ ...context, token: draft.token })}>보고서 내려받아 확인 →</a></div> : <p className="notice">내용이나 근거가 변경되었습니다. 내용 수정 단계에서 Word 파일을 다시 만들어 주세요.</p>}
      <label className="confirmation report-confirm"><input type="checkbox" disabled={working || !draft || !!staleContent} checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />분석 근거·사업 검토 내역·최종 의견을 확인했습니다.</label>
      <div className="form-actions"><button className="primary" disabled={working || !confirmed || !draft || !canCreateFile} onClick={save}>{busy ? '저장 중…' : '확인한 최종 보고서 저장'}</button><button className="secondary" disabled={working} onClick={() => setStep(2)}>내용 다시 수정</button></div>
    </section>}
  </section></div>;
}
