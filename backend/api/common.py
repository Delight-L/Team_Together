"""여러 API에서 함께 쓰는 도구: 요청·응답 형태, 분석 자료 읽기, 지역 권한 검사."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.db import analysis_repository, group_repository

# 경로는 현재 터미널 폴더가 아니라 이 파일 위치를 기준으로 계산합니다.
ROOT = Path(__file__).resolve().parents[2]
MAP_FILE = ROOT / 'backend' / 'resources' / 'data' / 'map_boundaries.json'
ANALYZED_CITY = '강남구'  # 동별 분석 결과가 연결된 지역


class Request:
    """API 함수가 받는 요청 정보입니다.

    params: GET은 주소의 ?a=1&b=2 값, POST는 보낸 JSON 내용
    user: 로그인한 사용자(로그인 전에 쓰는 API에서는 None)
    session_token: 브라우저 쿠키의 세션 토큰
    """

    def __init__(self, params, user, session_token):
        self.params = params
        self.user = user
        self.session_token = session_token

    def text(self, name):
        """요청 값 하나를 앞뒤 공백을 지운 문자열로 꺼냅니다. 없으면 빈 문자열입니다."""
        return str(self.params.get(name, '')).strip()


class Response:
    """JSON 대신 상태 코드·쿠키·파일 이름을 함께 정해야 할 때 쓰는 응답입니다.

    API 함수가 dict를 돌려주면 상태 200의 JSON 응답으로 보냅니다.
    payload가 bytes이고 filename이 있으면 Word 파일로 내려받게 합니다.
    """

    def __init__(self, payload, status=200, cookie=None, filename=None):
        self.payload = payload
        self.status = status
        self.cookie = cookie
        self.filename = filename


class StreamResponse:
    """보미 «복지사업 찾기»처럼 답변을 글자 단위로 이어서 보내는 응답입니다."""

    def __init__(self, events):
        self.events = events


class ApiError(Exception):
    """401·400 이외의 상태 코드(예: 503)로 오류를 알려야 할 때 씁니다."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def dashboard_data():
    """화면에 필요한 동별 분석 결과와 지도 경계를 한 번에 읽습니다.

    분석 결과는 DB를 먼저 읽고, 실패하면 저장소의 CSV를 읽습니다(analysis_repository 참고).
    """
    data = analysis_repository.load_analysis2_data()
    data['geometry'] = json.loads(MAP_FILE.read_text(encoding='utf-8'))

    months = set()
    for row in data['assessment']:
        months.add(row['기준연월'])
    data['months'] = sorted(months)

    seoul = ZoneInfo('Asia/Seoul')
    data['dataCheckedAt'] = datetime.now(seoul).isoformat(timespec='seconds')
    # 결과 버전이 'analysis2-숫자'이면 숫자가 분석 파일을 바꾼 시각(나노초)입니다.
    run_id = str(data.get('runId', ''))
    if run_id.startswith('analysis2-') and run_id[10:].isdigit():
        changed = datetime.fromtimestamp(int(run_id[10:]) / 1e9, seoul)
        data['analysisFileModifiedAt'] = changed.isoformat(timespec='seconds')
    return data


def evidence_for(data, context):
    """선택한 지역·동·기준월의 분석 결과 행만 골라냅니다."""
    if context['city'] != ANALYZED_CITY:
        return []
    rows = []
    for row in data['assessment']:
        if row['기준연월'] == context['month'] and row['행정동명'] == context['district'] and (not context.get('age') or row.get('age_label') == context['age']):
            rows.append(row)
    return rows


def rows_for_month(data, context):
    """동을 고르지 않았을 때 쓰는, 그 달 전체 동의 분석 결과입니다."""
    if context['city'] != ANALYZED_CITY:
        return []
    rows = []
    for row in data['assessment']:
        if row['기준연월'] == context['month']:
            rows.append(row)
    return rows


def check_city_access(user, city):
    """관리자가 아니면 자기 소속 지역의 자료만 볼 수 있습니다."""
    if not user['admin'] and city != user['org']:
        raise PermissionError('소속 지역의 자료만 사용할 수 있습니다.')


def region_context(request, data, district_required=True):
    """요청의 지역·동·기준월을 검사해 업무 처리에 쓸 context를 만듭니다."""
    context = {
        'city': request.text('city'),
        'district': request.text('district'),
        'month': request.text('month'),
    }
    age = request.text('age')
    if age:
        if age not in ['20대', '30대', '40대', '50대', '60대 이상']:
            raise ValueError('유효한 분석 연령대를 선택하세요.')
        context['age'] = age
    check_city_access(request.user, context['city'])
    if context['month'] not in data['months']:
        raise ValueError('유효한 기준월을 선택하세요.')

    district_names = set()
    for unit in data['geometry'].get(context['city'], {}).get('units', []):
        district_names.add(unit['n'])
    district_is_empty = context['district'] == ''
    if district_required or not district_is_empty:
        if context['district'] not in district_names:
            raise ValueError('행정동을 선택하세요.')

    context['user'] = request.user
    context['workflow_mode'] = 'live'
    return context


def group_context(request):
    """연령·성별 그룹 요청을 검사하고 (context, 그룹 상세 자료)를 돌려줍니다."""
    context = {}
    for name in ['city', 'code', 'month', 'age', 'sex']:
        context[name] = request.text(name)
    check_city_access(request.user, context['city'])
    detail = group_repository.group_detail(context)
    from backend.db.age_analysis_repository import detection_for
    detail['ageDetection'] = detection_for(context)
    context['district'] = detail['current']['district']
    return context, detail
