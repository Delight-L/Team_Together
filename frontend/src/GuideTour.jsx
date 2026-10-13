import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import './guide-tour.css';

// 처음 방문한 담당자를 위한 단계별 안내입니다.
// 배경을 어둡게 하고 안내할 부분만 밝게 강조한 뒤, 말풍선으로 사용법을 설명합니다.
// target은 화면에서 찾을 요소의 선택자 목록이며, 앞에서부터 처음 보이는 요소를 강조합니다.
export const GUIDE_STEPS = [
  {
    targets: ['.gd-case:not([hidden]) .gd-overview', '.gd-case:not([hidden]) .gd-summary', '.gd-files-panel:not([hidden])', '.gd-case:not([hidden])'],
    title: '이번 달 먼저 볼 변화를 확인하세요',
    text: '후보로 판정된 동의 그룹이 먼저 열립니다. 유동량이 지난달보다 얼마나 달라졌는지, 왜 이 동을 먼저 보는지 확인할 수 있어요.',
  },
  {
    targets: ['.bomi-chat.panel', '.gd-chat-slot:not([hidden]) .bomi-chat'],
    title: '보미에게 물어보세요',
    text: '«이 화면 분석»에서는 지금 보는 변화의 뜻과 근거를, «복지사업 찾기»에서는 필요한 지원과 담당 기관을 물어볼 수 있어요.',
  },
  {
    targets: ['.sidebar button[aria-label="사업 매칭 검토"]'],
    title: '필요한 지원으로 연결하세요',
    text: '확인한 필요에 맞는 복지사업을 사업 매칭 검토에서 찾아 보고, 업무 기록과 보고서 작성으로 이어 가세요.',
  },
];

const findTarget = (step) => step.targets.flatMap((s) => Array.from(document.querySelectorAll(s))).find((el) => {
  const box = el.getBoundingClientRect();
  return box.width > 0 && box.height > 0 && getComputedStyle(el).visibility !== 'hidden';
});

export default function GuideTour({ onClose, steps = GUIDE_STEPS }) {
  const [index, setIndex] = useState(0), [rect, setRect] = useState(null), [bubble, setBubble] = useState(null);
  const bubbleRef = useRef(null), primaryRef = useRef(null);
  const step = steps[index], last = index === steps.length - 1;
  // 대상 위치를 계산하고, 화면 밖이면 보이도록 스크롤합니다. 대상이 아직 그려지지 않았으면 잠시 뒤 다시 찾습니다.
  useLayoutEffect(() => {
    let tries = 0, timer;
    const measure = () => {
      const el = findTarget(step);
      if (!el) { setRect(null); if (tries++ < 10) timer = setTimeout(measure, 150); return; }
      const box = el.getBoundingClientRect();
      if (box.top < 0 || box.bottom > innerHeight) { el.scrollIntoView({ block: 'center' }); }
      const r = el.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
    };
    measure();
    const onResize = () => { tries = 0; measure(); };
    addEventListener('resize', onResize);
    return () => { clearTimeout(timer); removeEventListener('resize', onResize); };
  }, [index, step]);
  // 말풍선은 대상 아래 → 위 → 왼쪽 → 오른쪽 중 들어갈 자리에 둡니다. 좁은 화면에서는 아래쪽 판으로 보여 줍니다.
  useLayoutEffect(() => {
    const el = bubbleRef.current;
    if (!el) return;
    const w = el.offsetWidth, h = el.offsetHeight, gap = 14, pad = 12;
    if (!rect || innerWidth < 640) { setBubble(null); return; }
    const clampX = (x) => Math.min(Math.max(x, pad), innerWidth - w - pad);
    const clampY = (y) => Math.min(Math.max(y, pad), innerHeight - h - pad);
    const below = rect.top + rect.height + gap, above = rect.top - gap - h;
    if (below + h <= innerHeight - pad) setBubble({ top: below, left: clampX(rect.left + rect.width / 2 - w / 2) });
    else if (above >= pad) setBubble({ top: above, left: clampX(rect.left + rect.width / 2 - w / 2) });
    else if (rect.left - gap - w >= pad) setBubble({ top: clampY(rect.top + rect.height / 2 - h / 2), left: rect.left - gap - w });
    else setBubble({ top: clampY(rect.top + rect.height / 2 - h / 2), left: clampX(rect.left + rect.width + gap) });
  }, [rect, index]);
  useEffect(() => { primaryRef.current?.focus(); }, [index]);
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowRight' && !last) setIndex((i) => i + 1);
      else if (e.key === 'ArrowLeft' && index > 0) setIndex((i) => i - 1);
    };
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  }, [index, last, onClose]);
  const pad = 6;
  return <div className="guide-tour" role="dialog" aria-modal="true" aria-labelledby="guide-title" aria-describedby="guide-text">
    {rect ? <div className="guide-spotlight" style={{ top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }} />
      : <div className="guide-dim" />}
    <section ref={bubbleRef} className={`guide-bubble ${bubble ? '' : 'docked'}`} style={bubble ? { top: bubble.top, left: bubble.left } : undefined}>
      <h2 id="guide-title">{step.title}</h2>
      <p id="guide-text">{step.text}</p>
      <footer>
        <span aria-label={`${steps.length}단계 중 ${index + 1}단계`}>{index + 1} / {steps.length}</span>
        {index === 0 ? <button className="guide-secondary" onClick={onClose}>건너뛰기</button>
          : <button className="guide-secondary" onClick={() => setIndex(index - 1)}>이전</button>}
        <button ref={primaryRef} className="guide-primary" onClick={() => (last ? onClose() : setIndex(index + 1))}>{last ? '시작하기' : '다음'}</button>
      </footer>
    </section>
  </div>;
}
