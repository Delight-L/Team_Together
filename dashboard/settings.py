"""파트 1. 자주 바꾸는 설정을 한곳에 모았습니다."""
from pathlib import Path

# __file__은 이 파일의 위치입니다. 다른 폴더에서 실행해도 데이터를 찾습니다.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
APP_TITLE = "고립예방 에이전트"

# 데이터 교체: 아래 경로를 바꾸거나, data 폴더의 CSV 내용을 교체하세요.
RISK_FILE = DATA_DIR / "risk_factors.csv"
PEOPLE_FILE = DATA_DIR / "people.csv"
MAP_FILE = DATA_DIR / "map_boundaries.json"
DATA_LABEL = "샘플 데이터"  # 실제 자료로 교체한 뒤 출처에 맞게 수정하세요.

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
LEVEL_COLORS = {"양호": "#CFE4DC", "주의": "#F0D98C", "위험": "#E7935B", "심각": "#B02E4C"}
STATUSES = ["미배정", "방문 예정", "상담 완료", "모니터링"]
PAGES = ["종합 현황", "동별 분석", "대상자 관리", "조치 현황", "데이터 연계", "위험도 기준"]

# 원본 HTML과 같은 시연 계정입니다. 실제 인증용 계정 저장소가 아닙니다.
# 실제 서비스 전환 시 로그인 함수와 계정 관리를 인증 서비스로 교체하세요.
DEMO_ACCOUNTS = {
    "gangnam01": {"password": "demo1234", "org": "강남구", "admin": False},
    "chuncheon01": {"password": "demo1234", "org": "춘천시", "admin": False},
    "admin": {"password": "admin1234", "org": "전체 관리자", "admin": True},
}
