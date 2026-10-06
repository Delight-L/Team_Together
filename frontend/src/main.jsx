import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './style.css';
import './briefing.css';
// index.html의 <div id="root"> 안에 App을 표시하는 React 시작점입니다.
// StrictMode는 개발 중 잘못된 부수 효과를 찾기 위해 일부 함수를 두 번 실행합니다.
createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
