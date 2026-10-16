"""Exact-month age evidence keeps unknown flags and invalid changes distinct."""
import math
import unittest

import pandas as pd

from backend.bomi.adapters import v16
from chatbot_agent.query_service import _age_signal_changes, execute
from chatbot_agent.repository import AGE_LABEL
from chatbot_agent.schemas import QueryIntent


class AgeRepository:
    def __init__(self):
        self.calls = []
        self.rows = {
            "20s": self.row("20s", True),
            "30s": self.row("30s", False),
            "40s": self.row("40s", None, "partially_assessed"),
            "50s": self.row("50s", float("nan"), "deferred"),
        }
        self.rows["30s"]["weekday_move_count_valid"] = False

    @staticmethod
    def row(age, flag, status="assessed"):
        return {"date": "2025-12", "행정동": "삼성1동", "age_band": age,
                "assessment_status": status, "signal_status": "No_signal" if status == "assessed" else "Deferred",
                "communication_signal": False, "mobility_signal": flag, "combined_signal": False,
                "any_signal": flag, "weekday_move_count": 20.0, "weekend_move_count": 10.0,
                "weekday_move_count_log_change": math.log(0.9), "weekend_move_count_log_change": math.log(1.1),
                "weekday_move_count_valid": True, "weekend_move_count_valid": True}

    def activity(self, dong, start, end, age):
        self.calls.append((dong, start, end, age))
        return pd.DataFrame([self.rows[age]]) if age in self.rows else pd.DataFrame()

    def available_period(self):
        return "2025-07", "2025-12"


class AgeSignalEvidenceTest(unittest.TestCase):
    def test_same_month_only_preserves_true_false_unknown_and_missing_bands(self):
        repository = AgeRepository()
        rows = _age_signal_changes(repository, [{"행정동": "삼성1동", "date": "2025-12", "signal_type": "mobility"}])
        self.assertEqual(repository.calls, [("삼성1동", "2025-12", "2025-12", band) for band in AGE_LABEL])
        self.assertEqual([row["age_signal"] for row in rows], [True, False, None, None, None])
        self.assertEqual(rows[-1]["assessment_status"], "missing")
        self.assertIsNone(rows[-1]["changes"]["weekday_move_count"])
        self.assertAlmostEqual(rows[0]["changes"]["weekday_move_count"], -10.0)
        self.assertIsNone(rows[1]["changes"]["weekday_move_count"])
        self.assertEqual(rows[2]["component_signals"], {"communication": False, "mobility": None, "combined": False})

    def test_partial_row_keeps_assessed_communication_separate_from_deferred_mobility(self):
        repository = AgeRepository()
        communication = _age_signal_changes(repository, [{"행정동": "삼성1동", "date": "2025-12", "signal_type": "communication"}])
        mobility = _age_signal_changes(repository, [{"행정동": "삼성1동", "date": "2025-12", "signal_type": "mobility"}])
        self.assertIs(communication[2]["age_signal"], False)
        self.assertIsNone(mobility[2]["age_signal"])
        self.assertEqual(communication[2]["assessment_status"], "partially_assessed")
        self.assertEqual(mobility[2]["signal_status"], "Deferred")

    def test_age_activity_retains_domain_statuses_and_invalid_value_cannot_be_reported_as_change(self):
        repository = AgeRepository()
        intent = QueryIntent("track_change", "age_activity", dong="삼성1동", start_month="2025-12", end_month="2025-12",
                             signal="mobility", age_bands=("30s", "40s"))
        evidence = execute(repository, intent)
        self.assertEqual(len(evidence.rows), 2)
        self.assertEqual([(row["행정동"], row["date"]) for row in evidence.rows], [("삼성1동", "2025-12")] * 2)
        self.assertIs(evidence.rows[0]["age_signal"], False)
        self.assertIsNone(evidence.rows[0]["weekday_move_count_change_pct"])
        self.assertIsNone(evidence.rows[1]["age_signal"])
        self.assertEqual(evidence.rows[1]["assessment_status"], "partially_assessed")
        self.assertIs(evidence.rows[1]["component_signals"]["communication"], False)

    @unittest.skipUnless(v16.data_ready(), '게시된 v16 DB1(PostgreSQL)이 없어 건너뜀')
    def test_active_readonly_db_same_overall_signal_has_five_fully_assessed_age_rows(self):
        repository = v16._repository()
        intent = QueryIntent("find_region", "signals", start_month="2025-07", end_month="2025-12")
        evidence = execute(repository, intent)
        self.assertEqual([(row["행정동"], row["date"]) for row in evidence.rows], [("삼성1동", "2025-12")])
        ages = evidence.supplementary["age_signal_changes"]
        self.assertEqual(len(ages), 5)
        self.assertEqual({(row["행정동"], row["date"]) for row in ages}, {("삼성1동", "2025-12")})
        self.assertEqual({row["age_band"] for row in ages}, set(AGE_LABEL))
        self.assertTrue(all(row["age_signal"] is False and row["assessment_status"] == "assessed" for row in ages))


if __name__ == "__main__":
    unittest.main()
