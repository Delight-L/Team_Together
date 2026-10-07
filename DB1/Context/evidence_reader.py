"""Dependency-free explanation status and publication filtering for DB1 readers."""
import json
from datetime import date
def lookup(c,kind,period):
    row=c.execute('SELECT available_from,proof,registered_at FROM ctx_publication_registry WHERE kind=? AND period=?',(kind,period)).fetchone()
    return dict(row) if row else {'available_from':None,'proof':None,'registered_at':None}
def known(c,kind,period,as_of):
    d=lookup(c,kind,period)['available_from'];return d is not None and d<=as_of
def core_available(c,label,as_of):
    # Availability of all input labels through requested score, not just newest file.
    labels=[r[0][:7] for r in c.execute('SELECT date FROM a2_age_source WHERE date<=?',(label,))]
    return bool(labels) and all(known(c,kind,p,as_of) for p in labels for kind in ['telecom','interest'])
def status(available,reason,**extra):return {'status':'available' if available else 'unavailable','reason':reason,**extra}
def enrich(c,item,as_of=None):
    if as_of and date.fromisoformat(as_of).isoformat()!=as_of:raise ValueError('as_of must be YYYY-MM-DD')
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='ctx_weather_window'").fetchone():
        item['supplemental_context_status']='not_installed'
        return item if as_of is None else None
    label=item['source_label_date'];age=item['age_band'];cons=item['observation_consumption_json']
    if as_of and not core_available(c,label,as_of):return None
    p=c.execute('SELECT observation_weather_json,youth_detail_json FROM v_a123_age_evidence_context WHERE adm_cd=? AND age_band=? AND source_label_date=? AND model_version=?',(item['adm_cd'],age,label,item['model_version'])).fetchone()
    weather=json.loads(p[0]) if p and p[0] else None;youth=json.loads(p[1]) if p and p[1] else []
    guides=[dict(r) for r in c.execute('SELECT source_id,age_scope,topic,payload_json FROM ctx_evidence_guide')] if age in ['20s','30s'] else []
    for g in guides:g['payload_json']=json.loads(g['payload_json'])
    availability={'telecom':lookup(c,'telecom',label[:7]),'interest':lookup(c,'interest',label[:7])}
    if as_of:
        if weather and not all(known(c,'weather',m,as_of) for m in weather['observation_months']):
            weather={**weather,'totals':{k:None for k in weather['totals']},'monthly_values':[],'quality_status':'publication_unverified_or_after_cutoff'}
        if cons:
            for d in cons['domains']:
                market_periods=[d['market_period']]+((d.get('market_comparison') or {}).get('baseline_periods',[]))
                if d['market_period'] and not all(known(c,'market',q,as_of) for q in market_periods):
                    for k in ['market_change_pct','market_comparison','market_baseline_n']:d[k]=None
                    d['market_publication_status']='unverified_or_after_cutoff'
                d['card_monthly_context']=[m for m in d['card_monthly_context'] if known(c,'card',m['period'],as_of)]
                d['card_available_months']=[m['period'] for m in d['card_monthly_context']]
                d['card_full_window_available']=len(d['card_available_months'])==3
                if not all(known(c,'card',m,as_of) for m in d['card_observation_months']+d['card_previous_window_months']):
                    d['card_window_change_pct']=None;d['card_window_comparison']=None;d['card_comparison_reason']='publication_unverified_or_after_cutoff'
        youth=[r for r in youth if known(c,'survey',r['source_id'],as_of)]
        guides=[g for g in guides if known(c,'survey',g['source_id'],as_of)]
        bg=item.get('survey_and_elder_background')
        if bg:
            sid='seoul_'+str(bg['survey_year'])
            if not known(c,'survey',sid,as_of):bg['survey_context_json']=None;bg['survey_publication_status']='unverified_or_after_cutoff'
            # Annual elderly releases have not been registered by this adapter.
            bg['elder_context_json']=None;bg['elder_publication_status']='unverified'
    item.update(observation_weather=weather,youth_reference={'applicability':'applicable_static_reference' if age in ['20s','30s'] else 'not_applicable','metrics':youth,'guides':guides,'geography':'gangnam_not_dong','risk_score_modified':False},source_availability=availability,auxiliary_as_of=as_of)
    item['feature_period_annotation']={'legacy_weather_and_calendar_fields_period':label[:7],'legacy_weather_matches_behavior_window':False,'aligned_weather_field':'observation_weather','legacy_fields':['rainfall_mm','rain_days','snow_days','days_in_month','weekday_days','weekend_days'],'note':'Do not use label-month legacy weather as simultaneous three-month behavior evidence.'}
    quality={
        'communication':status(item['communication_signal'] is not None,item['assessment_status']),
        'mobility':status(item['mobility_signal'] is not None,item['assessment_status']),
        'sns':status(item['same_period_sns_json'] is not None and item['same_period_sns_json'].get('sns_index_mean') is not None,item['same_period_sns_json'].get('quality_status') if item['same_period_sns_json'] else 'missing',time_comparison_allowed=False),
        'weather':status(weather is not None and weather['quality_status']=='available',weather['quality_status'] if weather else 'missing',not_detection_input=True),
        'youth':{'status':'not_applicable' if age not in ['20s','30s'] else 'available' if youth else 'unavailable','reason':'static_age_reference_only','age_alignment_review':age=='20s'},
        'consumption':[]}
    if cons:
        for d in cons['domains']:
            quality['consumption'].append({'domain':d['domain'],'market':status(d['market_change_pct'] is not None,'ready' if d['market_change_pct'] is not None else d.get('market_publication_status') or ('no_exact_quarter_match' if d['market_period'] is None else 'missing_snapshot_or_history')),'card':status(d['card_window_change_pct'] is not None,d['card_comparison_reason'])})
    bg=item.get('survey_and_elder_background');metrics=bg.get('survey_context_json') if bg else None
    quality['survey']=status(bool(metrics),'district_age_annual_retrospective' if metrics else 'missing_or_unavailable')
    quality['survey']['metric_quality']={k:{'quality_status':v.get('quality_status'),'notes':v.get('metadata',{}).get('notes',[]),'n_valid':v.get('n_valid'),'effective_n':v.get('effective_n')} for k,v in (metrics or {}).items()}
    quality['youth']['metric_review_count']=sum(r['quality_status']!='available' or bool(r.get('metadata',{}).get('notes')) for r in youth)
    quality['youth']['review_note']='Sparse responses, age mismatch and survey proxy/weight limits remain visible in per-metric metadata; availability is not confidence.'
    quality['elder']={'status':'partial_age_alignment' if age=='60plus' and bg and bg.get('elder_context_json') else 'unavailable' if age=='60plus' else 'not_applicable','reason':'source_65plus_not_exact_60plus'}
    item['evidence_status']=quality
    item['quality_is_not_confidence_or_risk_score']=True
    return item
