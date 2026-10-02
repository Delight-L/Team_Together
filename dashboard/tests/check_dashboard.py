"""대시보드의 CSV 연결·계산·컴포넌트 검증."""

import json
import subprocess
import tempfile
import shutil
import sys
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DASHBOARD_DIR.parent))

from streamlit.testing.v1 import AppTest
from dashboard.settings import (
    BASE_DIR,
    RISK_FILE,
    MAP_FILE,
    FACTORS,
    DEFAULT_WEIGHTS,
    FACTOR_COLORS,
    THRESHOLDS,
)
from dashboard.data_utils import load_risk_data, load_boundaries

# 브라우저를 열지 않고 Python 코드와 컴포넌트 등록에 오류가 없는지 확인합니다.
app = AppTest.from_file(str(DASHBOARD_DIR.parent / "main.py"), default_timeout=30).run()
assert not app.exception, [item.message for item in app.exception]
assert not app.error, [item.value for item in app.error]

data = load_risk_data(RISK_FILE, RISK_FILE.stat().st_mtime_ns)
data["date"] = data["date"].dt.strftime("%Y-%m-%d")
boot = {
    "geometry": load_boundaries(MAP_FILE, MAP_FILE.stat().st_mtime_ns),
    "riskRows": data[["date", "city", "district", *FACTORS]].values.tolist(),
    "endDate": data["date"].max(),
    "startDate": data["date"].min(),
    "factorNames": list(FACTORS.values()),
    "factorShortNames": list(FACTORS.values()),
    "weights": list(DEFAULT_WEIGHTS.values()),
    "thresholds": THRESHOLDS,
    "factorColors": FACTOR_COLORS,
    "months": sorted(data["date"].str[:7].unique().tolist()),
}
node = shutil.which("node")
if node is None:
    raise RuntimeError(
        "JavaScript 계산 검증에는 Node.js가 필요합니다. Node.js를 설치하고 다시 실행하세요."
    )
with tempfile.TemporaryDirectory() as directory:
    payload = Path(directory) / "payload.json"
    payload.write_text(json.dumps(boot, ensure_ascii=False), encoding="utf-8")
    subprocess.run(
        [str(node), str(Path(__file__).with_suffix(".cjs")), str(payload)], check=True
    )

print("PASS: Python entry, CSV calculations, JavaScript syntax")
