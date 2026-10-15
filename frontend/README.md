# 프런트엔드 개발 안내

React + Vite 화면입니다. 최초 Python·DB 설정은 [전체 실행 안내](../README.md#13-실행-방법)를 확인하세요.

## 설치와 실행

아래 명령은 `frontend` 폴더에서 실행합니다. 의존성을 변경하면 `package-lock.json`도 함께 저장합니다.

```powershell
npm ci
npm run dev
npm run build
```

개발 서버는 `http://127.0.0.1:5173`을 기본으로 사용합니다. 빌드한 화면을 Python 서버에서 확인하려면 프로젝트 루트에서 `python main.py`를 실행합니다.

## 구성과 확인

- `src/`: 화면·컴포넌트·스타일·지도 자료
- `tests/`: 화면 로직과 지도 검증
- `public/`: 정적 파일
- `vite.config.js`: 개발 서버와 빌드 설정

```powershell
npm run test:map
npm run test:briefing
```

디자인 기준은 [디자인 규칙](../docs/design-rules.md), 전체 폴더 역할은 [폴더 구성](../docs/folder-organization.md)을 참고하세요.

## 문서 목차

- [지도 자료와 출처](#map-data)

<a id="map-data"></a>

## 지도 자료와 출처

작업 기준 폴더: `frontend/src/data/`

`administrative-regions.json`은 아래 공개 GeoJSON에서 강남구 22개 행정동과 춘천시 25개 읍면동을 추출한 WGS84 경계입니다. 속성은 city/name/code만 보존하고 좌표는 원본을 유지했습니다. 기존 map_boundaries.json의 모든 이름과 매칭했습니다.

- 버전: 2025-10-01
- 원본: https://github.com/vuski/admdongkor/blob/master/ver20251001/HangJeongDong_ver20251001.geojson
- 데이터 라이선스: https://github.com/vuski/admdongkor/blob/master/LICENSE-DATA
- 통계청 통계지리정보서비스(SGIS, https://sgis.kostat.go.kr)의 공공누리 제1유형 행정동 경계를 vuski/admdongkor가 가공한 데이터이며, 가공물은 CC BY 4.0으로 배포됩니다.

도로 지도는 MapLibre GL JS로 표시합니다. `missionMapStyle.js`에 밝은 회색 배경, 민트색 공원, 하늘색 물, 흰 도로를 정의했으며 분석 상태는 기존 분홍/주황/파랑 구분을 유지합니다. 지역 선택은 기존 상세 카드·분석·챗봇의 공통 상태와 연결됩니다.

배경은 OpenFreeMap의 OpenMapTiles 호환 벡터 타일을 사용하며 별도 API 키가 필요하지 않습니다. 지도에 보이는 타일만 요청하고 출처는 지도 하단에 표시합니다. 외부 배경 로딩이 실패해도 로컬 행정동 경계와 지역 선택은 유지됩니다. WebGL을 사용할 수 없는 브라우저에서는 기존 기본 지역 지도로 전환합니다.

`VITE_MAP_SOURCE_URL` 빌드 환경변수로 OpenMapTiles 스키마의 다른 벡터 TileJSON URL을 지정할 수 있습니다. 기존 래스터 타일용 `VITE_MAP_TILE_URL`/`VITE_MAP_ATTRIBUTION`은 사용하지 않습니다. 기본 공급자: https://tiles.openfreemap.org/planet

공급자 안내: https://openfreemap.org/quick_start/

경계 버전은 화면의 월별 분석값과 별개입니다. 2025년 경계를 사용하며, 과거 월별 행정동 분할·통합을 소급 재계산하지 않습니다.
