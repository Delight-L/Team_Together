import { compareDistrictAge } from './caseOrder.mjs';
import { useDraft } from './useDraft';
import { useTransientMessage } from './useTransientMessage';
import { draftKey, clearDrafts, hasDrafts } from './draftStore.mjs';
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { api, query } from './api';
import { Icon, Bomi, EvidenceTable } from './components';
import BomiChat from './BomiChat';
import AISettings from './AISettings';
import { Activity, Upload, WorkflowSteps } from './Workspace';
import { RegionalOverview, summarizeRegions, exampleQuestion } from './Briefing';
import { DataDialog, ReportQuality } from './Experience';
import GuideTour from './GuideTour';
import GroupDashboard from './GroupDashboard';
import RegionAnalysis from './RegionAnalysis';
import ServiceCase from './ServiceCase.jsx';
import ServiceCandidate from './ServiceCandidate.jsx';
import {
  selectedServiceContext,
  serviceDetection,
  confirmServiceEvidence,
  dashboardCaseFocus,
} from './serviceCase.mjs';
import { ReportMaterials, ReportHistory, ReportReadingPreview } from './ReportTools.jsx';
import { normalizeAgeNames } from './ageSignals.mjs';
import { serviceReviewCases, selectedReviewCase, serviceReviewContext } from './serviceReview.mjs';
import { userName } from './personas.mjs';
import { PLANNING_PROPOSAL } from './experienceLogic.mjs';
import { importReportDraft } from './reportDraft.mjs';

const menus = [
  ['dashboard', '종합 현황'],
  ['map', '지역 현황'],
  ['chart', '지역 분석'],
  ['services', '사업 매칭 검토'],
  ['report', '보고서 작성'],
];
// 예전 메뉴 이름으로 이동을 요청해도 합쳐진 메뉴의 해당 탭으로 연결합니다.
// 없어진 업무 기록 메뉴(records·followup·missions)로 이동하면 보고서 작성으로 연결합니다.
const legacyViews = {
  compare: ['chart', 'compare'],
  records: ['report'],
  followup: ['report'],
  missions: ['report'],
};
const adminMenus = [
  ['data', '데이터 관리'],
  ['activity', '활동 이력'],
  ['ai', 'AI 설정'],
];
// 메뉴마다 서로 다른 아이콘을 써서 메뉴를 접었을 때도 구분되게 합니다.
const menuIcons = { activity: 'history' };
const subtitles = {
  map: '지도에서 지역을 고르고, 탐지 이후 변화를 추적합니다.',
  chart: '지역 유형과 소비 변화, 주민들의 사회적 연결을 함께 살펴봅니다.',
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
          {sessionNotice && (
            <p className="error" role="status">
              {sessionNotice}
            </p>
          )}
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
  function openSupport() {
    setSupportOpen(true);
  }
  // 단계별 안내: 계정마다 처음 로그인할 때 한 번 자동으로 열고, 상단 ? 버튼으로 다시 볼 수 있습니다.
  const [tourOpen, setTourOpen] = useState(false);
  const tourKey = user ? 'welfind-guide-seen-v1:' + (user.account_id || user.id) : '';
  function openTour() {
    go('dashboard');
    setTourOpen(true);
  }
  function closeTour() {
    setTourOpen(false);
    try {
      localStorage.setItem(tourKey, '1');
    } catch {
      /* 저장이 막힌 브라우저는 다음 접속 때 다시 안내합니다. */
    }
  }
  const [supportOpen, setSupportOpen] = useState(false),
    [view, setView] = useState('dashboard'),
    [city, setCity] = useState('강남구'),
    [month, setMonth] = useState(''),
    [district, setDistrict] = useState(''),
    [age, setAge] = useState('');
  // 메뉴 접힘 상태도 React가 관리합니다. 화면 내용/선택 지역은 그대로 유지됩니다.
  const [navCollapsed, setNavCollapsed] = useState(() => window.innerWidth <= 1100);
  const [analysisTab, setAnalysisTab] = useState('evidence');
  const [dashboardFocus, setDashboardFocus] = useState(null);
  const [serviceSignalMonth, setServiceSignalMonth] = useState('');
  const [serviceCaseFilter, setServiceCaseFilter] = useState('all');
  const [serviceTracking, setServiceTracking] = useState(null);
  const [serviceTrackingError, setServiceTrackingError] = useState('');
  const inServices = view === 'services';
  // 모든 화면 이동은 go를 거칩니다. 좁은 화면에서는 이동 후 메뉴를 접어 본문을 가리지 않게 합니다.
  function go(target, selectedCase) {
    const [next, tab] = legacyViews[target] || [target];
    if (['dashboard', 'map', 'services'].includes(next)) {
      if (next === 'services') setServiceChatContext(false);
      const selected = selectedCase
        ? selectedServiceContext('dashboard', context, selectedCase, null)
        : context;
      setCity(selected.city);
      setDistrict(selected.district);
      setAge(selected.age || '');
      if (next === 'dashboard') setDashboardFocus(dashboardCaseFocus(data, selected, Date.now()));
      if (next === 'services') setServiceCaseFilter('all');
      const origin = selectedCase;
      const detection = serviceDetection(data, selected);
      if (origin?.signalMonth) setServiceSignalMonth(origin.signalMonth);
      else if (detection?.any_signal) setServiceSignalMonth(selected.month);
    }
    // Reports keep the original detected event's stored work context.
    if (view === 'services' && next === 'report' && serviceSelection && !serviceChatContext)
      setMonth(workflowContext.month);
    if (next === 'chart') setAnalysisTab(tab || 'evidence');
    setView(next);
    if (window.innerWidth <= 760) setNavCollapsed(true);
  }
  const [workflow, setWorkflow] = useState({}),
    [reportSeed, setReportSeed] = useState(null),
    [serviceSeed, setServiceSeed] = useState(null),
    [serviceChatContext, setServiceChatContext] = useState(false),
    [busy, setBusy] = useState(false);
  const [notice, setNotice] = useTransientMessage();
  const [chatDraft, setChatDraft] = useState(null);
  const [chatGroup, setChatGroup] = useState(null);
  const [workflowScope, setWorkflowScope] = useState('');
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
      setSessionNotice(
        '서버가 다시 시작되어 로그인 세션이 초기화되었습니다. 다시 로그인해 주세요.',
      );
    };
    window.addEventListener('welfind-session-expired', returnToLogin);
    return () => window.removeEventListener('welfind-session-expired', returnToLogin);
  }, []);
  useEffect(() => {
    if (!user) return;
    setReportSeed(null);
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
  const context = useMemo(
    () => ({ city, district, month, ...(age ? { age } : {}) }),
    [city, district, month, age],
  );
  useEffect(() => {
    if (!inServices || !user) return;
    let active = true;
    setServiceTracking(null);
    setServiceTrackingError('');
    api('/region-insights?' + query({ city }))
      .then((result) => {
        if (active) setServiceTracking({ city, tracking: result.activityTracking });
      })
      .catch((error) => {
        if (active) setServiceTrackingError(error.message);
      });
    return () => {
      active = false;
    };
  }, [inServices, city, user?.id]);
  useEffect(() => {
    setServiceCaseFilter('all');
  }, [city, month]);
  const serviceTrackingReady = inServices && serviceTracking?.city === city;
  const serviceCases = useMemo(
    () => (serviceTrackingReady ? serviceReviewCases(data, serviceTracking.tracking, context) : []),
    [serviceTrackingReady, serviceTracking, data, city, month],
  );
  const serviceSelection = serviceChatContext
    ? serviceCases.find(
        (item) => item.district === district && item.age === age && item.signalMonth === month,
      ) || null
    : selectedReviewCase(serviceCases, context, serviceSignalMonth);
  const workflowContext = useMemo(
    () =>
      inServices && !serviceChatContext ? serviceReviewContext(context, serviceSelection) : context,
    [inServices, serviceChatContext, context, serviceSelection],
  );
  const latestWorkflowContext = useRef(workflowContext);
  latestWorkflowContext.current = workflowContext;
  function selectDashboardCase(selected) {
    setDistrict(selected.district);
    setAge(selected.age || '');
    if (serviceDetection(data, selected)?.any_signal) setServiceSignalMonth(selected.month);
  }
  function selectServiceCase(selected) {
    setServiceChatContext(false);
    setCity(selected.city);
    setDistrict(selected.district);
    setAge(selected.age || '');
    setServiceSignalMonth(selected.signalMonth);
  }
  useEffect(() => {
    if (!inServices || serviceChatContext || !serviceTrackingReady) return;
    if (serviceSelection) {
      if (
        serviceSelection.district !== district ||
        serviceSelection.age !== age ||
        serviceSelection.signalMonth !== serviceSignalMonth
      )
        selectServiceCase(serviceSelection);
    }
  }, [
    inServices,
    serviceChatContext,
    serviceTrackingReady,
    serviceSelection,
    district,
    age,
    serviceSignalMonth,
  ]);

  const latestContext = useRef(context);
  latestContext.current = context;
  const rows = useMemo(
    () => (data?.assessment || []).filter((r) => city === '강남구' && r['기준연월'] === month),
    [data, city, month],
  );
  const selectedRows = rows.filter((r) => r['행정동명'] === district);
  useEffect(() => {
    setWorkflow({});
    setWorkflowScope('');
    setNotice('');
    if (!workflowContext.district) return;
    let active = true;
    api('/workflow?' + query(workflowContext))
      .then((d) => {
        if (active) {
          setWorkflow(d);
          setWorkflowScope(JSON.stringify(workflowContext));
        }
      })
      .catch((e) => active && setNotice(e.message, { persistent: true }));
    return () => {
      active = false;
    };
  }, [workflowContext, user?.id]);
  // 저장 공통 처리: 중복 클릭 방지 → 서버 저장 → 최신 업무 상태 반영.
  // 실제 저장 성공 여부와 단계 검증은 Python API 결과로 판단합니다.
  async function mutate(path, extra = {}) {
    setBusy(true);
    setNotice('');
    try {
      const result = await api(path, { ...workflowContext, ...extra });
      // 저장 중 지역을 바꿨다면 이전 지역의 상태를 새 지역 화면에 덮어쓰지 않습니다.
      if (latestWorkflowContext.current === workflowContext) {
        setWorkflow(result);
        setWorkflowScope(JSON.stringify(workflowContext));
        setNotice('저장했습니다.');
      }
      return result;
    } catch (e) {
      if (latestWorkflowContext.current === workflowContext)
        setNotice(e.message, { persistent: true });
      return null;
    } finally {
      setBusy(false);
    }
  }
  function expandChat() {
    document.querySelector('.bomi-chat textarea')?.focus();
  }
  async function logout() {
    if (
      hasDrafts() &&
      !window.confirm('로그아웃하면 임시 보관 중인 작성 내용이 삭제됩니다. 로그아웃할까요?')
    )
      return;
    await api('/logout', {});
    clearDrafts();
    setUser(null);
    setData(null);
    setView('dashboard');
    setSupportOpen(false);
  }
  const regions = useMemo(
    () =>
      summarizeRegions(
        data?.assessment || [],
        data?.geometry[city],
        city,
        month,
        data?.months || [],
      ),
    [data, city, month],
  );
  const dashboardAnalysis = useMemo(
    () =>
      data && {
        assessment: data.assessment,
        geometry: data.geometry[city],
        months: data.months,
        analysisScope: data.analysisScope,
        ageDetections: data.ageDetections,
      },
    [data, city],
  );
  useEffect(() => {
    if (!data || !tourKey || view !== 'dashboard') return;
    let seen = false;
    try {
      seen = localStorage.getItem(tourKey) === '1';
    } catch {
      /* 저장소를 읽을 수 없으면 안내를 보여 줍니다. */
    }
    if (!seen) setTourOpen(true);
  }, [data, tourKey]);
  // 동을 고르지 않고 지역 분석을 열면 확인 후보가 가장 많은 동을 먼저 보여 줍니다.
  useEffect(() => {
    if (view !== 'chart' || district) return;
    const top = regions.find((r) => r.count > 0) || regions.find((r) => r.rows.length);
    if (top) setDistrict(top.name);
  }, [view, regions]);
  if (checking) return <div className="loading">복지탐정 업무 공간을 준비하고 있습니다…</div>;
  if (!user)
    return (
      <Login
        onLogin={(nextUser) => {
          setSessionNotice('');
          setUser(nextUser);
        }}
        sessionNotice={sessionNotice}
      />
    );
  const select = (name) => setDistrict(name);
  const briefingProps = {
    regions,
    assessment: data?.assessment || [],
    age,
    onAgeChange: setAge,
    onMonthChange: setMonth,
    signalMonth: serviceSignalMonth,
    onSignalMonthChange: setServiceSignalMonth,
    city,
    month,
    geometry: data?.geometry[city],
    selected: district,
    onSelect: select,
    // 지역 상세의 «보미와 근거 살펴보기»: 그 동 기준으로 채팅을 맞추고 예시 질문을 입력란에 넣어 둡니다.
    onChat: (region) => {
      if (!region?.name) {
        expandChat();
        return;
      }
      setDistrict(region.name);
      setChatDraft({
        id: Date.now(),
        contextKey: JSON.stringify({ city, district: region.name, month }),
        question: exampleQuestion(region),
        guide: true,
      });
    },
    onInspect: (name) => {
      setDistrict(name);
      go('chart');
    },
    onAsk: (name, question) => {
      setDistrict(name);
      setChatDraft({
        id: Date.now(),
        contextKey: JSON.stringify({ city, district: name, month }),
        question,
      });
      expandChat();
    },
    busy,
    months: data?.months || [],
  };

  return (
    <div
      className={`app-shell unified-shell with-chat ${navCollapsed ? 'nav-collapsed' : ''} ${view === 'dashboard' ? 'briefing-shell group-shell' : view === 'chart' ? 'region-insights-shell' : view === 'map' ? 'followup-shell' : ''}`}
    >
      <button
        className="panel-handle menu-handle"
        onClick={() => setNavCollapsed((v) => !v)}
        aria-label={navCollapsed ? '왼쪽 메뉴 펼치기' : '왼쪽 메뉴 접기'}
        aria-expanded={!navCollapsed}
        title={navCollapsed ? '메뉴 펼치기' : '메뉴 접기'}
      >
        {navCollapsed ? '›' : '‹'}
      </button>
      <nav className="sidebar" aria-label="주 메뉴">
        <button
          className="logo-toggle"
          onClick={() => setNavCollapsed((v) => !v)}
          aria-label={navCollapsed ? '왼쪽 메뉴 펼치기' : '왼쪽 메뉴 접기'}
          aria-expanded={!navCollapsed}
          title={navCollapsed ? '메뉴 펼치기' : '메뉴 접기'}
        >
          {!navCollapsed ? (
            <span className="gd-brand">
              <img src="/brand/bomi-face.png" alt="" />
              <span>
                <b>복지탐정</b>
                <small>WELFIND</small>
              </span>
            </span>
          ) : (
            <img
              className={navCollapsed ? 'bomi-face' : 'brand-logo'}
              src={navCollapsed ? '/brand/bomi-face.png' : '/brand/welfind_logo.png'}
              alt={navCollapsed ? '보미 얼굴' : 'WELFIND 복지탐정'}
            />
          )}
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
        {user.admin && (
          <>
            <span className="nav-label">관리</span>
            {adminMenus.map(([key, label]) => (
              <button
                key={key}
                className={view === key ? 'active' : ''}
                onClick={() => go(key)}
                aria-label={label}
                aria-current={view === key ? 'page' : undefined}
              >
                <Icon name={menuIcons[key] || key} />
                <span>{label}</span>
              </button>
            ))}
          </>
        )}
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
            <button
              className="icon-button guide-trigger"
              disabled={!data}
              onClick={openTour}
              aria-label="사용 안내 다시 보기"
              title="사용 안내 다시 보기"
            >
              <Icon name="help" size={18} />
            </button>
            <span className="connected">
              <span className="online-dot" />
              {data ? `분석 자료 ${data.months?.at(-1) || ''}까지 반영` : '분석 자료 확인 중'}
            </span>
            {view !== 'dashboard' && (
              <button
                className="icon-button"
                onClick={expandChat}
                aria-label="보미 질문 입력하기"
                title="보미에게 질문"
              >
                <Icon name="chat" />
                <span className="topbar-chat-label">보미</span>
              </button>
            )}
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
              <p>
                {view === 'dashboard'
                  ? '복지 담당자가 지역의 사회적 고립 위험 신호와 생활 여건을 살펴보고, 필요한 지원을 검토하도록 돕습니다.'
                  : subtitles[view]}
              </p>
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
                {view === 'chart' && <div id="region-period-slot" />}
                {view === 'map' && <div id="followup-period-slot" />}
                {view !== 'dashboard' && view !== 'chart' && view !== 'map' && (
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
                )}
              </div>
            </div>
          </div>
          {error ? (
            <div className="error" role="alert">
              {error}
              <p>
                분석 자료를 연결하지 못했습니다. 다시 연결한 뒤에도 문제가 계속되면 관리자에게
                문의하세요.
              </p>
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
              {!rows.length && view !== 'dashboard' && (
                <div className="notice" role="status">
                  {city} · {month}의 분석 자료가 없습니다. 지역 또는 기준월을 확인해 주세요.
                </div>
              )}
              {view === 'dashboard' && (
                <GroupDashboard
                  key={user.id + ':' + city}
                  city={city}
                  month={month}
                  user={user}
                  analysis={dashboardAnalysis}
                  onActiveGroup={setChatGroup}
                  onMonthChange={setMonth}
                  focusCase={dashboardFocus}
                  selectedDistrict={district}
                  selectedAge={age}
                  onCaseSelect={selectDashboardCase}
                  onServices={(group) => go('services', group)}
                />
              )}
              {view === 'map' && <RegionalOverview {...briefingProps} />}
              {view === 'chart' && (
                <div className="scroll-view">
                  <RegionAnalysis
                    city={city}
                    district={district}
                    onSelect={setDistrict}
                    age={age}
                    onAgeChange={setAge}
                  />
                </div>
              )}
              {view === 'services' && (
                <Services
                  key={user.id + JSON.stringify(workflowContext) + month}
                  context={workflowContext}
                  reviewMonth={month}
                  requestedContext={context}
                  cases={serviceCases}
                  reviewSelection={serviceSelection}
                  caseFilter={serviceCaseFilter}
                  onCaseFilter={setServiceCaseFilter}
                  casesLoading={!serviceTrackingReady && !serviceTrackingError}
                  casesError={serviceTrackingError}
                  workflow={workflowScope === JSON.stringify(workflowContext) ? workflow : {}}
                  analysis={data}
                  onCaseChange={selectServiceCase}
                  user={user}
                  mutate={mutate}
                  busy={busy}
                  fromChatContext={serviceChatContext}
                  seed={serviceSeed}
                  onSeedUsed={() => setServiceSeed(null)}
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
                  onSaved={() => {
                    if (latestContext.current === context) setReportSeed(null);
                  }}
                />
              )}
              {view === 'data' && user.admin && (
                <div className="scroll-view">
                  <Upload />
                  <div className="data-source-strip">
                    <span>분석 출처와 판단 기준은 데이터 기준에서 확인할 수 있습니다.</span>
                    <button className="text-button" onClick={() => openSupport()}>
                      데이터 기준 보기
                    </button>
                  </div>
                </div>
              )}
              {view === 'activity' && user.admin && <Activity />}
              {view === 'ai' && user.admin && <AISettings />}
              {view === 'chat' && (
                <div className="chat-context-view">
                  <span className="eyebrow">CONNECTED ANALYSIS</span>
                  <h2>선택 지역과 대화를 연결하세요</h2>
                  <p>
                    선택한 지역을 보미의 검색 맥락에 반영합니다. 기준월은 분석 자료의 기준이며 사업
                    운영 시점과는 다릅니다.
                  </p>
                  <select
                    aria-label="챗봇 분석 지역"
                    value={district}
                    onChange={(e) => select(e.target.value)}
                  >
                    <option value="">읍·면·동 선택</option>
                    {[...(data.geometry[city]?.units || [])].sort(compareDistrictAge).map((u) => (
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
      {data && supportOpen && (
        <DataDialog
          onClose={() => setSupportOpen(false)}
          data={data}
          context={context}
          rows={selectedRows}
          user={user}
        />
      )}
      {data && tourOpen && <GuideTour onClose={closeTour} />}
      {data && (
        <BomiChat
          key={user.id}
          layout="panel"
          draft={chatDraft}
          onAction={(action) => {
            // 보고서 작성 에이전트의 초안은 보고서 탭의 편집 칸으로 넘깁니다.
            // 그룹 화면에서 요청한 경우 앱의 선택 동이 비어 있으므로 초안의 지역·기준월로 맞춥니다.
            // 복지사업 에이전트가 안내한 사업은 사업 매칭 검토 탭에서 바로 검토하도록 key를 넘깁니다.
            const target = action.reportDraft?.context;
            if (target) {
              setCity(target.city);
              setMonth(target.month);
              setDistrict(target.district);
              setAge(target.age || '');
            }
            if (action.reportDraft) setReportSeed(action.reportDraft);
            // 복지사업 에이전트가 안내한 사업은 질문한 동의 사업 매칭 검토 탭에서 바로 검토하도록 key를 넘깁니다.
            const asked = action.serviceKeys && action.context;
            if (asked?.district) {
              setCity(asked.city || city);
              setMonth(asked.month || month);
              setDistrict(asked.district);
              setAge(asked.age || '');
            }
            if (action.serviceKeys) {
              setServiceChatContext(true);
              setServiceSeed({
                id: Date.now(),
                keys: action.serviceKeys,
                names: action.serviceNames || {},
              });
            }
            if (action.view === 'services' && action.serviceKeys) setView('services');
            else if (action.reportDraft) {
              setView('report');
              if (window.innerWidth <= 760) setNavCollapsed(true);
            } else if (action.view) go(action.view);
          }}
          visible={true}
          context={
            view === 'dashboard' && chatGroup
              ? {
                  city: chatGroup.city,
                  district: chatGroup.district,
                  month: chatGroup.month,
                  age: chatGroup.age,
                  sex: chatGroup.sex,
                }
              : {
                  ...context,
                  ...(view === 'chart' &&
                  analysisTab === 'evidence' &&
                  district &&
                  selectedRows.length
                    ? {
                        screen: {
                          kind: 'evidence',
                          from: month,
                          to: month,
                          districts: [district],
                          metrics: selectedRows.map((row) => row.metric_label),
                        },
                      }
                    : {}),
                }
          }
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
function DetectionWorkflowSteps({ context, workflow, current, onView }) {
  const steps = [
    {
      key: 'chart',
      label: '분석 확인·근거 검토',
      done: workflow.done?.includes(0) && workflow.done?.includes(1),
    },
    { key: 'services', label: '사업 매칭 검토', done: workflow.done?.includes(2) },
    { key: 'report', label: '보고서 저장', done: !!workflow.workflow_complete },
  ];
  const index = steps.findIndex((s) => s.key === current);
  const blocker = !context.district
    ? { key: 'map', label: '지역 선택' }
    : steps.slice(0, index).find((s) => !s.done);
  // 보고서 화면에는 자체 작성 단계가 있으므로, 앞 단계가 막혔을 때만 업무 단계를 보여 줍니다.
  if (current === 'report' && !blocker) return null;
  return (
    <div className={`workflow-steps detection-workflow-steps ${blocker ? 'blocked' : ''}`}>
      <ol aria-label="업무 진행 단계">
        {steps.map((s, i) => (
          <li key={s.key} className={`${s.done ? 'done' : ''} ${i === index ? 'current' : ''}`}>
            <span aria-hidden="true">{s.done ? '✓' : i + 1}</span>
            <b>{s.label}</b>
            {s.done ? <small>완료</small> : i === index ? <small>지금 단계</small> : null}
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

function Services({
  context,
  workflow,
  mutate,
  busy,
  user,
  seed,
  onSeedUsed,
  onView,
  analysis,
  onCaseChange,
  fromChatContext = false,
  reviewMonth,
  cases,
  reviewSelection,
  casesLoading,
  casesError,
  caseFilter,
  onCaseFilter,
  requestedContext,
}) {
  const detection = serviceDetection(analysis, context);
  const [confirming, setConfirming] = useState(false);
  const requiresEvidence = Boolean(detection?.any_signal) && !fromChatContext;
  const reviewed = Boolean(workflow.done?.includes(1));
  function filterCases(value) {
    onCaseFilter(value);
    const visible = value === 'all' ? cases : cases.filter((item) => item.signalMonth === value);
    if (!visible.some((item) => item === reviewSelection) && visible[0]) onCaseChange(visible[0]);
  }
  async function confirmEvidence() {
    if (confirming || busy || !detection?.any_signal || workflow.analysis_changed) return;
    setConfirming(true);
    try {
      await confirmServiceEvidence(workflow, mutate);
    } finally {
      setConfirming(false);
    }
  }
  const [matches, setMatches] = useState([]),
    [error, setError] = useState(''),
    [loading, setLoading] = useState(false),
    [loaded, setLoaded] = useState(false),
    [pageSize, setPageSize] = useState(5),
    [page, setPage] = useState(1),
    [selected, setSelected] = useState(''),
    [sector, setSector] = useState('전체'),
    [focus, setFocus] = useState(null);
  const [reviewDrafts, setReviewDrafts, clearReviewDrafts] = useDraft(
    draftKey(user, context, 'services'),
    {},
  );
  const sectors = ['전체', ...new Set(matches.map((item) => item.sector).filter(Boolean))];
  const prioritized = [
    ...matches.filter((item) => focus?.keys.includes(item.key)),
    ...matches.filter((item) => !focus?.keys.includes(item.key)),
  ];
  const filteredMatches =
    sector === '전체' ? prioritized : prioritized.filter((item) => item.sector === sector);
  const pageCount = Math.max(1, Math.ceil(filteredMatches.length / pageSize));
  const pageStart = (page - 1) * pageSize;
  const visibleMatches = filteredMatches.slice(pageStart, pageStart + pageSize);
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
  const autoLookupAttempted = useRef(false);
  useEffect(() => {
    if (
      seed ||
      !requiresEvidence ||
      !reviewed ||
      busy ||
      confirming ||
      workflow.analysis_changed ||
      autoLookupAttempted.current ||
      loaded
    )
      return;
    autoLookupAttempted.current = true;
    load();
  }, [seed, requiresEvidence, reviewed, busy, confirming, workflow.analysis_changed, loaded]);
  const pagination = (
    <div className="service-pagination" aria-label="사업 목록 페이지">
      <button
        className="secondary"
        disabled={busy || loading || page === 1}
        onClick={() => changePage(page - 1)}
      >
        이전
      </button>
      <span aria-live="polite">
        {page} / {pageCount} 페이지
      </span>
      <button
        className="secondary"
        disabled={busy || loading || page === pageCount}
        onClick={() => changePage(page + 1)}
      >
        다음
      </button>
    </div>
  );
  async function load(fromChat = null) {
    if (
      busy ||
      confirming ||
      !context.district ||
      (!fromChatContext && !detection?.any_signal) ||
      (requiresEvidence && (!reviewed || workflow.analysis_changed))
    )
      return;
    setLoading(true);
    setError('');
    setSelected('');
    if (!fromChat) setFocus(null);
    try {
      const found = (await api('/services?' + query(context))).matches;
      setMatches(found);
      setSector('전체');
      setLoaded(true);
      setPage(1);
      if (fromChat) {
        const keys = fromChat.keys.filter((key) => found.some((m) => m.key === key));
        const missing = fromChat.keys
          .filter((key) => !keys.includes(key))
          .map((key) => fromChat.names[key] || '이름 미확인 사업');
        setFocus({ keys, missing });
        if (keys.length) setSelected(keys[0]);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  // 보미 채팅의 '사업 매칭 검토에서 검토하기'로 들어오면 바로 조회합니다. 동이 정해질 때까지는 넘긴 사업을 보관합니다.
  useEffect(() => {
    if (
      !seed ||
      !context.district ||
      busy ||
      confirming ||
      (requiresEvidence && (!reviewed || workflow.analysis_changed))
    )
      return;
    onSeedUsed();
    load(seed);
  }, [
    seed?.id,
    context.district,
    reviewed,
    requiresEvidence,
    busy,
    confirming,
    workflow.analysis_changed,
  ]);
  useEffect(() => {
    if (selected && focus?.keys[0] === selected)
      document.getElementById('service-review-form')?.scrollIntoView({ block: 'center' });
  }, [selected, focus]);
  return (
    <div className="scroll-view">
      {casesError && (
        <p className="error" role="alert">
          추적 자료를 불러오지 못했습니다. {casesError}
        </p>
      )}
      <ServiceCase
        context={context}
        detection={detection}
        assessment={analysis?.assessment || []}
        workflow={workflow}
        busy={busy || confirming}
        onConfirm={confirmEvidence}
        cases={cases}
        onCaseChange={onCaseChange}
        reviewMonth={reviewMonth}
        reviewSelection={reviewSelection}
        casesLoading={casesLoading}
        casesError={casesError}
        caseFilter={caseFilter}
        onCaseFilter={filterCases}
        fromChatContext={fromChatContext}
        requestedContext={requestedContext}
      />
      <section className="card info-card service-review-workspace">
        {fromChatContext && context.district && (
          <WorkflowSteps context={context} workflow={workflow} current="services" onView={onView} />
        )}
        {requiresEvidence && (
          <DetectionWorkflowSteps
            context={context}
            workflow={workflow}
            current={reviewed ? 'services' : 'chart'}
            onView={onView}
          />
        )}
        {requiresEvidence && (
          <p className="service-review-gate" role="status">
            {reviewed
              ? '근거 검토가 저장되었습니다. 관련 사업을 조회해 조건을 확인하세요.'
              : '근거 검토 완료를 저장하면 관련 사업 조회가 활성화됩니다.'}
          </p>
        )}
        {workflow.analysis_changed && (
          <p className="notice" role="status">
            이 업무를 시작한 뒤 분석 자료가 새로 적재되었습니다. 저장된 사업 검토는 이전 분석 근거를
            기준으로 합니다.{' '}
            <button
              className="text-button"
              disabled={busy}
              onClick={async () => {
                if (
                  window.confirm(
                    '최신 분석으로 업무를 다시 시작할까요? 지금까지의 사업 검토는 이전 회차 기록으로 보관되고, 저장한 보고서는 이력에 남습니다.',
                  )
                )
                  await mutate('/workflow/restart', { confirmed: true });
              }}
            >
              최신 분석으로 다시 시작
            </button>
          </p>
        )}
        <button
          className="primary"
          onClick={() => load()}
          disabled={
            busy ||
            confirming ||
            loading ||
            !context.district ||
            (!fromChatContext && !detection?.any_signal) ||
            (requiresEvidence && (!reviewed || workflow.analysis_changed))
          }
        >
          {loading ? '사업을 찾는 중…' : '관련 사업 조회'}
        </button>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {seed && !context.district && (
          <p className="hint" role="status">
            보미가 안내한 사업 {seed.keys.length}개를 받았습니다. 검토할 동을 선택하면 바로
            조회합니다.
          </p>
        )}
        {focus && (focus.keys.length > 0 || focus.missing.length > 0) && (
          <p className="hint service-chat-focus" role="status">
            {focus.keys.length > 0 &&
              `보미가 안내한 사업 ${focus.keys.length}개를 맨 위에 두었습니다. `}
            {focus.missing.length > 0 &&
              `${focus.missing.join(', ')}은(는) ${context.district} 검토 후보에 없어 여기서 검토할 수 없습니다. 이 탭은 선택 지역·연령 조건을 확인한 사업을 조회합니다.`}
          </p>
        )}
        {matches.length > 0 && (
          <div className="service-browse-heading">
            <div>
              <h2>지역·연령별 지원 사업</h2>
              <small>
                {context.city} · {context.age} · 현재 사업 자료 기준
              </small>
            </div>
            <div className="service-sector-filter" role="group" aria-label="지원 사업 분야">
              {sectors.map((name) => (
                <button
                  key={name}
                  className={sector === name ? 'active' : ''}
                  aria-pressed={sector === name}
                  onClick={() => {
                    setSector(name);
                    changePage(1);
                  }}
                >
                  {name}
                </button>
              ))}
            </div>
          </div>
        )}
        {matches.length > 0 && (
          <div className="service-list-toolbar">
            <label className="service-page-size">
              표시 개수
              <select
                aria-label="페이지당 사업 개수"
                value={pageSize}
                disabled={busy || loading}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  changePage(1);
                }}
              >
                {[5, 10, 15].map((size) => (
                  <option key={size} value={size}>
                    {size}개씩
                  </option>
                ))}
              </select>
            </label>
            <span className="service-result-count">
              총 {filteredMatches.length}개 · {pageStart + 1}–
              {Math.min(pageStart + pageSize, filteredMatches.length)}개 표시
            </span>
            {pagination}
          </div>
        )}
        {visibleMatches.map((m) => {
          const review = reviewDrafts[m.key] || { decision: '보류', note: '' };
          return (
            <article className={`service-card ${selected === m.key ? 'chosen' : ''}`} key={m.key}>
              <ServiceCandidate
                match={m}
                context={context}
                fromChat={Boolean(focus?.keys.includes(m.key))}
                selected={selected === m.key}
                disabled={busy || loading}
                onReview={() => setSelected(selected === m.key ? '' : m.key)}
              />
              {selected === m.key && (
                <div
                  className="review-form service-inline-review"
                  id="service-review-form"
                  role="group"
                  aria-label={`${m.service.name} 검토 입력`}
                >
                  <b>{m.service.name} · 검토 기록</b>
                  <label>
                    검토 결과
                    <select
                      value={review.decision}
                      disabled={busy}
                      onChange={(e) => updateReview(m.key, 'decision', e.target.value)}
                    >
                      {['적합', '보류', '부적합'].map((decision) => (
                        <option key={decision}>{decision}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    검토 근거
                    <textarea
                      value={review.note}
                      disabled={busy}
                      onChange={(e) => updateReview(m.key, 'note', e.target.value)}
                      placeholder="사업 조건과 지역 근거를 함께 기록하세요."
                    />
                  </label>
                  <button
                    className="primary"
                    disabled={busy || !review.note.trim()}
                    onClick={async () => {
                      // 첫 검토라면 서버가 지금 분석 근거를 업무에 함께 기록합니다.
                      const result = await mutate('/workflow/review', {
                        serviceKey: m.key,
                        ...review,
                      });
                      if (result) {
                        const remaining = { ...reviewDrafts };
                        delete remaining[m.key];
                        if (Object.keys(remaining).length) setReviewDrafts(remaining);
                        else clearReviewDrafts();
                        setSelected('');
                      }
                    }}
                  >
                    {busy ? '저장 중…' : '사업 검토 기록 저장'}
                  </button>
                </div>
              )}
            </article>
          );
        })}
        {matches.length > 0 && <div className="service-list-footer">{pagination}</div>}
        {loaded && !loading && !error && !matches.length && (
          <p className="hint">
            선택한 지역·연령 조건으로 검토할 사업이 현재 DB2 수집 자료에서 확인되지 않았습니다.
          </p>
        )}
      </section>
      <section className="card info-card">
        <h2>저장된 사업 검토 기록</h2>
        {workflow.reviews?.length > 0 && (
          <div className="form-actions">
            <button className="primary" onClick={() => onView('report')}>
              보고서 작성으로 →
            </button>
          </div>
        )}
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

// 보고서 항목별 글자 수 상한입니다(서버 report_writer.LIMITS와 같음).
const REPORT_LIMITS = { title: 80, summary: 350, situation: 900, proposal: 1200, next_steps: 600 };
// 내용 수정 단계의 항목과 처음 보이는 높이(minHeight)입니다.
const reportFields = (planning) => [
  { key: 'title', label: '보고서 제목', minHeight: 48 },
  { key: 'summary', label: '검토 요지', minHeight: 96 },
  { key: 'situation', label: '지역 현황', minHeight: 160 },
  planning
    ? { key: 'proposal', label: '사업 구상·추진 제안', minHeight: 160 }
    : { key: 'proposal', label: '복지서비스 연계·추진 제안', minHeight: 160 },
  { key: 'next_steps', label: '향후 조치 및 담당자 의견', minHeight: 120 },
];
const FIELD_MAX_HEIGHT = 480;

// 보고서 항목 하나: 내용에 맞춰 높이가 늘고(최대 FIELD_MAX_HEIGHT), 글자 수·빈 항목·안내 문구 문제를 칸 바로 아래에 보여 줍니다.
function ReportField({ field, limit, value, disabled, onChange }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    const height = Math.max(el.scrollHeight + 2, field.minHeight);
    el.style.height = Math.min(height, FIELD_MAX_HEIGHT) + 'px';
    el.style.overflowY = height > FIELD_MAX_HEIGHT ? 'auto' : 'hidden';
  }, [value, field.minHeight]);
  const length = value.length;
  const problem = !value.trim()
    ? '비어 있습니다. 내용을 입력해야 Word 파일을 만들 수 있습니다.'
    : length > limit
      ? `${length - limit}자를 줄여야 Word 파일을 만들 수 있습니다.`
      : field.key === 'proposal' && value.includes(PLANNING_PROPOSAL)
        ? '안내 문구를 지우고 구상·제안 내용을 직접 작성해 주세요.'
        : '';
  const note =
    !problem && length >= limit
      ? `최대 ${limit}자라 더 입력되지 않습니다. 다른 문장을 줄이면 이어서 쓸 수 있습니다.`
      : '';
  const id = 'report-field-' + field.key;
  return (
    <div className={`full report-field ${problem ? 'invalid' : ''}`}>
      <label htmlFor={id}>{field.label}</label>
      <textarea
        ref={ref}
        id={id}
        rows={field.key === 'title' ? 1 : 3}
        maxLength={Math.max(limit, length)}
        disabled={disabled}
        value={value}
        aria-invalid={!!problem || undefined}
        aria-describedby={`${id}-count${problem || note ? ` ${id}-problem` : ''}`}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className="field-meta">
        {(problem || note) && (
          <span
            id={id + '-problem'}
            className={problem ? 'field-problem' : 'field-note'}
            role={problem ? 'alert' : undefined}
          >
            {problem || note}
          </span>
        )}
        <small
          id={id + '-count'}
          className={length > limit ? 'over' : length >= limit * 0.9 ? 'near' : ''}
        >
          {length} / {limit}자
        </small>
      </div>
    </div>
  );
}

// Word 문서 생성은 Python build_report(), 단계/해시 검증은 mission_store.py가 처리합니다.
function Report({ context, workflow, user, mutate, busy, seed, onSaved, onView }) {
  const initial = {
    author: userName(user),
    department: context.city + ' 복지정책과',
    contact: '',
    content: null,
    seedId: null,
  };
  const [localDraft, setLocalDraft, clearLocalDraft, storageFailed] = useDraft(
    draftKey(user, context, 'report'),
    initial,
  );
  const { author, department, contact, content } = localDraft;
  const [material, setMaterial] = useState(null),
    [materialError, setMaterialError] = useState('');
  const [versions, setVersions] = useState([]),
    [historyLoading, setHistoryLoading] = useState(true),
    [historyError, setHistoryError] = useState('');
  useEffect(() => {
    let live = true;
    setMaterial(null);
    setMaterialError('');
    api('/report/material?' + query(context))
      .then((value) => {
        if (live) setMaterial(value);
      })
      .catch((e) => {
        if (live) setMaterialError(e.message);
      });
    return () => {
      live = false;
    };
  }, [JSON.stringify(context), workflow.analysis_run_id, JSON.stringify(workflow.reviews || [])]);
  useEffect(() => {
    let live = true;
    setHistoryLoading(true);
    setHistoryError('');
    api('/report/versions?' + query(context))
      .then((value) => {
        if (live) setVersions(value.items);
      })
      .catch((e) => {
        if (live) setHistoryError(e.message);
      })
      .finally(() => {
        if (live) setHistoryLoading(false);
      });
    return () => {
      live = false;
    };
  }, [JSON.stringify(context), workflow.report?.revision]);
  const rawSelection = localDraft.selection ?? content?.selection;
  const selection =
    rawSelection && material
      ? {
          metrics: (rawSelection.metrics || []).filter((key) => material.metrics.includes(key)),
          services: (rawSelection.services || []).filter((key) =>
            material.services.some((item) => item.key === key),
          ),
        }
      : null;
  const staleAnalysis = !!(
    content?.analysis_run_id &&
    material?.analysis_run_id &&
    content.analysis_run_id !== material.analysis_run_id
  );
  const [step, setStep] = useState(() => (localDraft.content ? 2 : 1));
  const setAuthor = (author) => setLocalDraft((prev) => ({ ...prev, author }));
  const setDepartment = (department) => setLocalDraft((prev) => ({ ...prev, department }));
  const setContact = (contact) => setLocalDraft((prev) => ({ ...prev, contact }));
  const setContent = (content) =>
    setLocalDraft((prev) => ({
      ...prev,
      content: typeof content === 'function' ? content(prev.content) : content,
    }));
  useEffect(() => {
    // 이미 임시 저장된 초안의 기본 계정명도 바꾸되, 직접 입력한 작성자는 유지합니다.
    if (localDraft.author === user.id || localDraft.author === user.account_id) {
      setLocalDraft((prev) => ({ ...prev, author: userName(user) }));
    }
  }, [localDraft.author, user.id, user.account_id, user.name]);
  const [confirmed, setConfirmed] = useState(false),
    [draft, setDraft] = useState(null),
    [draftBusy, setDraftBusy] = useState(false),
    [error, setError] = useState('');
  // AI 문장 다듬기: AI 연결이 있을 때만 고를 수 있고, 저장된 근거와 대조를 통과한 문장만 씁니다.
  const [aiAvailable, setAiAvailable] = useState(false),
    [useAi, setUseAi] = useState(true);
  useEffect(() => {
    let live = true;
    api('/chat/config')
      .then((d) => live && setAiAvailable(!!d.aiAvailable))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
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
    if (importReportDraft(localDraft, seed, context)) {
      setLocalDraft((prev) => importReportDraft(prev, seed, context) || prev);
      setStep(2);
      setDraft(null);
      setConfirmed(false);
    }
  }, [seed, reviewKey, JSON.stringify(context)]);
  const staleContent = content && JSON.stringify(content.review_snapshot || []) !== reviewKey;
  async function generate() {
    if (
      content &&
      !window.confirm('현재 편집 내용을 새 초안으로 바꿀까요? 기존 편집 내용은 사라집니다.')
    )
      return;
    setDraftBusy(true);
    setError('');
    try {
      setContent(await api('/report/content', { ...context, ai: aiAvailable && useAi, selection }));
      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setDraftBusy(false);
    }
  }
  // 사업 검토가 바뀌었을 때 제안 칸만 최신 검토로 다시 만들고, 나머지 항목의 편집 내용은 그대로 둡니다.
  async function refreshProposal() {
    setDraftBusy(true);
    setError('');
    try {
      const fresh = await api('/report/proposal', {
        ...context,
        selection: content.selection ?? null,
      });
      setContent((prev) => ({
        ...prev,
        ...fresh,
        previous_proposal: prev.proposal,
        notice:
          fresh.kind !== prev.kind
            ? fresh.kind === 'planning'
              ? '저장된 사업 검토가 없어 구상 보고서로 바뀌었습니다. 제목을 확인해 주세요.'
              : '사업 검토가 추가되어 연계 검토보고로 바뀌었습니다. 제목을 확인해 주세요.'
            : prev.notice,
      }));
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
      setDraft(
        await api('/report/preview', {
          ...context,
          author,
          department,
          contact,
          content,
          review_id: content.review_id,
        }),
      );
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
  function copyVersion(item) {
    if (content && !window.confirm('작성 중인 내용을 선택한 저장본으로 바꿀까요?')) return;
    const copied = Object.fromEntries(
      [
        'title',
        'summary',
        'situation',
        'proposal',
        'next_steps',
        'selection',
        'review_id',
        'review_snapshot',
        'kind',
      ].map((key) => [key, item.content[key]]),
    );
    setLocalDraft((prev) => ({
      ...prev,
      author: item.author || userName(user),
      department: item.department || initial.department,
      contact: item.contact || '',
      selection: copied.selection,
      content: {
        ...copied,
        analysis_run_id: item.analysis_run_id,
        notice: `${item.revision}차 저장본을 복사했습니다. 현재 근거와 내용을 확인한 후 새 차수로 저장하세요.`,
      },
    }));
    setStep(2);
    setError('');
  }
  // 사업 검토가 없으면 구상 보고서입니다. 검토 도움말은 업무 근거가 아직 없을 때 초안에 담긴 분석 근거로 대조합니다.
  const planning = !workflow.reviews?.length;
  const qualityWorkflow = {
    ...workflow,
    analysis_evidence: workflow.analysis_evidence || content?.analysis_evidence,
    analysis_source: workflow.analysis_source || content?.analysis_source,
  };
  const placeholderLeft = !!content?.proposal?.includes(PLANNING_PROPOSAL);
  // Word 파일을 만들 수 없는 이유를 버튼 옆에 그대로 보여 주기 위해 하나씩 모읍니다.
  const fieldLabels = Object.fromEntries(
    reportFields(planning).map((field) => [field.key, field.label]),
  );
  const emptyFields = Object.keys(REPORT_LIMITS)
    .filter((key) => !(content?.[key] || '').trim())
    .map((key) => fieldLabels[key]);
  const longFields = Object.entries(REPORT_LIMITS)
    .filter(([key, limit]) => (content?.[key] || '').length > limit)
    .map(([key]) => fieldLabels[key]);
  const fileBlockers = !content
    ? []
    : [
        staleAnalysis &&
          '초안의 분석 근거가 현재 업무와 다릅니다. 초안 준비에서 현재 근거로 다시 만들어 주세요.',
        !material && '보고서 근거를 불러온 후 파일을 만들 수 있습니다.',
        staleContent &&
          '사업 검토 근거가 달라졌습니다. 위의 ‘제안 칸만 최신 검토로 갱신’을 먼저 눌러 주세요.',
        !(author.trim() && department.trim()) && '작성 부서와 작성자를 입력해 주세요.',
        emptyFields.length && `비어 있는 항목: ${emptyFields.join(', ')}`,
        longFields.length && `글자 수를 넘은 항목: ${longFields.join(', ')}`,
        placeholderLeft && '제안 칸의 안내 문구를 지우고 내용을 직접 작성해 주세요.',
      ].filter(Boolean);
  const canCreateFile = content && !fileBlockers.length;
  return (
    <div className="scroll-view">
      <section className="card info-card report-workspace">
        <WorkflowSteps context={context} workflow={workflow} current="report" onView={onView} />
        <div className="workspace-heading">
          <div>
            <h2>
              {context.district || '지역 선택 필요'} ·{' '}
              {planning ? '복지 사업 구상 검토보고' : '복지서비스 연계 검토보고'}
            </h2>
            <p className="hint">{context.month} 기준</p>
          </div>
        </div>
        {workflow.workflow_complete && (
          <div className="saved-report">
            <span>
              {workflow.reviews_after_report
                ? '보고서를 저장한 뒤 사업 검토가 추가되었습니다. 초안을 다시 만들어 저장하면 다음 차수 보고서가 됩니다.'
                : '최종 보고서가 저장되어 있습니다. 새로 작성해도 이전 저장본은 이력에 남습니다.'}
            </span>
            <a className="text-button" href={'/api/report?' + query(context)}>
              저장된 Word 보고서 내려받기 →
            </a>
          </div>
        )}
        <ReportHistory
          versions={versions}
          loading={historyLoading}
          error={historyError}
          context={context}
          onCopy={copyVersion}
          disabled={working}
        />
        {workflow.analysis_changed && (
          <div className="notice" role="status">
            <p>
              새 분석 자료가 있습니다. 현재 보고서는 저장 당시 분석 근거로 작성됩니다. 최신 분석으로
              전환하면 기존 사업 검토는 이전 회차에 보관됩니다.
            </p>
            <button
              className="secondary"
              disabled={working}
              onClick={async () => {
                if (
                  !window.confirm(
                    '최신 분석으로 업무를 다시 시작할까요? 기존 검토는 이전 회차에 보관됩니다. 편집 중인 보고서는 남지만 새 근거로 초안을 다시 만들어야 합니다.',
                  )
                )
                  return;
                const result = await mutate('/workflow/restart', { confirmed: true });
                if (result) {
                  setDraft(null);
                  setConfirmed(false);
                  setStep(1);
                }
              }}
            >
              최신 분석으로 다시 작성
            </button>
          </div>
        )}
        {materialError && (
          <p className="error" role="alert">
            근거 조회 실패: {materialError}{' '}
            <button
              className="text-button"
              onClick={() => {
                setMaterialError('');
                api('/report/material?' + query(context))
                  .then(setMaterial)
                  .catch((e) => setMaterialError(e.message));
              }}
            >
              다시 조회
            </button>
          </p>
        )}
        {staleAnalysis && (
          <p className="notice" role="status">
            편집 중인 초안은 이전 분석 근거로 작성되었습니다. 초안 준비에서 현재 근거로 다시 만들어
            주세요.{' '}
            <button className="text-button" onClick={() => setStep(1)}>
              초안 준비로 이동
            </button>
          </p>
        )}
        <ol className="report-steps" aria-label="보고서 작업 순서">
          {['초안 준비', '내용 수정', '파일 확인·저장'].map((label, i) => (
            <li key={label} className={step === i + 1 ? 'current' : ''}>
              <button
                aria-current={step === i + 1 ? 'step' : undefined}
                disabled={working || (i > 0 && !content) || (i === 2 && !draft)}
                onClick={() => setStep(i + 1)}
              >
                <span>{i + 1}</span>
                {label}
              </button>
            </li>
          ))}
        </ol>
        {storageFailed && (
          <p className="error" role="alert">
            브라우저 임시 보관에 실패했습니다. 새로고침 전에 내용을 복사해 두세요.
          </p>
        )}
        {staleContent && (
          <p className="notice">
            사업 검토 근거가 달라졌습니다. 제안 칸만 최신 검토로 갱신하면 다른 항목의 편집 내용은
            그대로 남습니다.{' '}
            <button className="text-button" disabled={working} onClick={refreshProposal}>
              {draftBusy ? '갱신 중…' : '제안 칸만 최신 검토로 갱신'}
            </button>
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {step === 1 && (
          <section className="report-stage" aria-label="초안 준비">
            <h3>작성 정보 확인</h3>
            <ReportMaterials
              material={material}
              selection={selection}
              onChange={(value) => setLocalDraft((prev) => ({ ...prev, selection: value }))}
              disabled={working}
            />
            <div className="report-form">
              <label>
                작성 부서
                <input
                  value={department}
                  maxLength={100}
                  disabled={working}
                  onChange={(e) => setDepartment(e.target.value)}
                />
              </label>
              <label>
                작성자
                <input
                  value={author}
                  maxLength={60}
                  disabled={working}
                  onChange={(e) => setAuthor(e.target.value)}
                />
              </label>
              <label className="full">
                연락처 (선택)
                <input
                  value={contact}
                  maxLength={80}
                  disabled={working}
                  onChange={(e) => setContact(e.target.value)}
                />
              </label>
            </div>
            <label className="confirmation">
              <input
                type="checkbox"
                disabled={working || !aiAvailable}
                checked={aiAvailable && useAi}
                onChange={(e) => setUseAi(e.target.checked)}
              />
              <span>
                AI로 문장 다듬기
                <small>
                  {aiAvailable
                    ? '외부 AI 사용 · 근거와 대조를 통과한 문장만 반영'
                    : 'AI 연결 설정 필요'}
                </small>
              </span>
            </label>
            <div className="form-actions">
              {!content ? (
                <button
                  className="primary"
                  disabled={working || !context.district || !material}
                  onClick={generate}
                >
                  {draftBusy ? '초안 만드는 중…' : '보고서 초안 만들기'}
                </button>
              ) : (
                <button className="primary" disabled={working} onClick={() => setStep(2)}>
                  작성 중인 초안 이어서 수정
                </button>
              )}
            </div>
            {content && (
              <div className="regenerate-section">
                <button
                  className="text-button"
                  disabled={working || !context.district || !material}
                  onClick={generate}
                >
                  {draftBusy ? '초안 만드는 중…' : '선택한 근거로 초안 새로 만들기'}
                </button>
              </div>
            )}
          </section>
        )}
        {step === 2 && content && (
          <section className="report-stage" aria-label="내용 수정">
            <div className="report-stage-head">
              <h3>내용 수정</h3>
              {content.mode && (
                <span className={`bomi-badge ${content.mode.includes('AI') ? 'ai' : 'data'}`}>
                  {content.mode}
                </span>
              )}
            </div>
            {content.notice && <p className="notice">{content.notice}</p>}
            <div className="report-form report-editor">
              {reportFields(planning).map((field) => (
                <ReportField
                  key={field.key}
                  field={field}
                  limit={REPORT_LIMITS[field.key]}
                  value={content[field.key] || ''}
                  disabled={working}
                  onChange={(value) => setContent((prev) => ({ ...prev, [field.key]: value }))}
                />
              ))}
            </div>
            <ReportQuality content={content} workflow={qualityWorkflow} />
            {content.previous_proposal && (
              <details className="secondary-details">
                <summary>갱신 전 제안 내용</summary>
                <pre className="previous-proposal">{content.previous_proposal}</pre>
                <button
                  className="text-button"
                  disabled={working}
                  onClick={() => setContent((prev) => ({ ...prev, previous_proposal: undefined }))}
                >
                  갱신 전 내용 닫기
                </button>
              </details>
            )}
            <div className="form-actions report-sticky-actions">
              {fileBlockers.length > 0 && (
                <div className="file-blockers" id="report-file-blockers">
                  <strong>Word 파일을 만들려면 다음을 해결해 주세요.</strong>
                  <ul>
                    {fileBlockers.map((text) => (
                      <li key={text}>{text}</li>
                    ))}
                  </ul>
                </div>
              )}
              <button
                className="primary"
                disabled={working || !canCreateFile}
                aria-describedby={fileBlockers.length ? 'report-file-blockers' : undefined}
                onClick={preview}
              >
                {draftBusy ? 'Word 파일 만드는 중…' : 'Word 파일 만들고 확인하기'}
              </button>
              <button className="secondary" disabled={working} onClick={() => setStep(1)}>
                작성 정보 수정
              </button>
            </div>
          </section>
        )}
        {step === 3 && content && (
          <section className="report-stage" aria-label="파일 확인·저장">
            <h3>파일 확인·저장</h3>
            <ReportReadingPreview
              content={content}
              author={author}
              department={department}
              contact={contact}
              month={context.month}
              fields={reportFields(planning)}
            />
            {draft ? (
              <div className="report-file">
                <span>
                  <strong>{content.title}</strong>
                  <small>Word 문서 · 현재 편집 내용</small>
                </span>
                <a
                  className="secondary"
                  href={'/api/report/draft?' + query({ ...context, token: draft.token })}
                >
                  내려받기
                </a>
              </div>
            ) : (
              <p className="notice">
                내용이나 근거가 변경되었습니다. 내용 수정 단계에서 Word 파일을 다시 만들어 주세요.
              </p>
            )}
            <label className="confirmation report-confirm">
              <input
                type="checkbox"
                disabled={working || !draft || !!staleContent}
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
              />
              {planning
                ? '분석 근거와 구상·제안 내용을 확인했습니다(구상 보고서로 저장).'
                : '분석 근거와 사업 검토 내용을 확인했습니다.'}
            </label>
            <div className="form-actions">
              <button
                className="primary"
                disabled={working || !confirmed || !draft || !canCreateFile}
                onClick={save}
              >
                {busy ? '저장 중…' : '최종 보고서 저장'}
              </button>
              <button className="secondary" disabled={working} onClick={() => setStep(2)}>
                내용 다시 수정
              </button>
            </div>
          </section>
        )}
      </section>
    </div>
  );
}
