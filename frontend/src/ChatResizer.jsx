import React from 'react';

// 보미 패널 폭은 300px ~ 화면 절반(최대 760px) 사이에서 조절합니다.
export const CHAT_MIN = 300;
const chatMax = () => Math.max(CHAT_MIN, Math.min(760, Math.round(window.innerWidth / 2)));
export const clampChatWidth = width => Math.round(Math.max(CHAT_MIN, Math.min(chatMax(), width)));

// 보미 패널 왼쪽 경계의 크기 조절 손잡이. 끌거나 ←/→ 키로 폭을 바꾸고, 더블클릭하면 기본 폭으로 돌아갑니다.
export default function ChatResizer({ width, onChange }) {
  const panelWidth = el => width || el.parentElement.getBoundingClientRect().width;
  function start(event) {
    if (event.button !== 0) return;
    const handle = event.currentTarget, right = handle.parentElement.getBoundingClientRect().right;
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add('chat-resizing');
    const move = e => onChange(clampChatWidth(right - e.clientX));
    const end = () => {
      document.body.classList.remove('chat-resizing');
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', end);
      handle.removeEventListener('pointercancel', end);
    };
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', end);
    handle.addEventListener('pointercancel', end);
  }
  function key(event) {
    const current = panelWidth(event.currentTarget);
    const next = { ArrowLeft: current + 24, ArrowRight: current - 24, Home: CHAT_MIN, End: chatMax() }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    onChange(clampChatWidth(next));
  }
  return <div
    className="chat-resizer"
    role="separator"
    aria-orientation="vertical"
    aria-label="보미 패널 너비 조절"
    aria-valuemin={CHAT_MIN}
    aria-valuemax={chatMax()}
    aria-valuenow={width || undefined}
    tabIndex={0}
    title="끌어서 보미 패널 너비 조절 · 더블클릭하면 기본 너비"
    onPointerDown={start}
    onKeyDown={key}
    onDoubleClick={() => onChange(null)}
  />;
}
