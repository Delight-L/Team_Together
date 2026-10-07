# 동·연령별 변화 탐지 실행 결과

- period: 2025-07~2025-12
- rows: 660
- fully_assessed: 656
- partially_assessed: 4
- fully_deferred: 0
- communication_signal_rows: 10
- mobility_signal_rows: 0
- joint_candidates: 0
- age_signal_rows_without_legacy_dong_signal: 10
- gangnam_age_month_rows: 30
- calibrated_thresholds: 60
- model_version: a2_age_detection_v1_bd2dbf881a54

## 실제 신호

```text
      date   행정동코드  행정동 age_band  communication_signal mobility_signal  legacy_dong_signal  call_contacts_change_pct  text_contacts_change_pct
2025-10-01 1123051  신사동      30s                  True           False               False                 -5.514193                 -5.311164
2025-10-01 1123059 삼성2동      30s                  True           False               False                 -4.255531                 -4.688541
2025-10-01 1123064 역삼1동      40s                  True           False               False                 -4.653119                 -5.034722
2025-10-01 1123065 역삼2동      40s                  True           False               False                 -4.221927                 -4.352816
2025-10-01 1123067 도곡2동      40s                  True           False               False                 -3.960481                 -4.466502
2025-10-01 1123072 일원본동      40s                  True           False               False                 -3.962679                 -5.219185
2025-10-01 1123074 일원2동      40s                  True           False               False                 -4.868251                 -3.547755
2025-10-01 1123077 압구정동      40s                  True           False               False                 -4.377589                 -3.985454
2025-10-01 1123059 삼성2동      50s                  True           False               False                 -4.298449                 -4.164425
2025-11-01 1123065 역삼2동      30s                  True           False               False                 -2.249946                 -3.996290
```

## 해석

소통 감소만 확인된 신호 10건을 사회적 고립으로 확정할 수 없다. 현재 탐색용 기준에서 이동과 겹친 후보는 0건이며 이것이 고립이 없다는 증거는 아니다. 실제 이동 감소 방향의 관측과 이례적 이동 감소 신호를 구분한다. 기존 동별 신호와 새 연령별 신호는 집계 및 임계값이 달라 단순히 더 많은 신호가 더 높은 정확도를 뜻하지 않는다.

전체 판정 가능 656건, 이동 자료 부족에 따른 부분 판정 4건이다. 일원2동 관심집단 0값은 관련 보조 근거를 사용할 수 없는 상태로 보존했다. 새로 검토한 등록인구 자료는 사용하지 않았다.

## 검증

- 현재/미래 자료가 이전 결과나 기준 임계값에 들어가지 않는지 검증.
- 특정 동·연령의 소통·이동 급락과 전체 구의 특정 연령 급락을 합성자료로 탐지.
- 실제 증가를 상대적 감소로 오인하지 않는지 검증.
- 품질 부족·관심집단 단절·MAD 0·중복/빠진 월을 처리하는지 검증.
- 합성 2026-01 추가 시 과거 결과·모델을 유지하고 DB에 110행만 추가하는지 외래키와 함께 검증. 합성자료는 운영 DB에 저장하지 않음.
- 일반 scan 재실행: 추가 저장 0건, 2026-01 원본 대기 상태로 정상 종료.
- 임계값 보정은 고립 발생 정답 없이 수행한 역사적 하위 꼬리 탐색이며 정확도 검증이 아니다.

## 회귀 검증 완료

Analysis2 검증 33개(전체 32개 및 추가 맥락 보존 검증 1개), DB1 공통 검증 8개를 통과했다. 최종 탐지 명령 재실행은 저장 0행으로 종료했다. 원본 없는 2026-01은 운영 결과를 생성하지 않고 대기했다.
