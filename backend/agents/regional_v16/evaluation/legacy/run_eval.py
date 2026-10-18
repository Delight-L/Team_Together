"""Replay actual steps. Lexical similarity is not factual accuracy.

PATH01/02 main service adapter; PATH03/04 v16 dashboard/session component.
This does not claim main dashboard end-to-end integration coverage.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import math
import re
import sys
try:
    from .validate_dataset import validate
except ImportError:
    from validate_dataset import validate
V16_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
for root in (PROJECT_ROOT, V16_ROOT):
    if str(root) not in sys.path: sys.path.insert(0, str(root))

def tokens(text):
    return re.findall(r'[가-힣A-Za-z0-9]+', text.lower())

def bleu1(reference, candidate):
    if not reference or not candidate: return 0.0
    n = sum((Counter(reference) & Counter(candidate)).values())
    return n / len(candidate) * min(1.0, math.exp(1 - len(reference) / len(candidate)))

def _f1(n, r, c):
    return 2*n/(len(r)+len(c)) if r and c else 0.0

def rouge1(reference, candidate):
    return _f1(sum((Counter(reference) & Counter(candidate)).values()), reference, candidate)

def rouge_l(reference, candidate):
    prev = [0]*(len(candidate)+1)
    for a in reference:
        row = [0]
        for j, b in enumerate(candidate, 1):
            row.append(prev[j-1]+1 if a == b else max(prev[j], row[-1]))
        prev = row
    return _f1(prev[-1], reference, candidate)

def check_snapshot(rows, database):
    digest = hashlib.sha256(Path(database).read_bytes()).hexdigest()
    if any(r.get('snapshot_sha256') != digest for r in rows):
        raise ValueError(f'Snapshot mismatch: {digest}; evaluation refused')
    return digest

class Runtime:
    def __init__(self, item, database):
        from agents.regional_analysis import v16_service
        self.service, self.item, self.database = v16_service, item, database
        self.history, self.store = [], None
        self.adapter = 'main_v16_service' if item['path_id'] in {'PATH-01', 'PATH-02'} else 'v16_dashboard_session_component'
        if self.adapter == 'v16_dashboard_session_component':
            from backend.app.session_store import SessionStore
            from chatbot_agent.orchestrator import Chatbot
            from chatbot_agent.repository import DataRepository
            from chatbot_agent.llm_intent_resolver import IntentResolver, _explicit_districts
            class OfflineResolver(IntentResolver):
                def resolve(self, question, districts, memory):
                    self.last_source = 'evaluation_local_fallback'
                    return self._fallback(question, districts, memory, _explicit_districts(question, districts))
            self.store = SessionStore(V16_ROOT, 'offline')
            bot = Chatbot(V16_ROOT, model='offline', repository=DataRepository(V16_ROOT, db=database),
                          intent_resolver=OfflineResolver(V16_ROOT, 'offline'), moderator=v16_service._SupervisorModerator())
            bot.allow_ai_generation = False
            self.store._sessions['evaluation'] = bot

    def perform(self, step):
        if step['action'] == 'dashboard_selection':
            from backend.app.dashboard import build_brief
            from chatbot_agent.repository import DataRepository
            selection = step['selection']
            response = build_brief(DataRepository(V16_ROOT, db=self.database), **selection,
                                  snapshot_id=self.item['snapshot_id'], revision=step['selection_revision'])
            digest = hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()
            response = self.store.activate_dashboard('evaluation', step['selection_revision'], digest, response, str(self.database))
            if response.get('status') not in {'ready', 'no_signal', 'partial', 'not_assessable'}:
                raise ValueError(f'Failed dashboard selection: {response}')
            self.history = []
            return {'answer': response['narrative'], 'raw_response': response, 'display': response.get('display')}
        if self.store:
            result = self.store.get('evaluation').answer(step['text'])
            response = {'answer': result.text, 'followUps': list(result.follow_ups)}
        else:
            # No answer-key scope is passed to production code.
            response = self.service.reply(step['text'], deepcopy(self.history), {}, use_ai=False)
        self.history.extend([{'role': 'user', 'content': step['text']}, {'role': 'assistant', 'content': response['answer']}])
        return {'answer': response['answer'], 'raw_response': response}

def run_case(item, database, runtime_factory=Runtime):
    result = {**deepcopy(item), 'trace': [], 'actual_answer': '', 'execution_status': 'ok', 'error': None,
              'bleu1': None, 'rouge1': None, 'rougeL': None}
    try:
        runtime = runtime_factory(item, database)
        result['adapter'] = runtime.adapter
        for step in item['steps']:
            entry = {'input': deepcopy(step), 'history_before': deepcopy(runtime.history)}
            result['trace'].append(entry)
            try:
                response = runtime.perform(step)
                entry.update(response)
                if not response.get('answer', '').strip(): raise ValueError('Empty answer/precondition')
                if step.get('score_target'):
                    result['actual_answer'] = response['answer']
                    result['actual_display'] = response.get('display')
            except Exception as exc:
                entry['error'] = f'{type(exc).__name__}: {exc}'
                raise
        a = tokens(result['actual_answer'])
        refs = [tokens(r) for r in item['reference_answers']]
        result.update(bleu1=max(bleu1(r,a) for r in refs), rouge1=max(rouge1(r,a) for r in refs), rougeL=max(rouge_l(r,a) for r in refs))
    except Exception as exc:
        result.update(execution_status='error', error=f'{type(exc).__name__}: {exc}')
    return result

def evaluate(dataset, output_dir, use_ai=False):
    if use_ai: raise ValueError('This evaluation is offline; --use-ai is unsupported')
    from chatbot_agent.repository import DataRepository
    rows = validate(dataset)
    database = DataRepository(V16_ROOT).db
    digest = check_snapshot(rows, database)
    results = []
    for item in rows:
        if DataRepository(V16_ROOT).db != database: raise ValueError('Active DB changed during evaluation')
        check_snapshot([item], database)
        result = run_case(item, database)
        results.append(result)
        print(f"{item['case_id']}: {result['execution_status']}", flush=True)
    check_snapshot(rows, database)
    good = [r for r in results if r['execution_status'] == 'ok']
    payload = {'dataset': str(dataset.resolve()), 'database': str(database), 'snapshot_sha256': digest,
               'case_count': len(results), 'success_count': len(good), 'error_count': len(results)-len(good),
               'mode': 'offline_components_not_main_dashboard_end_to_end', 'human_review_status': 'not_performed',
               'metric_definition': 'Lowercase regex Korean/Latin/digit tokens, punctuation removed, no stemming; BLEU1 clipped precision with brevity penalty; ROUGE1/L F1; best reference per metric; not accuracy',
               'averages': {k: sum(r[k] for r in good)/len(good) if good else None for k in ('bleu1','rouge1','rougeL')}, 'results': results}
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y%m%d-%H%M%S-%f')
    target = output_dir/f'run32-{stamp}.json'
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return target

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--output-dir', type=Path, default=V16_ROOT/'evaluation/results')
    parser.add_argument('--use-ai', action='store_true')
    args = parser.parse_args()
    print(evaluate(args.dataset, args.output_dir, args.use_ai))
