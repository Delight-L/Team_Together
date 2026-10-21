// 보미 대화 내보내기: 화면에 남은 대화를 담당자가 업무 메모에 붙여 쓸 수 있는 텍스트(.txt)로 만듭니다.
// 서버를 거치지 않고 브라우저에서 바로 파일을 만듭니다. 질문은 서버가 개인정보를 가린 문장으로 이미 바뀌어 있습니다.

// 서버가 알려 준 답변 방식(mode)에 AI 단계가 있으면 AI가 만든 답입니다.
export const usedAi = (mode) => /AI (대화|해석|문장 다듬기|의도 판단)/.test(mode || '');

// 분석 근거 이름을 담당자가 알아볼 수 있는 말로 표시합니다.
const SOURCE_NAMES = [
  [/a2_feature/i, '통신·이동 지표'],
  [/a2_|analysis2|sequential|탐지/i, '통신·이동 변화 탐지 결과'],
  [/a1_|analysis1|지역유형|elder/i, '지역 배경(지역 유형) 자료'],
  [/analysis3/i, '소비·생활 보조 자료'],
  [/유동인구|_pop\b/i, '집단별 유동인구 집계'],
  [/서울서베이/, '서울서베이'],
  [/DB2|복지서비스/i, '지자체 복지서비스 자료'],
];
export const sourceLabel = (source) =>
  SOURCE_NAMES.find(([pattern]) => pattern.test(source || ''))?.[1] || '저장된 분석 자료';

const pad = (value) => String(value).padStart(2, '0');
const stamp = (date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
const LIMIT_NOTE =
  '지역·집단 집계는 개인의 고립 여부를 판정하지 않으며, 사업의 운영·이용 자격은 담당 기관 확인이 필요합니다.';

function answerBlock(message) {
  const lines = [`[보미${message.agent ? ' · ' + message.agent : ''}]`];
  if (message.mode)
    lines.push(`(${usedAi(message.mode) ? 'AI 답변' : '자료 기반'} · ${message.mode})`);
  lines.push(message.text || '답변을 완료하지 못했습니다.');
  if (message.interrupted) lines.push('※ 완료되지 않은 응답입니다.');
  for (const notice of message.notices || []) lines.push(`ⓘ ${notice}`);
  if (message.sources?.length) {
    lines.push('참고한 팀 자료:');
    for (const record of message.sources) {
      const location = record.pages
        ? ` (p. ${record.pages})`
        : record.url
          ? ` · ${record.url}`
          : '';
      lines.push(`- ${record.name}: ${record.source}${location} · ${record.status}`);
    }
  }
  return lines.join('\n');
}

// place: '강남구 삼성1동' 또는 '삼성1동 · 70대 · 여성', month: 기준월, aiMode: 내보낼 때 AI 사용 여부
export function chatTranscript({ messages, place, month, aiMode, exportedAt = new Date() }) {
  const header = [
    '보미 대화 기록',
    `지역: ${place}`,
    `기준월: ${month || '-'}`,
    `내보낸 시각: ${stamp(exportedAt)}`,
    `답변 방식: ${aiMode ? 'AI 사용(질문과 최근 대화가 관리자가 설정한 외부 AI로 전송됨)' : '자료 기반(외부로 전송하지 않음)'}`,
  ].join('\n');
  const body = messages
    .filter((m) => m.role === 'user' || m.text || m.interrupted)
    .map((m) => (m.role === 'user' ? `[나]\n${m.text}` : answerBlock(m)));
  return [header, ...body, `ⓘ ${LIMIT_NOTE}`].join('\n\n' + '-'.repeat(40) + '\n\n') + '\n';
}

// 파일 이름에 쓸 수 없는 문자(\ / : * ? " < > |)와 공백은 _로 바꿉니다.
export function chatFileName(place, exportedAt = new Date()) {
  const safe = String(place || '보미')
    .replace(/[\\/:*?"<>|\s·]+/g, '_')
    .replace(/^_+|_+$/g, '');
  const time = `${exportedAt.getFullYear()}${pad(exportedAt.getMonth() + 1)}${pad(exportedAt.getDate())}-${pad(exportedAt.getHours())}${pad(exportedAt.getMinutes())}`;
  return `보미대화_${safe}_${time}.txt`;
}

// 메모장에서도 한글이 깨지지 않도록 BOM과 Windows 줄바꿈(CRLF)으로 저장합니다.
export function downloadChat(text, fileName) {
  const blob = new Blob(['﻿' + text.replace(/\r?\n/g, '\r\n')], {
    type: 'text/plain;charset=utf-8',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
