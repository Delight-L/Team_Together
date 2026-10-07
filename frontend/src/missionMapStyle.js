// 행정동 경계와 분석값은 로컬 자료이며, 도로 배경만 OpenFreeMap에서 가져옵니다.
export const MAP_COLORS = {
  background: '#f7f9fc', park: '#e0efe7', water: '#dcecf8',
  quiet: '#b9cec7', rose: '#f36e91', orange: '#eda65d', sky: '#78a9ed', blue: '#3978d6',
};

export function regionColor(region) {
  return region.status === '연속 후보' ? MAP_COLORS.orange
    : region.count > 0 ? MAP_COLORS.rose : region.pending ? MAP_COLORS.sky : MAP_COLORS.quiet;
}

export function geometryBounds(geometry) {
  const bounds = [[Infinity, Infinity], [-Infinity, -Infinity]];
  const visit = (coordinates) => {
    if (typeof coordinates[0] === 'number') {
      bounds[0][0] = Math.min(bounds[0][0], coordinates[0]);
      bounds[0][1] = Math.min(bounds[0][1], coordinates[1]);
      bounds[1][0] = Math.max(bounds[1][0], coordinates[0]);
      bounds[1][1] = Math.max(bounds[1][1], coordinates[1]);
    } else coordinates.forEach(visit);
  };
  visit(geometry.coordinates);
  return bounds;
}

export function featureBounds(features) {
  return geometryBounds({ coordinates: features.map((feature) => feature.geometry.coordinates) });
}

export function districtData(features, regions, selected) {
  const byName = new Map(regions.map((region) => [region.name, region]));
  return {
    type: 'FeatureCollection',
    features: features.filter((feature) => byName.has(feature.properties.name)).map((feature) => {
      const region = byName.get(feature.properties.name);
      return { ...feature, id: feature.properties.name, properties: {
        ...feature.properties, color: regionColor(region), selected: region.name === selected,
        fillOpacity: region.count > 0 ? 0.27 : region.pending ? 0.17 : 0.07,
        lineColor: region.count > 0 || region.pending ? regionColor(region) : '#a4b6c4',
        lineWidth: region.count > 0 ? 2 : 1,
      } };
    }),
  };
}

export function createMapStyle(data, sourceUrl = 'https://tiles.openfreemap.org/planet') {
  const base = { source: 'basemap' };
  const road = { ...base, type: 'line', 'source-layer': 'transportation',
    layout: { 'line-cap': 'round', 'line-join': 'round' } };
  const roadFilter = (classes) => ['all', ['==', ['geometry-type'], 'LineString'],
    ['match', ['get', 'class'], classes, true, false]];
  return {
    version: 8,
    glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    sources: {
      basemap: { type: 'vector', url: sourceUrl,
        attribution: '<a href="https://openfreemap.org/" target="_blank" rel="noopener noreferrer">OpenFreeMap</a> · <a href="https://openmaptiles.org/" target="_blank" rel="noopener noreferrer">OpenMapTiles</a> · © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a>' },
      districts: { type: 'geojson', data },
    },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': MAP_COLORS.background } },
      { id: 'parks', ...base, type: 'fill', 'source-layer': 'park', paint: { 'fill-color': MAP_COLORS.park } },
      { id: 'woods', ...base, type: 'fill', 'source-layer': 'landcover',
        filter: ['==', ['get', 'class'], 'wood'], paint: { 'fill-color': MAP_COLORS.park, 'fill-opacity': 0.7 } },
      { id: 'water', ...base, type: 'fill', 'source-layer': 'water', paint: { 'fill-color': MAP_COLORS.water } },
      { id: 'waterways', ...base, type: 'line', 'source-layer': 'waterway',
        paint: { 'line-color': MAP_COLORS.water, 'line-width': 1.5 } },
      { id: 'buildings', ...base, type: 'fill', 'source-layer': 'building', minzoom: 14,
        paint: { 'fill-color': '#e8ecf1', 'fill-opacity': 0.65 } },
      { id: 'small-roads', ...road, minzoom: 12, filter: roadFilter(['minor', 'service', 'track']),
        paint: { 'line-color': '#e4e9ef', 'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.4, 17, 2.5] } },
      { id: 'road-edges', ...road, filter: roadFilter(['motorway', 'trunk', 'primary', 'secondary', 'tertiary']),
        paint: { 'line-color': '#e2e8ef', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 15, 5, 18, 12] } },
      { id: 'main-roads', ...road, filter: roadFilter(['motorway', 'trunk', 'primary', 'secondary', 'tertiary']),
        paint: { 'line-color': '#ffffff', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.5, 15, 3, 18, 9] } },
      { id: 'district-fill', source: 'districts', type: 'fill', paint: {
        'fill-color': ['case', ['get', 'selected'], '#a9c9fb', ['get', 'color']],
        'fill-opacity': ['case', ['get', 'selected'], 0.28, ['get', 'fillOpacity']],
      } },
      { id: 'district-lines', source: 'districts', type: 'line', layout: { 'line-join': 'round' },
        paint: { 'line-color': ['get', 'lineColor'], 'line-width': ['get', 'lineWidth'], 'line-opacity': 0.9 } },
      { id: 'district-selected', source: 'districts', type: 'line', filter: ['==', ['get', 'selected'], true],
        paint: { 'line-color': MAP_COLORS.blue, 'line-width': 3 } },
      { id: 'road-names', ...base, type: 'symbol', 'source-layer': 'transportation_name', minzoom: 14,
        layout: { 'symbol-placement': 'line', 'text-field': ['coalesce', ['get', 'name'], ['get', 'name:nonlatin'], ''],
          'text-font': ['Noto Sans Regular'], 'text-size': 10, 'text-max-angle': 25 },
        paint: { 'text-color': '#97a5b4', 'text-halo-color': '#ffffff', 'text-halo-width': 1.5 } },
    ],
  };
}
