import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { createServer } from 'node:http';
const require = createRequire(import.meta.url);
const { build } = createRequire(require.resolve('vite/package.json'))('esbuild');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const temp = await mkdtemp(resolve('.draft-test-'));
let browser, server;
try {
  await build({ stdin: { contents: `
    import React, { useState } from 'react';
    import { createRoot } from 'react-dom/client';
    import App, { Report, Services } from './src/App.jsx';
    import { ReviewWorkspace, Comparison, SupportDialog } from './src/Experience.jsx';
    import './src/style.css';
    import './src/briefing.css';
    import './src/experience.css';
    import './src/case-briefing.css';
    const months = ['2024-07','2024-08','2024-09','2024-10','2024-11','2024-12','2025-01'];
    const names = ['세곡동', '수서동', '개포동', '일원동', '논현동'];
    const data = { months, source: '통신 집계 분석 자료', runId: 'test-v1', capabilities: {},
      geometry: { '강남구': { units: names.map(n => ({ n })) } },
      assessment: names.flatMap((n,i) => months.map((month,j) => ({ '행정동명': n, '기준연월': month, metric_label: '전화 연락', change_pct: j === 3 ? null : i * 2 - j, has_enough_history: true, is_risk_signal: j > 4 }))) };
    window.__testData = data;
    function Harness() {
      const [view, setView] = useState('review'), [district, setDistrict] = useState('세곡동');
      const context = { city: '강남구', district, month: '2025-01' };
      const user = { id: 'draft-test' };
      const [workflow, setWorkflow] = useState({ done: [0,1,2], reviews: [] });
      return <React.StrictMode><nav>{['review','report','services','compare','data','away'].map(v => <button key={v} onClick={() => setView(v)}>{v}</button>)}
        <button onClick={() => setDistrict(district === '세곡동' ? '수서동' : '세곡동')}>지역 변경</button>
        <button onClick={() => setWorkflow({ ...workflow, reviews: [{ note: '변경' }] })}>근거 변경</button></nav>
        {view === 'compare' && <Comparison data={data} context={context} />}
        {view === 'data' && <SupportDialog initialTab="data" onClose={() => setView('away')} data={data} context={context} rows={[]} workflow={workflow} onView={setView} onSelect={() => {}} regions={[]} user={user} onTrial={() => {}} busy={false} page="data" />}
        {view === 'review' && <ReviewWorkspace key={district} context={context} user={user} onView={setView} />}
        {view === 'services' && <Services key={district} context={context} user={user} workflow={workflow} busy={false} mutate={async () => true} />}
        {view === 'report' && <Report key={district} context={context} user={user} workflow={workflow} busy={false} mutate={async () => true} onSaved={() => {}} />}
      </React.StrictMode>;
    }
    createRoot(document.getElementById('root')).render(location.pathname === '/app' ? <React.StrictMode><App /></React.StrictMode> : <Harness />);
  `, resolveDir: resolve('.'), loader: 'jsx' }, bundle: true, outfile: join(temp, 'test.js'), define: { 'process.env.NODE_ENV': '"development"' }, logLevel: 'silent' });
  const js = await readFile(join(temp, 'test.js'));
  const css = await readFile(join(temp, 'test.css'));
  server = createServer((req, res) => {
    res.setHeader('Content-Type', req.url === '/test.js' ? 'text/javascript' : req.url === '/test.css' ? 'text/css' : 'text/html');
    res.end(req.url === '/test.js' ? js : req.url === '/test.css' ? css : '<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="/test.css"><style>body{overflow:auto;height:auto}#root{max-width:1120px;margin:24px auto;padding:16px}#root>nav{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}.scroll-view{overflow:visible;height:auto}</style><div id="root"></div><script src="/test.js"></script>');
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  let saveFails = true, appAdmin = false;
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let body = { version: 0, checks: {}, history: [] }, status = 200;
    if (path === '/api/session') body = { user: { id: 'app-test', org: '강남구', admin: appAdmin } };
    if (path === '/api/dashboard') body = await page.evaluate(() => window.__testData);
    if (path === '/api/experience' && route.request().method() === 'POST') {
      if (saveFails) { body = { error: '테스트 저장 실패' }; status = 500; }
      else body = { ...route.request().postDataJSON(), version: 1 };
    }
    if (path === '/api/services') body = { matches: [{ key: 'service-a', service: { name: '테스트 사업' }, reasons: [] }] };
    if (path === '/api/report/preview') body = { token: 'test-token' };
    if (path === '/api/report/content') body = { title: '제목', summary: '요지', situation: '현황', proposal: '제안', next_steps: '조치', review_snapshot: [], review_id: 'test' };
    await route.fulfill({ status, json: body });
  });
  await page.goto('http://127.0.0.1:' + server.address().port);
  const note = () => page.getByLabel('검토 의견·인계 내용');
  await note().fill('작성 중인 검토 의견');
  await page.getByRole('button', { name: 'away', exact: true }).click();
  await page.getByRole('button', { name: 'review', exact: true }).click();
  await note().waitFor(); await assertEventually(() => note().inputValue(), '작성 중인 검토 의견');
  await page.reload(); await assertEventually(() => note().inputValue(), '작성 중인 검토 의견');
  await page.getByRole('button', { name: '지역 변경', exact: true }).click();
  await assertEventually(() => note().inputValue(), '');
  await note().fill('수서동 의견');
  await page.getByRole('button', { name: '지역 변경', exact: true }).click();
  await assertEventually(() => note().inputValue(), '작성 중인 검토 의견');
  await page.getByRole('button', { name: '검토·후속 조치 저장', exact: true }).click();
  await page.getByText('테스트 저장 실패', { exact: true }).waitFor();
  await page.reload(); await assertEventually(() => note().inputValue(), '작성 중인 검토 의견');
  await page.getByText('이전 기록·다시 불러오기', { exact: true }).click();
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: '최신 기록 다시 불러오기' }).click();
  assert.equal(await note().inputValue(), '작성 중인 검토 의견');
  saveFails = false;
  await page.getByRole('button', { name: '검토·후속 조치 저장', exact: true }).click();
  await page.getByText('검토·후속 조치 기록을 저장했습니다.', { exact: true }).waitFor();
  assert.equal(await page.evaluate(() => Object.keys(sessionStorage).some(k => k.includes('세곡동') && k.includes('review'))), false);
  await page.getByRole('button', { name: 'report', exact: true }).click();
  await page.getByLabel('작성자', { exact: true }).fill('임시 작성자');
  await page.getByRole('button', { name: '보고서 초안 만들기' }).click();
  await page.getByLabel('검토 요지').fill('편집한 보고서 요지');
  await page.getByRole('button', { name: 'away', exact: true }).click();
  await page.getByRole('button', { name: 'report', exact: true }).click();
  assert.equal(await page.getByLabel('검토 요지').inputValue(), '편집한 보고서 요지');
  await page.reload();
  await page.getByRole('button', { name: 'report', exact: true }).click();
  await page.getByRole('button', { name: '작성 정보 수정', exact: true }).click();
  assert.equal(await page.getByLabel('작성자', { exact: true }).inputValue(), '임시 작성자');
  await page.getByRole('button', { name: '작성 중인 초안 이어서 수정', exact: true }).click();
  assert.equal(await page.getByLabel('검토 요지').inputValue(), '편집한 보고서 요지');
  await page.getByRole('button', { name: '작성 정보 수정', exact: true }).click();
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: '저장된 근거로 초안 다시 만들기' }).click();
  await page.getByRole('button', { name: '작성 중인 초안 이어서 수정', exact: true }).click();
  assert.equal(await page.getByLabel('검토 요지').inputValue(), '편집한 보고서 요지');
  await page.getByRole('button', { name: 'Word 파일 만들고 확인하기' }).click();
  const finalSave = page.getByRole('button', { name: '확인한 최종 보고서 저장' });
  assert.equal(await finalSave.isDisabled(), true);
  await page.getByLabel('분석 근거·사업 검토 내역·최종 의견을 확인했습니다.').check();
  assert.equal(await finalSave.isEnabled(), true);
  await page.getByRole('button', { name: '내용 다시 수정' }).click();
  await page.getByLabel('검토 요지').fill('다시 수정한 요지');
  await page.getByRole('button', { name: 'Word 파일 만들고 확인하기' }).click();
  assert.equal(await finalSave.isDisabled(), true);
  await page.getByRole('button', { name: '내용 다시 수정' }).click();
  await page.getByRole('button', { name: '근거 변경', exact: true }).click();
  assert.equal(await page.getByLabel('검토 요지').inputValue(), '다시 수정한 요지');
  assert.equal(await page.getByRole('button', { name: 'Word 파일 만들고 확인하기' }).isDisabled(), true);
  await page.getByRole('button', { name: 'services', exact: true }).click();
  await page.getByRole('button', { name: '관련 사업 조회', exact: true }).click();
  await page.getByRole('button', { name: '이 사업 검토', exact: true }).click();
  await page.getByLabel('검토 근거').fill('사업 검토 중인 내용');
  await page.reload();
  await page.getByRole('button', { name: 'services', exact: true }).click();
  await page.getByRole('button', { name: '관련 사업 조회', exact: true }).click();
  await page.getByRole('button', { name: '이 사업 검토', exact: true }).click();
  assert.equal(await page.getByLabel('검토 근거').inputValue(), '사업 검토 중인 내용');
  await page.getByRole('button', { name: '사업 검토 기록 저장', exact: true }).click();
  await page.getByRole('button', { name: '이 사업 검토', exact: true }).waitFor();
  assert.equal(await page.evaluate(() => Object.keys(sessionStorage).some(k => k.includes('services'))), false);
  await page.getByRole('button', { name: 'compare', exact: true }).click();
  assert.equal(await page.getByLabel('시작월', { exact: true }).inputValue(), '2024-08');
  assert.equal(await page.locator('table').isVisible(), false);
  await page.getByText('비교 지역 선택·변경', { exact: true }).click();
  await page.getByLabel('동 검색', { exact: true }).fill('수서');
  await page.getByLabel('수서동', { exact: true }).check();
  await page.getByLabel('동 검색', { exact: true }).fill('');
  await page.getByLabel('개포동', { exact: true }).check();
  await page.getByLabel('일원동', { exact: true }).check();
  assert.equal(await page.getByLabel('논현동', { exact: true }).isDisabled(), true);
  await page.getByText('비교 지역 선택·변경', { exact: true }).click();
  await page.getByText('월별 상세 수치 보기', { exact: true }).click();
  assert.equal(await page.locator('table tbody tr').count(), 24);
  await page.getByLabel('시작월', { exact: true }).selectOption('2025-01');
  await page.getByLabel('종료월', { exact: true }).selectOption('2024-12');
  await page.getByRole('alert').waitFor();
  await page.getByRole('button', { name: '최근 6개월', exact: true }).click();
  const details = page.getByText('월별 상세 수치 보기', { exact: true }).locator('..');
  if (await details.getAttribute('open') !== null) await page.getByText('월별 상세 수치 보기', { exact: true }).click();
  if (process.env.UI_SCREENSHOTS) await page.screenshot({ path: resolve(process.env.UI_SCREENSHOTS, 'comparison.png'), fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'review', exact: true }).click();
  assert.equal(await page.getByLabel('담당자·인계 대상', { exact: true }).isVisible(), false);
  await page.getByRole('button', { name: '후속 조치', exact: true }).click();
  await page.getByLabel('담당자·인계 대상', { exact: true }).fill('김담당');
  await page.getByRole('button', { name: '검토 기록', exact: true }).click();
  await page.getByRole('button', { name: '후속 조치', exact: true }).click();
  assert.equal(await page.getByLabel('담당자·인계 대상', { exact: true }).inputValue(), '김담당');
  if (process.env.UI_SCREENSHOTS) await page.screenshot({ path: resolve(process.env.UI_SCREENSHOTS, 'followup.png'), fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: 'data', exact: true }).click();
  await page.getByRole('dialog').waitFor();
  assert.equal(await page.getByRole('button', { name: '데이터 기준', exact: true }).getAttribute('aria-pressed'), 'true');
  assert.equal(await page.getByText('분석 버전·갱신 정보', { exact: true }).isVisible(), true);
  assert.equal(await page.getByText('test-v1', { exact: true }).isVisible(), false);
  if (process.env.UI_SCREENSHOTS) await page.screenshot({ path: resolve(process.env.UI_SCREENSHOTS, 'data-guide.png'), fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: '이용 안내 닫기' }).click();
  await page.getByRole('button', { name: 'report', exact: true }).click();
  if (process.env.UI_SCREENSHOTS) await page.screenshot({ path: resolve(process.env.UI_SCREENSHOTS, 'report-edit.png'), fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: '작성 정보 수정' }).click();
  if (process.env.UI_SCREENSHOTS) await page.screenshot({ path: resolve(process.env.UI_SCREENSHOTS, 'report-prepare.png'), fullPage: true, animations: 'disabled' });
  await page.setViewportSize({ width: 390, height: 844 });
  for (const view of ['review','report','compare']) {
    await page.getByRole('button', { name: view, exact: true }).click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, view + ' horizontal overflow');
    if (process.env.UI_SCREENSHOTS) await page.screenshot({ path: resolve(process.env.UI_SCREENSHOTS, view + '-mobile.png'), fullPage: true, animations: 'disabled' });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('http://127.0.0.1:' + server.address().port + '/app');
  await page.getByRole('button', { name: '지역 분석', exact: true }).click();
  assert.equal(await page.getByRole('button', { name: '데이터 안내', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: '데이터 관리', exact: true }).count(), 0);
  await page.getByRole('button', { name: '데이터 기준 보기', exact: true }).click();
  await page.getByRole('dialog').waitFor();
  assert.equal(await page.getByRole('button', { name: '데이터 기준', exact: true }).getAttribute('aria-pressed'), 'true');
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({ state: 'detached' });
  appAdmin = true;
  await page.reload();
  await page.getByRole('button', { name: '데이터 관리', exact: true }).click();
  await page.getByRole('heading', { name: '데이터 검사와 DB1 반영' }).waitFor();
  assert.equal(await page.getByRole('button', { name: '업로드 자료 검사 및 분석', exact: true }).isDisabled(), true);
  assert.deepEqual(errors, []);
  console.log('통과: 작성 내용 보존, 보고서 3단계·확인 초기화, 비교 기간·4개 제한·접힘, 검토 구역 전환, 모바일 가로 넘침, 데이터 안내 연결·관리자 메뉴');
} finally {
  await browser?.close();
  if (server) await new Promise(r => server.close(r));
  if (!temp.startsWith(resolve('.') + '\\') && !temp.startsWith(resolve('.') + '/')) throw new Error('Invalid temporary directory');
  await rm(temp, { recursive: true, force: true });
}
async function assertEventually(read, expected) {
  for (let i = 0; i < 60; i++) { if (await read() === expected) return; await new Promise(r => setTimeout(r, 50)); }
  assert.equal(await read(), expected);
}
