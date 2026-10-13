import unittest
from contextlib import closing
from pathlib import Path
import tempfile
import sqlite3
import numpy as np
import pandas as pd
from age_detection import CORE,DISTANCE,BANDS,DEFAULT,SCHEMA,pipeline,historical_z,commit,records,canonical,add_context


def synthetic(months=48):
    rng=np.random.default_rng(729)
    dates=pd.date_range('2022-01-01',periods=months,freq='MS')
    rows=[]
    for dong in range(22):
        for age in BANDS:
            increments=rng.normal(0,.01,(months,6))
            levels=np.exp(np.cumsum(increments,axis=0))*np.array([30,15,25,10,100,80])
            for pos,date in enumerate(dates):
                row={'date':date,'행정동코드':1123000+dong,'행정동':f'dong{dong}', 'age_scheme':'service','age_band':age,
                     'total_population':2000,'interest_one_person_population':500,'interest_structural_issue':False,
                     'comm_low_rate':.05,'weekday_outing_low_rate':.1,'weekend_outing_low_rate':.1}
                for metric,value in zip(CORE+DISTANCE,levels[pos]):
                    row[metric]=value;row[metric+'_valid_population']=1900
                rows.append(row)
    return pd.DataFrame(rows)


class AgeDetectionTests(unittest.TestCase):
    def test_shock_localized_to_dong_and_age_with_evidence(self):
        f=synthetic()
        target=f.행정동코드.eq(1123000)&f.age_band.eq('20s')&f.date.ge(pd.Timestamp('2025-07-01'))
        f.loc[target,CORE+DISTANCE]*=.4
        f.loc[target,'comm_low_rate']=.15;f.loc[target,'weekday_outing_low_rate']=.2
        result,_,_,_=pipeline(f)
        july=result.loc[result.date.eq(pd.Timestamp('2025-07-01'))]
        row=july.loc[july.행정동코드.eq(1123000)&july.age_band.eq('20s')].iloc[0]
        self.assertTrue(row.combined_signal)
        self.assertEqual(row.evidence_level,'joint_candidate_with_supporting_evidence')
        self.assertEqual(row.signal_status,'New')
        other=july.loc[july.행정동코드.eq(1123000)&july.age_band.eq('30s')].iloc[0]
        self.assertFalse(other.combined_signal)

    def test_future_changes_do_not_change_past_or_model(self):
        f=synthetic()
        first,common,calib,model=pipeline(f)
        changed=f.copy();changed.loc[changed.date.ge(pd.Timestamp('2025-11-01')),CORE+DISTANCE]*=.01
        second,common2,calib2,model2=pipeline(changed)
        pd.testing.assert_frame_equal(first.loc[first.date.lt(pd.Timestamp('2025-11-01'))],second.loc[second.date.lt(pd.Timestamp('2025-11-01'))])
        pd.testing.assert_frame_equal(calib,calib2)
        self.assertEqual(model,model2)

    def test_age_common_decline_not_removed_from_absolute_track(self):
        f=synthetic();mask=f.age_band.eq('40s')&f.date.ge(pd.Timestamp('2025-07-01'))
        f.loc[mask,CORE+DISTANCE]*=.35
        result,common,_,_=pipeline(f)
        g=result.loc[result.age_band.eq('40s')&result.date.eq(pd.Timestamp('2025-07-01'))]
        self.assertTrue(g.combined_absolute_signal.all())
        c=common.loc[common.age_band.eq('40s')&common.date.eq(pd.Timestamp('2025-07-01'))].iloc[0]
        self.assertTrue(c.combined_common_signal)

    def test_invalid_mobility_does_not_disable_communication(self):
        f=synthetic();mask=f.행정동코드.eq(1123000)&f.age_band.eq('20s')&f.date.eq(pd.Timestamp('2025-07-01'))
        f.loc[mask,CORE[:2]]*=.3
        f.loc[mask,'weekend_move_count_valid_population']=0
        result,_,_,_=pipeline(f)
        row=result.loc[result.행정동코드.eq(1123000)&result.age_band.eq('20s')&result.date.eq(pd.Timestamp('2025-07-01'))].iloc[0]
        self.assertTrue(row.communication_signal)
        self.assertTrue(pd.isna(row.mobility_signal))
        self.assertEqual(row.assessment_status,'partially_assessed')

    def test_structural_interest_not_used_as_zero_risk(self):
        f=synthetic();mask=f.행정동코드.eq(1123000)&f.age_band.eq('20s')&f.date.ge(pd.Timestamp('2025-07-01'))
        f.loc[mask,CORE+DISTANCE]*=.4;f.loc[mask,'interest_structural_issue']=True
        result,_,_,_=pipeline(f)
        row=result.loc[result.행정동코드.eq(1123000)&result.age_band.eq('20s')&result.date.eq(pd.Timestamp('2025-07-01'))].iloc[0]
        self.assertTrue(row.combined_signal)
        self.assertTrue(pd.isna(row.interest_support))
        self.assertIn('interest_evidence_unavailable',row.review_reasons)

    def test_zero_mad_does_not_manufacture_scores(self):
        score,count,_,_=historical_z([0.]*15+[-2.],12,.6745)
        self.assertTrue(np.isnan(score[-1]));self.assertEqual(count[-1],15)

    def test_relative_slow_growth_is_not_actual_decline(self):
        f=synthetic();stream=f.date.ge(pd.Timestamp('2025-07-01'))
        f.loc[stream,CORE+DISTANCE]*=5
        target=f.행정동코드.eq(1123000)&f.age_band.eq('20s')&stream
        f.loc[target,CORE+DISTANCE]/=4
        result,_,_,_=pipeline(f)
        row=result.loc[result.행정동코드.eq(1123000)&result.age_band.eq('20s')&result.date.eq(pd.Timestamp('2025-07-01'))].iloc[0]
        self.assertFalse(row.any_signal)

    def test_new_month_preserves_baseline_and_previous_results(self):
        f=synthetic();previous,_,_,model=pipeline(f)
        january=f.loc[f.date.eq(pd.Timestamp('2025-12-01'))].copy()
        january['date']=pd.Timestamp('2026-01-01')
        january[CORE+DISTANCE]*=.99
        current,common,_,new_model=pipeline(pd.concat([f,january],ignore_index=True))
        pd.testing.assert_frame_equal(previous.reset_index(drop=True),current.loc[current.date.lt(pd.Timestamp('2026-01-01'))].reset_index(drop=True))
        self.assertEqual(model,new_model)
        self.assertEqual(len(current.loc[current.date.eq(pd.Timestamp('2026-01-01'))]),110)

    def test_foreign_key_storage_of_new_month(self):
        f=synthetic()
        result,common,_,model=pipeline(f)
        january=f.loc[f.date.eq(pd.Timestamp('2025-12-01'))].copy();january['date']=pd.Timestamp('2026-01-01')
        new,common2,_,model2=pipeline(pd.concat([f,january],ignore_index=True))
        with tempfile.TemporaryDirectory() as d:
            with closing(sqlite3.connect(Path(d)/'test.sqlite')) as con,con:
                con.execute('PRAGMA foreign_keys=ON')
                con.execute('CREATE TABLE a2_age_feature (adm_cd TEXT,date TEXT,age_scheme TEXT,age_band TEXT,PRIMARY KEY(adm_cd,date,age_scheme,age_band))')
                for row in records(pd.concat([f,january],ignore_index=True)):
                    con.execute('INSERT INTO a2_age_feature VALUES (?,?,?,?)',(str(row['행정동코드']),pd.Timestamp(row['date']).strftime('%Y-%m-%d'),row['age_scheme'],row['age_band']))
                con.executescript(SCHEMA)
                self.assertEqual(commit(con,result.loc[result.date.ge(pd.Timestamp('2025-07-01'))],common.loc[common.date.ge(pd.Timestamp('2025-07-01'))],model),660)
                self.assertEqual(commit(con,new.loc[new.date.ge(pd.Timestamp('2025-07-01'))],common2.loc[common2.date.ge(pd.Timestamp('2025-07-01'))],model2),110)
                self.assertEqual(con.execute('SELECT COUNT(*) FROM a2_age_detection').fetchone()[0],770)
                self.assertFalse(con.execute('PRAGMA foreign_key_check').fetchall())

    def test_later_context_update_does_not_rewrite_saved_context(self):
        with closing(sqlite3.connect(':memory:')) as con:
            con.executescript(SCHEMA)
            con.execute('CREATE TABLE a1_context (adm_cd TEXT,period TEXT,effective_from TEXT,cluster INTEGER,cluster_type TEXT)')
            con.execute("INSERT INTO a1_context VALUES ('1123000','2025H2','2025-07-01',1,'original')")
            frame=pd.DataFrame([{'date':pd.Timestamp('2025-07-01'),'행정동코드':1123000,'age_band':'20s'}])
            first=add_context(con,frame,'m')
            con.execute('INSERT INTO a2_age_detection VALUES (?,?,?,?,?,?,?,?,?,?,?)',('1123000','2025-07-01','service','20s','m','assessed',0,0,0,0,canonical(records(first)[0])))
            con.execute("UPDATE a1_context SET cluster_type='revised'")
            second=add_context(con,frame,'m')
            self.assertEqual(second.a1_cluster_type.iloc[0],'original')

    def test_duplicate_and_missing_month_rejected(self):
        f=synthetic()
        for changed in [pd.concat([f,f.iloc[:1]]),f.loc[f.date.ne(pd.Timestamp('2023-01-01'))]]:
            with self.assertRaises(ValueError):pipeline(changed)

    def test_idempotency_and_result_revision_block(self):
        result,common,_,model=pipeline(synthetic())
        result=result.loc[result.date.ge(pd.Timestamp(DEFAULT['detection_start']))].copy()
        common=common.loc[common.date.ge(pd.Timestamp(DEFAULT['detection_start']))].copy()
        with tempfile.TemporaryDirectory() as d:
            with closing(sqlite3.connect(Path(d)/'test.sqlite')) as con,con:
                con.executescript(SCHEMA)
                self.assertEqual(commit(con,result,common,model),660)
                self.assertEqual(commit(con,result,common,model),0)
                changed=result.copy();changed.iloc[0,changed.columns.get_loc('review_reasons')]='changed'
                with self.assertRaises(ValueError):commit(con,changed,common,model)


if __name__=='__main__':unittest.main()
