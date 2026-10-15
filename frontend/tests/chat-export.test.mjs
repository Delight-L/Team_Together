import assert from 'node:assert/strict';
import { test } from 'node:test';
import { chatFileName, chatTranscript, usedAi } from '../src/chatExport.mjs';

const at = new Date(2026, 9, 15, 9, 5);
const messages = [
  { role: 'user', text: '[전화번호 가림] 세곡동행 대상은?' },
  { role: 'assistant', agent: '복지사업 에이전트', mode: 'AI 대화', text: '자료상 대상은 강남구 내 사회적 고립가구입니다.',
    notices: ['개인정보로 보이는 내용(전화번호)을 가리고 처리했어요.'],
    sources: [{ name: '세곡동행', source: '추진 계획.pdf', pages: '3–4', status: '현재 운영·실적 미확인' }] },
  { role: 'user', text: '이 동의 변화를 요약해 줘' },
  { role: 'assistant', agent: '지역 변화 신호 에이전트 (v16)', mode: 'v16 · 외부 AI 호출 없음 · DB1 근거', text: '평일 이동이 6.1% 줄었어요.' },
  { role: 'user', text: '중지한 질문' },
  { role: 'assistant', text: '', interrupted: true },
];

test('대화 기록에 지역·기준월·답변 방식·담당·출처·안내가 순서대로 들어감', () => {
  const text = chatTranscript({ messages, place: '강남구 삼성1동', month: '2025-12', aiMode: false, exportedAt: at });
  assert.match(text, /^보미 대화 기록\n지역: 강남구 삼성1동\n기준월: 2025-12\n내보낸 시각: 2026-10-15 09:05\n답변 방식: 자료 기반/);
  assert.ok(text.indexOf('[나]\n[전화번호 가림] 세곡동행 대상은?') < text.indexOf('[보미 · 복지사업 에이전트]'));
  assert.match(text, /\(AI 답변 · AI 대화\)/);
  assert.match(text, /\(자료 기반 · v16 · 외부 AI 호출 없음 · DB1 근거\)/);
  assert.match(text, /ⓘ 개인정보로 보이는 내용\(전화번호\)을 가리고 처리했어요\./);
  assert.match(text, /- 세곡동행: 추진 계획\.pdf \(p\. 3–4\) · 현재 운영·실적 미확인/);
  assert.match(text, /답변을 완료하지 못했습니다\.\n※ 완료되지 않은 응답입니다\./);
  assert.match(text, /ⓘ 지역·집단 집계는 개인의 고립 여부를 판정하지 않으며/);
});

test('AI 모드로 내보내면 외부 전송 사실을 적음', () => {
  assert.match(chatTranscript({ messages: [], place: '강남구 전체', month: '', aiMode: true, exportedAt: at }), /답변 방식: AI 사용\(질문과 최근 대화가 관리자가 설정한 외부 AI로 전송됨\)/);
});

test('파일 이름은 쓸 수 없는 문자와 공백을 _로 바꾸고 시각을 붙임', () => {
  assert.equal(chatFileName('삼성1동 · 70대 · 여성', at), '보미대화_삼성1동_70대_여성_20261015-0905.txt');
  assert.equal(chatFileName('강남구 a/b:c', at), '보미대화_강남구_a_b_c_20261015-0905.txt');
});

test('AI 답변 판별은 v16의 AI 의도 판단도 포함', () => {
  assert.equal(usedAi('v16 · AI 의도 판단 · DB1 근거'), true);
  assert.equal(usedAi('데이터 근거 안내 · 외부 AI 호출 없음'), false);
});
