from pathlib import Path
import json
R=Path(__file__).resolve().parent
DB1=next((p for p in R.parents if (p/'run_db1.py').exists()),Path(r'C:\Users\user\Desktop\Team_Together\DB1'))
O=DB1/'outputs/validation/retrospective_20261007' if (R/'DEPLOYED.txt').exists() else R/'outputs'
p=json.loads((O/'validation_results.json').read_text(encoding='utf-8'));sns=json.loads((O/'sns_review.json').read_text(encoding='utf-8'))
state={'both_below_reference':'두 지표 기준 미만','mixed_recovery':'회복 방향 엇갈림','recovered_to_reference':'두 지표 기준 이상','unavailable':'판정 불가'}
lines=['# DB1 과거 재현·민감도·대체 소통 검증', '', '검토일: 2026-10-07. 운영 DB1을 읽기 전용으로 분석했다. 기존 탐지·활동 수준 모델과 임계값을 수정하지 않았다. 검증 대상은 결과 재현과 설정 민감도 및 해석 제한이며, 사회적 고립 정답 자료를 통한 정확도 검증이 아니다.', '', '## 결론', '', '현재 10건의 공식 신호는 저장값과 정확히 재현됐다. 미래 월을 포함한 계산과 그 이전 자료만으로 재계산한 과거 점수도 완전히 동일했다. 현재 구조의 시간 순서 계산은 확인됐지만, 원천 공개일이 검증되지 않아 당시 실제 이용 가능 자료를 모두 재현한 것은 아니다.', '', '현재 10건의 개수와 활동 수준의 상대 상태는 설정에 민감하다. 더 엄격한 임계값 또는 비교 기준 변경으로 결과가 바뀌므로 안정적인 고립 사례 수로 발표하면 안 된다. 이전 SNS 증감률과 8건 품질 부족 판단은 철회했다. SNS 음수는 유효한 표준화 지수이며 시계열 비교는 허용되지 않는다.', '', '## 과거 시점 재현', '', '각 시나리오는 탐지 시작 전까지만 임계값을 보정하고, 각 월의 점수는 그 월 이전 관측만 이용한다. 나중 월은 앞선 점수 계산에 들어가지 않는다. 현재 운영 결과와 별개로 저장했다.', '', '| 탐지 기간 | 기준선 | 동·연령·월 행 | 소통 | 이동 | 결합 |', '|---|---|---:|---:|---:|---:|']
for s in p['historical_replays']+[p['current_reference']]:
 st=s['settings'];lines.append(f"| {st['detection_start'][:7]}~{s['months'][-1]['date'][:7]} | {st['baseline_start'][:7]}~{st['baseline_end'][:7]} | {s['rows']} | {s['communication']} | {s['mobility']} | {s['combined']} |")
lines+=['', '2024년 전체와 2024년 하반기의 결과는 서로 겹치는 자료이고 기준선도 다르므로 합산하지 않는다. 행 수·기간이 다른 시나리오의 건수를 직접 성능 비교하지 않는다. 과거 3개 재현에서 구 공통 지표의 별도 임계값은 최소 보정 점수 24개를 충족하지 못한 20개 셀이 있었다. 이는 동별 absolute/local 판정과 별개이며 공통 신호가 없다는 뜻으로 바꾸지 않는다.', '', '연령별 빈도는 시기·설정에 따라 다르다. 2025H1 소통 신호 21건은 20대 13건·30대 8건이었고 다른 연령은 0건이었다. 현재 2025H2는 30대 3건·40대 6건·50대 1건이다. 정답 자료가 없으므로 특정 세대의 실제 고립이 많거나 탐지 공정성이 입증됐다고 해석하지 않는다.', '', '## 임계값 민감도', '', '과거 하위 분위수 1%·2.5%·5%와 robust z 제한 -2·-2.5·-3의 9개 조합을 비교했다. 실제 임계값은 각 연령·지표·경로에서 제한과 과거 분위수 중 더 엄격한 값이다. 조합별 빈도는 확률·유의성·신뢰도가 아니다.', '', '| 하위 분위수 | z 제한 -2 | -2.5 | -3 |', '|---|---:|---:|---:|']
for q in [.01,.025,.05]:
 values=[next(s['communication'] for s in p['threshold_variants'] if s['settings']['lower_quantile']==q and s['settings']['threshold_cap']==cap) for cap in [-2,-2.5,-3]]
 lines.append(f'| {q*100:g}% | '+ ' | '.join(map(str,values))+' |')
lines+=['', '9개 조합 모두 이동·결합 신호는 0건이다. -2.5 제한에서도 남는 3건은 역삼1동 40대·역삼2동 40대(10월), 역삼2동 30대(11월)다. 더 엄격한 설정에서도 모두 유지되는 사례는 없다. 신호 수를 많게 만들기 위한 설정 선택을 하지 않았고 운영 설정은 유지했다.', '', '## 기준 기간과 사례별 민감도', '', '기준 기간을 2023-01~2025-06으로 줄이면 현재 구간 소통 6건(기존 10건 중 6건 유지), 기준 종료를 2024-12로 앞당기면 11건(기존 10건 유지)이다. 두 번째 시나리오에서는 2025년 1~6월이 각 월 점수의 과거 이력에는 들어가지만 임계값 보정에는 들어가지 않는다.', '', '| 사례 | 임계값 9개 설정 중 유지 | 기준 기간 2개 대안 중 유지 | SNS 같은 기준월 지수 |', '|---|---:|---:|---|']
case_payload=[]
levelsets={x['method']:{(r['adm_cd'],r['signal_date'],r['age_band']):r for r in x['latest']} for x in p['level_method_comparisons']}
for case in p['case_sensitivity']:
 sr=next(x for x in sns['cases'] if x['adm_cd']==case['adm_cd'] and x['signal_date']==case['date'] and x['age_band']==case['age_band']);first=sr['same_period_context']
 text=f"{first['sns_index_mean']:+.3f} / {first['quality_status']}" if first['sns_index_mean'] is not None else '자료 부족'
 lines.append(f"| {case['date'][:7]} {case['dong']} {case['age_band']} | {case['retained_in_threshold_variants']}/9 | {case['retained_in_window_variants']}/2 | {text} |")
 states={method:{'seasonal_state':look[(case['adm_cd'],case['date'],case['age_band'])]['seasonal_state'],'local_state':look[(case['adm_cd'],case['date'],case['age_band'])]['local_state']} for method,look in levelsets.items()}
 case_payload.append({**case,'sensitivity_is_not_probability':True,'level_method_states':states,'sns_same_period':first,'observation_window':sr['observation_window'],'review_required':['threshold_and_window_sensitivity','same_person_linkage_unavailable','survey_not_dong_specific','publication_dates_unverified','sns_time_comparison_prohibited'],'confirmed_social_isolation':None})
lines+=['', '## 活動 수준 비교 방식 민감도', '', '| 같은 달 기준 방식 | 12월 정규화 전화·문자 모두 기준 미만 | 구 공통 분리 후 모두 기준 미만 |', '|---|---:|---:|']
for x in p['level_method_comparisons']:
 lines.append(f"| {x['method']} | {sum(r['seasonal_state']=='both_below_reference' for r in x['latest'])} | {sum(r['local_state']=='both_below_reference' for r in x['latest'])} |")
lines+=['', '최근 2년 방식은 비교 진단을 위해 같은 달 최소 이력을 2개로 낮춘 대안이고 운영에 적용하지 않았다. 평균 방식은 과거 같은 달의 기준값만 평균으로 바꾸고 구 공통 통계는 중앙값으로 유지했다. 각 기준에 대한 상대적 회복 상태가 달라지므로 어느 하나를 실제 고립에 맞는 정답으로 고르지 않는다.', '', '도곡2동 40대·일원2동 40대·압구정동 40대는 세 대안 모두에서 두 소통 지표가 구 상대 기준보다 낮았다. 다만 일부 차이는 1% 안팎으로 작고 통계적 유의성이 검증되지 않았다. 이를 새로운 고립 후보나 자동 우선순위로 전환하지 않는다.']
lines+=['', '## 원천 정의 정정', '', 'SNS는 시점별 표준화 기준이 달라 시계열 비교에 부적합하다. 음수는 유효하며 이전 백분율 및 8건 품질 부족 판단을 철회했다. 10건 모두 유한 지수가 있고 3건은 0값 의미 검토 표시가 있다. 같은 기준월·연령 내 지역 상대 비교만 제공한다.', '', '집계 기준월 T는 직전 3개월 관측이다. 10월 기준은 7~9월이며 2025Q3 소비와 정렬한다. 11월 기준은 8~10월로 분기 상권 증감은 연결하지 않는다. 이전 같은 라벨월 소비 해석은 후속 기간 맥락이며 동시 변화 근거로 사용하지 않는다.', '', '휴일의 공휴일 포함 여부와 실제 공개일은 미확인이다. 상세 정정 및 10건 소비 재연결은 docs/SOURCE_DEFINITIONS_RESULT_20261007.md, 사용법은 docs/AI_AGENT_QUICKSTART.md를 참조한다. 신호 기준과 기존 모델 점수는 유지한다. 보고서의 월 표기는 모두 원천 집계 기준월이다.']
(O/'RETROSPECTIVE_VALIDATION_20261007.md').write_text('\n'.join(lines).replace('活動','활동'),encoding='utf-8')
policy=(DB1/'docs/AI_AGENT_EXPLANATION_RULES.md').read_text(encoding='utf-8')
(O/'AI_AGENT_EXPLANATION_RULES.md').write_text(policy,encoding='utf-8')
(O/'agent_case_review.json').write_text(json.dumps({'as_of':'2026-10-07','observations_through':'2025-12','purpose':'validation_snapshot_not_operational_risk','cases':case_payload},ensure_ascii=False,indent=2),encoding='utf-8')
print('Report, explanation rules, and 10 case review records ready')
