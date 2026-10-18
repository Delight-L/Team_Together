import unittest
from unittest.mock import patch
from backend.bomi.routing import Router
from backend.bomi.agents.region_analysis import RegionAnalysisAgent
from backend.bomi.tests.helpers import make_request, GROUP
from backend.bomi.adapters import v16
from backend.db import region_workspace, group_workspace


class ScreenSummaryTest(unittest.TestCase):
    def test_screen_wording_is_fixed_route_and_workspace_even_with_v16(self):
        for text in ['화면 정보 요약해줘','화면 내용 요약해줘','지금 보는 화면 설명해줘','대시보드 정리해줘']:
            request=make_request(text)
            self.assertEqual(Router().fixed(request),'region_analysis')
            with patch.object(v16,'data_ready',return_value=True):
                self.assertTrue(RegionAnalysisAgent._uses_workspace(request))

    def test_ai_summary_bypasses_v16_and_uses_current_district(self):
        request=make_request('화면 정보 요약해줘',use_ai=True)
        with patch.object(region_workspace,'ai_explain_region',return_value={'answer':'삼성1동 화면 요약'}) as ai, patch.object(v16,'reply') as legacy:
            reply=RegionAnalysisAgent()._reply(request)
        ai.assert_called_once_with(request.context,request.question,request.data,[])
        legacy.assert_not_called()
        self.assertTrue(reply.generated_by_ai)

    def test_group_summary_uses_selected_group(self):
        request=make_request('화면 요약해줘',use_ai=True,group=GROUP)
        with patch.object(group_workspace,'ai_explain',return_value={'answer':'선택 그룹 요약'}) as ai:
            RegionAnalysisAgent()._reply(request)
        ai.assert_called_once_with(request.group.context,request.question,request.group.detail,[])

    def test_ai_off_uses_grounded_summary(self):
        request=make_request('화면 요약해줘')
        with patch.object(region_workspace,'ai_explain_region') as ai:
            reply=RegionAnalysisAgent()._reply(request)
        ai.assert_not_called()
        self.assertIn('삼성1동',reply.text)

    def test_summary_prompt_requests_natural_grounded_prose(self):
        request=make_request('화면 정보 요약해줘',use_ai=True)
        with patch('backend.chatbot.explain_ai.ask_with_evidence',return_value=('화면 요약',[])) as ask:
            region_workspace.ai_explain_region(request.context,request.question,request.data,[])
        prompt=ask.call_args.args[0]
        self.assertIn('자연스럽고 편안한 한국어 문단',prompt)
        self.assertIn('실제 증가를 감소로 설명하지 마세요',prompt)
        self.assertIn('삼성1동',prompt)
        self.assertIn('-12.3',prompt)
