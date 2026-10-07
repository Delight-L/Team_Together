"""Explain existing DB1 signals; never fit models or write to SQLite."""
import argparse
import json
import math
from pathlib import Path
import sys

LABELS={'call_contacts':'통화 상대 수','text_contacts':'문자 상대 수','weekday_move_count':'평일 이동 횟수','weekend_move_count':'주말 이동 횟수'}

def percent(value):
    return math.expm1(value)*100 if isinstance(value,(int,float)) and math.isfinite(value) else None

def finite(value):
    return isinstance(value,(int,float)) and math.isfinite(value)

def basis_check(metrics,basis):
    tests=[(m,next(t for t in m['tests'] if t['basis']==basis)) for m in metrics]
    assessed=[m['metric'] for m,t in tests if t['assessable']]
    triggered=[m['metric'] for m,t in tests if t['assessable'] and t['signal']]
    return {'status':'confirmed' if triggered else 'not_detected' if assessed else 'not_assessable',
            'triggered_metrics':triggered,'assessable_metrics':assessed,
            'not_assessable_metrics':[m['metric'] for m,t in tests if not t['assessable']]}

def consumption_check(row):
    domains=(row.get('observation_consumption_json') or {}).get('domains',[])
    comparisons=[]
    for domain in domains:
        comparison=domain.get('market_comparison') or {}
        available=(domain.get('market_alignment')=='exact_full_quarter'
                   and bool(comparison.get('comparison_available'))
                   and bool(domain.get('market_period')) and finite(domain.get('market_change_pct')))
        value=domain.get('market_change_pct') if available else None
        comparisons.append({'domain':domain.get('domain'),'available':available,
                            'period':domain.get('market_period'),'change_pct':value,
                            'direction':'decrease' if available and value<0 else 'increase' if available and value>0 else 'unchanged' if available else 'unavailable',
                            'comparison_reason':comparison.get('comparison_reason') or domain.get('market_alignment'),
                            'baseline_n':domain.get('market_baseline_n'),
                            'baseline_method':comparison.get('baseline_method')})
    available=[c for c in comparisons if c['available']]
    decreases=[c['domain'] for c in available if c['direction']=='decrease']
    if not available:status='unavailable'
    elif len(decreases)==len(available):status='all_comparable_domains_decreased'
    elif decreases:status='mixed_directions'
    else:status='no_decrease_in_comparable_domains'
    card=[d['domain'] for d in domains if d.get('card_full_window_available') and d.get('card_previous_window_available') and finite(d.get('card_window_change_pct'))]
    return {'status':status,'available_domain_count':len(available),'total_domain_count':len(domains),
            'coverage_complete':bool(domains) and len(available)==len(domains),
            'decreased_domains':decreases,'domains':comparisons,
            'card_comparable_domains':card,
            'card_status':'comparison_available' if card else 'comparison_unavailable',
            'scope':'merchant_location_context_not_same_residents',
            'not_individual_isolation_confirmation':True}

def evidence_checks(row,metrics):
    r=row.get('result_json') or {}
    follow=row.get('activity_followup_same_label') or {}
    signal=bool(row.get('communication_signal') or row.get('mobility_signal'))
    survey=row.get('survey_and_elder_background') or {}
    return {'self_history':basis_check(metrics,'absolute'),
            'regional_comparison':basis_check(metrics,'local'),
            'persistence':{'status':'requires_followup' if signal else 'not_applicable',
                           'adjacent_signal_run':r.get('adjacent_signal_run'),
                           'consecutive_both_below_months':follow.get('consecutive_both_below_months'),
                           'months_since_signal':follow.get('months_since_signal'),
                           'reference_date':follow.get('reference_date'),
                           'independent_windows_verified':False,
                           'note':'Same-label followup and overlapping windows alone do not verify persistence; independent temporal verification is not implemented.'},
            'auxiliary':{'consumption':consumption_check(row),
                         'survey_status':'annual_district_background' if survey.get('survey_context_json') else 'unavailable',
                         'youth_applicability':(row.get('youth_reference') or {}).get('applicability','unavailable'),
                         'elder_age_alignment':survey.get('elder_age_alignment','unavailable')},
            'interpretation':'independent_evidence_checks_not_risk_levels_or_sequential_gates'}

def check_labels(checks):
    # A positive local check can exist without a positive self-history check.
    def basis_label(check):
        if check['status']=='confirmed':return '확인: '+ '·'.join(LABELS[k] for k in check['triggered_metrics'])
        return '추가 탐지 없음' if check['status']=='not_detected' else '평가 자료 부족'
    return [basis_label(checks['self_history']),basis_label(checks['regional_comparison'])]

def explain(row):
    r=row.get('result_json') or {}
    comm=bool(row.get('communication_signal')); move=bool(row.get('mobility_signal'))
    assessed=row.get('assessment_status')=='assessed'
    category=('communication_and_mobility' if comm and move else 'communication_only' if comm else 'mobility_only' if move else 'no_signal' if assessed else 'insufficient_data')
    titles={'communication_and_mobility':'소통·이동 복합 변화 신호','communication_only':'소통 변화 관찰 신호','mobility_only':'이동 변화 관찰 신호','no_signal':'이번 기간 탐지 신호 없음','insufficient_data':'평가 자료 부족'}
    name=r.get('행정동') or (row.get('same_period_sns_json') or {}).get('adm_nm') or row.get('adm_cd')
    age={'20s':'20대','30s':'30대','40s':'40대','50s':'50대','60plus':'60세 이상'}.get(row.get('age_band'),row.get('age_band'))
    lines=[f"{name} {age}: {titles[category]}. 자료 라벨은 {row.get('source_label_date')}이며 실제 관측 기간은 {row.get('observation_start')}~{row.get('observation_end')}입니다."]
    metrics=[]
    for key,label in LABELS.items():
        evidence={'metric':key,'label':label,'value':r.get(key),'change_pct':percent(r.get(key+'_log_change')),'common_change_pct':percent(r.get(key+'_common_change')),'coverage':r.get(key+'_coverage'),'tests':[]}
        for basis in ('absolute','local'):
            evidence['tests'].append({'basis':basis,'assessable':r.get(key+'_'+basis+'_assessable'),'signal':r.get(key+'_'+basis+'_signal'),'rz':r.get(key+'_'+basis+'_rz'),'threshold':r.get(key+'_'+basis+'_threshold'),'baseline_n':r.get(key+'_'+basis+'_baseline_n')})
        metrics.append(evidence)
        changes=evidence['change_pct']
        if changes is not None:lines.append(f"{label}의 직전 라벨 대비 변화는 {changes:+.2f}%입니다. 두 관측 창은 2개월이 겹치므로 독립된 월별 변화로 해석하지 않습니다.")
        for test in evidence['tests']:
            if test['signal'] and test['assessable'] and test['rz'] is not None and test['threshold'] is not None:
                basis='과거 자체 변화 기준' if test['basis']=='absolute' else '동일 연령의 강남구 공통 변화를 제외한 기준'
                lines.append(f"{label}는 {basis}에서 탐지되었습니다(rZ {test['rz']:.3f}, 적용 경계 {test['threshold']:.3f}, 과거 비교 {test['baseline_n']}건).")
        if key.endswith('move_count') and changes is not None and not any(t['signal'] for t in evidence['tests']):
            common=evidence['common_change_pct']
            suffix=f" 동일 연령의 지역 공통 변화는 {common:+.2f}%입니다." if common is not None else ''
            lines.append(f"{label}는 저장된 탐지 기준에서 신호로 판정되지 않았습니다.{suffix} 단순 감소율만으로 이동 이상 신호를 추가하지 않습니다.")
    checks=evidence_checks(row,metrics)
    # Display these checks independently; auxiliary context never promotes a signal.
    self_label,regional_label=check_labels(checks)
    market=checks['auxiliary']['consumption']
    market_label={'unavailable':'기간이 일치하는 비교자료 없음','all_comparable_domains_decreased':'비교 가능한 영역 모두 감소','mixed_directions':'감소·증가 등이 혼재','no_decrease_in_comparable_domains':'비교 가능한 영역에서 감소 없음'}[market['status']]
    checks['display']={'self_history':self_label,'regional_comparison':regional_label,
                       'persistence':'추가 추적 필요' if checks['persistence']['status']=='requires_followup' else '해당 없음',
                       'consumption':market_label}
    lines.insert(1,f"근거 확인 상태 — 자체 과거 기준: {self_label}; 지역 비교: {regional_label}; 지속성: {checks['display']['persistence']}; 상권 소비 배경: {market_label}.")
    candidate=bool(r.get('isolation_related_candidate'))
    lines.append('기존 DB1의 사회적 고립 관련 복합 후보 기준을 충족합니다.' if candidate else '기존 DB1의 사회적 고립 관련 복합 후보 기준은 충족하지 않았습니다. 소통·활동 위축 가능성을 후속 관찰하는 근거로 사용합니다.' if comm or move else '신호가 없다는 결과만으로 사회적 고립 가능성이 없다고 판단하지 않습니다.')
    lines.append(f"Analysis1 지역유형은 {r.get('a1_cluster_type','미확인')} ({r.get('context_period','미확인')})이며 지역 배경으로 사용합니다. 기존 군집은 유지했습니다.")
    follow=row.get('activity_followup_same_label') or {}
    states={'mixed_recovery':'통화·문자의 회복 방향이 서로 다름','both_below_reference':'통화·문자 모두 기준보다 낮음','both_recovered':'통화·문자 모두 기준 수준 회복'}
    if follow:
        raw=follow.get('raw_state');local=follow.get('local_state')
        lines.append(f"같은 라벨의 후속 추적: 원자료 상태 {states.get(raw,raw)}, 지역 공통 변화를 고려한 상태 {states.get(local,local)}. 기준 라벨 {follow.get('reference_date')}. 겹치는 관측 창의 연속 신호를 독립된 반복 사건으로 세지 않습니다.")
    if comm or move:
        lines.append('지속성은 추가 추적이 필요합니다. 같은 라벨의 추적 상태와 겹치는 관측 창의 연속 감소만으로 지속성이 확인됐다고 판정하지 않습니다.')
    consumption=(row.get('observation_consumption_json') or {}).get('domains',[])
    for domain in consumption:
        value=domain.get('market_change_pct')
        check=next(c for c in market['domains'] if c['domain']==domain.get('domain'))
        if check['available']:
            lines.append(f"{domain.get('domain')} 상권 소비 비교: {domain['market_period']}, 과거 동일 분기 비교 기준 대비 {value:+.2f}%. 동 소재 가맹점의 소비 배경이며 해당 연령 주민의 소비 변화로 환산하지 않습니다.")
        else:lines.append(f"{domain.get('domain')} 상권 소비는 관측 창과 정확히 일치하는 분기 비교가 없어 연결 판단을 유보합니다.")
        card=domain.get('card_window_change_pct')
        if isinstance(card,(int,float)) and domain.get('card_previous_window_available'):
            lines.append(f"강남구 해당 연령 카드 소비의 동일 창 비교는 {card:+.2f}%입니다. 가맹점 소재지 기준 보조자료입니다.")
    if consumption and not any(isinstance(d.get('card_window_change_pct'),(int,float)) and d.get('card_previous_window_available') for d in consumption):
        lines.append('신한카드의 이전 3개월 비교자료가 부족해 소통 변화와 소비 감소의 동반 여부를 판단할 수 없습니다. 현재 월별 값은 기술통계로만 제공됩니다.')
    survey=row.get('survey_and_elder_background') or {}
    selected={k:v for k,v in (survey.get('survey_context_json') or {}).items() if k in ('no_support_all3','loneliness_outside_mean10')}
    for key,v in selected.items():
        value=v.get('value')
        if value is not None:
            display=f"{value*100:.2f}%" if v.get('unit')=='proportion' else f"{value:.2f}/10"
            label={'no_support_all3':'세 상황 모두 도움받을 사람이 없는 응답 비율','loneliness_outside_mean10':'외부 소외감 평균'}.get(key,key)
            lines.append(f"{survey.get('survey_year')}년 강남구 관계망 배경 {label}: {display} (유효 응답 {v.get('n_valid')}명, 품질 {v.get('quality_status')}). 구 단위 연간 통계이며 이 동의 발생률이나 탐지 확률이 아닙니다.")
    youth=row.get('youth_reference') or {}
    lines.append('고립·은둔 청년조사는 적용 연령에 해당하는 정적 참고자료로 연결했습니다. 조사 분류·표본·분모는 구조화 근거에 유지했습니다.' if youth.get('applicability')=='applicable_static_reference' else '고립·은둔 청년조사는 해당 연령에 적용하지 않습니다.')
    lines.append('독거노인 자료는 해당 연령 범위와 일치할 때만 참고합니다. 연령 범위 불일치는 구조화 근거에 표시했습니다.')
    sns=row.get('same_period_sns_json') or {}
    lines.append(f"SNS 자료의 품질은 {sns.get('quality_status','자료 없음')}이며 동일 라벨의 동·연령 비교에만 사용합니다. SNS 감소율을 계산하지 않습니다.")
    weather=row.get('observation_weather') or {}
    lines.append(f"실제 관측 창 기상자료 품질은 {weather.get('quality_status','자료 없음')}입니다. 기상은 이동 해석의 참고자료이며 현재 탐지 모델의 보정 입력은 아닙니다.")
    lines.append('현재 결과는 사후 관측자료에 근거한 지역·연령 집단 신호입니다. 개인별 고립 확률이나 미래 발생 확률을 산출하지 않습니다.')
    return {'signal_id':f"{row.get('adm_cd')}_{row.get('age_band')}_{row.get('source_label_date')}",'dong_name':name,'age':age,'category':category,'title':titles[category],'isolation_related_candidate':candidate,'assessment_status':row.get('assessment_status'),'probability':None,'observation_start':row.get('observation_start'),'observation_end':row.get('observation_end'),'source_label_date':row.get('source_label_date'),'metrics':metrics,'evidence_checks':checks,'explanation':lines,'source_view':'v_a123_age_source_context','evidence':row}

def build(data):
    rows=[explain(r) for r in data['rows']]
    summary={'self_history_confirmed':sum(r['evidence_checks']['self_history']['status']=='confirmed' for r in rows),
             'regional_comparison_confirmed':sum(r['evidence_checks']['regional_comparison']['status']=='confirmed' for r in rows),
             'persistence_requires_followup':sum(r['evidence_checks']['persistence']['status']=='requires_followup' for r in rows),
             'all_comparable_market_domains_decreased':sum(r['evidence_checks']['auxiliary']['consumption']['status']=='all_comparable_domains_decreased' for r in rows)}
    return {'schema_version':'isolation_explanation_v2','scope':'administrative_dong_age_group','database_mode':'read_only','model_refitted':False,'as_of':data.get('as_of'),'count':len(rows),'category_counts':{k:sum(r['category']==k for r in rows) for k in sorted(set(r['category'] for r in rows))},'isolation_related_candidate_count':sum(r['isolation_related_candidate'] for r in rows),'evidence_check_counts':summary,'rows':rows}

def markdown(data):
    out=['# DB1 사회적 고립 관련 신호 설명','',f"총 {data['count']}건. 기존 모델과 군집을 유지하고 저장된 탐지 결과를 설명했습니다.",'',f"유형별 건수: {data['category_counts']}. 기존 복합 후보 기준 충족: {data['isolation_related_candidate_count']}건.",'']
    out.extend(['근거 확인 상태는 독립된 항목입니다. 위험 등급이나 순차 통과 조건이 아니며 소비·조사 자료만으로 기존 신호를 승격하지 않습니다.','',
                '| 탐지 대상 | 자료 라벨 | 자체 과거 기준 | 지역 비교 | 지속성 | 상권 소비 배경 |',
                '|---|---|---|---|---|---|'])
    for row in data['rows']:
        display=row['evidence_checks']['display']
        out.append(f"| {row['dong_name']} {row['age']} | {row['source_label_date']} | {display['self_history']} | {display['regional_comparison']} | {display['persistence']} | {display['consumption']} |")
    out.extend(['','지속성은 겹치지 않는 기간 등을 고려한 별도 검증이 필요하므로 현재 생성기는 확인 완료로 판정하지 않습니다. 상권 소비는 가맹점 소재지 기준 배경입니다.',''])
    for n,r in enumerate(data['rows'],1):
        out.extend([f"## {n}. {r['dong_name']} {r['age']} · {r['source_label_date']}",'',*['- '+s for s in r['explanation']],'',f"근거 식별자: `{r['signal_id']}`. 상세 원본·품질·분모·추적 상태는 JSON의 evidence에 포함합니다.",''])
    return '\n'.join(out)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',default=str(Path(__file__).resolve().parents[1]/'outputs/db1.sqlite'))
    for name in ('dong','age','label','as-of','output','markdown'):p.add_argument('--'+name)
    p.add_argument('--limit',type=int,default=1000);p.add_argument('--include-no-signals',action='store_true')
    a=p.parse_args()
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from read_agent_context import read
    data=build(read(a.db,a.label,a.dong,a.age,not a.include_no_signals,a.limit,a.as_of))
    content=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)
    if a.output:Path(a.output).write_text(content,encoding='utf-8')
    else:print(content)
    if a.markdown:Path(a.markdown).write_text(markdown(data),encoding='utf-8')

if __name__=='__main__':main()
