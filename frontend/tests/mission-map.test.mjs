import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { createMapStyle, districtData, featureBounds, geometryBounds, MAP_COLORS } from '../src/missionMapStyle.js';

const boundaries = JSON.parse(readFileSync(new URL('../src/data/administrative-regions.json', import.meta.url), 'utf8'));
const features = boundaries.features.filter((feature) => feature.properties.city === '강남구');
const regions = features.map((feature, index) => ({ name: feature.properties.name,
  status: index === 0 ? '신규 후보' : index === 1 ? '연속 후보' : index === 2 ? '판단 보류' : '기준 미해당',
  count: index < 2 ? 2 : 0, pending: index === 2 }));

test('MapLibre 좌표는 경도/위도 순서이며 두 도시의 모든 경계를 포함한다', () => {
  for (const city of ['강남구', '춘천시']) {
    const local = boundaries.features.filter((feature) => feature.properties.city === city);
    const bounds = featureBounds(local);
    assert(bounds[0][0] > 126 && bounds[1][0] < 129);
    assert(bounds[0][1] > 37 && bounds[1][1] < 39);
    for (const feature of local) {
      const district = geometryBounds(feature.geometry);
      for (let axis = 0; axis < 2; axis += 1) {
        assert(district[0][axis] >= bounds[0][axis]);
        assert(district[1][axis] <= bounds[1][axis]);
      }
    }
  }
});

test('행정동 식별자와 원본 좌표를 보존하고 분석 지역 밖의 사업 값은 포함하지 않는다', () => {
  const original = JSON.stringify(features);
  const data = districtData(features, regions.slice(0, 3), regions[1].name);
  assert.equal(data.features.length, 3);
  assert.equal(data.features.filter((feature) => feature.properties.selected).length, 1);
  assert.equal(data.features[1].id, regions[1].name);
  assert.equal(data.features[1].properties.color, MAP_COLORS.orange);
  assert.equal(data.features[0].properties.color, MAP_COLORS.rose);
  assert.equal(data.features[2].properties.color, MAP_COLORS.sky);
  assert.equal(JSON.stringify(features), original);
  assert.deepEqual(data.features[1].geometry, features[1].geometry);
});

test('월/선택 변경 시 오래된 선택 상태를 다음 데이터에 남기지 않는다', () => {
  const old = districtData(features, regions, regions[0].name);
  const updated = districtData(features, regions.map((region) => ({ ...region, count: 0, pending: false, status: '기준 미해당' })), '');
  assert(old.features[0].properties.selected);
  assert(updated.features.every((feature) => !feature.properties.selected && feature.properties.color === MAP_COLORS.quiet));
});

test('외부 도로 배경과 로컬 행정동 소스를 분리하여 배경 실패 시 지역을 유지한다', () => {
  const data = districtData(features, regions, '');
  const style = createMapStyle(data);
  assert.equal(style.sources.districts.type, 'geojson');
  assert.equal(style.sources.districts.data, data);
  assert.equal(style.sources.basemap.type, 'vector');
  for (const layer of style.layers.filter((item) => item.id.startsWith('district-'))) {
    assert.equal(layer.source, 'districts');
  }
  assert.equal(new Set(style.layers.map((layer) => layer.id)).size, style.layers.length);
});
