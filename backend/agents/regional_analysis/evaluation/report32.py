"""Read-only result rendering; assistant review is separate from user's review."""

import argparse
import html
import json
from collections import Counter
from pathlib import Path


def render(result, reviews):
    data = json.loads(result.read_text(encoding='utf-8'))
    verdicts = json.loads(reviews.read_text(encoding='utf-8'))
    counts = Counter(v['label'] for v in verdicts.values())
    sections = []
    for row in data['results']:
        case = row['case_id']
        review = verdicts[case]
        esc = lambda x: html.escape(str(x))
        references = row.get('reference_answers') or [row.get('reference_answer', '')]
        steps = row.get('step_results', row.get('trace', []))
        sections.append(f'''<article><h2>{esc(case)} · {esc(row.get('title', ''))}</h2>
<p>{esc(row['path_id'])} · <strong>{esc(review['label'])}</strong></p>
<p>{esc(review['reason'])}</p><h3>원래 입력 순서</h3><pre>{esc(json.dumps(row.get('steps', []), ensure_ascii=False, indent=2))}</pre>
<div class="pair"><section><h3>모범답안</h3><p>{esc(references[0])}</p></section>
<section><h3>실제 마지막 답변</h3><p>{esc(row.get('actual_answer', ''))}</p></section></div>
<details><summary>실행 기록</summary><pre>{esc(json.dumps(steps, ensure_ascii=False, indent=2))}</pre></details></article>''')
    out = result.with_name(result.stem + '-assistant-review.html')
    out.write_text(
        '''<!doctype html><meta charset="utf-8"><title>32개 답변 재평가</title>
<style>body{font:16px/1.7 sans-serif;max-width:1400px;margin:40px auto;background:#f5f7fa;color:#182434}article{background:white;padding:24px;margin:20px 0;border:1px solid #ccd6df;border-radius:10px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:30px}p,pre{white-space:pre-wrap;overflow-wrap:anywhere}pre{font-size:13px}h1,h2{color:#174a70}</style>
<h1>32개 답변 재평가 · AI 검토</h1><p>사용자 휴먼 리뷰와 별개의 검토입니다. 외부 AI를 사용하지 않은 구성요소 실행 결과이며 웹 UI 전체 성능으로 해석하지 않습니다. 표현 유사도는 정답률이 아닙니다.</p>
<p>'''
        + html.escape(str(dict(counts)))
        + '</p>'
        + ''.join(sections),
        encoding='utf-8',
    )
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('result', type=Path)
    parser.add_argument('reviews', type=Path)
    args = parser.parse_args()
    print(render(args.result, args.reviews))
