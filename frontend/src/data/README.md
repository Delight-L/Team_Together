# 도로 지도와 행정동 경계

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
