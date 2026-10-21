import React, { useEffect, useState } from 'react';
import { api } from './api';
import { useTransientMessage } from './useTransientMessage';

// 관리자 «AI 설정»: 기관 전체의 외부 AI 사용 여부(기본 꺼짐)·제공사·모델·API 키를 정합니다.
// 키는 서버에만 저장되고 화면에는 끝 4자리만 보입니다. 입력한 키는 저장 후 바로 입력란에서 지웁니다.
export default function AISettings() {
  const [view, setView] = useState(null);
  const [form, setForm] = useState({ enabled: false, provider: 'openai', model: '' });
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [message, setMessage] = useTransientMessage();

  function apply(next) {
    setView(next);
    const selected = next.providers.find((p) => p.id === next.provider);
    setForm({ enabled: next.enabled, provider: next.provider, model: selected?.model || '' });
  }
  useEffect(() => {
    let active = true;
    api('/admin/ai')
      .then((d) => active && apply(d))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, []);

  async function save(extra = {}) {
    setBusy(true);
    setMessage('');
    setError('');
    try {
      apply(await api('/admin/ai', { ...form, apiKey, ...extra }));
      setApiKey('');
      // 열려 있는 보미 채팅이 새 설정(AI 사용 가능 여부)을 다시 불러오게 알립니다.
      window.dispatchEvent(new Event('welfind-ai-settings'));
      setMessage('저장했습니다. 보미와 보고서 작성에 바로 적용됩니다.');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function test() {
    setBusy(true);
    setMessage('');
    setError('');
    try {
      const result = await api('/admin/ai/test', {});
      (result.ok ? setMessage : setError)(result.message);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!view)
    return (
      <div className="scroll-view">
        <section className="card info-card">
          <h2>AI 설정</h2>
          {error ? <p className="error">{error}</p> : <p className="hint">불러오는 중…</p>}
        </section>
      </div>
    );
  const provider = view.providers.find((p) => p.id === form.provider);
  const dirty =
    !!apiKey ||
    form.enabled !== view.enabled ||
    form.provider !== view.provider ||
    form.model !== (view.providers.find((p) => p.id === view.provider)?.model || '');
  const changeProvider = (id) => {
    setApiKey('');
    setMessage('');
    setError('');
    setForm((f) => ({
      ...f,
      provider: id,
      model: view.providers.find((p) => p.id === id)?.model || '',
    }));
  };
  return (
    <div className="scroll-view">
      <section className="card info-card ai-settings">
        <h2>AI 설정</h2>
        <p>
          보미 답변과 보고서 문장 다듬기에 쓸 외부 AI를 정합니다. 꺼 두면 모든 사용자가 자료
          검색·데이터 근거로만 답을 받습니다.
        </p>
        <p className={`ai-state ${view.ready ? 'on' : 'off'}`} role="status">
          저장된 설정:{' '}
          {view.ready
            ? `사용 가능 · ${view.providers.find((p) => p.id === view.provider)?.label} · ${view.model}`
            : view.enabled
              ? '허용됨 · API 키 없음(사용 불가)'
              : '꺼짐'}
        </p>
        {dirty && (
          <p className="notice" role="status">
            아직 저장하지 않은 변경 사항이 있습니다. 저장한 뒤 연결을 확인하세요.
          </p>
        )}

        <label className="confirmation">
          <input
            type="checkbox"
            checked={form.enabled}
            disabled={busy}
            onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))}
          />
          외부 AI 사용 허용 · 켜면 사용자가 보미에서 AI 스위치를 켤 수 있습니다
        </label>

        <div className="ai-fields">
          <label>
            AI 제공사
            <select
              value={form.provider}
              disabled={busy}
              onChange={(e) => changeProvider(e.target.value)}
            >
              {view.providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                  {p.hasKey ? '' : ' · 키 없음'}
                </option>
              ))}
            </select>
          </label>
          <label>
            모델
            <input
              value={form.model}
              disabled={busy}
              maxLength={100}
              placeholder={`비우면 기본값 ${provider?.defaultModel}`}
              onChange={(e) => setForm((f) => ({ ...f, model: e.target.value.trim() }))}
            />
          </label>
          <label>
            API 키
            <input
              type="password"
              autoComplete="off"
              value={apiKey}
              disabled={busy}
              maxLength={300}
              placeholder={
                provider?.hasKey
                  ? `저장된 키 ${provider.keyHint} (${provider.keySource}) · 바꿀 때만 입력`
                  : '키를 입력하세요'
              }
              onChange={(e) => setApiKey(e.target.value.trim())}
            />
          </label>
        </div>
        <p className="hint">
          키는 서버에만 저장되며 다시 보여 주지 않습니다. 비워서 저장하면 기존 키를 유지합니다. 설정
          화면의 키가 없으면 서버 환경설정의 키를 사용합니다.
          {provider?.id === 'anthropic' &&
            ' Claude는 안전 검사로 답을 거절하면 서버가 다른 Claude 모델로 이어 답하도록(fallback) 설정되어 있습니다.'}
        </p>
        <p className="hint">
          유해 콘텐츠 검사:{' '}
          {view.moderation
            ? 'AI 사용 시 OpenAI로 검사'
            : 'OpenAI 키가 없어 검사 생략(개인정보 가림·근거 대조는 계속 적용)'}
        </p>

        <div className="ai-actions">
          <button className="primary" disabled={busy} onClick={() => save()}>
            저장
          </button>
          <button className="secondary" disabled={busy || !view.ready || dirty} onClick={test}>
            저장된 설정 연결 확인
          </button>
          {provider?.keySource === '설정 화면' && (
            <button
              className="text-button"
              disabled={busy || dirty}
              onClick={() => save({ clearKey: true })}
            >
              저장된 키 삭제
            </button>
          )}
        </div>
        <p className="hint">
          연결 확인은 저장된 설정으로 짧은 요청을 보냅니다. 키 삭제 후 서버 환경설정에 키가 남아
          있으면 해당 키를 사용합니다.
        </p>
        {message && (
          <p className="success" role="status">
            {message}
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>
    </div>
  );
}
