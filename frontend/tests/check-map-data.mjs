import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = JSON.parse(readFileSync(new URL('../src/data/administrative-regions.json', import.meta.url), 'utf8').replace(/^\uFEFF/, ''));
const existing = JSON.parse(readFileSync(new URL('../../dashboard/data/map_boundaries.json', import.meta.url), 'utf8'));
const identities = new Set();
assert.equal(source.type, 'FeatureCollection');

for (const feature of source.features) {
  const { city, name } = feature.properties;
  const key = `${city}/${name}`;
  assert(!identities.has(key), `중복 경계: ${key}`);
  identities.add(key);
  const { type, coordinates } = feature.geometry;
  assert(['Polygon', 'MultiPolygon'].includes(type), `지원하지 않는 경계: ${key}`);
  const polygons = type === 'Polygon' ? [coordinates] : coordinates;
  for (const polygon of polygons) {
    for (const ring of polygon) {
      assert(ring.length >= 4, `유효하지 않은 폴리곤: ${key}`);
      assert.deepEqual(ring[0], ring.at(-1), `닫히지 않은 경계: ${key}`);
      for (const [longitude, latitude] of ring) {
        assert(Number.isFinite(longitude) && Number.isFinite(latitude), `좌표 누락: ${key}`);
        assert(longitude > 126 && longitude < 129 && latitude > 37 && latitude < 39,
          `강남구·춘천시 범위를 벗어나는 WGS84 좌표: ${key}`);
      }
    }
  }
}
for (const [city, geometry] of Object.entries(existing)) {
  for (const unit of geometry.units) assert(identities.has(`${city}/${unit.n}`), `분석 지역의 도로 지도 경계 누락: ${city}/${unit.n}`);
}
assert.equal(identities.size, 47);
console.log('지도 경계 검증 통과: 47개 지역의 이름 매칭, WGS84 좌표, 폴리곤 유효성');
