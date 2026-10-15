// 실제 DB를 변경하지 않고 조회 실패·재시도·자료 반영 갱신을 브라우저에서 확인합니다.
// node tests/menu-upgrade-harness.mjs 실행 후 http://127.0.0.1:8520 접속.
import { createRequire } from 'node:module';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createServer } from 'node:http';
const require = createRequire(import.meta.url);
const { build } = createRequire(require.resolve('vite/package.json'))('esbuild');
const folder = await mkdtemp(resolve('.menu-ui-test-'));
await writeFile(resolve(folder, 'menu-upload.csv'), 'region,month,value\ntest-region,2025-12,1\n');
const entry = `
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import App, { Report } from './src/App.jsx';
import { Activity, Upload } from './src/Workspace.jsx';
import BomiChat from './src/BomiChat.jsx';
import { useApiQuery } from './src/useApiQuery.js';
import './src/style.css'; import './src/briefing.css'; import './src/experience.css'; import './src/workspace-layout.css';
function Race() {
  const [path,setPath] = useState('/slow'); const query = useApiQuery(path);
  return <><button onClick={() => setPath('/fast')}>빠른 조회로 변경</button><p role="status">{query.loading ? '조회 중' : query.data?.value || query.error}</p></>;
}
function Harness() {
  const [screen, setScreen] = useState('activity'), [published,setPublished] = useState(0);
  const context = {city:'강남구',district:'삼성1동',month:'2025-12'};
  return <React.StrictMode><nav aria-label="검증 화면">{['activity','upload','chat','report','race'].map(name => <button key={name} onClick={() => setScreen(name)}>{name}</button>)}</nav>
    {screen === 'activity' && <Activity/>}
    {screen === 'upload' && <><Upload onPublished={() => setPublished(n => n+1)}/><p role="status">자료 갱신 요청 {published}회</p></>}
    {screen === 'chat' && <BomiChat context={context} userId="ui-test" view="services" />}
    {screen === 'report' && <Report context={context} workflow={{done:[0,1,2,3],workflow_complete:true,report:{revision:1},reviews:[]}} user={{id:'ui-test',name:'검증 담당자'}} mutate={async()=>null} onView={()=>{}} onSaved={()=>{}} />}
    {screen === 'race' && <Race/>}
  </React.StrictMode>;
}
createRoot(document.getElementById('root')).render(location.pathname === '/app' ? <React.StrictMode><App/></React.StrictMode> : <Harness/>);
`;
await build({ stdin: { contents: entry, resolveDir: resolve('.'), loader: 'jsx' }, bundle: true, define: { 'import.meta.env': '{}' }, outfile: resolve(folder, 'test.js'), loader: { '.png': 'dataurl', '.svg': 'dataurl' } });
let activityRequests = 0, versionRequests = 0, configRequests = 0, chatRequests = [], published = false, dashboards = [];
const server = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const json = (data, status = 200) => { res.writeHead(status, {'Content-Type':'application/json; charset=utf-8'}); res.end(JSON.stringify(data)); };
  let body = '';
  for await (const chunk of req) body += chunk;
  const input = body ? JSON.parse(body) : {};
  if (url.pathname === '/api/slow') return setTimeout(() => json({value:'늦은 결과'}), 1500);
  if (url.pathname === '/api/fast') return json({value:'최신 결과'});
  if (url.pathname === '/api/activity') {
    activityRequests++;
    return setTimeout(() => activityRequests <= 2 ? json({error:'활동 조회 실패 테스트'},503) : json({activity:[{created_at:'2026-10-14T12:00',actor:'검증 담당자',kind:'monthly',detail:'월별 자료 반영',result:'성공'}]}), 350);
  }
  if (url.pathname === '/api/report/versions') {
    versionRequests++;
    return versionRequests <= 2 ? json({error:'보고서 목록 조회 실패 테스트'},503) : json({items:[{revision:1,created_at:'2026-10-14T12:00',author:'검증 담당자',title:'검증 보고서'}]});
  }
  if (url.pathname === '/api/chat/config') {
    configRequests++;
    if (configRequests <= 2) return json({error:'설정 조회 실패 테스트'},503);
    return json({aiAvailable:false,resourceCount:1});
  }
  if (url.pathname === '/api/chat') {
    chatRequests.push(input);
    res.writeHead(200, {'Content-Type':'text/event-stream; charset=utf-8'});
    const send = (event,data) => res.write('event: '+event+'\ndata: '+JSON.stringify(data)+'\n\n');
    if (chatRequests.length === 1) {
      send('notice',{message:'개인정보 가림 테스트',question:'[가림] 조건 확인'});
      send('error',{message:'일시적인 응답 실패 테스트'});
    } else send('replace',{text:'사업 대상과 접수 여부를 운영기관에 확인하세요.',mode:'자료 기반'});
    send('done',{}); return res.end();
  }
  if (url.pathname === '/api/upload/validate') return json({token:'test-token',period:'2025-12',rows:1,preview:[{지역:'삼성1동'}]});
  if (url.pathname === '/api/upload/publish') { published = true; return json({runId:'test-v2'}); }
  if (url.pathname === '/api/session') return json({user:{id:'ui-test',name:'검증 담당자',org:'강남구',admin:true}});
  if (url.pathname === '/api/dashboard') {
    const runId=published?'test-v2':'test-v1'; dashboards.push(runId);
    return json({runId,source:'검증 자료',months:['2025-11','2025-12'],geometry:{'강남구':{units:[{n:'삼성1동'},{n:'대치1동'}]}},assessment:[{행정동명:'삼성1동',기준연월:'2025-12',metric_label:'전화 연락',has_enough_history:true,is_risk_signal:false,change_pct:1}],regionalStructures:[],runs:[],capabilities:{}});
  }
  if (url.pathname === '/api/groups') return json({groups:[],months:['2025-12'],districts:[],ages:[],sexes:[],runId:'test-v1'});
  if (url.pathname === '/api/workflow') return json({done:[],reviews:[]});
  if (url.pathname === '/checks') return json({activityRequests,versionRequests,chatRequests,published,dashboards});
  if (url.pathname === '/test.js' || url.pathname === '/test.css') {
    res.writeHead(200, {'Content-Type':url.pathname.endsWith('css')?'text/css':'text/javascript'});
    return res.end(await readFile(resolve(folder,url.pathname.slice(1))));
  }
  if (url.pathname.startsWith('/brand/')) { res.writeHead(404); return res.end(); }
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});
  res.end('<!doctype html><meta charset="utf-8"><title>메뉴 개선 검증</title><link rel="stylesheet" href="/test.css"><div id="root"></div><script src="/test.js"></script>');
});
server.listen(8520,'127.0.0.1',()=>console.log('메뉴 개선 검증: http://127.0.0.1:8520 · 전체 앱: /app\n검증용 업로드 파일: '+resolve(folder,'menu-upload.csv')));
async function cleanup() {
  server.close();
  const workspace = resolve('.') + '/';
  if (!folder.replaceAll('\\','/').startsWith(workspace.replaceAll('\\','/'))) throw Error('검증 폴더 경로 확인 실패');
  await rm(folder,{recursive:true,force:true}); process.exit(0);
}
process.on('SIGINT',cleanup); process.on('SIGTERM',cleanup);
