"""담당 에이전트 4종. 새 에이전트는 Agent 인터페이스(base.py)를 구현하고 여기에 등록합니다."""
from backend.bomi.agents.guide import GuideAgent
from backend.bomi.agents.region_analysis import RegionAnalysisAgent
from backend.bomi.agents.report import ReportAgent
from backend.bomi.agents.welfare import WelfareAgent


def default_agents() -> dict:
    agents = (RegionAnalysisAgent(), WelfareAgent(), ReportAgent(), GuideAgent())
    return {agent.id: agent for agent in agents}
