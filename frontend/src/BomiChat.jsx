import React, { useEffect, useRef, useState } from 'react';
import { api, streamChat } from './api';
import { Icon } from './components';
import { chatFileName, chatTranscript, downloadChat, usedAi } from './chatExport.mjs';
import './bomi-chat.css';

// 보미 챗봇은 모든 메뉴에서 같은 화면을 씁니다.
// 질문은 모두 /api/chat으로 보내고, 서버의 총괄 에이전트(backend/agents/supervisor.py)가 담당을 고릅니다.
// 지역 분석 설명 · 복지사업 찾기 · 보고서 초안 작성 중 하나가 답하고, 답변마다 담당을 표시합니다.
const SUGGESTIONS = {
  group: ['이 사례의 탐지 이유', '이후 변화는 어때?', '소비·날씨 맥락 설명'],
  district: ['이 동의 변화를 요약해 줘', '어르신 돌봄 지원사업을 찾아 줘', '보고서 초안 만들어 줘'],
  city: ['이번 달 후보 지역을 알려 줘', '후보 판정은 무슨 뜻인가요?', '혼자 사는 어르신 돌봄 지원'],
};
const MENU_SUGGESTIONS = {
  map: ['이번 달 후보 지역을 알려 줘', '자료 부족과 기준 미해당은 어떻게 다른가요?', '후보 지역에서 다음에 확인할 일을 알려 줘'],
  chart: ['이 동의 지표 변화를 설명해 줘', '평소 대비 차이와 전월 변화율은 어떻게 다른가요?', '추가로 확인할 자료를 알려 줘'],
  services: ['이 지역의 지원사업 후보를 찾아 줘', '사업 이용 조건에서 무엇을 확인해야 하나요?', '어르신 돌봄 지원사업을 찾아 줘'],
  records: ['검토 의견에 어떤 내용을 기록해야 하나요?', '현장에서 추가로 확인할 사항을 알려 줘', '사업 연계 전에 확인할 일을 알려 줘'],
  report: ['보고서 초안 만들어 줘', '지역 집계자료를 보고서에 어떻게 설명해야 하나요?', '보고서에 단정하면 안 되는 내용을 알려 줘'],
};
// 답변을 기다리는 동안 보이는 말풍선: 움직이는 보미와 «. → .. → ...» 점.
// 운영체제의 움직임 줄이기 설정을 켠 사용자에게는 멈춘 그림과 고정된 «…»을 보여 줍니다.
function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return reduced;
}
function Typing() {
  const reduced = useReducedMotion();
  return <article className="bomi-message assistant bomi-typing" role="status" aria-label="보미가 답변을 작성하고 있어요">
    <img src={reduced ? '/brand/bomi-face.png' : '/brand/bomi-waiting.gif'} alt="" />
    <p>보미가 답변을 작성하고 있어요<span className={`bomi-dots ${reduced ? 'still' : ''}`} aria-hidden="true" /></p>
  </article>;
}

// 이전 대화는 최근 3쌍(질문·답 6개)만 함께 보냅니다.
const HISTORY_SIZE = 6;
// AI 스위치 상태는 사용자별로 이 브라우저에 기억합니다. 저장소를 쓸 수 없으면 기본(꺼짐)으로 둡니다.
const aiSwitchKey = userId => 'welfind-bomi-ai:' + (userId || 'guest');
function loadAiSwitch(userId) {
  try { return localStorage.getItem(aiSwitchKey(userId)) === 'on'; } catch { return false; }
}
function saveAiSwitch(userId, on) {
  try { localStorage.setItem(aiSwitchKey(userId), on ? 'on' : 'off'); } catch { /* 기억하지 못해도 동작에는 문제없음 */ }
}
export { usedAi };

function useChat(context, group, userId) {
  const contextKey = JSON.stringify([context, group || null]);
  const [messages, setMessages] = useState([]), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [config, setConfig] = useState(null);
  const [configError, setConfigError] = useState(''), [configRevision, setConfigRevision] = useState(0);
  const [retryQuestion, setRetryQuestion] = useState('');
  // AI 사용 스위치: 기본 꺼짐. 관리자가 AI를 허용했고 사용자가 켰을 때만 외부 AI를 씁니다.
  const [aiOn, setAiOn] = useState(() => loadAiSwitch(userId));
  const request = useRef(null);
  useEffect(() => {
    let active = true;
    let generation = 0;
    const load = () => {
      const current = ++generation; setConfigError('');
      api('/chat/config').then(d => { if (active && current === generation) setConfig(d); })
        .catch(() => { if (active && current === generation) { setConfig(null); setConfigError('보미 설정을 불러오지 못했습니다.'); } });
    };
    load();
    // 관리자가 AI 설정을 저장하면 다시 불러옵니다.
    window.addEventListener('welfind-ai-settings', load);
    return () => { active = false; window.removeEventListener('welfind-ai-settings', load); };
  }, [configRevision]);
  const mode = aiOn && config?.aiAvailable ? 'ai' : 'data';
  function setAi(on) { setAiOn(on); saveAiSwitch(userId, on); }
  useEffect(() => {
    request.current?.abort(); request.current = null; setMessages([]); setError(''); setRetryQuestion(''); setBusy(false);
    return () => { request.current?.abort(); request.current = null; };
  }, [contextKey]);
  function stop() {
    request.current?.abort(); request.current = null; setBusy(false);
    setMessages(previous => previous.map((m, i) => i === previous.length - 1 && m.role === 'assistant'
      ? { ...m, text: m.text || '응답이 중지되었습니다.', interrupted: true } : m));
  }
  async function send(question, retry = false) {
    if (request.current) return;
    const controller = new AbortController(); request.current = controller;
    // 화면에는 대화 전체를 남기고, 서버에는 최근 3쌍과 이번 질문만 보냅니다.
    const base = retry ? messages.slice(0, Math.max(0, messages.length - 2)) : messages;
    const kept = base.filter(m => m.text && !m.interrupted);
    const recent = kept.slice(-HISTORY_SIZE);
    const next = [...base, { role: 'user', text: question }];
    const index = next.length;
    setMessages([...next, { role: 'assistant', text: '', sources: [] }]);
    setError(''); setRetryQuestion(''); setBusy(true);
    let safeQuestion = question;
    const update = fn => { if (request.current === controller) setMessages(previous => previous.map((m, i) => i === index ? fn(m) : m)); };
    // 최근 답에서 찾은 복지사업 id: «보고서 작성해줘»를 하면 이 사업들로 초안을 만듭니다.
    const sources = [...new Set(recent.flatMap(m => (m.sources || []).map(r => r.id)))].slice(0, 10);
    try {
      const body = {
        ...context, mode, sources,
        messages: [...recent, { role: 'user', text: question }].map(m => ({ role: m.role, content: m.text.slice(0, 6000) })),
        ...(group ? { group } : {}),
      };
      await streamChat(body, (event, payload) => {
        if (request.current !== controller) return;
        if (event === 'route') update(m => ({ ...m, agent: payload.label }));
        else if (event === 'token') update(m => ({ ...m, text: m.text + payload.text }));
        else if (event === 'sources') update(m => ({ ...m, sources: payload.records, mode: payload.mode }));
        else if (event === 'replace') update(m => ({ ...m, text: payload.text, mode: payload.mode, source: payload.source || m.source }));
        else if (event === 'actions') update(m => ({ ...m, actions: payload.actions }));
        // v16 지역 변화 신호 에이전트가 제안하는 다음 질문: 답변 아래 버튼으로 보여 주고 누르면 바로 보냅니다.
        else if (event === 'follow_ups') update(m => ({ ...m, followUps: payload.questions }));
        else if (event === 'notice') {
          // 가드레일 안내(개인정보 가림, 자료에 없는 정보 가림)는 해당 답변 아래에 표시합니다.
          update(m => ({ ...m, notices: [...(m.notices || []), payload.message] }));
          // 서버가 가린 질문으로 내 말풍선을 바꿔, 다음 질문 때 개인정보가 다시 전송되지 않게 합니다.
          if (payload.question) { safeQuestion = payload.question; setMessages(previous => previous.map((m, i) => i === index - 1 ? { ...m, text: payload.question } : m)); }
        }
        else if (event === 'error') { setError(payload.message); setRetryQuestion(safeQuestion); update(m => ({ ...m, interrupted: true, actions: [] })); }
      }, controller.signal);
    } catch (e) {
      if (request.current === controller && e.name !== 'AbortError') { setError(e.message); setRetryQuestion(safeQuestion); update(m => ({ ...m, interrupted: true, actions: [] })); }
    } finally {
      if (request.current === controller) { request.current = null; setBusy(false); }
    }
  }
  const reset = () => { request.current?.abort(); request.current = null; setMessages([]); setError(''); setRetryQuestion(''); setBusy(false); };
  return { messages, busy, error, send, reset, stop, config, configError, reloadConfig: () => setConfigRevision(value => value + 1), retryQuestion, mode, aiOn, setAi };
}

// inert: 좁은 화면에서 서랍이 닫혀 있을 때 키보드 초점이 숨은 대화창으로 들어가지 않게 합니다.
export default function BomiChat({ context, group, userId, view, layout = 'embedded', expanded = false, onExpand, draft, actions = [], onAction, visible = true, inert, resizer }) {
  const [input, setInput] = useState('');
  // guided: 다른 화면에서 예시 질문을 넣어 준 상태. 입력란을 강조하고 보내는 방법을 안내합니다.
  const [guided, setGuided] = useState(false);
  const chat = useChat(context, group, userId);
  const end = useRef(null), field = useRef(null), appliedDraft = useRef(null);
  const contextKey = JSON.stringify(context);
  const targetKey = JSON.stringify([context, group || null]);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }); }, [chat.messages, chat.busy]);
  // 지역이 바뀌면 안내를 지웁니다. 아래 예시 질문 효과보다 먼저 실행되어야 같은 순간에 넣은 안내가 남습니다.
  useEffect(() => { setGuided(false); setInput(''); }, [targetKey]);
  useEffect(() => {
    if (draft?.contextKey === contextKey && appliedDraft.current !== draft.id) {
      appliedDraft.current = draft.id;
      setInput(draft.question); setGuided(!!draft.guide);
      field.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      field.current?.focus();
      // 입력란 끝에 커서를 두어 예시 문장을 바로 고칠 수 있게 합니다.
      requestAnimationFrame(() => field.current?.setSelectionRange(draft.question.length, draft.question.length));
    }
  }, [draft, contextKey]);
  function submit(value = input) {
    const question = value.trim();
    if (!question || chat.busy || question.length > 2000) return;
    setInput(''); setGuided(false); chat.send(question);
  }
  const target = group || context.age ? 'group' : context.district ? 'district' : 'city';
  const place = group ? `${group.district} · ${group.age}${group.sex === '통합' ? '' : ` · ${group.sex}`}` : `${context.city} ${context.district || '전체'}${context.age ? ` · ${context.age}` : ''}`;
  const suggestions = group || !context.district ? SUGGESTIONS[target] : MENU_SUGGESTIONS[view] || SUGGESTIONS[target];
  const month = group?.month || context.month;
  const aiAvailable = !!chat.config?.aiAvailable;
  // 대화 내보내기: 브라우저에서 바로 .txt 파일을 만듭니다(서버로 보내지 않음).
  function exportChat() {
    const exportedAt = new Date();
    downloadChat(chatTranscript({ messages: chat.messages, place, month, aiMode: chat.mode === 'ai', exportedAt }), chatFileName(place, exportedAt));
  }
  return <aside className={`bomi-chat ${group || context.age ? 'has-case' : ''} ${layout} ${layout === 'panel' ? 'chat-panel' : ''} ${expanded ? 'expanded' : ''}`} style={{ display: visible ? undefined : 'none' }} inert={inert} aria-label="보미에게 질문">
    {resizer}
    <header className="bomi-chat-head">
      <img src="/brand/bomi-face.png" alt="" />
      <div><strong>보미에게 질문</strong></div>
      <nav className="bomi-chat-actions" aria-label="대화 설정">
      <button type="button" role="switch" aria-label="AI 사용" aria-checked={chat.mode === 'ai'} className={`bomi-ai-switch ${chat.mode === 'ai' ? 'on' : ''}`}
        disabled={chat.busy || !aiAvailable} onClick={() => chat.setAi(!chat.aiOn)}
        title={aiAvailable ? '켜면 질문을 외부 AI로 보내 답변을 만듭니다' : '관리자가 AI 설정에서 AI를 켜야 사용할 수 있어요'}>
        <span className="track" aria-hidden="true"><span className="thumb" /></span>AI {chat.mode === 'ai' ? '켜짐' : '꺼짐'}
      </button>
      <button className="bomi-new" disabled={chat.busy || !chat.messages.length} onClick={exportChat} title="지금까지의 대화를 텍스트 파일(.txt)로 내려받습니다">내보내기</button>
      <button className="bomi-new" disabled={chat.busy} onClick={() => { chat.reset(); setInput(''); }}>새 대화</button>
      </nav>
      {onExpand && <>
        <button className="icon-button" onClick={onExpand} aria-label={expanded ? '챗봇 패널로 돌아가기' : '챗봇 크게 보기'}><Icon name={expanded ? 'minimize' : 'expand'} size={17} /></button>
      </>}
    </header>
    {(group || context.age) && <div className="bomi-selected-case" aria-label="챗봇 선택 사례"><span className="online-dot" />{place} · {month}</div>}
    <p className="bomi-scope">{group || context.age ? place : context.district ? context.district : `${context.city} 전체`} 기준으로 분석 설명 · 복지사업 찾기 · 보고서 초안을 도와드려요.</p>
    <p className={`bomi-mode-line ${chat.mode === 'ai' ? 'ai' : ''}`} role="status">
      {chat.mode === 'ai'
        ? `AI 사용 중 · 질문과 최근 대화가 외부 AI(${chat.config?.aiProvider || '관리자 설정'})로 전송돼요`
        : aiAvailable ? '자료 기반 답변 · 외부로 전송하지 않아요. 위 스위치로 AI를 켤 수 있어요'
          : '자료 기반 답변 · 외부 AI는 관리자에게 연결을 요청하세요'}
      {` · 최근 질문·답변 3쌍을 함께 참고해요`}
    </p>
    {chat.configError && <p className="bomi-error" role="alert">{chat.configError} <button className="text-button" onClick={chat.reloadConfig}>설정 다시 불러오기</button></p>}
    <div className="bomi-messages" aria-live="polite">
      {!chat.messages.length && <div className="bomi-welcome">
        <h3>{group || context.age ? '선택한 사례를 함께 살펴볼까요?' : '무엇을 도와드릴까요?'}</h3>
        <p>분석 근거부터 관련 복지사업과 보고서 초안까지 물어보세요.</p><div className="bomi-welcome-character"><img src="/brand/bomi-face.png" alt=""/><p>궁금한 내용을 물어보시면<br/>보미가 함께 찾아드릴게요.</p></div>
      </div>}
      {chat.messages.map((m, i) => m.role === 'assistant' && !m.text && chat.busy && i === chat.messages.length - 1 ? <Typing key={i} /> : <article key={i} className={`bomi-message ${m.role}`}>
        <small>{m.role === 'user' ? '나' : m.agent ? `보미 · ${m.agent}` : '보미'}</small>
        <p>{m.text || '답변을 완료하지 못했습니다.'}</p>
        {m.interrupted && <span className="bomi-notice">완료되지 않은 응답입니다.</span>}
        {m.role === 'assistant' && m.mode && <span className="bomi-meta">
          <span className={`bomi-badge ${usedAi(m.mode) ? 'ai' : 'data'}`}>{usedAi(m.mode) ? 'AI 답변' : '자료 기반'}</span>
          {[m.mode.split(' · ')[0], m.source].filter(Boolean).join(' · ')}
        </span>}
        {m.notices?.map(n => <p key={n} className="bomi-notice" role="status">ⓘ {n}</p>)}
        {m.role === 'assistant' && m.followUps?.length > 0 && <div className="bomi-followups" aria-label="다음 질문">
          <span>다음 질문</span>
          {m.followUps.map(q => <button type="button" key={q} disabled={chat.busy} onClick={() => submit(q)}>{q}</button>)}
        </div>}
        {m.sources?.length > 0 && <details className="bomi-sources"><summary>참고한 팀 자료 · {m.sources.length}건</summary>
          {m.sources.map(r => <div key={r.id}><strong>{r.name}</strong><p>{r.source} · p. {r.pages}</p><small>{r.status}</small></div>)}
        </details>}
        {onAction && m.actions?.map(a => <button key={a.label} className="bomi-action" onClick={() => onAction(a)}>{a.label} →</button>)}
      </article>)}
      {chat.error && <div role="alert" className="bomi-error">{chat.error}{chat.retryQuestion && <button className="text-button" disabled={chat.busy} onClick={() => chat.send(chat.retryQuestion, true)}>실패한 질문 다시 보내기</button>}</div>}
      <div ref={end} />
    </div>
    <div className="bomi-suggestions">
      {suggestions.map(q => <button key={q} disabled={chat.busy} onClick={() => { setInput(q); setGuided(true); field.current?.focus(); }}>{q}</button>)}
      {actions.map(a => <button key={a.label} className="bomi-action" onClick={a.onClick}>{a.label} →</button>)}
    </div>
    {guided && <p className="bomi-draft-guide" role="status">예시 질문을 넣어 두었어요. 그대로 보내거나 고쳐서 물어보세요. <kbd>Enter</kbd> 보내기</p>}
    <form className={`bomi-input ${guided ? 'guided' : ''}`} onSubmit={e => { e.preventDefault(); submit(); }}>
      <textarea ref={field} rows={guided ? 3 : 2} value={input} maxLength={2000} onChange={e => { setInput(e.target.value); if (!e.target.value) setGuided(false); }}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}
        placeholder="예: 이 지역은 왜 후보인가요? / 병원 동행 지원이 필요해요" aria-label="보미에게 질문" />
      {chat.busy ? <button type="button" onClick={chat.stop}>중지</button>
        : <button className="primary" disabled={!input.trim()} aria-label="질문 보내기"><Icon name="send" size={20} /></button>}
    </form>
    <p className="bomi-footnote">ⓘ 지역·집단 집계는 개인의 고립 여부를 판정하지 않으며, 사업의 운영·자격은 담당 기관 확인이 필요합니다. 개인정보는 입력하지 마세요.</p>
  </aside>;
}
