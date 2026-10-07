"""Age-specific behavior/consumption context; never changes detection scores."""
from pathlib import Path
import argparse,calendar,json,sqlite3
import pandas as pd

AGES={'20s':'20대','30s':'30대','40s':'40대','50s':'50대','60plus':'60대이상'}
VERSION='a23_age_link_v1'
TABLES=['a23_age_detail','a23_age_monthly','a23_age_quarter','a23_age_available_context']
SCHEMA='\n'.join(f'''CREATE TABLE IF NOT EXISTS {t}(adm_cd TEXT,date TEXT,age_band TEXT,model_version TEXT,payload_json TEXT NOT NULL{',domain TEXT' if t in ('a23_age_detail','a23_age_available_context') else ''},PRIMARY KEY(adm_cd,date,age_band,model_version{',domain' if t in ('a23_age_detail','a23_age_available_context') else ''}));
CREATE VIEW IF NOT EXISTS v_{t} AS SELECT * FROM {t};''' for t in TABLES)

def dumps(v):return json.dumps(v,ensure_ascii=False,allow_nan=False,sort_keys=True)
def negative(value):return None if value is None else value<0
def available(con,source,event):
    cutoff=event[:7]+'-'+str(calendar.monthrange(int(event[:4]),int(event[5:7]))[1])
    maximum=event[:7] if source=='card' else str(pd.Period(event[:7],freq='M').asfreq('Q'))
    for period, in con.execute('SELECT period FROM a3_run WHERE source=? AND period<=? AND available_from IS NOT NULL AND substr(available_from,1,10)<=? ORDER BY period DESC',(source,maximum,cutoff)):
        end=pd.Period(period,freq='M' if source=='card' else 'Q').end_time.strftime('%Y-%m-%d')
        if end<=cutoff:return period
    return None

def run(db,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(db) as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_detection'").fetchone():return {'status':'age_detection_unavailable'}
        con.executescript(SCHEMA)
        def load(table,keys):
            return {tuple(r[:-1]):json.loads(r[-1]) for r in con.execute(f'SELECT {keys},payload_json FROM {table}')}
        markets=load('a3a_comparison','period,adm_cd,age,domain')
        cards=load('a3b_feature','period,district,age,domain')
        domains=[r[0] for r in con.execute('SELECT DISTINCT domain FROM a3_dimension ORDER BY domain')]
        details=[];monthly=[];available_rows=[];quarters={}
        for adm,date,scheme,band,model,status,communication,mobility,combined,candidate,j in con.execute('SELECT * FROM a2_age_detection ORDER BY date,adm_cd,age_band,model_version'):
            if scheme!='service' or band not in AGES:continue
            behavior=json.loads(j);month=date[:7];quarter=str(pd.Period(month,freq='M').asfreq('Q'))
            base={'adm_cd':adm,'date':date,'age_band':band,'model_version':model,'link_version':VERSION,'adm_nm':behavior.get('행정동'),'consumption_age':AGES[band],'assessment_status':status,'communication_signal':communication,'mobility_signal':mobility,'combined_signal':combined,'isolation_related_candidate':candidate,'behavior_signal':behavior.get('any_signal'),'context_period':behavior.get('context_period'),'a1_cluster_type':behavior.get('a1_cluster_type')}
            local=[]
            for domain in domains:
                m=markets.get((quarter,str(adm),AGES[band],domain),{})
                c=cards.get((month,'11680',AGES[band],domain),{})
                valid=bool(m.get('comparison_available'))
                change=m.get('change_pct') if valid else None
                card_change=c.get('matched_mom_daily_change_pct') if not c.get('missing_domain',True) else None
                row={**base,'domain':domain,'social_contact_proxy_domain':domain.startswith(('A_','B_','C_')),'market_period':quarter if m else None,'market_alignment':'retrospective_same_quarter','market_scope':'merchant_dong_customer_age','market_comparison_available':valid,'market_change_pct':change,'market_below_prior_min':m.get('below_prior_min') if valid else None,'market_down':negative(change),'market_baseline_n':m.get('baseline_n'),'market_matched_industry_count':m.get('matched_industry_count'),'card_period':month if c else None,'card_scope':'gangnam_merchant_district_customer_age_context','card_change_pct':card_change,'card_down':negative(card_change),'card_relative_change_pp':c.get('relative_change_pp'),'card_seasonal_history_available':c.get('seasonal_history_available'),'same_people_observed':False,'confirmed_isolation':False}
                row['market_card_same_domain_down']=None if row['market_down'] is None or row['card_down'] is None else bool(row['market_down'] and row['card_down'])
                details.append(row);local.append(row)
                pm=available(con,'market',date);pc=available(con,'card',date)
                am=markets.get((pm,str(adm),AGES[band],domain),{}) if pm else {}
                ac=cards.get((pc,'11680',AGES[band],domain),{}) if pc else {}
                available_rows.append({**base,'domain':domain,'market_period':pm,'card_period':pc,'market_change_pct':am.get('change_pct') if am.get('comparison_available') else None,'card_change_pct':ac.get('matched_mom_daily_change_pct'),'alignment':'known_publication_by_event_month_end','market_scope':row['market_scope'],'card_scope':row['card_scope']})
            social=[r for r in local if r['social_contact_proxy_domain']]
            summary={**base,'market_period':quarter,'market_alignment':'retrospective_same_quarter','market_assessable_domains':sum(r['market_comparison_available'] for r in local),'market_down_domains':sum(r['market_down'] is True for r in local),'social_market_down_domains':sum(r['market_down'] is True for r in social),'social_market_unusually_low_domains':sum(r['market_below_prior_min'] is True for r in social),'district_card_assessable_domains':sum(r['card_down'] is not None for r in local),'district_card_down_domains':sum(r['card_down'] is True for r in local),'social_district_card_down_domains':sum(r['card_down'] is True for r in social),'evidence_label':'behavior_signal_with_local_social_consumption_decline' if base['behavior_signal'] and any(r['market_down'] is True for r in social) else 'behavior_signal_without_local_social_consumption_decline' if base['behavior_signal'] else 'no_behavior_signal' if base['behavior_signal'] is not None else 'behavior_unassessable','consumption_isolation_score':None,'domains':local}
            summary['social_market_card_same_domain_down_domains']=sum(r['market_card_same_domain_down'] is True for r in social)
            monthly.append(summary)
            key=(adm,quarter,band,model)
            q=quarters.setdefault(key,{**base,'date':quarter,'observed_months':0,'fully_assessed_months':0,'communication_signal_months':[],'mobility_signal_months':[],'combined_signal_months':[],'market_domain_context':[{k:r[k] for k in ('domain','market_change_pct','market_below_prior_min','market_comparison_available')} for r in local],'card_month_context':[]})
            q['observed_months']+=1;q['fully_assessed_months']+=status=='assessed'
            for flag in ('communication','mobility','combined'):
                if base[flag+'_signal']:q[flag+'_signal_months'].append(month)
            q['card_month_context'].append({'month':month,'district_down_domains':summary['district_card_down_domains'],'assessable_domains':summary['district_card_assessable_domains']})
        # Quarter flags are month lists, not the first month's scalar flags.
        for q in quarters.values():
            for key in ('communication_signal','mobility_signal','combined_signal','isolation_related_candidate','behavior_signal','assessment_status'):q.pop(key,None)
        with con:
            for table,rows in zip(TABLES,[details,monthly,list(quarters.values()),available_rows]):
                con.execute('DELETE FROM '+table)
                for r in rows:
                    keys=[r[k] for k in ('adm_cd','date','age_band','model_version')]
                    if table in ('a23_age_detail','a23_age_available_context'):con.execute('INSERT INTO '+table+' VALUES(?,?,?,?,?,?)',(*keys,dumps(r),r['domain']))
                    else:con.execute('INSERT INTO '+table+' VALUES(?,?,?,?,?)',(*keys,dumps(r)))
        def export(name,rows):
            frame=pd.DataFrame(rows)
            for column in frame:
                frame[column]=frame[column].map(lambda x:dumps(x) if isinstance(x,(list,dict)) else x)
            tmp=directory/(name+'.csv.tmp');frame.to_csv(tmp,index=False,encoding='utf-8-sig');tmp.replace(directory/(name+'.csv'))
        for name,rows in [('analysis23_age_detail',details),('analysis23_age_monthly',monthly),('analysis23_age_quarter',list(quarters.values())),('analysis23_age_available_context',available_rows),('age_signal_consumption_context',[r for r in monthly if r['behavior_signal']])]:export(name,rows)
        signals=[r for r in monthly if r['behavior_signal']]
        report={'link_version':VERSION,'monthly_rows':len(monthly),'detail_rows':len(details),'quarter_rows':len(quarters),'behavior_signal_rows':len(signals),'signal_with_local_social_market_decline':sum(r['social_market_down_domains']>0 for r in signals),'signal_with_local_social_market_below_prior_min':sum(r['social_market_unusually_low_domains']>0 for r in signals),'signal_with_social_district_card_decline':sum(r['social_district_card_down_domains']>0 for r in signals),'known_publication_market_rows':sum(r['market_period'] is not None for r in available_rows),'known_publication_card_rows':sum(r['card_period'] is not None for r in available_rows),'confirmed_isolation':False}
        report['signal_with_same_social_domain_market_card_decline']=sum(r['social_market_card_same_domain_down_domains']>0 for r in signals)
        (directory/'age_consumption_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(dumps(run(a.db,a.output)))
