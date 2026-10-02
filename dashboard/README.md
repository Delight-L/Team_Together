# Team Together 대시보드

Python이 CSV·JSON을 읽고, Streamlit Custom Component v2에 전달합니다. 화면 표시와 클릭·필터·점수 계산은 `ui/`의 JavaScript가 담당합니다. 화면의 지역 점수와 집단별 자료는 시연용이며 실제 위험분석 CSV가 자동으로 연결되는 구조는 아닙니다.

## 실행

Windows에서는 프로젝트 최상위의 `setup_team.bat`를 한 번 실행한 뒤 `run_team.bat`에서 1번을 선택합니다. 권장 Python은 현재 검증에 사용한 3.13입니다.

터미널에서는 프로젝트 최상위에서 실행합니다.

```powershell
python main.py
```

처음 실행할 때 가상환경에 패키지를 설치해야 합니다. 전체 팀원 실행·수정 안내는 [팀원 안내](../docs/팀원_실행_안내.md)를 참고하세요.

## 현재 사용하는 파일

| 바꾸려는 내용 | 파일 |
| --- | --- |
| 데이터 연결·화면 전달 자료 | `main.py`의 `render_app()` |
| 자료 경로·요인 이름·가중치·색·시연 계정 | `settings.py` |
| CSV·JSON 읽기와 유효성 검사 | `data_utils.py` |
| Streamlit에 HTML·CSS·JS 등록 | `design_ui.py` |
| 일·월 평균과 점수 계산 | `ui/data.js` |
| 그래프 크기·축·종류 | `ui/charts.js` |
| 메뉴·지도·로그인·필터·챗봇 클릭 | `ui/dashboard.js` |
| 집단별 변화율·우선순위·서비스 유형·조치 상태 | `ui/responses.js` |
| 월별 요약·업무 지도·미션·보고서 초안 | `ui/workspace.js` |
| 색·글꼴·간격·배치 | `ui/style.css` |
| 로그인·앱·챗봇의 HTML 뼈대 | `ui/layout.html` |

JavaScript의 `BOOT`는 Python이 넘긴 자료입니다. `S`는 현재 지역·월·선택 동·가중치, `R`은 집단별 대응 필터·조치 상태를 기억합니다. 짧은 이름의 뜻은 해당 파일 위쪽 주석에 적었습니다.

## 위험 요인 CSV 교체

`data/risk_factors.csv`의 열을 유지합니다.

| 열 | 뜻 |
| --- | --- |
| `date` | 날짜, YYYY-MM-DD |
| `city` | 지자체 |
| `district` | 행정동 |
| `flow` | 유동인구 감소 점수 |
| `card` | 카드 결제 감소 점수 |
| `single` | 1인 가구 비율/점수 |
| `elder` | 고령 인구 비율/점수 |
| `welfare` | 복지 연계 공백 점수 |

한 행은 하루·지자체·행정동 하나이고 같은 조합은 중복할 수 없습니다. 다섯 요인은 빈칸 없이 0~100의 숫자로 준비합니다. 원래 인구수·결제액을 그대로 점수 열에 넣지 않습니다.

점수는 다섯 요인의 가중 평균입니다. 월별 값은 관측된 날짜의 평균이며, 일별 비교는 7일 전, 월별 비교는 전월입니다. 비교 자료가 없으면 0점 대신 자료 없음으로 표시합니다. 가중치 변경은 현재 화면에서만 유지되며 새로고침하면 기본값으로 돌아갑니다.

## 집단별 대응 JSON

`data/group_signals.json`은 `isDemo: true`인 가상 집계입니다. 행에는 `month`, `city`, `district`, `gender`, `age`, `flow`, `card`, `sampleCount`, `observedDays`가 있습니다. `flow`와 `card`는 일평균 명·건이며 점수 CSV와 다른 자료입니다.

시연 기준은 다음과 같습니다.

- 두 지표 모두 15% 이상 감소: 우선 확인
- 하나라도 10% 이상 감소: 확인 필요
- 그 외: 관찰
- 전월 자료 없음·전월 값 0·지표 누락·관측 규모 30 미만·월 집계 미완료: 판단 보류

변화율은 `(당월 일평균 - 전월 일평균) / 전월 일평균 × 100`입니다. 성별·연령대는 집단을 구분하는 값이며 그 자체로 점수를 높이지 않습니다. 지역 전체 대비 변화와 장기 지속성은 아직 판단에 반영하지 않습니다.

복지 자원 연계 화면은 서비스 유형을 제안합니다. 실제 사업·기관·이용 조건은 아직 연결되지 않았습니다. 조치 상태는 현재 화면에서만 유지됩니다.

## 지도·그래프·업무 공간

`data/map_boundaries.json`은 SVG 그림 좌표이며 위도·경도나 GeoJSON이 아닙니다. CSV의 동 이름은 지도 경계의 `n` 값과 일치해야 합니다. 새 지자체를 추가하면 지도 경계와 시연 계정 소속도 함께 추가합니다.

`ui/charts.js`의 `TREND_CHART_TYPE`을 `line`, `area`, `bar`로 변경하면 추이 그래프 종류를 바꿀 수 있습니다.

업무 공간의 신규 상승·지속 상승은 전전월·전월·당월 점수로 계산합니다. 검토 대기는 위험·심각 단계 중 현재 세션에서 지도 상세를 확인하지 않은 지역입니다. 보고서는 현재 지역·월의 텍스트 초안이며, 외부 기관 전달이나 실제 AI 생성 기능은 아닙니다.

## 보관용·초기 추출 도구

`main_native.py`는 이전 Streamlit 기본 위젯 화면입니다. `charts.py`, `legacy_data.py`, `data/people.csv`는 이 보관용 화면에 사용합니다. 현재 화면 수정에는 필요하지 않습니다.

```powershell
python -m streamlit run dashboard/main_native.py
```

`prepare_design.py`와 `export_html_data.cjs`는 초기 HTML 분리·데이터 추출 도구입니다. 다시 실행하면 현재 파일을 덮어쓸 수 있습니다. `prepare_design.py`는 `--overwrite`를 지정한 경우에만 덮어씁니다. 일반 수정은 `ui/`에서 합니다.

## 개발용 검증

프로젝트 최상위에서 실행합니다. JavaScript 검증에는 Node.js가 필요합니다. 대시보드 일반 실행에는 Node.js가 필요하지 않습니다.

```powershell
python dashboard/tests/check_dashboard.py
python dashboard/verify_design.py
python dashboard/verify_dashboard.py
```

첫 검사는 CSV 계산·자료 누락·집단 필터·서비스 보류·조치 상태와 JavaScript 문법을 검사합니다. 두 번째는 원본 공식과 계산을 비교하고 현재 HTML의 연결 요소를 검사합니다. 세 번째는 보관용 화면의 로그인·메뉴·가중치·챗봇 등을 검사합니다. 브라우저의 실제 시각적 모양까지 확인하는 검사는 아닙니다.
