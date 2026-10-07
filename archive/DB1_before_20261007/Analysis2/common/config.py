# common/config.py

"""
DB1 Analysis2 configuration

Colab에서 검증한 Analysis2 방법론의 주요 설정값을 관리한다.
"""

# --------------------------------------------------
# 기본 데이터 구조
# --------------------------------------------------

EXPECTED_AREAS = 22
EXPECTED_MONTHS = 48

START_DATE = "2022-01-01"
END_DATE = "2025-12-01"


# --------------------------------------------------
# Key columns
# --------------------------------------------------

DATE_COLUMN = "date"
AREA_CODE_COLUMN = "행정동코드"
AREA_NAME_COLUMN = "행정동"

KEY_COLUMNS = [
    DATE_COLUMN,
    AREA_CODE_COLUMN,
]


# --------------------------------------------------
# Detection Core
# --------------------------------------------------

COMMUNICATION_COLUMNS = [
    "call_contacts",
    "text_contacts",
]

MOBILITY_COLUMNS = [
    "weekday_move_count",
    "weekend_move_count",
]

DETECTION_CORE_COLUMNS = (
    COMMUNICATION_COLUMNS
    + MOBILITY_COLUMNS
)


# --------------------------------------------------
# Evidence
# --------------------------------------------------

MOBILITY_EVIDENCE_COLUMNS = [
    "weekday_move_distance",
    "weekend_move_distance",
]


# --------------------------------------------------
# Validation
# --------------------------------------------------

INTEREST_VALIDATION_COLUMNS = [
    "comm_low_rate",
    "weekday_outing_low_rate",
    "weekend_outing_low_rate",
]

STRUCTURAL_ISSUE_COLUMN = "interest_structural_issue"


# --------------------------------------------------
# QC
# --------------------------------------------------

QC_COLUMNS = [
    "weekday_count_est_ratio",
    "weekday_distance_est_ratio",
    "weekend_count_est_ratio",
    "weekend_distance_est_ratio",
]


# --------------------------------------------------
# External Context
# --------------------------------------------------

WEATHER_COLUMNS = [
    "rain_days",
    "rainfall_mm",
    "snow_days",
]

CALENDAR_COLUMNS = [
    "days_in_month",
    "weekday_days",
    "weekend_days",
]


# --------------------------------------------------
# Detection parameters
# --------------------------------------------------

# Historical-only Expanding Robust Z 계산에 필요한
# 최소 과거 Residual 개수
MIN_HISTORY = 12

# 최종 sensitivity analysis를 통해 선택한 운영 임계값
ROBUST_Z_THRESHOLD = -2.0

# Robust Z = 0.6745 * (x - median) / MAD
ROBUST_Z_SCALE = 0.6745


# --------------------------------------------------
# Expected input size
# --------------------------------------------------

EXPECTED_ROWS = EXPECTED_AREAS * EXPECTED_MONTHS