"""Build 32 sequential cases only after comparing source and main DB contents."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import sqlite3

HERE = Path(__file__).resolve().parent
MAIN = HERE.parents[3]
SOURCE = MAIN.parent / 'Team_Together/risk_analysis_version16'
DB = HERE.parent / 'outputs/db1.sqlite'
SOURCE_DB = SOURCE / 'outputs/runtime/snapshots/db1-202512-74eb3ce3e2eb.sqlite'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def connect(path):
    return sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)


def main():
    source_file = SOURCE / 'evaluation/datasets/v16_questions_64.jsonl'
    cases = [json.loads(line) for line in source_file.read_text(encoding='utf-8').splitlines()]
    cases = [case for case in cases if case['case_id'] in {f'B{i:02}' for i in range(1, 33)}]
    assert len(cases) == 32
    report = {'source_db_sha256': digest(SOURCE_DB), 'main_db_sha256': digest(DB), 'tables': {}, 'case_checks': {}}
    with connect(SOURCE_DB) as old, connect(DB) as new:
        names = lambda conn: {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert names(old) == names(new), 'Table inventory differs; inspect before importing'
        for table in sorted(names(old)):
            quoted = '"' + table.replace('"', '""') + '"'
            a = old.execute(f'SELECT * FROM {quoted}').fetchall()
            b = new.execute(f'SELECT * FROM {quoted}').fetchall()
            same = Counter(a) == Counter(b)
            report['tables'][table] = {'source_rows': len(a), 'main_rows': len(b), 'all_rows_identical': same}
            if not same:
                columns = [r[1] for r in old.execute(f'PRAGMA table_info({quoted})')]
                report['tables'][table]['changed_columns'] = [column for i, column in enumerate(columns) if Counter(row[i] for row in a) != Counter(row[i] for row in b)]
        allowed_differences = {'a1_region_baseline', 'a1_region_feature', 'db1_run', 'a1_input', 'a1_context', 'pipeline_state', 'month_run'}
        assert all(v['all_rows_identical'] or t in allowed_differences for t, v in report['tables'].items())
        # Every evidence-bearing activity/age/consumption table must match exactly.
        assert all(v['all_rows_identical'] for t, v in report['tables'].items() if t.startswith(('a2_', 'a3')))
        for case in cases:
            checks = []
            for evidence in case['source_evidence']:
                if evidence['type'] != 'readonly_sql':
                    continue
                if evidence['table'] == 'a1_context JOIN a1_input':
                    key = evidence['key']
                    row = new.execute('SELECT c.cluster_type, i.input_json FROM a1_context c JOIN a1_input i ON c.adm_cd=i.adm_cd AND c.period=i.period WHERE c.adm_cd=? AND c.period=?', (key['adm_cd'], key['period'])).fetchone()
                    payload = json.loads(row[1])
                    actual = {'cluster_type': row[0], 'hh_1_ratio': payload['hh_1_ratio'], 'hh_2_ratio': payload['hh_2_ratio']}
                    assert actual == evidence['values'], (case['case_id'], actual, evidence['values'])
                    checks.append({'table': evidence['table'], 'method': 'main_db_direct_query', 'verified_values': actual})
                elif evidence['table'] == 'derived':
                    checks.append({'table': 'derived', 'method': 'same_stored_log_changes_same_expm1_derivation', 'derivation': evidence['derivation']})
                elif 'a1_context' in evidence['table']:
                    # The signal lookup joins context for dong names only.
                    assert old.execute('SELECT adm_cd, period, adm_nm FROM a1_context ORDER BY 1,2').fetchall() == new.execute('SELECT adm_cd, period, adm_nm FROM a1_context ORDER BY 1,2').fetchall()
                    checks.append({'table': evidence['table'], 'method': 'signal_tables_exact_match_and_context_names_exact_match'})
                else:
                    tables = [t for t in report['tables'] if t in evidence['table']]
                    assert tables and all(report['tables'][t]['all_rows_identical'] for t in tables), evidence['table']
                    checks.append({'table': evidence['table'], 'method': 'all_source_table_rows_exact_match'})
            report['case_checks'][case['case_id']] = checks
            case['source_snapshot_sha256'] = case['snapshot_sha256']
            case['snapshot_sha256'] = report['main_db_sha256']
            case['snapshot_id'] = 'main-db1-' + report['main_db_sha256'][:12]
            case['reference_review_status'] = 'main_db_evidence_verified_agent_review_pending'
            case['reference_status'] = 'main_db_and_rules_grounded'
            case['evidence_audit'] = 'DATASET32_DB_AUDIT.json'
            case['approved_for_reporting'] = False
            case['review_rubric'] = {'required': '질문에서 요청한 지역·기간·지표·비교 또는 확인 질문을 정확히 답한다. 수치가 있다면 DB와 일치해야 한다.', 'optional': '질문에 요구되지 않은 모범답안의 부가 수치·배경·주의문 누락만으로 오답 처리하지 않는다. 추가 설명에 사실 오류가 있으면 감점한다.', 'similarity_scores': 'BLEU/ROUGE는 표현 유사도이며 최종 판정 기준이 아니다.'}
            if case['case_id'] in {'B03', 'B11', 'B27'}:
                case['review_rubric']['required'] = '요청된 연령별 통화·문자 변화 방향/변화율과 지역·기간을 정확히 설명한다. 변화율을 요청한 질문은 원값 생략만으로 감점하지 않는다.'
    assert Counter(c['path_id'] for c in cases) == {f'PATH-0{i}': 8 for i in range(1, 5)}
    assert all(sum(bool(s.get('score_target')) for s in c['steps']) == 1 and c['steps'][-1]['score_target'] for c in cases)
    assert digest(DB) == report['main_db_sha256'], 'DB changed during audit'
    destination = HERE / 'datasets/v16_questions_32.jsonl'
    destination.write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases), encoding='utf-8')
    manifest = json.loads((SOURCE / 'evaluation/datasets/v16_questions_64.manifest.json').read_text(encoding='utf-8'))
    manifest.update(dataset_id='v16-questions-32', version='1.0.0', created_at='2026-10-15', case_count=32, basic_count=32, variation_count=0, reference_answer_count=32, snapshot_id=cases[0]['snapshot_id'], snapshot_sha256=report['main_db_sha256'], snapshot_relative_path='outputs/db1.sqlite', dataset_sha256=digest(destination), reference_review_status='main_db_evidence_verified_agent_review_pending', scoring_contract='32개 기본 사례의 모든 steps를 순서대로 재현하고 마지막 응답을 평가한다. DB 근거 검증 완료. 사람 최종 검토와 독립 평가셋 검증은 별도다.')
    (HERE / 'datasets/v16_questions_32.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE / 'DATASET32_DB_AUDIT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 32개 데이터셋 DB 근거 검증', '', '- 기본 사례 B01~B32를 선택했습니다. 경로별 8개이며 선행 대화·화면 선택 단계를 모두 보존했습니다.', '- 기존 64개 파일과 사용자 리뷰를 수정하지 않았습니다.', '- 원본 snapshot과 메인 DB의 모든 테이블·모든 행을 비교했습니다.', '- 활동·연령·이상신호·소비 테이블은 원본과 완전히 동일합니다.', '- 지역배경 분석은 elder_v2 모델로 변경되었습니다. B04/B12/B28이 사용하는 삼성1동·삼성2동 유형명과 1·2인가구 비율을 메인 DB에서 직접 조회했고 원본 근거와 모두 일치했습니다.', '- 따라서 이 32개 답안의 숫자와 지역유형 문구는 유지할 수 있습니다. DB 파일 해시만 교체한 검증이 아닙니다.', '- 자료 의미·기간 안내는 기존 명세를 근거로 유지했으며, 챗봇 출력을 정답으로 복사하지 않았습니다.', '- 모범답안은 개발 평가용입니다. 독립적인 최종 성능 검증셋으로 주장하지 않습니다.', '', '| 테이블 | 원본 행 | 메인 행 | 전체 행 일치 |', '|---|---:|---:|---|']
    lines += [f"| {t} | {v['source_rows']} | {v['main_rows']} | {'예' if v['all_rows_identical'] else '아니요'} |" for t, v in report['tables'].items()]
    (HERE / 'DATASET32_DB_AUDIT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'cases': len(cases), 'tables': len(report['tables']), 'different_tables': [t for t,v in report['tables'].items() if not v['all_rows_identical']], 'dataset': str(destination)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
