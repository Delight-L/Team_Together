"""임시 SQLite로 적재의 원본 보존·중복 방지·롤백·DB 기반 대화를 검증합니다."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.exc import IntegrityError

from backend.db import welfare_chatbot_repository as repository


class WelfareChatbotRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://").execution_options(schema_translate_map={"db2": None})
        self.addCleanup(self.engine.dispose)
        from backend.chatbot.welfare.app.dialogue import resources
        # 사업 목록은 1분간 기억하므로 테스트마다 비우고 시작·종료합니다.
        resources.clear_cache()
        self.addCleanup(resources.clear_cache)
        self.candidates = json.loads((repository.DATA_DIR / "policy_candidates.json").read_text(encoding="utf-8"))
        self.plans = json.loads((repository.DATA_DIR / "gangnam_policy_plans_2025.json").read_text(encoding="utf-8"))

    def test_lossless_roundtrip_and_repeat_import(self):
        expected = {"candidates": len(self.candidates["records"]), "plans": len(self.plans)}
        self.assertEqual(repository.import_json(engine=self.engine), expected)
        self.assertEqual(repository.import_json(engine=self.engine), expected)
        candidate_rows, plan_rows = repository.load_dataset_rows(engine=self.engine)
        self.assertEqual(candidate_rows, self.candidates["records"])
        self.assertEqual(plan_rows, list(enumerate(self.plans)))
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(select(func.count()).select_from(repository.candidates)).scalar_one(), expected["candidates"])
            self.assertEqual(conn.execute(select(func.count()).select_from(repository.plans)).scalar_one(), expected["plans"])
            header = conn.execute(select(repository.datasets).where(repository.datasets.c.dataset_key == "candidates")).mappings().one()
        self.assertEqual(header["document_metadata"], {k: v for k, v in self.candidates.items() if k != "records"})
        self.assertEqual(len(header["sha256"]), 64)
        self.assertIsNotNone(header["imported_at"])

    def test_database_edits_reach_search_and_agent_without_json_reads(self):
        repository.import_json(engine=self.engine)
        from backend.chatbot.welfare.app.dialogue import resources
        from backend.chatbot.welfare.service import stream_reply
        from backend.agents.supervisor import rule_route
        with self.engine.begin() as conn:
            conn.execute(update(repository.plans).where(repository.plans.c.plan_index == 0).values(
                agency="DB에서 수정한 담당 기관", procedure="DB에서 수정한 확인 절차"))
        with patch.dict("os.environ", {"WELFIND_WELFARE_SOURCE": "db"}), \
                patch.object(repository, "get_engine", return_value=self.engine), \
                patch.object(Path, "read_text", side_effect=AssertionError("JSON을 읽으면 안 됩니다.")):
            records = resources.search("세곡동행의 신청 방법은?", city="강남구")
            self.assertEqual(records[0]["agency"], "DB에서 수정한 담당 기관")
            self.assertEqual(rule_route("세곡동행", {"city": "강남구"}), "welfare")
            events = list(stream_reply([{"role": "user", "content": "세곡동행의 신청 방법은?"}],
                                       {"city": "강남구"}, use_ai=False))
        answer = "".join(value.get("text", "") for event, value in events if event == "token")
        self.assertIn("DB에서 수정한 담당 기관", answer)
        self.assertIn("DB에서 수정한 확인 절차", answer)
        self.assertEqual(events[-1][0], "done")

    def test_resources_are_read_once_per_cache_window(self):
        repository.import_json(engine=self.engine)
        from backend.chatbot.welfare.app.dialogue import resources
        with patch.dict("os.environ", {"WELFIND_WELFARE_SOURCE": "db"}), \
                patch.object(repository, "get_engine", return_value=self.engine), \
                patch.object(resources, "load_dataset_rows", wraps=repository.load_dataset_rows) as reads:
            first = resources.load_resources()
            first[0]["name"] = "호출한 쪽에서 고친 이름"
            resources.search("세곡동행", city="강남구")
            self.assertNotEqual(resources.load_resources()[0]["name"], "호출한 쪽에서 고친 이름")
            self.assertEqual(reads.call_count, 1)
            with patch.object(resources.time, "monotonic", return_value=resources.time.monotonic() + resources.CACHE_SECONDS + 1):
                resources.load_resources()
            self.assertEqual(reads.call_count, 2)

    def test_failed_import_rolls_back_both_datasets(self):
        repository.import_json(engine=self.engine)
        changed = json.loads(json.dumps(self.candidates))
        changed["records"][0]["description"] = "저장되면 안 되는 수정"
        plans = json.loads(json.dumps(self.plans))
        plans[0]["기관"] = None  # 두 번째 테이블의 NOT NULL 제약을 위반합니다.
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "policy_candidates.json").write_text(json.dumps(changed), encoding="utf-8")
            (folder / "gangnam_policy_plans_2025.json").write_text(json.dumps(plans), encoding="utf-8")
            with self.assertRaises(IntegrityError):
                repository.import_json(folder, engine=self.engine)
        candidate_rows, plan_rows = repository.load_dataset_rows(engine=self.engine)
        self.assertEqual(candidate_rows, self.candidates["records"])
        self.assertEqual(plan_rows, list(enumerate(self.plans)))

    def test_missing_database_does_not_fall_back_to_json(self):
        from backend.chatbot.welfare.app.dialogue import resources
        with patch.dict("os.environ", {"WELFIND_WELFARE_SOURCE": "db"}), \
                patch.object(repository, "get_engine", return_value=self.engine), \
                patch.object(Path, "read_text", side_effect=AssertionError("JSON 대체 금지")):
            with self.assertRaises(repository.WelfareDataError) as failure:
                resources.search("세곡동행")
        self.assertIn("복지자료 DB", str(failure.exception))
        self.assertNotIn("SELECT", str(failure.exception))

    def test_explicit_json_mode_is_available_for_offline_tests(self):
        from backend.chatbot.welfare.app.dialogue import resources
        with patch.dict("os.environ", {"WELFIND_WELFARE_SOURCE": "json"}), \
                patch.object(resources, "load_dataset_rows", side_effect=AssertionError("DB 호출 금지")):
            self.assertEqual(resources.search("세곡동행")[0]["id"], "plan-0")
        with patch.dict("os.environ", {"WELFIND_WELFARE_SOURCE": "auto"}):
            with self.assertRaises(ValueError):
                resources.resource_source()

    def test_database_failure_finishes_agent_stream_without_exposing_details(self):
        from backend.agents import supervisor
        context = {"city": "강남구", "district": "세곡동", "month": "2025-12"}
        # 담당 선택 중 사업명을 조회하는 경우와 복지 담당이 실제 검색하는 경우를 검사합니다.
        for question in ("배움마켓", "세곡동행 지원 내용을 알려줘"):
            with self.subTest(question=question), \
                    patch.dict("os.environ", {"WELFIND_WELFARE_SOURCE": "db"}), \
                    patch("backend.chatbot.welfare.app.dialogue.resources.load_dataset_rows",
                          side_effect=repository.WelfareDataError("internal-secret")):
                events = list(supervisor.stream([{"role": "user", "content": question}],
                                                context, {}, use_ai=False))
            self.assertEqual(events[-1][0], "done")
            errors = [value["message"] for event, value in events if event == "error"]
            self.assertEqual(len(errors), 1)
            self.assertIn("복지자료 DB", errors[0])
            self.assertNotIn("internal-secret", errors[0])


if __name__ == "__main__":
    unittest.main()
