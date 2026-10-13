"""Verified item-level summaries of 2022 youth surveys, separate from detection inputs."""
from pathlib import Path
from contextlib import closing
import sqlite3,json,hashlib,re
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from survey import metric_row
VERSION='youth_detail_v1'
SCHEMA='''
CREATE TABLE IF NOT EXISTS ctx_youth_source(source_id TEXT PRIMARY KEY,kind TEXT,year INTEGER,sha256 TEXT,method_version TEXT,payload_json TEXT);
CREATE TABLE IF NOT EXISTS ctx_youth_metric(source_id TEXT,district TEXT,age_band TEXT,metric TEXT,value REAL,unit TEXT,n_total INTEGER,n_valid INTEGER,n_event INTEGER,n_households INTEGER,effective_n REAL,quality_status TEXT,payload_json TEXT,PRIMARY KEY(source_id,district,age_band,metric));
CREATE VIEW IF NOT EXISTS v_youth_detail AS SELECT s.kind,s.year,s.method_version,m.* FROM ctx_youth_metric m JOIN ctx_youth_source s USING(source_id);
'''
def dump(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False,default=str)
def codebook(sheet):
    blocks={};key=None
    for row in sheet.values:
        code,label=row[:2]
        if isinstance(code,str):key=code.upper();blocks[key]={'question':label,'codes':{}}
        elif isinstance(code,(int,float)) and key:blocks[key]['codes'][int(code)]=label
    return blocks
def block(book,name):
    candidates=[v for k,v in book.items() if k==name.upper() or k.startswith(name.upper()+' TO ')]
    if len(candidates)!=1:raise ValueError('Ambiguous/missing codebook '+name)
    return candidates[0]
def checked(s,allowed):
    v=pd.to_numeric(s,errors='raise')
    if (~v.isna()&~v.isin(allowed)).any():raise ValueError('Unexpected item response code')
    return v
def binary(s,allowed,event,unknown=()):
    v=checked(s,list(allowed)+list(unknown));return v.isin(event).astype(float).where(v.isin(allowed))
def support(frame,columns,unknown=()):
    values=frame[columns].apply(pd.to_numeric,errors='raise')
    allowed=[1,2,3,4,*unknown]
    if (~values.isna()&~values.isin(allowed)).any().any():raise ValueError('Unexpected support selection')
    none=values.eq(4).any(axis=1);helper=values.isin([1,2,3]).any(axis=1);unk=values.isin(unknown).any(axis=1) if unknown else pd.Series(False,index=values.index)
    if (none&helper).any() or (unk&(none|helper)).any():raise ValueError('Contradictory support options')
    return none.astype(float).where(none|helper)
def packet(kind,path):
    path=Path(path);sha=hashlib.sha256(path.read_bytes()).hexdigest();sid='youth2022_'+kind
    w=load_workbook(path,read_only=True,data_only=True)
    try:
        it=w.worksheets[0].values;headers=next(it);book=codebook(w.worksheets[1])
        outing='A4x1' if kind=='household' else 'A7';duration='A5x1' if kind=='household' else 'A8'
        friends='A7x1_3' if kind=='household' else 'A13_3';other='A7x1_4' if kind=='household' else 'A13_4'
        support_prefix='A6x1' if kind=='household' else 'A12'
        support_cols={n:[f'{support_prefix}_{n}_{j}' for j in range(1,6 if kind=='household' else 5)] for n in range(1,5)}
        base=['SEQ','SQ4',outing,duration,friends,other]+sum(support_cols.values(),[])
        base+=['SQ11_1_RR','WT_ALL3','HIKI_C'] if kind=='household' else ['SQ2','A10','A17','KEY_1']+[f'C4_{n}' for n in range(1,10)]
        idx=[headers.index(c) for c in base];d=pd.DataFrame([[r[i] for i in idx] for r in it],columns=base)
    finally:w.close()
    if '강남구'!=block(book,'SQ4')['codes'].get(1):raise ValueError('Gangnam code changed')
    for item,c,term in [(outing,7,'집 밖'),(friends,1,'전혀'),(support_cols[1][0],4,'없음')]:
        if term not in str(block(book,item)['codes'].get(c)):raise ValueError('Item code semantics changed '+item)
    if kind=='youth':
        if '그렇다'!=block(book,'A17')['codes'].get(1):raise ValueError('Online code changed')
        if '중복 선택' not in block(book,'C4_1')['question']:raise ValueError('Support item changed')
    d['weight']=d.WT_ALL3 if kind=='household' else 1.;d['household_id']=d.SEQ
    if kind=='household':
        ages=checked(d.SQ11_1_RR,[1,2,3,4]);d['fine_age']=ages.map({1:'19to24',2:'25to29',3:'30to34',4:'35to39'})
        if ages.isna().any():raise ValueError('Missing household age')
        masks={'19to39':pd.Series(True,index=d.index),'19to29':ages.isin([1,2]),'30s':ages.isin([3,4]),**{label:d.fine_age.eq(label) for label in ['19to24','25to29','30to34','35to39']}}
    else:
        ages=pd.to_numeric(d.SQ2,errors='raise')
        if ages.isna().any() or not ages.between(19,39).all():raise ValueError('Youth age outside 19..39')
        masks={'19to39':ages.between(19,39),'20s':ages.between(20,29),'30s':ages.between(30,39),**{label:ages.between(lo,hi) for label,lo,hi in [('19to24',19,24),('25to29',25,29),('30to34',30,34),('35to39',35,39)]}}
    specs=[]
    def add(name,v,item,definition,unit='proportion',denominator='valid_item_respondents',labels=None):
        specs.append((name,v,item,definition,unit,denominator,labels))
    classifier='HIKI_C' if kind=='household' else 'KEY_1'
    add('survey_isolated_or_withdrawn_share',binary(d[classifier],[1,2,3] if kind=='household' else [1,2],[1,2] if kind=='household' else [1]),classifier,'Source isolation/withdrawal classification; household weighted proportion or youth unweighted respondent share, not current dong isolation prevalence')
    valid=range(1,9);unknown=[9] if kind=='household' else []
    add('limited_outing_share',binary(d[outing],valid,[5,6,7,8],unknown),outing,'Usually at home, outings only for own hobby/convenience or no outings; source responses 5..8')
    add('homebound_share',binary(d[outing],valid,[7,8],unknown),outing,'Does not go outside home; source responses 7/8')
    dur=checked(d[duration],list(range(1,9))+unknown)
    duration_v=dur.ge(3).astype(float).where(dur.isin(range(1,9))&d[outing].isin([5,6,7,8]))
    add('limited_outing_six_months_share',duration_v,duration,'Duration >=6 months among limited-outing respondents with valid duration','proportion','limited_outing_with_valid_duration')
    for name,item in [('friends',friends),('other_people',other)]:
        add('rare_face_to_face_'+name+'_share',binary(d[item],range(1,7),[1,2],[7] if kind=='household' else []),item,'Face-to-face interaction none or once/twice per year; source responses 1/2')
    support_values=[]
    for n,name in enumerate(['advice','urgent','money','emotion'],1):
        v=support(d,support_cols[n],[5] if kind=='household' else []);support_values.append(v)
        add('no_support_'+name+'_share',v,support_cols[n][0],'No helper selected, none option=4; all blank/unknown excluded')
    allsupport=pd.concat(support_values,axis=1)
    v=allsupport.eq(1).all(axis=1).astype(float).where(allsupport.notna().all(axis=1))
    add('no_support_all_four_share',v,support_cols[1][0],'No helper in all four situations; complete valid responses only','proportion','all_four_support_items_valid')
    if kind=='youth':
        contacts=pd.to_numeric(d.A10,errors='raise')
        if ((contacts<0)|(~np.isfinite(contacts)&contacts.notna())).any():raise ValueError('Invalid contacts count')
        add('face_to_face_contacts_mean',contacts,'A10','Number of distinct conversation partners in last 2 weeks; excludes shopping/ordering incidental contacts','persons')
        add('no_face_to_face_contacts_share',contacts.eq(0).astype(float).where(contacts.notna()),'A10','Zero conversation partners in last 2 weeks; not a clinical diagnosis')
        add('online_conversation_share',binary(d.A17,[1,2],[1]),'A17','Has online conversation; independent survey population, not telecom SNS Z index')
        cv=d[[f'C4_{n}' for n in range(1,10)]].apply(pd.to_numeric,errors='raise')
        for n in range(1,10):
            s=cv[f'C4_{n}'];checked(s,[n])
        eligible=cv.notna().any(axis=1)
        for n in range(1,10):
            add(f'support_need_{n}_share',cv[f'C4_{n}'].eq(n).astype(float).where(eligible),'C4_1',f'Selects support option {n}: '+str(block(book,'C4_1')['codes'][n]),'proportion','respondents_with_at_least_one_support_selection',block(book,'C4_1')['codes'][n])
    records=[]
    for district,geo in [('gangnam',d.SQ4.eq(1)),('seoul',pd.Series(True,index=d.index))]:
        for age,mask in masks.items():
            select=geo&mask;group=d.loc[select]
            for name,v,item,definition,unit,denominator,label in specs:
                vals=v.loc[select];event=vals if unit=='proportion' else None
                r=list(metric_row(group,sid,district,age,name,vals,unit,definition,event));p=json.loads(r[-1])
                p.update(source_item=item,codebook=block(book,item),denominator=denominator,response_label=label,weight='WT_ALL3' if kind=='household' else 'unweighted',method_version=VERSION,age_alignment='includes_19_not_exact_20s' if age=='19to29' else 'source_defined_age',population_scope='household_proxy' if kind=='household' else 'youth_respondents_not_population_prevalence',geography_alignment='district_not_dong',static_reference=True,not_detection_input=True)
                r[-1]=dump(p);records.append(tuple(r))
    meta={'source_path':str(path),'sha256':sha,'kind':kind,'year':2022,'method_version':VERSION,'source_fields':base,'rows':len(d),'weight':'WT_ALL3' if kind=='household' else 'unweighted','raw_person_rows_not_stored':True}
    return sid,meta,records
def run(c,config):
    count=0
    for kind,opt in config.get('survey_context',{}).get('youth_reference',{}).items():
        path=Path(opt['path']);sha=hashlib.sha256(path.read_bytes()).hexdigest();sid='youth2022_'+kind
        original=c.execute('SELECT fingerprint FROM ctx_survey_source WHERE source_id=?',(sid,)).fetchone()
        if not original or original[0]!=sha:raise ValueError('Youth original source not registered or changed')
        old=c.execute('SELECT sha256,method_version FROM ctx_youth_source WHERE source_id=?',(sid,)).fetchone()
        if old:
            if tuple(old)!=(sha,VERSION):raise ValueError('Youth detail correction requires explicit migration')
            continue
        sid,meta,rows=packet(kind,path)
        c.execute('INSERT INTO ctx_youth_source VALUES(?,?,?,?,?,?)',(sid,kind,2022,sha,VERSION,dump(meta)))
        c.executemany('INSERT INTO ctx_youth_metric VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',rows);count+=len(rows)
    return count
