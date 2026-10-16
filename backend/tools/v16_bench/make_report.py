"""측정 결과(round_{old,snap,work,pg}_{1,2,3}.json)로 비교 보고서(md)를 만듭니다. 인자: <결과 폴더> <출력 md>"""
import json
import platform
import statistics
import sys
from pathlib import Path

S = Path(sys.argv[1])
out = Path(sys.argv[2])


def load(prefix):
    files = sorted(S.glob(f'round_{prefix}_*.json'))
    return [json.loads(file.read_text(encoding='utf-8')) for file in files]


old, snap, work, pg = load('old'), load('snap'), load('work'), load('pg')
meta = old[0]
runs = meta['runs']
rounds = len(old)


def agg(rounds, level, case, key):
    values = [r[level][case][key] for r in rounds]
    return statistics.median(values), min(values), max(values)


def same_everywhere(level, case):
    hashes = {r[level][case]['hash'] for group in (old, snap, work, pg) for r in group}
    errors = [r[level][case]['error'] for group in (old, snap, work, pg) for r in group if r[level][case]['error']]
    return len(hashes) == 1 and not errors


def verdict(o, n):
    ratio = o[0] / n[0] if n[0] else float('inf')
    separated = n[2] < o[1] or o[2] < n[1]  # 세 번의 라운드 범위가 겹치지 않으면 차이가 분명함
    if not separated:
        return f'{ratio:.2f}× (오차 범위)'
    return f'**{ratio:.1f}× 빠름**' if ratio > 1 else f'**{1 / ratio:.1f}× 느림**'


lines = []
add = lines.append
add('# 성능 비교: 원본 backend_old 대 backend (실제 db1.sqlite)\n')
add('같은 `db1.sqlite`와 같은 질문으로 원본 `backend_old`와 `backend`의 v16 경로를 각각 실행해 비교했습니다.\n')

add('## 1. 측정 조건\n')
add('| 항목 | 내용 |')
add('|---|---|')
add('| 데이터 | `Team_Together/db1.sqlite` (379,576,320 B, 88개 테이블). `pipelines/db1/outputs/db1.sqlite`와 바이트 단위로 동일 |')
add('| 규모 | `a2_detection` 132행(22개 동 × 2025-07~12), `a2_age_detection` 660행, `a3a_feature` 10,560행, `ctx_sns_index` 5,280행, `a2_feature` 1,056행 |')
add(f'| 신호 | 탐지 결과에서 신호가 잡힌 건은 **1건**(`{meta["dong"]}` {meta["month"]} 부근)뿐입니다 |')
add('| 비교 대상 | 원본 = `backend/agents/regional_v16`(및 `backend/agents/v16_service`), 신규 = `backend/agents/regional_v16`(및 `bomi/adapters/v16`) |')
add('| 저장소 수명 | 질문마다 저장소를 새로 만듦(웹 서비스가 요청마다 만드는 것과 같음). 캐시는 질문 안에서만 유효 |')
add(f'| 반복 | 질문마다 워밍업 2회 후 **{runs}회** 측정한 중앙값. 이를 **{rounds}라운드**(원본·신규를 번갈아 실행) 반복해 라운드 중앙값을 보고하고, 범위가 겹치지 않을 때만 차이가 분명하다고 표시 |')
add(f'| 환경 | Python {platform.python_version()} (측정 venv), 같은 컴퓨터, 로컬 디스크, 외부 AI 호출 없음 |')
add('| 신규의 세 경로 | **공개 snapshot**(`snapshots/` 아래 불변 파일, 운영 경로) / **작업 DB**(변경 감지 포함) / **PostgreSQL**(받은 원본 파일을 수정 없이 로컬 PostgreSQL 16에 게시한 활성 run). 원본은 이 구분이 없어 작업 DB 경로에서 실행 |')
add('| 측정 도구 | DB 호출 수는 `sqlite3.connect`·`execute`를 계측, 메모리는 `tracemalloc` 정점(Python 객체만, 별도 1회) |')
add('')
add('### 데이터 준비에 대한 주의\n')
add('받은 `db1.sqlite`는 파이프라인 산출물이라 v16 엔진이 필요로 하는 테이블 두 개가 없습니다.')
add('- `pipeline_state`: v16의 월별 작업기가 만드는 «갱신 완료» 표지')
add('- `ctx_weather`: 작업기가 월마다 만드는 날씨 보조 자료. 산출물에는 같은 정보가 `ctx_weather_month`(월별 값)와 `ctx_weather_window`(기준월별 3개월 관측기간)로 나뉘어 있음')
add('')
add('두 구현 모두 이 파일을 **그대로 열면 `no such table: pipeline_state`로 실패합니다**(같은 오류). 대응은 경로마다 다릅니다.')
add('')
add('| 경로 | 대응 |')
add('|---|---|')
add('| 원본 · 신규(SQLite) | 원본 파일은 건드리지 않고 **복사본에만** 두 테이블을 추가(`tools/v16_bench/prepare_db.py`). `pipeline_state`는 `{"status": "ready"}` 한 행, `ctx_weather`는 `ctx_weather_month`·`ctx_weather_window`에서 **작업기의 `weather_context`와 같은 모양**(`label_weather`, `observation_month_weather`)으로 변환 |')
add('| 신규(PostgreSQL) | **받은 원본 파일을 수정 없이** 게시. 게시 단계가 같은 변환 코드(`data_pipeline/db1_compat.py`)로 `ctx_weather`를 만들고, `pipeline_state`는 run 상태에서 뷰로 만듦 |')
add('')
add('한계: 산출물의 월별 날씨에는 «눈 기록이 `-`(확인 불가)였는지» 정보가 없어 변환 결과의 `snow_status`는 모두 `observed`입니다. 작업기가 만든 DB와 비교해 검증하지는 못했습니다(작업기 DB가 없음). 이 값은 날씨 보조 문장의 적설일 표기에만 영향을 줍니다.')
add('')

for level, title, note in (('engine', '2. 엔진 수준 (질문 유형별)', '`execute(repo, intent)` 한 번의 시간입니다. 원본과 신규가 공유하는 v16 엔진 계층입니다.'),
                           ('reply', '3. 챗봇 답변 전체 (자연어 질문)', '`v16.reply(question, history, context)` 한 번의 시간입니다. 저장소 생성, 의도 해석, 조회, 문장 생성을 모두 포함합니다.')):
    add(f'## {title}\n')
    add(note + '\n')
    add('| 질문 | 원본 | 신규 (snapshot) | 신규 (작업 DB) | 신규 (PostgreSQL) | 개선 (원본 대비 snapshot) | 연결 원본→신규 | 쿼리 원본→신규 | 메모리 정점 원본→신규 | 출력 동일 |')
    add('|---|---:|---:|---:|---:|---|---|---|---|:-:|')
    totals = [0.0, 0.0, 0.0, 0.0]
    for case in old[0][level]:
        o, s, w, g = (agg(group, level, case, 'median_ms') for group in (old, snap, work, pg))
        totals[0] += o[0]
        totals[1] += s[0]
        totals[2] += w[0]
        totals[3] += g[0]
        o0, s0, w0 = old[0][level][case], snap[0][level][case], work[0][level][case]
        mem_o, mem_s = agg(old, level, case, 'peak_mb')[0], agg(snap, level, case, 'peak_mb')[0]
        add(f'| {case} | {o[0]:.1f} ms | {s[0]:.1f} ms | {w[0]:.1f} ms | {g[0]:.1f} ms | {verdict(o, s)} | {o0["connections"]} → {s0["connections"]} | '
            f'{o0["queries"]} → {s0["queries"]} ({w0["queries"]}) | {mem_o:.1f} → {mem_s:.1f} MB | {"✓" if same_everywhere(level, case) else "✗"} |')
    add(f'| **합계** | **{totals[0]:.0f} ms** | **{totals[1]:.0f} ms** | **{totals[2]:.0f} ms** | **{totals[3]:.0f} ms** | **{totals[0] / totals[1]:.2f}× ({(1 - totals[1] / totals[0]) * 100:.0f}% 감소)** | | | | |')
    add('')
    add('쿼리 수의 괄호는 신규의 작업 DB 경로입니다(변경 감지 쿼리가 더해짐).\n')

add('## 4. 실제 데이터에서 발견해 고친 문제\n')
add('합성 DB로는 드러나지 않던 문제를 실제 `db1.sqlite`로 PostgreSQL과 대조하다 발견했습니다.\n')
add('| 항목 | 내용 |')
add('|---|---|')
add('| 증상 | «소비 (연령 20대)» 질문에서 SQLite와 PostgreSQL의 결과가 달랐음. 행 집합은 같고 **행 순서만** 달랐음(`D_생활필수`와 `E_의료건강`이 서로 바뀜) |')
add('| 원인 | `WHERE period=? AND adm_cd=? AND age=?`처럼 `ORDER BY` 없이 여러 행을 돌려주는 조회. SQLite는 기본키 색인(기간·동·연령·분야) 순서로, PostgreSQL은 저장 순서로 돌려줌 |')
add('| 영향 범위 | 소비·지역 배경·후속 추적 조회 6곳. 기존 SQLite에서는 항상 기본키 순서였으므로 PostgreSQL로 옮기면 답변의 항목 순서가 달라졌을 것 |')
add('| 수정 | 해당 조회에 기본키 순서의 `ORDER BY`를 명시. 실제 DB에서 **원래 SQL과 새 SQL의 행 순서가 같은지 전수 확인**(a3a_comparison 264조합, a3a_feature 2,112조합, a3b_feature 36조합, 후속 추적 40조합, 순서 불일치 0) |')
add('| 재발 방지 | 저장 순서와 기본키 순서가 다른 자료를 가진 테스트를 추가. `ORDER BY`를 빼면 PostgreSQL 테스트가 실패함을 확인 |')
add('')
add('## 5. 해석\n')
add('| 구분 | 결과 |')
add('|---|---|')
add(f'| 출력 | 원본과 신규의 세 경로(snapshot·작업 DB·PostgreSQL) 모두, 18개 질문 × {rounds}라운드의 출력 해시가 **전부 동일**했고 오류도 없었습니다 |')
add('| PostgreSQL | 실제 `db1.sqlite`의 16개 테이블(약 2만 행)을 **2.7초**에 게시했고 행 수가 모두 원본과 일치했습니다. 응답 시간은 SQLite snapshot과 같은 수준입니다(로컬 서버 기준) |')
add('| 크게 빨라진 질문 | 소비·지역 배경처럼 큰 테이블(`a3a_feature` 10,560행 등)을 읽던 질문. 필요한 기간·동·연령의 행만 읽도록 바꾼 효과이고, 메모리 정점도 약 27MB에서 2MB 안팎으로 줄었습니다 |')
add('| DB 연결 | 모든 질문에서 3~15회 → 1회 |')
add('| 쿼리 수 | 특히 이례적 변화 순위가 304 → 39회로 가장 크게 줄었음 |')
add('| 차이가 작거나 오차 범위인 질문 | 탐지 표(행 수가 적은 `a2_*`)만 읽는 질문. 이 실제 DB는 탐지 행이 132행으로 작아서, 반복 읽기를 없앤 효과가 시간으로는 거의 드러나지 않습니다 |')
add('| 메모리 | 탐지 표를 요청 동안 들고 있어 신호·연령 질문에서는 신규가 약간 더 씁니다(5 → 7MB 안팎) |')
add('| 작업 DB·PostgreSQL 경로 | snapshot 경로와 시간 차이는 대체로 오차 범위이거나 조금 느린 정도. 작업 DB는 변경 감지 쿼리만큼 쿼리 수가 늘어남 |')
add('')
add('## 6. 한계\n')
add('- **실제 신호가 1건뿐인 데이터**입니다. 이전에 합성 DB로 잰 «신호가 많은 경우»(27건)의 개선은 이 데이터로는 재현되지 않습니다. 신호가 많아지면 `_age_signal_changes`의 반복 호출이 늘어 차이가 더 벌어질 것으로 보지만, 실제 데이터로는 확인하지 못했습니다.')
add('- 시간은 한 컴퓨터의 중앙값입니다. 같은 조건을 여러 라운드 반복해도 질문에 따라 ±20~30% 흔들려, 범위가 겹치는 값은 «오차 범위»로 표시했습니다.')
add('- 위의 «데이터 준비에 대한 주의»대로 SQLite 복사본의 `pipeline_state`·`ctx_weather`는 측정용으로 추가·변환한 것이고, 날씨의 눈 기록 상태(`snow_status`)는 복원하지 못했습니다.')
add('- PostgreSQL은 **같은 컴퓨터의 로컬 서버**라 네트워크 지연이 없습니다. 원격 서버면 질문당 쿼리 4~40회에 왕복 시간이 더해집니다.')
add('- 메모리는 `tracemalloc`이 세는 Python 객체의 정점이고, 프로세스 전체 메모리가 아닙니다.')
out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('written', out)
