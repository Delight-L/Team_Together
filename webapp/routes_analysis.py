"""분석 자료 API: 화면 데이터, 관리자 활동 이력, 관리자 자료 업로드."""
import base64
import logging
import tempfile
from pathlib import Path

from db import analysis_repository
from webapp import sessions
from webapp.common import ANALYZED_CITY, ApiError, dashboard_data

MAX_FILE_BYTES = 15_000_000
MAX_TOTAL_BYTES = 20_000_000


def dashboard(request):
    """GET /api/dashboard: 지도 경계와 동별 분석 결과를 돌려줍니다.

    관리자가 아니면 자기 소속 지역의 지도만 보내고, 분석 결과가 없는 지역이면 결과를 비웁니다.
    """
    data = dashboard_data()
    user = request.user
    if not user['admin']:
        own_city = user['org']
        own_geometry = {}
        if own_city in data['geometry']:
            own_geometry[own_city] = data['geometry'][own_city]
        data['geometry'] = own_geometry
        if own_city != ANALYZED_CITY:
            data['assessment'] = []
            data['signals'] = []
            data['alerts'] = []
    return data


def activity(request):
    """GET /api/activity: 관리자에게 자료 반영 이력을 보여 줍니다."""
    if not request.user['admin']:
        raise PermissionError('관리자만 조회할 수 있습니다.')
    try:
        history = analysis_repository.load_dashboard_data().get('activity', [])
    except Exception:
        logging.exception('DB1 activity lookup failed')
        raise ApiError(503, 'DB1 활동 이력을 조회하지 못했습니다. DB 연결을 확인하세요.')
    return {'activity': history}


def read_uploaded_files(request):
    """업로드한 파일(base64 글자)을 (파일 이름, 내용 bytes) 목록으로 바꿉니다."""
    files = request.params.get('files', [])
    if not isinstance(files, list) or not 1 <= len(files) <= 5:
        raise ValueError('파일 1~5개를 선택하세요.')

    decoded = []
    total = 0
    for file in files:
        # 경로가 붙어 와도 파일 이름만 사용합니다.
        name = Path(str(file['name']).replace('\\', '/')).name
        if Path(name).suffix.lower() not in {'.csv', '.xlsx'}:
            raise ValueError('CSV/XLSX만 사용할 수 있습니다.')
        content = base64.b64decode(file['content'], validate=True)
        if len(content) > MAX_FILE_BYTES:
            raise ValueError('파일당 15MB 이하를 선택하세요.')
        decoded.append((name, content))
        total += len(content)
    if total > MAX_TOTAL_BYTES:
        raise ValueError('전체 파일은 20MB 이하를 선택하세요.')
    return decoded


def upload_validate(request):
    """POST /api/upload/validate: 관리자가 올린 자료를 검사하고 미리보기를 만듭니다.

    파일은 서버에 저장하지 않고, 검사에 성공하면 30분짜리 임시 초안만 만듭니다.
    """
    if not request.user['admin']:
        raise PermissionError('관리자만 자료를 반영할 수 있습니다.')
    files = read_uploaded_files(request)
    kind = request.params.get('kind')

    if kind == 'monthly':
        if len(files) != 1:
            raise ValueError('탐지 결과는 한 파일씩 검사하세요.')
        name, content = files[0]
        prepared = analysis_repository.monthly_upload(content, name)
    elif kind == 'structure':
        names = set()
        for name, content in files:
            names.add(name)
        if len(names) != len(files):
            raise ValueError('파일 이름이 중복되었습니다.')
        with tempfile.TemporaryDirectory(prefix='welfind-upload-') as folder:
            for name, content in files:
                (Path(folder) / name).write_bytes(content)
            prepared = analysis_repository.structure_upload(folder)
    else:
        raise ValueError('자료 종류를 선택하세요.')

    token = sessions.store_preview(request.user, 'upload', prepared)
    return {
        'token': token,
        'period': prepared['period'],
        'rows': len(prepared['data']),
        'preview': analysis_repository.records(prepared['data'].head(8)),
    }


def upload_publish(request):
    """POST /api/upload/publish: 검사한 자료를 DB에 반영합니다."""
    if not request.user['admin']:
        raise PermissionError('관리자만 자료를 반영할 수 있습니다.')
    token = request.params.get('token')
    with sessions.write_lock:
        prepared = sessions.get_preview(token, request.user, 'upload')
        run_id = analysis_repository.publish(prepared, request.user['id'])
        sessions.remove_preview(token)
    return {'runId': run_id}
