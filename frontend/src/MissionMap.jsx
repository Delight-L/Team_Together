import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import boundaries from './data/administrative-regions.json';
import { Icon } from './components';
import { ReliefMap } from './ReliefMap';

const statusColor = (region) => region.status === '연속 후보' ? '#f4922d'
  : region.count > 0 ? '#ff527b' : region.pending ? '#448bef' : '#8b9c91';
const tileUrl = import.meta.env.VITE_MAP_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const tileAttribution = import.meta.env.VITE_MAP_ATTRIBUTION ||
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors';

// WGS84 경계를 Leaflet이 도로 타일과 같은 좌표계로 투영합니다.
// 분석값과 선택 콜백은 기존 화면과 동일하며 드래그/휠 처리는 Leaflet에 맡깁니다.
export function MissionMap(props) {
  const [mode, setMode] = useState('road');
  if (!props.flat) return <OverviewMap {...props} />;
  return (
    <div className="mission-map-switchable">
      <div className="map-view-toggle" role="group" aria-label="지도 표현 방식">
        <button aria-pressed={mode === 'relief'} onClick={() => setMode('relief')}>입체</button>
        <button aria-pressed={mode === 'road'} onClick={() => setMode('road')}>도로</button>
      </div>
      {mode === 'relief' ? <ReliefMap {...props} /> : <RoadMap {...props} />}
    </div>
  );
}

function OverviewMap(props) {
  return <div className="single-overview quiet-road-overview">
    <RoadMap {...props} contextual />
  </div>;
}

function RoadMap({ regions, selected, onSelect, geometry, flat = false, overview = false, detail = false, focusedName, onFocusPoint, contextual = false }) {
  const canvasRef = useRef(null);
  const mapRef = useRef(null);
  const districtLayers = useRef([]);
  const focusBounds = useRef(null);
  const overviewZoom = useRef(0);
  const selectionRef = useRef(onSelect);
  const selectedRef = useRef(selected);
  const [zoom, setZoom] = useState(null);
  const [tileError, setTileError] = useState(false);
  const tileLayerRef = useRef(null);
  selectionRef.current = onSelect;
  selectedRef.current = selected;
  const features = useMemo(() => {
    const city = boundaries.features.find((feature) =>
      geometry?.units.some((unit) => unit.n === feature.properties.name))?.properties.city;
    return boundaries.features.filter((feature) => feature.properties.city === city &&
      geometry?.units.some((unit) => unit.n === feature.properties.name) && (!detail || feature.properties.name === focusedName));
  }, [geometry, detail, focusedName]);
  const city = features[0]?.properties.city || '';
  const style = (region, isSelected) => ({
    color: detail ? (region.count || region.pending ? statusColor(region) : '#344f69') : isSelected ? '#215eb8' : region.count || region.pending ? statusColor(region) : '#71869b',
    weight: isSelected ? 3 : region.count ? 2.5 : 1.3,
    dashArray: null,
    fillColor: overview && !region.count && !region.pending ? '#dce3ec' : statusColor(region),
    fillOpacity: overview ? 0.85 : region.count ? 0.22 : region.pending ? 0.1 : 0.025,
  });

  useEffect(() => {
    if (!features.length || !canvasRef.current) return;
    const map = L.map(canvasRef.current, {
      zoomControl: false, scrollWheelZoom: true, dragging: true,
      attributionControl: true, minZoom: 0, maxZoom: 18, maxBoundsViscosity: 1,
      zoomSnap: 0.25, zoomDelta: 0.5, wheelPxPerZoomLevel: 100,
    });
    mapRef.current = map;
    const tiles = L.tileLayer(tileUrl, { attribution: tileAttribution, maxZoom: 19, noWrap: true });
    if (!overview) tiles.addTo(map);
    tileLayerRef.current = tiles;
    let failures = 0;
    tiles.on('loading', () => { failures = 0; });
    tiles.on('tileerror', () => { failures += 1; setTileError(true); });
    tiles.on('load', () => setTileError(failures > 0));
    map.attributionControl.addAttribution(
      '경계: <a href="https://sgis.kostat.go.kr" target="_blank" rel="noopener noreferrer">통계청 SGIS</a> / ' +
      '<a href="https://github.com/vuski/admdongkor" target="_blank" rel="noopener noreferrer">admdongkor</a> · CC BY 4.0',
    );
    const updateZoom = () => setZoom(map.getZoom());
    map.on('zoomend', updateZoom);
    map.createPane('municipality-mask');
    map.getPane('municipality-mask').style.zIndex = '350';
    map.getPane('municipality-mask').style.pointerEvents = 'none';
    const resize = new ResizeObserver(() => {
      map.invalidateSize({ pan: false });
      if (focusBounds.current) {
        overviewZoom.current = Math.min(detail ? 16 : 13, map.getBoundsZoom(focusBounds.current, false, L.point(24, 40)));
        map.setMinZoom(overviewZoom.current);
      }
    });
    resize.observe(canvasRef.current);
    // 도로 배경은 지도 화면에 보이는 타일만 요청합니다.
    return () => {
      resize.disconnect();
      map.remove();
      mapRef.current = null;
      tileLayerRef.current = null;
      districtLayers.current = [];
    };
  }, [features, overview, detail]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !features.length) return;
    const group = L.featureGroup().addTo(map);
    districtLayers.current = [];
    const current = new Map(regions.map((region) => [region.name, region]));
    const candidates = regions.filter((region) => region.count > 0)
      .sort((a, b) => (a.minZ ?? Infinity) - (b.minZ ?? Infinity));
    // 외부 지역의 도로와 이름을 가리고 소속 지자체만 드러냅니다.
    // 각 폴리곤의 바깥/안쪽 링을 evenodd 구멍으로 사용해 경계를 보존합니다.
    const maskRings = features.flatMap((feature) => {
      const polygons = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
      return polygons.flatMap((polygon) => polygon.map((ring) => ring.map(([lng, lat]) => [lat, lng])));
    });
    const mask = L.polygon([
      [[85, -180], [85, 180], [-85, 180], [-85, -180]], ...maskRings,
    ], { pane: 'municipality-mask', fillColor: '#f5f7fa', fillOpacity: 1,
      stroke: false, interactive: false, fillRule: 'evenodd' }).addTo(map);
    // 두 동이 공유하는 선분은 제외하여 관할 외곽선만 굵게 표시합니다.
    const edges = new Map();
    features.forEach((feature) => {
      const polygons = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates;
      polygons.forEach((polygon) => polygon.forEach((ring) => {
        for (let i = 1; i < ring.length; i += 1) {
          const a = ring[i - 1], b = ring[i];
          const key = [a.join(','), b.join(',')].sort().join('|');
          if (edges.has(key)) edges.get(key).count += 1;
          else edges.set(key, { count: 1, points: [[a[1], a[0]], [b[1], b[0]]] });
        }
      }));
    });
    L.polyline([...edges.values()].filter((edge) => edge.count === 1).map((edge) => edge.points),
      { color: '#344f69', weight: 3, opacity: 0.9, interactive: false }).addTo(group);
    features.forEach((feature) => {
      const region = current.get(feature.properties.name);
      if (!region) return;
      const layer = L.geoJSON(feature, {
        style: style(region, region.name === selectedRef.current),
        onEachFeature: (_, polygon) => {
          polygon.on('click', () => selectionRef.current(region.name));
          polygon.on('add', () => {
            const path = polygon.getElement();
            if (!path) return;
            path.setAttribute('tabindex', '0');
            path.setAttribute('role', 'button');
            path.setAttribute('aria-label', `${region.name}, ${region.status}, 후보 ${region.count}개`);
            path.setAttribute('aria-pressed', String(region.name === selectedRef.current));
            L.DomEvent.on(path, 'keydown', (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                L.DomEvent.preventDefault(event);
                selectionRef.current(region.name);
              }
            });
          });
        },
      }).addTo(group);
      districtLayers.current.push({ region, layer });
      const center = layer.getBounds().getCenter();
      if (!detail && region.count > 0 && candidates.indexOf(region) < 3) {
        const pin = document.createElement('button');
        pin.type = 'button';
        pin.className = 'roadmap-pin';
        pin.style.setProperty('--pin-color', statusColor(region));
        pin.setAttribute('aria-label', `${region.name} ${region.status} 상세`);
        const badge = document.createElement('span');
        badge.className = 'roadmap-pin-number';
        badge.textContent = String(candidates.indexOf(region) + 1);
        badge.dataset.number = badge.textContent;
        const label = document.createElement('span');
        label.className = 'roadmap-pin-label';
        const name = document.createElement('b');
        name.textContent = region.name;
        const count = document.createElement('small');
        count.textContent = `${region.status} · ${region.count}개 지표`;
        label.append(name, count);
        if (!contextual) pin.append(badge);
        if (!overview) pin.append(label);
        L.marker(center, { icon: L.divIcon({ html: pin, className: 'roadmap-marker',
          iconSize: contextual ? [135, 44] : [190, 54], iconAnchor: contextual ? [-12, 38] : [19, 54] }), keyboard: false })
          .on('click', () => selectionRef.current(region.name)).addTo(group);
      } else if ((!overview && !contextual) || region.name === focusedName || /압구정|청담|신사|논현1|역삼1|대치1|도곡1|수서|세곡/.test(region.name)) {
        const label = document.createElement('span');
        label.textContent = region.name;
        layer.bindTooltip(label, { permanent: true, direction: 'center', className: 'roadmap-district-label' });
      }
    });
    const allBounds = group.getBounds();
    focusBounds.current = allBounds;
    overviewZoom.current = Math.min(detail ? 16 : 13, map.getBoundsZoom(allBounds, false, L.point(24, 40)));
    map.setMinZoom(overviewZoom.current);
    map.fitBounds(allBounds, { padding: [12, 20], maxZoom: detail ? 16 : 13, animate: false });
    map.setMaxBounds(allBounds.pad(0.08));
    setZoom(map.getZoom());
    return () => { map.removeLayer(mask); map.removeLayer(group); districtLayers.current = []; focusBounds.current = null; };
  }, [features, regions, flat, overview, detail, focusedName]);

  useEffect(() => {
    districtLayers.current.forEach(({ region, layer }) => {
      layer.setStyle(style(region, region.name === selected));
      layer.eachLayer((polygon) => polygon.getElement()?.setAttribute('aria-pressed', String(region.name === selected)));
    });
  }, [selected]);

  useEffect(() => {
    const map = mapRef.current;
    if (!overview || !map || !onFocusPoint) return;
    const update = () => {
      const district = districtLayers.current.find(({ region }) => region.name === focusedName);
      if (district) {
        const point = map.latLngToContainerPoint(district.layer.getBounds().getCenter());
        onFocusPoint({ x: point.x, y: point.y });
      }
    };
    update();
    map.on('moveend resize', update);
    return () => map.off('moveend resize', update);
  }, [features, regions, focusedName, overview, onFocusPoint]);

  if (!geometry || !features.length) return <div className="empty">연결된 지도 경계가 없습니다.</div>;
  return (
    <div className="mission-map road-map" aria-label={`${city} 관할 지역 확인 후보 지도`}>
      <div className="road-map-canvas" ref={canvasRef} />
      <div className="map-tools">
        <button onClick={() => mapRef.current?.zoomIn()} aria-label="지도 확대">+</button>
        <button onClick={() => mapRef.current?.zoomOut()} aria-label="지도 축소">−</button>
        <button onClick={() => mapRef.current?.fitBounds(focusBounds.current, { padding: [12, 20], maxZoom: detail ? 16 : 13, animate: false })} aria-label="지도 배율 초기화">
          <Icon name="map" size={15} />
        </button>
      </div>
      {!detail && <><div className="map-jurisdiction">{city} 관할 지역 <span>{features.length}개 {city.endsWith('구') ? '행정동' : '읍면동'}</span></div>
      <div className="map-zoom-hint"><span>휠로 확대·축소 · 끌어서 이동</span><output aria-label="지도 확대 단계">{zoom === null ? '—' : `줌 ${zoom}`}</output></div></>}
      {tileError && <div className="map-tile-error" role="status">도로 지도 일부를 불러오지 못했습니다.
        <button onClick={() => { setTileError(false); tileLayerRef.current?.redraw(); }}>다시 불러오기</button>
      </div>}
    </div>
  );
}

