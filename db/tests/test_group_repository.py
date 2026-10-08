import copy
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

import pandas as pd

from db.group_repository import AGE_COLS, aggregate_age, clean_frame, group_detail, catalogue
from db.group_workspace import review, explain, services


def sample():
    rows = []
    for month, x, value in [('202507', 1, 10), ('202507', 2, 90), ('202508', 1, 8), ('202508', 3, 1000)]:
        rows.append(dict(STD_YM=month, BLOCK_CD='1123065000001', X_COORD=x, Y_COORD=1,
                         **{col: value for col in AGE_COLS}))
    return pd.DataFrame(rows)


class GroupDataTest(unittest.TestCase):
    def setUp(self):
        self.context = dict(city='강남구', code='1123065', month='2025-08', age='30대', sex='남성')
        rows = aggregate_age(clean_frame(sample(), list(AGE_COLS), {'1123065'}), {'1123065': '역삼2동'})
        self.snapshot = dict(groups=rows, activity=[], note='고유 인원 아님', mapping='test', run_id='test', source_files={})

    def test_common_grid_comparison_does_not_follow_new_grid_spike(self):
        d = group_detail(self.context, self.snapshot)
        self.assertAlmostEqual(d['current']['change_pct'], -20)
        self.assertEqual(d['current']['matched_points'], 1)
        self.assertEqual(d['current']['points'], 2)
        self.assertEqual(d['current']['mean'], 504)
        self.assertAlmostEqual(sum(r['share'] for r in d['composition']), 100)
        self.assertFalse(d['telecomAvailable'])

    def test_missing_and_zero_baseline_do_not_become_zero_change(self):
        first = group_detail(self.context | {'month': '2025-07'}, self.snapshot)
        self.assertIsNone(first['current']['change_pct'])
        frame = sample(); frame.loc[frame.STD_YM == '202507', list(AGE_COLS)] = 0
        rows = aggregate_age(clean_frame(frame, list(AGE_COLS), {'1123065'}), {'1123065': '역삼2동'})
        self.assertIsNone(next(r for r in rows if r['month'] == '2025-08')['change_pct'])

    def test_duplicate_negative_and_unknown_code_rejected(self):
        for frame in [pd.concat([sample(), sample().iloc[:1]]), sample().assign(MAN_FLOW_POP_CNT_30G=-1), sample().assign(BLOCK_CD='1123099000')]:
            with self.assertRaises(ValueError): clean_frame(frame, list(AGE_COLS), {'1123065'})

    def test_scope_validation_and_no_mutation(self):
        for change in [{'sex': '전체'}, {'age': '35대'}, {'city': '춘천시'}, {'code': '1123066'}, {'month': '2027-01'}]:
            with self.assertRaises(ValueError): group_detail(self.context | change, self.snapshot)
        d = group_detail(self.context, self.snapshot); d['current']['value'] = -1
        self.assertGreater(group_detail(self.context, self.snapshot)['current']['value'], 0)

    def test_catalogue_periods_are_scoped_to_supported_city(self):
        snapshot = self.snapshot | dict(months=['2025-07', '2025-08'], districts=[dict(code='1123065', name='역삼2동')])
        self.assertEqual(catalogue('강남구', '2025-08', snapshot)['months'], snapshot['months'])
        unsupported = catalogue('춘천시', '2025-08', snapshot)
        self.assertEqual(unsupported['months'], [])
        self.assertEqual(unsupported['groups'], [])

    def test_chat_does_not_claim_telecom_or_eligibility(self):
        d = group_detail(self.context, self.snapshot)
        self.assertIn('아직 없습니다', explain(self.context, '통화 신호', d)['answer'])
        self.assertIn('20.00%', explain(self.context, '변화 요약', d)['answer'])
        self.assertIn('확정할 수 없습니다', explain(self.context, '서비스', d)['answer'])

    def test_reviews_are_separate_by_user_age_sex_and_month(self):
        with tempfile.TemporaryDirectory() as temp, patch('db.group_workspace.STORE', Path(temp) / 'reviews.sqlite3'):
            user = {'id': 'tester'}
            review(user, self.context, dict(note='남성 집단 메모', need='안부·상담', sourceRun='test'))
            self.assertEqual(review(user, self.context)['note'], '남성 집단 메모')
            for c in [self.context | {'sex': '여성'}, self.context | {'age': '40대'}, self.context | {'month': '2025-07'}]:
                self.assertEqual(review(user, c)['note'], '')
            self.assertEqual(review({'id': 'someone-else'}, self.context)['note'], '')

    def test_services_use_declared_need_not_assumed_demographic_eligibility(self):
        with patch('db.mission_store.service_candidates', return_value=[{'name': '상담 사업', 'service_id': 'a'}, {'name': '주거 사업', 'service_id': 'b'}]):
            result = services(self.context, '안부·상담')
            self.assertEqual(len(result['items']), 1)
            self.assertIn('원문 확인', result['items'][0]['qualification'])
            with self.assertRaises(ValueError): services(self.context, '')

    def test_service_purpose_does_not_match_family_relationship_requirements(self):
        with patch('db.mission_store.service_candidates', return_value=[
            {'name': '생활용품', 'service_id': 'a', 'eligibility_text': '가족관계 확인 및 상담'},
            {'name': '사회 참여 모임', 'service_id': 'b'},
        ]):
            self.assertEqual([x['service']['service_id'] for x in services(self.context, '관계·사회참여')['items']], ['b'])


if __name__ == '__main__': unittest.main()
