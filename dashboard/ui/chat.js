// Topic selection and saved-result guidance never trigger an LLM request.
const CHAT_TOPICS = [
  ['analysis','지역 변화 살펴보기','지도에서 동·읍·면을 선택해 저장된 변화 지표와 분석 근거를 확인하세요.'],
  ['criteria','분석 기준 이해하기','Robust Z는 평소 변화와 얼마나 다른지를 나타냅니다. 현재 분석은 전화·문자 또는 평일·휴일 이동의 Z가 모두 -2.0 이하인 묶음을 후보로 표시합니다. 후보 여부와 비교 이력 부족을 구분하며 개인의 고립을 판정하지 않습니다.'],
  ['resources','복지사업 연결하기','분석 근거 확인 후 사업 매칭 검토에서 대상·거주·소득·모집 조건을 함께 확인하세요.'],
  ['reports','검토 보고서 작성하기','분석 확인 → 사업 검토 저장 → 보고서 생성과 최종 확인 순서로 진행합니다.'],
];
function chatMenu() {
  const topic = CHAT_TOPICS.find(item => item[0] === S.chatTopic);
  return `<section class="chat-welcome"><h3>무엇을 도와드릴까요?</h3><p>먼저 궁금한 주제를 선택해 주세요.</p><div class="chat-topics">${CHAT_TOPICS.map(([key,title]) => `<button data-chat-topic="${key}" aria-pressed="${S.chatTopic === key}">${title}</button>`).join('')}</div>${topic ? `<p>${esc(topic[2])}</p>` : ''}<div class="token-note">메뉴 선택·기본 안내·저장된 결과 확인은 AI 토큰을 사용하지 않습니다. AI 에이전트를 켜고 질문을 보내면 토큰이 사용될 수 있습니다.</div><div class="chat-agent-controls"><button class="btn sm ${S.agentEnabled ? 'ghost' : ''}" data-agent-mode="${S.agentEnabled ? 'off' : 'on'}">${S.agentEnabled ? 'AI 끄기 · 기본 안내로' : 'AI 에이전트 사용'}</button></div><small>${S.agentEnabled ? 'AI 질문 모드 · 질문 전송 시 호출' : '기본 안내 모드 · AI 호출 없음'}</small></section>`;
}
listen('click', event => {
  if (!S.user) return;
  const topic = event.target.closest('[data-chat-topic]');
  if (topic) { S.chatTopic = topic.dataset.chatTopic; updateAssistant(); }
  const agent = event.target.closest('[data-agent-mode]');
  if (agent) { S.agentEnabled = agent.dataset.agentMode === 'on'; updateAssistant(); }
});
