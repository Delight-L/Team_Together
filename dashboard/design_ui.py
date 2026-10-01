"""대시보드를 표시하는 Streamlit Custom Component v2.

Python: CSV 읽기·검사 / HTML·CSS·JS: 화면과 사용자 동작.
main.py에서 전달한 데이터만 사용하며 새로운 샘플 수치를 만들지 않습니다.
"""
import hashlib
import json
from pathlib import Path
import streamlit as st

UI_DIR = Path(__file__).resolve().parent / "ui"


def read_ui(name):
    return (UI_DIR / name).read_text(encoding="utf-8")


# 컴포넌트는 함수 밖에서 한 번 등록합니다. 파일 내용은 인라인 코드로 전달합니다.
JAVASCRIPT = """
export default function(component) {
    const { data: BOOT, parentElement } = component;
    const root = parentElement.querySelector('#dashboard-root');
    if (!root) return;
    if (root.dataset.version === BOOT.version) return;
    root.dataset.version = BOOT.version;
    let weightTimer;
    const listeners = [];
    const listen = (type, handler) => {
        root.addEventListener(type, handler);
        listeners.push([type, handler]);
    };
""" + read_ui("data.js") + read_ui("charts.js") + read_ui("responses.js") + read_ui("detection.js") + read_ui("dashboard.js") + """
    return () => {
        listeners.forEach(([type, handler]) => root.removeEventListener(type, handler));
        clearTimeout(weightTimer);
        delete root.dataset.version;
    };
}
"""

_DASHBOARD = st.components.v2.component(
    "isolation_dashboard",
    html=read_ui("layout.html"), css=read_ui("style.css"), js=JAVASCRIPT,
    isolate_styles=True,  # 대시보드 CSS를 Streamlit 본체의 스타일과 분리합니다.
)


def render_dashboard(payload):
    payload = dict(payload)
    payload["version"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return _DASHBOARD(data=payload, key="isolation_dashboard", width="stretch", height="content")
