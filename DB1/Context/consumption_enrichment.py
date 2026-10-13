"""Allow newly arriving consumption periods; retain immutable source anchors and audit history."""
import json,hashlib
SCHEMA='''
CREATE TABLE IF NOT EXISTS ctx_consumption_anchor(source TEXT,period TEXT,fingerprint TEXT,version TEXT,PRIMARY KEY(source,period));
CREATE TABLE IF NOT EXISTS ctx_enrichment_state(id INTEGER PRIMARY KEY CHECK(id=1),initialized INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS a23_context_revision(id INTEGER PRIMARY KEY,adm_cd TEXT,date TEXT,age_band TEXT,model_version TEXT,previous_json TEXT,current_json TEXT,arrived_periods_json TEXT,detection_sha256 TEXT,reason TEXT,registered_at TEXT DEFAULT CURRENT_TIMESTAMP);
'''
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)
def anchor_changes(c):
    initialized=c.execute('SELECT initialized FROM ctx_enrichment_state WHERE id=1').fetchone()
    current={(s,p):(h,v) for s,p,h,v in c.execute('SELECT source,period,fingerprint,version FROM a3_run')}
    old={(s,p):(h,v) for s,p,h,v in c.execute('SELECT source,period,fingerprint,version FROM ctx_consumption_anchor')}
    for key,value in old.items():
        if current.get(key)!=value:raise ValueError('Consumption source revision/removal blocked: '+str(key))
    added=set(current)-set(old) if initialized else set()
    return current,added
def finish_anchors(c,current):
    c.executemany('INSERT OR IGNORE INTO ctx_consumption_anchor VALUES(?,?,?,?)',[(s,p,h,v) for (s,p),(h,v) in current.items()])
    c.execute('INSERT OR IGNORE INTO ctx_enrichment_state VALUES(1,1)')
def allowed(old,new,added):
    if {k:v for k,v in old.items() if k!='domains'}!={k:v for k,v in new.items() if k!='domains'}:return False
    if len(old['domains'])!=len(new['domains']):return False
    changed=False
    for a,b in zip(old['domains'],new['domains']):
        if a==b:continue
        changed=True
        fixed=['domain','market_period','market_alignment','card_observation_months','card_previous_window_months','interpretation']
        if any(a[k]!=b[k] for k in fixed):return False
        market_keys=['market_comparison','market_change_pct','market_baseline_n']
        if any(a[k]!=b[k] for k in market_keys):
            if a['market_comparison'] is not None or ('market',b['market_period']) not in added:return False
        am={r['period']:r for r in a['card_monthly_context']};bm={r['period']:r for r in b['card_monthly_context']}
        if any(bm.get(p)!=r for p,r in am.items()):return False
        if any(('card',p) not in added for p in set(bm)-set(am)):return False
        card_keys=[k for k in a if k.startswith('card_')]
        if any(a[k]!=b[k] for k in card_keys):
            relevant=a['card_observation_months']+a['card_previous_window_months']
            if not any(('card',p) in added for p in relevant):return False
            if a['card_window_change_pct'] is not None and a['card_window_comparison']!=b['card_window_comparison']:return False
            if a['card_full_window_available'] and not b['card_full_window_available']:return False
            if a['card_previous_window_available'] and not b['card_previous_window_available']:return False
        known=set(fixed+market_keys+card_keys)
        if any(a[k]!=b[k] for k in a if k not in known):return False
    return changed
def upsert_context(c,payload,added):
    keys=[payload[k] for k in ['adm_cd','date','age_band','model_version']]
    row=c.execute('SELECT payload_json FROM a23_observation_context WHERE adm_cd=? AND date=? AND age_band=? AND model_version=?',keys).fetchone()
    text=canonical(payload)
    if not row:
        c.execute('INSERT INTO a23_observation_context VALUES(?,?,?,?,?)',keys+[text]);return (1,0)
    if row[0]==text:return (0,0)
    if not allowed(json.loads(row[0]),payload,added):raise ValueError('Historical consumption revision blocked; explicit migration required '+str(keys))
    detection=c.execute('SELECT result_json FROM a2_age_detection WHERE adm_cd=? AND date=? AND age_band=? AND model_version=?',keys).fetchone()[0]
    c.execute('INSERT INTO a23_context_revision(adm_cd,date,age_band,model_version,previous_json,current_json,arrived_periods_json,detection_sha256,reason) VALUES(?,?,?,?,?,?,?,?,?)',keys+[row[0],text,canonical(sorted(added)),hashlib.sha256(detection.encode()).hexdigest(),'new_consumption_period_arrival'])
    c.execute('UPDATE a23_observation_context SET payload_json=? WHERE adm_cd=? AND date=? AND age_band=? AND model_version=?',[text]+keys)
    return (0,1)
