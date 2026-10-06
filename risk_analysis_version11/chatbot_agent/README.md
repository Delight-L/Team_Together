# Version 5 Gemini 데이터 챗봇

Version 5의 Analysis2 및 전처리 결과를 근거로 고립 문제 데이터에 답하는 터미널 챗봇입니다. 질문을 먼저 분류하고, 35건 전체 신호와 Analysis2 방법론 질문은 Python이 직접 해석합니다. Gemini는 필요한 일반 결과 질문의 문장 정리에만 사용되며 원본 데이터는 수정하지 않습니다.

## 설치

프로젝트 루트에서 다음을 실행합니다.

```powershell
pip install -r requirements.txt
```

Gemini API 키는 다음 방법 중 하나로 설정합니다.

```powershell
$env:GEMINI_API_KEY = "발급받은_API_키"
```

또는 `chatbot_agent/api_key.example.txt`를 `chatbot_agent/api_key.txt`로 복사한 뒤, 한 줄에 실제 키만 입력합니다. `api_key.txt`는 Git에서 제외됩니다.

## 실행

프로젝트 루트에서 실행합니다.

```powershell
python chatbot_agent/main.py
```

`종료`, `exit`, `quit` 또는 EOF로 종료합니다. 모델은 기본적으로 무료 등급에서 사용할 수 있는 `gemini-2.5-flash-lite`이며, `GEMINI_MODEL` 환경 변수 또는 `config.json`에서 바꿀 수 있습니다.

챗봇은 다음 결과만 읽습니다.

- `Analysis2/outputs`와 Analysis2 기능 테이블
- `preprocessing_agent1/outputs`
- `preprocessing_agent2/outputs`
- `analysis2_execution_report.json`

다음 질문을 지원합니다.

- `35건 신호별 근거 알려줘`: Evidence Card 전체를 번호별로 설명
- `통신 신호가 뭐야?`, `Robust Z 기준은?`, `왜 -2.0이야?`: Analysis2 규칙 설명
- 특정 동·월·신호 유형의 결과 질문

고립 문제 데이터와 관계없는 질문에는 다음 문장만 표시하고 Gemini를 호출하지 않습니다.

`현재 챗봇의 목적에 맞지 않는 질문입니다. 고립 문제 데이터와 관련된 질문을 해주세요.`

원천 데이터와 reference 폴더는 읽지 않습니다. 넓은 질문도 전체 데이터셋을 전송하지 않고 스키마, 행 수, 설정된 수 이내의 관련 행만 보냅니다. 분석 신호는 관찰된 지표일 뿐 사회적 고립을 확정하지 않습니다.

## 로컬 테스트

API 키나 네트워크 없이 실행할 수 있습니다.

```powershell
python -m unittest chatbot_agent.tests.test_data_catalog -v
python -m py_compile chatbot_agent/main.py chatbot_agent/data_catalog.py
```
