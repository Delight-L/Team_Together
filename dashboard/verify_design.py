"""원본 디자인용 CSV 연결·계산·컴포넌트 검증. 실제 화면 비교는 브라우저에서 확인합니다."""
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
import re

from streamlit.testing.v1 import AppTest
from settings import BASE_DIR, RISK_FILE, MAP_FILE, FACTORS, DEFAULT_WEIGHTS, FACTOR_COLORS, THRESHOLDS
from data_utils import load_risk_data, load_boundaries

# 브라우저를 열지 않고 Python 코드와 컴포넌트 등록에 오류가 없는지 확인합니다.
app = AppTest.from_file(str(BASE_DIR / "main.py"), default_timeout=30).run()
assert not app.exception, [item.message for item in app.exception]
assert not app.error, [item.value for item in app.error]

data = load_risk_data(RISK_FILE, RISK_FILE.stat().st_mtime_ns)
data["date"] = data["date"].dt.strftime("%Y-%m-%d")
boot = {
    "geometry": load_boundaries(MAP_FILE, MAP_FILE.stat().st_mtime_ns),
    "riskRows": data[["date", "city", "district", *FACTORS]].values.tolist(),
    "endDate": data["date"].max(), "startDate": data["date"].min(),
    "factorNames": list(FACTORS.values()), "factorShortNames": list(FACTORS.values()),
    "weights": list(DEFAULT_WEIGHTS.values()), "thresholds": THRESHOLDS,
    "factorColors": FACTOR_COLORS, "months": sorted(data["date"].str[:7].unique().tolist()),
}
node = shutil.which("node")
if node is None:
    raise RuntimeError("JavaScript 계산 검증에는 Node.js가 필요합니다. Node.js를 설치하고 다시 실행하세요.")
with tempfile.TemporaryDirectory() as directory:
    payload = Path(directory) / "payload.json"
    payload.write_text(json.dumps(boot, ensure_ascii=False), encoding="utf-8")
    subprocess.run([str(node), str(BASE_DIR / "verify_design.cjs"), str(payload)], check=True)

# CSS는 원본에서 root/body를 컴포넌트 컨테이너로 바꾼 부분 외에는 같습니다.
html = (BASE_DIR / "isolation-dashboard_260921.html").read_text(encoding="utf-8")
css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
css = css.replace(":root", ".dashboard-root")
css = re.sub(r"\bhtml\{", ".dashboard-root{", css)
css = re.sub(r"\bbody\{", ".dashboard-root{", css)
assert css in (BASE_DIR / "ui/style.css").read_text(encoding="utf-8")
body = html.split("<body>", 1)[1].split("<script>", 1)[0]
assert body in (BASE_DIR / "ui/layout.html").read_text(encoding="utf-8")
print("PASS: Python entry, original CSS/layout, CSV calculations, JavaScript syntax")
