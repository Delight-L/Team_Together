# DB1 전처리 및 Analysis2 실행

프로젝트 루트에서 `python main.py`를 실행하면 다음 순서로 처리합니다.

최초 한 번 필요한 패키지를 설치합니다.

```powershell
python -m pip install -r requirements.txt
```

1. `preprocessing_agent1/main.py`
2. `preprocessing_agent2/main.py`
3. 전처리된 feature table을 `Analysis2` 입력 위치로 복사
4. `Analysis2/run_analysis2.py`
5. detection/evidence 결과 검증

`risk_detection_core`는 이 버전에서 제외했습니다. 다운로드를 끄려면 `--no-download`를 사용합니다. 검증 결과는 루트의 `analysis2_execution_report.json`에 저장됩니다.
