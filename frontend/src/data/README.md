# 도로 지도와 행정동 경계

`administrative-regions.json`은 아래 공개 GeoJSON에서 강남구 22개 행정동과 춘천시 25개 읍면동을 추출한 WGS84 경계입니다. 속성은 city/name/code만 보존하고 좌표는 원본을 유지했습니다. 기존 map_boundaries.json의 모든 이름과 매칭했습니다.

- 버전: 2025-10-01
- 원본: https://github.com/vuski/admdongkor/blob/master/ver20251001/HangJeongDong_ver20251001.geojson
- 데이터 라이선스: https://github.com/vuski/admdongkor/blob/master/LICENSE-DATA
- 통계청 통계지리정보서비스(SGIS, https://sgis.kostat.go.kr)의 공공누리 제1유형 행정동 경계를 vuski/admdongkor가 가공한 데이터이며, 가공물은 CC BY 4.0으로 배포됩니다.

도로 배경은 OpenStreetMap 타일을 브라우저에서 표시합니다. 지도에 보이는 타일만 요청하며 캐시는 브라우저의 기본 HTTP 캐시를 사용합니다. 지도 출처는 지도 하단에 표시합니다.

`VITE_MAP_TILE_URL`과 `VITE_MAP_ATTRIBUTION` 빌드 환경변수로 다른 타일 공급자를 지정할 수 있습니다. 기본 공급자: https://tile.openstreetmap.org/{z}/{x}/{y}.png

확인: https://operations.osmfoundation.org/policies/tiles/

경계 버전은 화면의 월별 분석값과 별개입니다. 2025년 경계를 사용하며, 과거 월별 행정동 분할·통합을 소급 재계산하지 않습니다.
