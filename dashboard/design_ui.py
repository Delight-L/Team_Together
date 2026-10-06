"""대시보드를 표시하는 Streamlit Custom Component v2.

Python: CSV 읽기·검사 / HTML·CSS·JS: 화면과 사용자 동작.
main.py에서 전달한 데이터만 사용하며 새로운 샘플 수치를 만들지 않습니다.
"""

import base64
import hashlib
import json
from pathlib import Path
import streamlit as st

UI_DIR = Path(__file__).resolve().parent / "ui"


def read_ui(name):
    return (UI_DIR / name).read_text(encoding="utf-8")


# 컴포넌트는 함수 밖에서 한 번 등록합니다. 파일 내용은 인라인 코드로 전달합니다.
JAVASCRIPT_START = """
export default function(component) {
    const { data: BOOT, parentElement, setStateValue, setTriggerValue } = component;
    const root = parentElement.querySelector('#dashboard-root');
    if (!root) return;
    if (root.dataset.version === BOOT.version) return;
    if (root._dashboardCleanup) root._dashboardCleanup();
    root.dataset.version = BOOT.version;
    let weightTimer;
    const listeners = [];
    const listen = (type, handler) => {
        const activeHandler = (event) => {
            if (root.dataset.version === BOOT.version) handler(event);
        };
        root.addEventListener(type, activeHandler);
        listeners.push([type, activeHandler]);
    };
"""

JAVASCRIPT_END = """
    const cleanup = () => {
        listeners.forEach(([type, handler]) => root.removeEventListener(type, handler));
        clearTimeout(weightTimer);
        if (root.dataset.version === BOOT.version) delete root.dataset.version;
        if (root._dashboardCleanup === cleanup) delete root._dashboardCleanup;
    };
    root._dashboardCleanup = cleanup;
    return cleanup;
}
"""

# 파일을 읽는 순서: 계산 → 그래프 → 대응 → 업무 공간 → 화면 동작입니다.
UI_SCRIPT_FILES = [
    "data.js",
    "charts.js",
    "responses.js",
    "workspace.js",
    "map.js",
    "chat.js",
    "bridge.js",
    "dashboard.js",
]
script_parts = [JAVASCRIPT_START]
for filename in UI_SCRIPT_FILES:
    script_parts.append(read_ui(filename))
script_parts.append(JAVASCRIPT_END)
JAVASCRIPT = "\n".join(script_parts)

_DASHBOARD = st.components.v2.component(
    "isolation_dashboard",
    html=read_ui("layout.html"),
    css=read_ui("style.css") + "\n" + read_ui("brand.css"),
    js=JAVASCRIPT,
    isolate_styles=True,  # 대시보드 CSS를 Streamlit 본체의 스타일과 분리합니다.
)


def render_dashboard(payload):
    """Python 데이터를 화면에 전달합니다. 원래 딕셔너리는 변경하지 않습니다."""
    payload = dict(payload)
    assets = UI_DIR.parents[1] / "ci"
    payload["brand"] = {
        name: "data:image/png;base64," + base64.b64encode((assets / filename).read_bytes()).decode("ascii")
        for name, filename in [("logo", "welfind_logo.png"), ("character", "welfind_character.png")]
    }
    component_state = st.session_state.get("isolation_dashboard", {})
    payload["savedUI"] = component_state.get("ui_state")
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    payload_bytes = payload_json.encode("utf-8")
    payload["version"] = hashlib.sha256(payload_bytes).hexdigest()
    return _DASHBOARD(
        data=payload,
        key="isolation_dashboard",
        width="stretch",
        height="content",
        on_request_change=lambda: None,
        on_ui_state_change=lambda: None,
    )
