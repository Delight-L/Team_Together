"""Db1Repository 계약 테스트 묶음. 구현에 묶이지 않도록 mixin으로 정의하고, 구현(PostgreSQL)은 test_pg_repository.py에서
`unittest.TestCase`와 함께 상속해 실행합니다. 합성 SQLite(db1_fixture)를 게시한 PostgreSQL을 대상으로 합니다.

- ContractCases     : 계약대로 조회하는가 (상태·범위·동 이름·신호·연령·지역 유형·소비·조회 순서·모든 질문 유형)
- EquivalenceCases  : 조건 내리기·동별 인덱스가 «전체를 읽어 거르는 예전 방식»과 같은 결과인가
- CacheCases        : 반환값을 바꿔도 캐시가 오염되지 않는가, close가 안전한가
- SqlStaysInsideRepositoryTest : 챗봇 로직에 SQL이 새지 않는가(소스 검사)

mixin을 쓰는 클래스가 `repo`(저장소), `path`(합성 SQLite 경로), `make_repo()`(새 저장소)를 제공합니다.
"""
import ast
import unittest

from backend.bomi.adapters.v16 import V16_ROOT  # sys.path에 v16 루트를 올립니다

from chatbot_agent.pg_repository import PostgresDb1Repository  # noqa: E402
from chatbot_agent.repository import SqlDb1Repository  # noqa: E402
from chatbot_agent.db1_repository import Db1Repository  # noqa: E402
from chatbot_agent.schemas import QueryIntent  # noqa: E402
from chatbot_agent.query_service import execute  # noqa: E402

ENGINE_DIR = V16_ROOT / 'chatbot_agent'


class ContractCases:
    def test_status_and_ranges(self):
        self.assertTrue(self.repo.has_data())
        self.assertEqual(self.repo.available_period(), ('2025-07', '2025-10'))
        self.assertEqual(self.repo.consumption_period(), ('2025-04', '2025-09'))
        status = self.repo.pipeline_status()
        self.assertEqual(status['history_end'][:7], '2025-10')
        self.assertEqual(status['detection_rows'], 12)
        self.assertEqual(status['waiting_for'], {'month': '2025-11'})

    def test_district_names_and_codes_use_alias(self):
        self.assertEqual(self.repo.districts(), {'삼성1동', '역삼1동', '개포3동'})  # 1123074 일원2동 → 개포3동
        self.assertEqual(self.repo.district_codes()['삼성1동'], '1123051')
        self.assertIn('개포3동', self.repo.district_codes())

    def test_activity_signals_and_anomalies(self):
        frame = self.repo.activity('삼성1동', '2025-07', '2025-10')
        self.assertEqual(list(frame['date']), ['2025-07-01', '2025-08-01', '2025-09-01', '2025-10-01'])
        signals = self.repo.signals('2025-07', '2025-10')
        self.assertEqual(sorted(zip(signals['date'], signals['행정동'])),
                         [('2025-08-01', '삼성1동'), ('2025-10-01', '삼성1동')])
        mobility = self.repo.signals('2025-07', '2025-10', None, 'mobility')
        self.assertEqual(list(mobility['date']), ['2025-10-01'])
        ranked, column = self.repo.anomalies('2025-07', '2025-10', 'weekday_move_count')
        self.assertEqual(column, 'weekday_move_count_residual_change_expanding_rz')
        self.assertEqual(ranked.iloc[0]['행정동'], '삼성1동')
        with self.assertRaises(ValueError):
            self.repo.anomalies(metric='unknown')

    def test_age_band_reads_age_detection(self):
        frame = self.repo.activity('삼성1동', '2025-08', '2025-08', '60plus')
        self.assertEqual(len(frame), 1)
        self.assertTrue(bool(frame.iloc[0]['consecutive_signal']))

    def test_context_respects_effective_date(self):
        found = self.repo.context('역삼1동', '2025-09-01')
        self.assertEqual(found.iloc[0]['period'], '2025H2')
        self.assertTrue(found.iloc[0]['retrospective_context'])
        self.assertTrue(self.repo.context('역삼1동', '2025-01-01').empty)  # 효력 시작 전

    def test_consumption_evidence_and_payloads(self):
        rows, shared = self.repo.consumption_evidence(('삼성1동',), '2025-07', '2025-09', None)
        self.assertEqual([r['period'] for r in rows], ['2025Q3'])  # 같은 분기는 한 번만
        self.assertEqual(sorted(shared), ['2025-07', '2025-08', '2025-09'])
        rows, shared = self.repo.consumption_evidence(('삼성1동',), '2025-07', '2025-07', '20s')
        self.assertEqual([row['domain'] for row in rows], ['교육', '음식'])
        self.assertEqual(list(shared), [('2025-07', '음식')])
        self.assertEqual(len(self.repo.consumption_payloads('a3a_feature')), 6)
        with self.assertRaises(ValueError):
            self.repo.consumption_payloads('a2_detection; DROP TABLE x')  # 허용 목록 밖은 거부

    def test_multi_row_lookups_are_ordered_by_key_not_by_storage(self):
        """저장 순서(음식 먼저)와 기본키 순서(교육 먼저)가 다른 자료에서도 행 순서는 기본키 순서여야 합니다.
        SQLite는 기본키 색인으로, PostgreSQL은 저장 순서로 돌려주므로 ORDER BY가 없으면 두 저장소의 출력이 달라집니다."""
        rows, _ = self.repo.consumption_evidence(('삼성1동',), '2025-07', '2025-07', '20s')
        self.assertEqual([row['domain'] for row in rows], ['교육', '음식'])
        supplements = self.repo.supplements(['삼성1동'], ['2025-10-01'], '20s')  # 관측기간이 2025Q3인 기준월
        self.assertEqual([row['domain'] for row in supplements['analysis3_dong']], ['교육', '음식'])

    def test_every_question_type_runs_against_the_contract(self):
        kinds = ['signals', 'reason', 'activity', 'context', 'support', 'consumption', 'anomaly', 'previous', 'data_status']
        for kind in kinds:
            intent = QueryIntent('track_change', kind, dong='삼성1동', dongs=('삼성1동',),
                                 start_month='2025-08', end_month='2025-09', metric='weekday_move_count')
            evidence = execute(self.repo, intent)
            self.assertTrue(evidence.title, kind)


class EquivalenceCases:
    @staticmethod
    def reference(repo, dong, start, end, band):
        """예전 activity(): 전체 표에서 기간 마스크 → 동 비교 → 정렬."""
        f = repo._period(repo._read('detection', band), start, end)
        if dong:
            f = f.loc[f['행정동'].eq(dong)]
        return f.sort_values(['date', '행정동'])

    def test_activity_matches_reference_for_many_filters(self):
        import itertools
        import pandas.testing as pdt
        dongs = [None, '삼성1동', '역삼1동', '개포3동', '없는동']
        periods = [(None, None), ('2025-08', '2025-08'), ('2025-07', '2025-09'), ('2025-09', None), (None, '2025-08'),
                   ('2025-08-01', '2025-08-01'), ('2025-10', '2025-07'), ('2026-01', '2026-02')]
        bands = [None, '20s', '60plus']
        for dong, (start, end), band in itertools.product(dongs, periods, bands):
            expected = self.reference(self.repo, dong, start, end, band)
            actual = self.repo.activity(dong, start, end, band)
            with self.subTest(dong=dong, start=start, end=end, band=band):
                pdt.assert_frame_equal(actual, expected)

    def test_consumption_filters_equal_filtering_after_a_full_read(self):
        everything = {table: self.repo.consumption_payloads(table) for table in SqlDb1Repository.CONSUMPTION_TABLES}
        codes = [self.repo.district_codes()['삼성1동']]
        cases = [
            ('a3a_feature', dict(periods=['2025Q3'], adm_cds=codes, ages=['20대']),
             lambda r: r['period'] == '2025Q3' and r['adm_cd'] in codes and r['age'] == '20대'),
            ('a3a_comparison', dict(periods=['2025Q2', '2025Q3']), lambda r: r['period'] in {'2025Q2', '2025Q3'}),
            ('a3b_feature', dict(periods=['2025-07', '2025-08'], districts=['11680'], ages=['20대']),
             lambda r: r['period'] in {'2025-07', '2025-08'} and r['district'] == '11680' and r['age'] == '20대'),
        ]
        for table, filters, keep in cases:
            expected = sorted((r for r in everything[table] if keep(r)), key=repr)
            actual = sorted(self.repo.consumption_payloads(table, **filters), key=repr)
            with self.subTest(table=table):
                self.assertEqual(actual, expected)
                self.assertTrue(actual)

    def test_empty_condition_means_no_rows_and_bad_condition_is_rejected(self):
        self.assertEqual(self.repo.consumption_payloads('a3a_feature', adm_cds=[]), [])
        self.assertEqual(self.repo.consumption_payloads('a3a_feature', periods=[]), [])
        with self.assertRaises(ValueError):
            self.repo.consumption_payloads('a3a_feature', districts=['11680'])  # 이 테이블에 없는 조건
        with self.assertRaises(ValueError):
            self.repo.consumption_payloads('a3b_feature', adm_cds=['1123051'])
        self.assertEqual(len(self.repo.consumption_payloads('a3a_feature', periods=[f'P{i}' for i in range(600)])), 6)  # 너무 긴 목록은 조건 생략(결과는 같음)


class CacheCases:
    def test_returned_frames_do_not_corrupt_the_cache(self):
        repo = self.make_repo()
        first = repo.activity('삼성1동', '2025-07', '2025-10')
        before = first['call_contacts'].tolist()
        first['call_contacts'] = -1.0
        first.loc[:, '행정동'] = '변조'
        again = repo.activity('삼성1동', '2025-07', '2025-10')
        repo.close()
        self.assertEqual(again['call_contacts'].tolist(), before)
        self.assertEqual(set(again['행정동']), {'삼성1동'})

    def test_returned_collections_do_not_corrupt_the_cache(self):
        repo = self.make_repo()
        repo.districts().add('변조')
        repo.district_codes()['변조'] = 'x'
        repo.consumption_payloads('a3a_feature')[0]['period'] = '변조'
        self.assertNotIn('변조', repo.districts())
        self.assertNotIn('변조', repo.district_codes())
        self.assertNotEqual(repo.consumption_payloads('a3a_feature')[0]['period'], '변조')
        repo.close()

    def test_close_is_safe_and_reopens(self):
        repo = self.make_repo()
        repo.close()
        repo.close()
        self.assertEqual(repo.available_period(), ('2025-07', '2025-10'))
        repo.close()


class SqlStaysInsideRepositoryTest(unittest.TestCase):
    """챗봇 로직이 SQL·연결을 직접 쓰지 않는지 소스로 확인합니다(구현 파일 repository.py·pg_repository.py만 예외)."""

    def test_no_sql_outside_the_repository(self):
        offenders = []
        for path in ENGINE_DIR.glob('*.py'):
            if path.name in {'repository.py', 'pg_repository.py', 'db1_repository.py'}:  # 저장소 구현과 계약
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(a.name.split('.')[0] == 'sqlite3' for a in node.names):
                    offenders.append(f'{path.name}: import sqlite3')
                if isinstance(node, ast.Attribute) and node.attr in {'connection', 'execute'} and \
                        isinstance(node.value, ast.Name) and node.value.id in {'repo', 'c', 'connection'}:
                    offenders.append(f'{path.name}:{node.lineno} {node.value.id}.{node.attr}')
                if isinstance(node, ast.Constant) and isinstance(node.value, str) and \
                        node.value.lstrip().upper().startswith(('SELECT ', 'INSERT ', 'UPDATE ')):
                    offenders.append(f'{path.name}:{node.lineno} SQL 문자열')
        self.assertEqual(offenders, [])

    def test_repository_implements_every_contract_method(self):
        contract = {name for name in dir(Db1Repository) if not name.startswith('_')}
        missing = [name for name in contract if not callable(getattr(PostgresDb1Repository, name, None))]
        self.assertEqual(missing, [])


if __name__ == '__main__':
    unittest.main()

