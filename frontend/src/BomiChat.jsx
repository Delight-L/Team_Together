import React, { useEffect, useRef, useState } from 'react';
import { api, streamChat } from './api';
import { Icon } from './components';
import './bomi-chat.css';

// 보미 챗봇은 모든 메뉴에서 같은 화면을 씁니다.
// 질문은 모두 /api/chat으로 보내고, 서버의 총괄 에이전트(agents/supervisor.py)가 담당을 고릅니다.
// 지역 분석 설명 · 복지사업 찾기 · 보고서 초안 작성 중 하나가 답하고, 답변마다 담당을 표시합니다.
const SUGGESTIONS = {
  group: ['이 그룹의 변화를 요약해 줘', '이 지표는 무슨 뜻인가요?', '관계 모임 지원사업을 찾아 줘'],
  district: ['이 동의 변화를 요약해 줘', '어르신 돌봄 지원사업을 찾아 줘', '보고서 초안 만들어 줘'],
  city: ['이번 달 후보 지역을 알려 줘', '후보 판정은 무슨 뜻인가요?', '혼자 사는 어르신 돌봄 지원'],
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

function useChat(context, group) {
  const contextKey = JSON.stringify([context, group || null]);
  const [messages, setMessages] = useState([]), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [config, setConfig] = useState(null);
  // 답변 방식은 담당 선택과 모든 담당 에이전트에 함께 적용됩니다. AI를 쓸 수 있으면 AI 사용이 기본입니다.
  const [answerMode, setAnswerMode] = useState(null);
  const request = useRef(null);
  useEffect(() => {
    let active = true;
    api('/chat/config').then(d => active && setConfig(d)).catch(() => active && setConfig({ aiAvailable: false, resourceCount: 0 }));
    return () => { active = false; };
  }, []);
  const mode = answerMode || (config?.aiAvailable ? 'ai' : 'data');
  useEffect(() => {
    request.current?.abort(); request.current = null; setMessages([]); setError(''); setBusy(false);
    return () => { request.current?.abort(); request.current = null; };
  }, [contextKey]);
  function stop() {
    request.current?.abort(); request.current = null; setBusy(false);
    setMessages(previous => previous.map((m, i) => i === previous.length - 1 && m.role === 'assistant'
      ? { ...m, text: m.text || '응답이 중지되었습니다.', interrupted: true } : m));
  }
  async function send(question) {
    if (request.current) return;
    const controller = new AbortController(); request.current = controller;
    const next = [...messages.filter(m => m.text && !m.interrupted).slice(-38), { role: 'user', text: question }];
    const index = next.length;
    setMessages([...next, { role: 'assistant', text: '', sources: [] }]);
    setError(''); setBusy(true);
    const update = fn => { if (request.current === controller) setMessages(previous => previous.map((m, i) => i === index ? fn(m) : m)); };
    try {
      const body = { ...context, mode, messages: next.map(m => ({ role: m.role, content: m.text.slice(0, 6000) })), ...(group ? { group } : {}) };
      await streamChat(body, (event, payload) => {
        if (request.current !== controller) return;
        if (event === 'route') update(m => ({ ...m, agent: payload.label }));
        else if (event === 'token') update(m => ({ ...m, text: m.text + payload.text }));
        else if (event === 'sources') update(m => ({ ...m, sources: payload.records, mode: payload.mode }));
        else if (event === 'replace') update(m => ({ ...m, text: payload.text, mode: payload.mode, source: payload.source || m.source }));
        else if (event === 'actions') update(m => ({ ...m, actions: payload.actions }));
        else if (event === 'notice') {
          // 가드레일 안내(개인정보 가림, 자료에 없는 정보 가림)는 해당 답변 아래에 표시합니다.
          update(m => ({ ...m, notices: [...(m.notices || []), payload.message] }));
          // 서버가 가린 질문으로 내 말풍선을 바꿔, 다음 질문 때 개인정보가 다시 전송되지 않게 합니다.
          if (payload.question) setMessages(previous => previous.map((m, i) => i === index - 1 ? { ...m, text: payload.question } : m));
        }
        else if (event === 'error') setError(payload.message);
      }, controller.signal);
    } catch (e) {
      if (request.current === controller && e.name !== 'AbortError') { setError(e.message); update(m => ({ ...m, interrupted: true })); }
    } finally {
      if (request.current === controller) { request.current = null; setBusy(false); }
    }
  }
  const reset = () => { request.current?.abort(); request.current = null; setMessages([]); setError(''); setBusy(false); };
  return { messages, busy, error, send, reset, stop, config, mode, setAnswerMode };
}

export default function BomiChat({ context, group, layout = 'embedded', expanded = false, onExpand, draft, actions = [], onAction, visible = true }) {
  const [input, setInput] = useState('');
  // guided: 다른 화면에서 예시 질문을 넣어 준 상태. 입력란을 강조하고 보내는 방법을 안내합니다.
  const [guided, setGuided] = useState(false);
  const chat = useChat(context, group);
  const end = useRef(null), field = useRef(null), appliedDraft = useRef(null);
  const contextKey = JSON.stringify(context);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }); }, [chat.messages, chat.busy]);
  // 지역이 바뀌면 안내를 지웁니다. 아래 예시 질문 효과보다 먼저 실행되어야 같은 순간에 넣은 안내가 남습니다.
  useEffect(() => { setGuided(false); }, [contextKey]);
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
  const target = group ? 'group' : context.district ? 'district' : 'city';
  const place = group ? `${group.district} · ${group.age} · ${group.sex}` : `${context.city} ${context.district || '전체'}`;
  const month = group?.month || context.month;
  const aiAvailable = !!chat.config?.aiAvailable;
  return <aside className={`bomi-chat ${layout} ${layout === 'panel' ? 'chat-panel' : ''} ${expanded ? 'expanded' : ''}`} style={{ display: visible ? undefined : 'none' }} aria-label="보미에게 질문">
    <header className="bomi-chat-head">
      <img src="/brand/bomi-face.png" alt="" />
      <div><strong>보미에게 질문</strong><small><span className="online-dot" />{place} · {month}</small></div>
      <button className="bomi-new" disabled={chat.busy} onClick={() => { chat.reset(); setInput(''); }}>새 대화</button>
      {onExpand && <>
        <button className="icon-button" onClick={onExpand} aria-label={expanded ? '챗봇 패널로 돌아가기' : '챗봇 크게 보기'}><Icon name={expanded ? 'minimize' : 'expand'} size={17} /></button>
      </>}
    </header>
    <p className="bomi-scope">{group ? '열어 둔 그룹' : context.district ? context.district : `${context.city} 전체`} 기준으로 분석 설명 · 복지사업 찾기 · 보고서 초안을 도와드려요.</p>
    <details className="bomi-mode"><summary>답변 방식 · {chat.mode === 'ai' ? 'AI 사용' : '외부 AI 사용 안 함'}{chat.config?.resourceCount ? ` · 복지사업 자료 ${chat.config.resourceCount}건` : ''}</summary>
      <select aria-label="답변 방식" value={chat.mode} disabled={chat.busy} onChange={e => chat.setAnswerMode(e.target.value)}>
        <option value="ai" disabled={!aiAvailable}>AI 사용{aiAvailable ? ' · 전송 시 외부 AI 사용' : ' · 연결 설정 필요'}</option>
        <option value="data">외부 AI 사용 안 함 · 데이터 근거와 자료 검색으로 답변</option>
      </select></details>
    <div className="bomi-messages" aria-live="polite">
      {!chat.messages.length && <div className="bomi-welcome">
        <h3>무엇을 도와드릴까요?</h3>
        <p>지금 보는 화면의 분석 근거, 관련 복지사업, 보고서 초안까지 한 곳에서 물어보세요. 질문에 맞는 담당 에이전트가 답해요.</p>
      </div>}
      {chat.messages.map((m, i) => m.role === 'assistant' && !m.text && chat.busy && i === chat.messages.length - 1 ? <Typing key={i} /> : <article key={i} className={`bomi-message ${m.role}`}>
        <small>{m.role === 'user' ? '나' : m.agent ? `보미 · ${m.agent}` : '보미'}</small>
        <p>{m.text || '답변을 완료하지 못했습니다.'}</p>
        {(m.mode || m.source) && <span className="bomi-meta">{[m.mode?.split(' · ')[0], m.source].filter(Boolean).join(' · ')}</span>}
        {m.notices?.map(n => <p key={n} className="bomi-notice" role="status">ⓘ {n}</p>)}
        {m.sources?.length > 0 && <details className="bomi-sources"><summary>참고한 팀 자료 · {m.sources.length}건</summary>
          {m.sources.map(r => <div key={r.id}><strong>{r.name}</strong><p>{r.source} · p. {r.pages}</p><small>{r.status}</small></div>)}
        </details>}
        {onAction && m.actions?.map(a => <button key={a.label} className="bomi-action" onClick={() => onAction(a)}>{a.label} →</button>)}
      </article>)}
      {chat.error && <p role="alert" className="bomi-error">{chat.error}</p>}
      <div ref={end} />
    </div>
    <div className="bomi-suggestions">
      {SUGGESTIONS[target].map(q => <button key={q} disabled={chat.busy} onClick={() => submit(q)}>{q}</button>)}
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
