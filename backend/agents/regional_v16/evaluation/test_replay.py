"""Regression tests for the evaluator errors that invalidated the original run."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_eval as runner


class ReplayTests(unittest.TestCase):
    def item(self):
        return {'case_id':'test','path_id':'PATH-02','reference_answers':['actual second'],
                'expected_scope': {'dong':'DO NOT INJECT'},
                'steps':[{'action':'chat','text':'first','score_target':False},
                         {'action':'chat','text':'second','score_target':True}]}

    def test_actual_history_and_case_reset(self):
        calls = []
        from agents.regional_analysis import v16_service
        def reply(question, history, context, use_ai):
            calls.append((question, deepcopy(history), context, use_ai))
            return {'answer':'actual '+question}
        with patch.object(v16_service, 'reply', side_effect=reply):
            for _ in range(2):
                result = runner.run_case(self.item(), Path('unused'))
                self.assertEqual(result['actual_answer'], 'actual second')
        self.assertEqual(calls[0][1], [])
        self.assertEqual(calls[1][1], [{'role':'user','content':'first'}, {'role':'assistant','content':'actual first'}])
        self.assertEqual(calls[2][1], [])
        self.assertTrue(all(call[2] == {} for call in calls))
        self.assertTrue(all(call[3] is False for call in calls))

    def test_failed_precondition_stops_target_and_excludes_score(self):
        calls = []
        class Broken:
            adapter = 'test'
            history = []
            def __init__(self,*args): pass
            def perform(self, step):
                calls.append(step)
                raise ValueError('selection failed')
        result = runner.run_case(self.item(), Path('unused'), Broken)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['execution_status'], 'error')
        self.assertIsNone(result['bleu1'])
        self.assertIn('selection failed', result['trace'][0]['error'])

    def test_snapshot_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'db'
            p.write_bytes(b'new database')
            with self.assertRaisesRegex(ValueError, 'Snapshot mismatch'):
                runner.check_snapshot([{'snapshot_sha256':'0'*64}], p)
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(runner.check_snapshot([{'snapshot_sha256':digest}], p), digest)

    def test_bleu_brevity_penalty_and_rouge_f1(self):
        import math
        self.assertAlmostEqual(runner.bleu1(['a','b','c','d'],['a','b']), math.exp(-1))
        self.assertAlmostEqual(runner.rouge1(['a','b','c','d'],['a','b']), 2/3)
        self.assertEqual(runner.bleu1(['a'],['a','a']), .5)
        self.assertEqual(runner.rouge_l(['a','b'],['b','a']), .5)

    def test_real_selection_age_switch_and_invalid_selection(self):
        from chatbot_agent.repository import DataRepository
        runtime = runner.Runtime({'path_id':'PATH-04','snapshot_id':'test'}, DataRepository(runner.V16_ROOT).db)
        for revision, age in enumerate(('20s','30s',None), 1):
            runtime.perform({'action':'dashboard_selection','selection':{'dong':'삼성1동','label_month':'2025-12','age_band':age},'selection_revision':revision})
            self.assertEqual(runtime.store.get('evaluation').dashboard_scope['age_band'], age)
        with self.assertRaisesRegex(ValueError, 'Failed dashboard selection'):
            runtime.perform({'action':'dashboard_selection','selection':{'dong':'없는동','label_month':'2025-12','age_band':None},'selection_revision':4})
        self.assertEqual(runtime.store.get('evaluation').dashboard_scope['dong'], '삼성1동')

if __name__ == '__main__':
    unittest.main()
