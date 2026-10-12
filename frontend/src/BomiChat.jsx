import React, { useEffect, useRef, useState } from 'react';
import { api, streamWelfareChat } from './api';
import { Icon } from './components';
import './bomi-chat.css';

// 보미 챗봇은 모든 메뉴에서 같은 화면을 씁니다.
// «이 화면 분석»: 그룹을 열었으면 그룹 근거(/groups/chat), 아니면 지금 보는 동·구의 분석 근거(/region/chat)를 설명합니다.
// «복지사업 찾기»: 팀 자료에서 복지사업과 담당 기관을 찾아 안내합니다(/chat 스트리밍).
const ANALYSIS_SUGGESTIONS = {
  group: ['이 그룹의 변화를 요약해 줘', '이 지표는 무슨 뜻인가요?', '다음에 무엇을 확인하나요?'],
  district: ['이 동의 변화를 요약해 줘', '후보 판정은 무슨 뜻인가요?', '다음에 무엇을 확인하나요?'],
  city: ['이번 달 후보 지역을 알려 줘', '후보 판정은 무슨 뜻인가요?', '다음에 무엇을 확인하나요?'],
};
const WELFARE_SUGGESTIONS = ['혼자 사는 어르신 돌봄 지원', '병원에 함께 가줄 지원이 있나요?', '청년이 참여할 관계 모임을 찾아주세요'];

function useAnalysisChat(context, group) {
  const target = group ? 'group' : context.district ? 'district' : 'city';
  const key = group ? JSON.stringify(group) : JSON.stringify(context);
  const [messages, setMessages] = useState([]), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [answerMode, setAnswerMode] = useState('data'), [aiAvailable, setAiAvailable] = useState(false);
  const controller = useRef(null);
  useEffect(() => { let live = true; api('/groups/config').then(d => live && setAiAvailable(d.aiAvailable)).catch(() => {}); return () => { live = false; }; }, []);
  useEffect(() => { controller.current?.abort(); setMessages([]); setError(''); setBusy(false); }, [key]);
  useEffect(() => () => controller.current?.abort(), []);
  async function send(question) {
    if (busy) return;
    setError(''); setBusy(true);
    const history = messages.slice(-8).map(m => ({ role: m.role, content: m.text.slice(0, 4000) }));
    setMessages(m => [...m, { role: 'user', text: question }]);
    controller.current = new AbortController();
    const signal = controller.current.signal;
    try {
      const body = { question, mode: answerMode, history };
      const result = group ? await api('/groups/chat', { ...group, ...body }, { signal }) : await api('/region/chat', { ...context, ...body }, { signal });
      if (!signal.aborted) setMessages(m => [...m, { role: 'assistant', text: result.answer, mode: result.mode, source: result.sources?.[0]?.label }]);
    } catch (e) { if (e.name !== 'AbortError') setError(e.message); }
    finally { if (!signal.aborted) setBusy(false); }
  }
  const reset = () => { controller.current?.abort(); setMessages([]); setError(''); setBusy(false); };
  const stop = () => { controller.current?.abort(); setBusy(false); };
  return { target, messages, busy, error, send, reset, stop, answerMode, setAnswerMode, aiAvailable };
}

function useWelfareChat(context) {
  const contextKey = JSON.stringify(context);
  const [messages, setMessages] = useState([]), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [status, setStatus] = useState('연결 확인 중');
  const request = useRef(null);
  useEffect(() => {
    let active = true;
    api('/chat/config').then(d => active && setStatus(`복지사업 자료 ${d.resourceCount}건에서 찾아요`)).catch(() => active && setStatus('연결 확인 필요'));
    return () => { active = false; };
  }, []);
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
      await streamWelfareChat(context, next.map(m => ({ role: m.role, content: m.text })), (event, payload) => {
        if (request.current !== controller) return;
        if (event === 'token') update(m => ({ ...m, text: m.text + payload.text }));
        else if (event === 'sources') update(m => ({ ...m, sources: payload.records, mode: payload.mode }));
        else if (event === 'replace') update(m => ({ ...m, text: payload.text, mode: payload.mode }));
        else if (event === 'error') setError(payload.message);
      }, controller.signal);
    } catch (e) {
      if (request.current === controller && e.name !== 'AbortError') { setError(e.message); update(m => ({ ...m, interrupted: true })); }
    } finally {
      if (request.current === controller) { request.current = null; setBusy(false); }
    }
  }
  const reset = () => { request.current?.abort(); request.current = null; setMessages([]); setError(''); setBusy(false); };
  return { messages, busy, error, send, reset, stop, status };
}

export default function BomiChat({ context, group, layout = 'embedded', expanded = false, onExpand, onClose, draft, actions = [], visible = true }) {
  const [tab, setTab] = useState('analysis');
  const [inputs, setInputs] = useState({ analysis: '', welfare: '' });
  const analysis = useAnalysisChat(context, group);
  const welfare = useWelfareChat(context);
  const chat = tab === 'analysis' ? analysis : welfare;
  const input = inputs[tab], setInput = value => setInputs(old => ({ ...old, [tab]: value }));
  const end = useRef(null), field = useRef(null), appliedDraft = useRef(null);
  const contextKey = JSON.stringify(context);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }); }, [chat.messages, chat.busy, tab]);
  useEffect(() => {
    if (draft?.contextKey === contextKey && appliedDraft.current !== draft.id) {
      appliedDraft.current = draft.id;
      const target = draft.tab || 'analysis';
      setTab(target); setInputs(old => ({ ...old, [target]: draft.question })); field.current?.focus();
    }
  }, [draft, contextKey]);
  function submit(value = input) {
    const question = value.trim();
    if (!question || chat.busy || question.length > 2000) return;
    setInput(''); chat.send(question);
  }
  const place = group ? `${group.district} · ${group.age} · ${group.sex}` : `${context.city} ${context.district || '전체'}`;
  const month = group?.month || context.month;
  const suggestions = tab === 'analysis' ? ANALYSIS_SUGGESTIONS[analysis.target] : WELFARE_SUGGESTIONS;
  return <aside className={`bomi-chat ${layout} ${layout === 'panel' ? 'chat-panel' : ''} ${expanded ? 'expanded' : ''}`} style={{ display: visible ? undefined : 'none' }} aria-label="보미에게 질문">
    <header className="bomi-chat-head">
      <img src="/brand/bomi-face.png" alt="" />
      <div><strong>보미에게 질문</strong><small><span className="online-dot" />{place} · {month}</small></div>
      <button className="bomi-new" disabled={chat.busy} onClick={() => { chat.reset(); setInput(''); }}>새 대화</button>
      {layout === 'panel' && <>
        <button className="icon-button" onClick={onExpand} aria-label={expanded ? '챗봇 패널로 돌아가기' : '챗봇 크게 보기'}><Icon name={expanded ? 'minimize' : 'expand'} size={17} /></button>
        <button className="icon-button" onClick={onClose} aria-label="챗봇 닫기"><Icon name="close" size={17} /></button>
      </>}
    </header>
    <div className="bomi-tabs" role="tablist" aria-label="질문 종류">
      {[['analysis', '이 화면 분석'], ['welfare', '복지사업 찾기']].map(([key, label]) => <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>)}
    </div>
    <p className="bomi-scope">{tab === 'analysis'
      ? (group ? '열어 둔 그룹의 집계 근거를 설명합니다.' : context.district ? '선택한 동의 분석 근거를 설명합니다.' : '이번 달 후보 지역과 판정 기준을 설명합니다.')
      : '팀 자료에서 복지사업과 담당 기관을 찾아 안내합니다.'}</p>
    {tab === 'analysis' && <details className="bomi-mode"><summary>답변 방식 · {analysis.answerMode === 'data' ? '데이터 근거 안내' : 'AI 해석'}</summary>
      <select aria-label="답변 방식" value={analysis.answerMode} disabled={analysis.busy} onChange={e => analysis.setAnswerMode(e.target.value)}>
        <option value="data">데이터 근거 안내 · 외부 AI 사용 안 함</option>
        <option value="ai" disabled={!analysis.aiAvailable}>AI 해석{analysis.aiAvailable ? ' · 전송 시 외부 AI 사용' : ' · 연결 설정 필요'}</option>
      </select></details>}
    {tab === 'welfare' && <p className="bomi-mode">{welfare.status}</p>}
    <div className="bomi-messages" aria-live="polite">
      {!chat.messages.length && <div className="bomi-welcome">
        <h3>{tab === 'analysis' ? '지금 보는 화면에 대해 물어보세요.' : '어떤 도움이 필요하신가요?'}</h3>
        <p>{tab === 'analysis' ? '변화의 크기, 판정의 뜻, 다음에 할 일을 근거와 함께 알려 드려요.' : '필요한 지원을 알려 주면 관련 사업과 확인할 다음 단계를 찾아 드려요.'}</p>
      </div>}
      {chat.messages.map((m, i) => <article key={i} className={`bomi-message ${m.role}`}>
        <small>{m.role === 'user' ? '나' : '보미'}</small>
        <p>{m.text || (chat.busy ? '관련 자료를 찾고 있어요…' : '답변을 완료하지 못했습니다.')}</p>
        {m.mode && <span className="bomi-meta">{m.mode.split(' · ')[0]}</span>}
        {m.sources?.length > 0 && <details className="bomi-sources"><summary>참고한 팀 자료 · {m.sources.length}건</summary>
          {m.sources.map(r => <div key={r.id}><strong>{r.name}</strong><p>{r.source} · p. {r.pages}</p><small>{r.status}</small></div>)}
        </details>}
      </article>)}
      {tab === 'analysis' && analysis.busy && <p className="bomi-pending">근거를 확인하고 있어요…</p>}
      {chat.error && <p role="alert" className="bomi-error">{chat.error}</p>}
      <div ref={end} />
    </div>
    <div className="bomi-suggestions">
      {suggestions.map(q => <button key={q} disabled={chat.busy} onClick={() => submit(q)}>{q}</button>)}
      {tab === 'analysis' && actions.map(a => <button key={a.label} className="bomi-action" onClick={a.onClick}>{a.label} →</button>)}
    </div>
    <form className="bomi-input" onSubmit={e => { e.preventDefault(); submit(); }}>
      <textarea ref={field} rows="2" value={input} maxLength={2000} onChange={e => setInput(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }}
        placeholder={tab === 'analysis' ? '예: 이 동은 왜 후보인가요?' : '예: 병원 동행 지원이 필요해요'} aria-label={tab === 'analysis' ? '화면 분석 질문' : '복지사업 질문'} />
      {chat.busy && tab === 'welfare' ? <button type="button" onClick={chat.stop}>중지</button>
        : <button className="primary" disabled={!input.trim() || chat.busy} aria-label="질문 보내기"><Icon name="send" size={20} /></button>}
    </form>
    <p className="bomi-footnote">{tab === 'analysis' ? 'ⓘ 지역·집단 집계이며 개인의 고립 여부를 판정하지 않습니다.' : 'ⓘ 운영·자격·접수는 담당 기관 확인이 필요합니다. 개인정보는 입력하지 마세요.'}</p>
  </aside>;
}
