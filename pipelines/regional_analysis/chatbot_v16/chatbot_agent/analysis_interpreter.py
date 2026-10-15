"""Compatibility helpers that use the same SQLite query path as the chatbot."""
from .repository import DataRepository,CORE
from .query_service import execute
from .schemas import QueryIntent
from .answer_generator import template_answer

def explain_all_signals(project_root):
    repo=DataRepository(project_root);start,end=repo.available_period()
    names=tuple(sorted(repo.signals(start,end)['행정동'].unique()))
    if not names:return '현재 새 탐지 구간에 신호 기록이 없습니다.'
    intent=QueryIntent('track_change','reason',start_month=start,end_month=end,dongs=names)
    evidence=execute(repo,intent)
    # This compatibility utility explains every signal including its diagnostic
    # scores; the interactive chatbot keeps its separate concise answer.
    lines=[evidence.summary,template_answer(intent,evidence,'')]
    for row in evidence.rows:
        scores=[f"{metric} Robust Z: {row[metric+'_residual_change_expanding_rz']:.2f}"
                for metric in CORE if row.get(metric+'_residual_change_expanding_rz') is not None]
        if scores:lines.append(f"{row['행정동']} · {row['date']}: "+' · '.join(scores))
    return '\n'.join(lines)

def summarize_dongs(project_root):
    repo=DataRepository(project_root);start,end=repo.available_period()
    intent=QueryIntent('find_region','rank_regions',start_month=start,end_month=end,limit=22)
    return template_answer(intent,execute(repo,intent),'')
