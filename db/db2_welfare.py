"""지자체 복지 API 저장소. 기존 DB2 테이블과 독립적인 추가 테이블만 사용한다."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

KST = timezone(timedelta(hours=9))
LOCK_ID = 15108347


class WelfareStore:
    def __init__(self, engine):
        self.engine = engine

    def initialize(self):
        sql = (Path(__file__).with_name("db2_welfare.sql")).read_text(encoding="utf-8")
        with self.engine.begin() as conn:
            conn.exec_driver_sql(sql)

    def start_run(self, scope, budget):
        run_id = str(uuid4())
        with self.engine.begin() as conn:
            conn.execute(text("""INSERT INTO db2.welfare_collection_runs
                (run_id, scope, daily_budget) VALUES (:id, :scope, :budget)"""),
                {"id": run_id, "scope": scope, "budget": budget})
        return run_id

    def finish_run(self, run_id, status, lists, details, errors, total, error=None):
        with self.engine.begin() as conn:
            conn.execute(text("""UPDATE db2.welfare_collection_runs SET
                finished_at=now(), status=:status, list_count=:lists,
                detail_count=:details, error_count=:errors, reported_total=:total,
                error_message=:error WHERE run_id=:id"""),
                dict(id=run_id, status=status, lists=lists, details=details,
                     errors=errors, total=total, error=error))

    def reserve_call(self, run_id, budget):
        """재시도와 실패 요청도 포함. 재실행해도 한국 날짜별 예산을 공유한다."""
        today = datetime.now(KST).date()
        with self.engine.begin() as conn:
            used = conn.execute(text("""INSERT INTO db2.welfare_api_daily_usage
                (usage_date, request_count) VALUES (:day, 1)
                ON CONFLICT (usage_date) DO UPDATE SET
                request_count=db2.welfare_api_daily_usage.request_count+1
                WHERE db2.welfare_api_daily_usage.request_count < :budget
                RETURNING request_count"""), {"day": today, "budget": budget}).scalar()
            if used is None:
                return False
            conn.execute(text("""UPDATE db2.welfare_collection_runs
                SET request_count=request_count+1 WHERE run_id=:id"""), {"id": run_id})
        return True

    def save_list(self, run_id, items, raw_xml):
        with self.engine.begin() as conn:
            self._snapshot(conn, run_id, "list", None, raw_xml)
            for item in items:
                conn.execute(text("""INSERT INTO db2.local_welfare_services
                    (service_id, name, province, district, summary, source_url,
                     source_modified, list_payload, detail_pending)
                    VALUES (:id,:name,:province,:district,:summary,:url,:modified,
                            CAST(:payload AS jsonb), true)
                    ON CONFLICT (service_id) DO UPDATE SET
                    name=EXCLUDED.name, province=EXCLUDED.province,
                    district=EXCLUDED.district, summary=EXCLUDED.summary,
                    source_url=EXCLUDED.source_url, source_modified=EXCLUDED.source_modified,
                    list_payload=EXCLUDED.list_payload, last_seen_at=now(),
                    detail_pending=db2.local_welfare_services.detail_pending OR
                        db2.local_welfare_services.source_modified IS DISTINCT FROM EXCLUDED.source_modified OR
                        (db2.local_welfare_services.list_payload - 'inqNum') IS DISTINCT FROM (EXCLUDED.list_payload - 'inqNum')
                    """), dict(id=item["servId"], name=item["servNm"],
                        province=item.get("ctpvNm"), district=item.get("sggNm"),
                        summary=item.get("servDgst"), url=item.get("servDtlLink"),
                        modified=item.get("lastModYmd"), payload=json.dumps(item, ensure_ascii=False)))

    def candidates(self, province, district, refresh_days, limit):
        with self.engine.connect() as conn:
            return conn.execute(text("""SELECT service_id FROM db2.local_welfare_services
                WHERE (:province='' OR province=:province)
                  AND (:district='' OR district=:district)
                  AND (detail_pending OR detail_checked_at IS NULL OR
                       detail_checked_at < now() - make_interval(days => :days))
                ORDER BY detail_pending DESC, detail_attempted_at NULLS FIRST,
                         service_id LIMIT :limit"""),
                dict(province=province, district=district, days=refresh_days, limit=limit)).scalars().all()

    def save_detail(self, run_id, service_id, payload, raw_xml, dates):
        with self.engine.begin() as conn:
            self._snapshot(conn, run_id, "detail", service_id, raw_xml)
            conn.execute(text("""UPDATE db2.local_welfare_services SET
                target_text=:target, eligibility_text=:criteria, benefit_text=:benefit,
                application_text=:application, effective_start=:start, effective_end=:end,
                detail_payload=CAST(:payload AS jsonb), detail_pending=false,
                detail_checked_at=now(), detail_attempted_at=now(), detail_error=NULL
                WHERE service_id=:id"""), dict(id=service_id,
                target=payload.get("sprtTrgtCn"), criteria=payload.get("slctCritCn"),
                benefit=payload.get("alwServCn"), application=payload.get("aplyMtdCn"),
                start=dates[0], end=dates[1], payload=json.dumps(payload, ensure_ascii=False)))

    def detail_failed(self, service_id, error):
        with self.engine.begin() as conn:
            conn.execute(text("""UPDATE db2.local_welfare_services SET
                detail_attempted_at=now(), detail_pending=true, detail_error=:error
                WHERE service_id=:id"""), dict(id=service_id, error=error))

    @staticmethod
    def _snapshot(conn, run_id, kind, service_id, raw_xml):
        conn.execute(text("""INSERT INTO db2.welfare_api_snapshots
            (run_id, operation, service_id, response_xml)
            VALUES (:run,:kind,:id,:xml)"""), dict(run=run_id, kind=kind, id=service_id, xml=raw_xml))
