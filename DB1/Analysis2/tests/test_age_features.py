import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
import numpy as np
import pandas as pd
from age_features import AGES, MOVE, INTEREST, build_age_frames, raw_check, persist, reconcile
from preprocessing.monthly_features import build_month_feature_frames


def fixtures():
    telecom = []
    interest = []
    for dong in range(22):
        for sex in [1, 2]:
            for age in AGES:
                population = 100 + age + sex + dong
                row = {'행정동코드': 1168000 + dong, '행정동': f'dong{dong}', '자치구': '강남구', '성별': sex, '연령대': age, '총인구수': population, '1인가구수': 50, '평균 통화대상자 수': age/10 + sex, '평균 문자대상자 수': age/20 + sex}
                for j, (_, value, missing) in enumerate(MOVE):
                    row[value] = age * (j+1) / 5
                    row[missing] = j + sex
                telecom.append(row)
                interest.append({'행정동코드': row['행정동코드'], '행정동명': row['행정동'], '자치구': '강남구', '성별': sex, '연령대': age, '1인가구수': 50, **{c: sex + age/10 for c in INTEREST}})
    rain = pd.DataFrame({'항목': ['강수량 (㎜)', '강수일수 (일)'], '2022. 01': [10, 2]})
    diary = pd.DataFrame({'시점': ['2022. 01'], '눈': ['-']})
    return pd.DataFrame(telecom), pd.DataFrame(interest), rain, diary


class AgeFeatureTests(unittest.TestCase):
    def test_weighted_rollup_and_age_grid(self):
        t, i, r, d = fixtures()
        age, _, _ = build_age_frames(t, i, r, d, 2022, 1)
        self.assertEqual(len(age), 374)
        self.assertEqual(len(age.loc[age.age_scheme.eq('service')]), 110)
        self.assertFalse(age.duplicated(['date', '행정동코드', 'age_scheme', 'age_band']).any())
        reconcile(age, build_month_feature_frames(t, i, r, d, 2022, 1))
        g = t.loc[t.행정동코드.eq(1168000) & t.연령대.lt(30)]
        expected = np.average(g['평균 통화대상자 수'], weights=g['총인구수'])
        observed = age.loc[age.age_scheme.eq('service') & age.age_band.eq('20s') & age.행정동코드.eq(1168000), 'call_contacts'].iloc[0]
        self.assertAlmostEqual(expected, observed)

    def test_duplicate_and_missing_age_rejected(self):
        t, _, _, _ = fixtures()
        for invalid in [t.iloc[1:], pd.concat([t, t.iloc[:1]])]:
            with self.assertRaises(ValueError): raw_check(invalid, 'telecom')

    def test_invalid_missing_population_rejected(self):
        t, _, _, _ = fixtures()
        t.loc[0, MOVE[0][2]] = t.loc[0, '총인구수'] + 1
        with self.assertRaises(ValueError): raw_check(t, 'telecom')

    def test_no_valid_mobility_marks_review(self):
        t, i, r, d = fixtures()
        t.loc[t.연령대.lt(30), MOVE[0][2]] = t.loc[t.연령대.lt(30), '총인구수']
        age, _, _ = build_age_frames(t, i, r, d, 2022, 1)
        g = age.loc[age.age_scheme.eq('service') & age.age_band.eq('20s')]
        self.assertTrue(g.weekday_move_count.isna().all())
        self.assertTrue(g.quality_status.eq('review_required').all())

    def test_idempotency_revision_block_and_no_gap(self):
        t, i, r, d = fixtures()
        age, t, i = build_age_frames(t, i, r, d, 2022, 1)
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory)/'test.sqlite'
            self.assertTrue(persist(db, age, t, i, {}))
            self.assertFalse(persist(db, age, t, i, {}))
            revised_weather = age.copy(); revised_weather['rain_days'] += 1
            with self.assertRaises(ValueError): persist(db, revised_weather, t, i, {})
            t.loc[0, '평균 통화대상자 수'] += 1
            with self.assertRaises(ValueError): persist(db, age, t, i, {})
            future = age.copy(); future['date'] = pd.Timestamp('2022-03-01')
            with self.assertRaises(ValueError): persist(db, future, t, i, {})
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM a2_age_feature').fetchone()[0], 374)
                self.assertEqual(con.execute('SELECT COUNT(*) FROM a2_age_raw').fetchone()[0], 1056)
            t.loc[0, '평균 통화대상자 수'] -= 1
            next_month = age.copy(); next_month['date'] = pd.Timestamp('2022-02-01')
            self.assertTrue(persist(db, next_month, t, i, {}))
            self.assertFalse(persist(db, next_month, t, i, {}))
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM a2_age_feature').fetchone()[0], 748)
                self.assertEqual(con.execute('SELECT MAX(date) FROM a2_age_source').fetchone()[0], '2022-02-01')


if __name__ == '__main__': unittest.main()
