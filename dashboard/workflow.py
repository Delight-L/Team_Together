"""Public workflow facade used by dialogs and reports."""
from agents.service_matching import match_services
from chatbot.service import explain_question

def selected_evidence(request, db_data):
    if request.get("city") != "강남구":
        return []
    return [r for r in db_data.get("assessment", []) if r["기준연월"] == request["month"] and r["행정동명"] == request.get("district")]
