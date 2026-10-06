import json
import unittest
from pathlib import Path

from chatbot.data_assistant.data_catalog import CatalogConfig, build_context, discover_sources


class DataCatalogTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = Path(__file__).resolve().parent / "fixtures"

    def test_discovers_only_allowlisted_outputs(self):
        root = self.fixtures / "allowlist"
        allowed = root / "agents/regional_analysis/Analysis2/outputs/result.csv"
        sources, _ = discover_sources(root)

        self.assertEqual([allowed.resolve()], sources)

    def test_missing_files_are_reported_without_failure(self):
        sources, missing = discover_sources(self.fixtures / "empty")

        self.assertEqual([], sources)
        self.assertEqual(len(missing), 8)

    def test_retrieval_prefers_matching_rows_and_respects_limits(self):
        config = CatalogConfig(max_rows_per_file=2, max_total_rows=1, max_context_chars=5000)
        result = build_context(self.fixtures / "matching", "역삼동 값", config)

        self.assertEqual(1, result.selected_rows)
        payload = json.loads(result.text)
        self.assertEqual("역삼동", payload["sample_or_relevant_rows"][0]["area"])
        self.assertEqual(1, len(payload["sample_or_relevant_rows"]))

    def test_context_character_limit_is_respected(self):
        config = CatalogConfig(max_rows_per_file=5, max_total_rows=5, max_context_chars=120)
        result = build_context(self.fixtures / "long", "전체", config)

        self.assertLessEqual(len(result.text), 120)


if __name__ == "__main__":
    unittest.main()
