"""파트 1. 자주 바꾸는 설정을 한곳에 모았습니다."""
from pathlib import Path

# __file__은 이 파일의 위치입니다. 다른 폴더에서 실행해도 데이터를 찾습니다.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
APP_TITLE = "고립예방 에이전트"

# 데이터 교체: 아래 경로를 바꾸거나, data 폴더의 CSV 내용을 교체하세요.
RISK_FILE = DATA_DIR / "risk_factors.csv"
GROUP_FILE = DATA_DIR / "group_signals.json"
MAP_FILE = DATA_DIR / "map_boundaries.json"

# 왼쪽은 CSV 열 이름, 오른쪽은 화면에 표시할 이름입니다.
# 모든 요인은 '값이 클수록 위험'인 0~100 점수로 준비합니다.
FACTORS = {
    "flow": "유동인구 감소", "card": "카드 결제 감소",
    "single": "1인 가구 비율", "elder": "고령 인구 비율",
    "welfare": "복지 연계 공백",
}
DEFAULT_WEIGHTS = {"flow": 25, "card": 25, "single": 20, "elder": 15, "welfare": 15}
FACTOR_COLORS = ["#2F7FA3", "#7060A8", "#C68B2C", "#4E9A76", "#B5527A"]

# 위험도 42 미만: 양호 / 42 이상: 주의 / 52 이상: 위험 / 60 이상: 심각
THRESHOLDS = [42, 52, 60]

# 대시보드 시연 계정입니다. 실제 인증용 계정 저장소가 아닙니다.
# 실제 서비스 전환 시 로그인 함수와 계정 관리를 인증 서비스로 교체하세요.
DEMO_ACCOUNTS = {
    "gangnam01": {"password": "demo1234", "org": "강남구", "admin": False},
    "chuncheon01": {"password": "demo1234", "org": "춘천시", "admin": False},
    "admin": {"password": "admin1234", "org": "전체 관리자", "admin": True},
}
