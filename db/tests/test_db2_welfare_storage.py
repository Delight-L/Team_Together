"""RUN_DB2_TESTS=1일 때 실제 PostgreSQL에서 실행하고 모든 테스트 행을 롤백한다."""
import os
import unittest
from contextlib import nullcontext
from uuid import uuid4

from sqlalchemy import text

from db.db2_welfare import WelfareStore


@unittest.skipUnless(os.getenv('RUN_DB2_TESTS') == '1', 'PostgreSQL 통합 검증은 opt-in')
class StorageTests(unittest.TestCase):
    def test_upsert_snapshots_changes_and_daily_quota(self):
        from db.connection import engine
        with engine.connect() as conn:
            transaction = conn.begin()
            class TransactionEngine:
                def begin(self):
                    return nullcontext(conn)

                def connect(self):
                    return nullcontext(conn)

            store = WelfareStore(TransactionEngine())
            try:
                service_id = 'test-' + str(uuid4())
                run = store.start_run('test', 900)
                item = dict(servId=service_id, servNm='테스트 복지', ctpvNm='테스트시',
                            sggNm='테스트구', lastModYmd='20261007', inqNum='1')
                store.save_list(run, [item], '<test-list/>')
                store.save_detail(run, service_id, dict(sprtTrgtCn='대상'), '<test-detail/>', (None,None))
                item['inqNum'] = '2'
                store.save_list(run, [item], '<test-list/>')
                row = conn.execute(text('SELECT detail_pending, target_text FROM db2.local_welfare_services WHERE service_id=:id'), {'id':service_id}).one()
                self.assertEqual(tuple(row), (False,'대상'))
                item['lastModYmd'] = '20261008'
                store.save_list(run, [item], '<changed-list/>')
                row = conn.execute(text('SELECT detail_pending, target_text FROM db2.local_welfare_services WHERE service_id=:id'), {'id':service_id}).one()
                self.assertEqual(tuple(row), (True,'대상'))
                self.assertIn(service_id, store.candidates('테스트시','테스트구',7,100))
                self.assertEqual(conn.execute(text('SELECT count(*) FROM db2.welfare_api_snapshots WHERE run_id=:run'), {'run':run}).scalar_one(),4)
                # 오늘 사용량은 테스트 트랜잭션 안에서만 재설정되고 아래에서 롤백된다.
                conn.execute(text("DELETE FROM db2.welfare_api_daily_usage WHERE usage_date=(now() AT TIME ZONE 'Asia/Seoul')::date"))
                self.assertTrue(store.reserve_call(run,2))
                self.assertTrue(store.reserve_call(run,2))
                self.assertFalse(store.reserve_call(run,2))
                self.assertEqual(conn.execute(text('SELECT request_count FROM db2.welfare_collection_runs WHERE run_id=:run'), {'run':run}).scalar_one(),2)
                store.finish_run(run,'completed',1,1,0,1)
            finally:
                transaction.rollback()


if __name__ == '__main__':
    unittest.main()
