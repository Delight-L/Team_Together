# 대시보드 시안 반영

- `frontend/src/dashboard-design.css`: 서류철 돌출부와 곡선 탭, 종이 테두리와 이중 클립, 카드 간격, 글자 크기, 챗패널 캐릭터 크기 및 반응형 배치.
- `frontend/src/assets/dossier-cover.svg`, `dossier-tab.svg`: CSS 배경으로 사용하는 서류철과 탭의 곡선 형태. 실제 탭 버튼은 유지.
- `frontend/src/components.jsx`, `GroupDashboard.jsx`: 변화 발견·지역 배경·지원 검토 단계의 선형 아이콘.
- `frontend/src/BomiChat.jsx`: 태블릿을 든 보미 이미지를 모듈로 불러와 안내 카드에 표시.
- `frontend/src/assets/bomi-tablet.png`: 제공된 브랜드 보드와 대시보드 시안을 참조해 내장 ImageGen으로 제작한 투명 배경 이미지. 원본 브랜드 이미지와 별도 보관.

공통 규격 적용: `App.jsx`의 종합 현황 전용 briefing-shell 클래스를 제거하고, `group-dashboard.css`, `workspace-layout.css`, `dashboard-design.css`의 전용 패널 너비·헤더 높이·본문 여백·색상 덮어쓰기를 정리했습니다. 사이드바 194px(접힘 64px), 챗패널 330px, 본문 배경 #fbfaf7, 공통 제목색 #0c1837을 사용합니다. 서류철 모양과 보미 캐릭터는 유지합니다.

스크롤 제거: `dashboard-design.css`에서 파일 영역을 가용 높이에 맞춘 그리드와 컨테이너 쿼리로 변경했습니다. 넓은 화면은 전체 카드, 좁거나 낮은 파일 영역은 변화 요약/지역 배경/동 전체 변화 버튼으로 표시합니다. `GroupDashboard.jsx`에서 브리핑 페이지 선택과 ResizeObserver에 따른 조사 파일 페이지당 표시 수를 추가했습니다. 기존 근거 항목 및 표 페이지 이동도 유지합니다. 1820×864, 1102×884, 1366×768에서 중앙 콘텐츠 및 표시 카드의 높이를 검증했습니다.

검증: npm run build 성공. 1820px·1102px에서 종합 현황/지역 현황/지역 분석의 패널 위치·너비·본문 여백·배경 및 기본 글자색 일치, 접힌 메뉴의 패널 너비 일치 확인.

## 이미지 생성 프롬프트

도구: 내장 image_gen. transparent_background=true. 참조: 사용자가 제공한 브랜드 아이덴티티 보드와 대시보드디자인수정.png.

Use case: identity-preserve. Asset: transparent PNG mascot for an existing WELFIND dashboard chat welcome card. Reference 1 is the official WELFIND brand board: preserve the white round robot with dark navy face, cyan oval eyes, beige detective hat with dark brown brim, beige trench coat, short white boots, and small colorful badge. Reference 2 is the exact dashboard design: match the small full-body robot in the right-hand chat welcome card, standing facing forward with both eyes open, holding a black tablet in its left hand (viewer right), right hand slightly extended. Produce ONLY this single character, complete full body, centered, tightly framed with 5% clear margin on all sides, in the same clean softly shaded 3D cartoon brand style. The face is friendly with two cyan oval eyes and a tiny smile. No magnifying glass, no text, no logos outside the costume badge, no board, no background, no sparkles, no decorative shapes. Actual transparent background. Do not reproduce the UI. This is a faithful brand mascot adaptation, not a redesign.
