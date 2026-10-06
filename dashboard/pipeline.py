"""Compatibility imports for dashboard dialogs; persistence lives in db/."""
from db.analysis_repository import (
    ANALYSIS_DIR, DETECTION_FILE, ROOT_DIR, SCHEMA, RULE_VERSION,
    get_engine, now_text, monthly_upload, prepare_analysis2,
    load_analysis2_data, structure_upload, append_frame, publish,
    records, load_dashboard_data,
)
