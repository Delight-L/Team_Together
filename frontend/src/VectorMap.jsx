import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Map as MapLibreMap, Marker, AttributionControl, setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';
import boundaries from './data/administrative-regions.json';
import { Icon } from './components';
import { ReliefMap } from './ReliefMap';
import { createMapStyle, districtData, featureBounds, geometryBounds, regionColor } from './missionMapStyle';

setWorkerUrl(workerUrl);
const sourceUrl = import.meta.env.VITE_MAP_SOURCE_URL || 'https://tiles.openfreemap.org/planet';
const boundaryAttribution = '경계: <a href="https://sgis.kostat.go.kr" target="_blank" rel="noopener noreferrer">통계청 SGIS</a> / ' +
  '<a href="https://github.com/vuski/admdongkor" target="_blank" rel="noopener noreferrer">admdongkor</a> · CC BY 4.0';
const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export default function VectorMap({ regions, selected, onSelect, geometry, flat = false }) {
  const canvasRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef([]);
  const initialCamera = useRef(null);
  const latest = useRef({ regions, selected, onSelect });
  latest.current = { regions, selected, onSelect };
  const [ready, setReady] = useState(false);
  const [zoom, setZoom] = useState(null);
  const [baseError, setBaseError] = useState(false);
  const [renderError, setRenderError] = useState(false);
  const features = useMemo(() => {
    const names = new Set(geometry?.units?.map((unit) => unit.n) || []);
    const city = boundaries.features.find((feature) => names.has(feature.properties.name))?.properties.city;
    return boundaries.features.filter((feature) => feature.properties.city === city && names.has(feature.properties.name));
  }, [geometry]);
  const city = features[0]?.properties.city || '';

  useEffect(() => {
    if (!features.length || !canvasRef.current) return;
    setReady(false);
    setBaseError(false);
    setRenderError(false);
    let map;
    try {
      const bounds = featureBounds(features);
      const width = bounds[1][0] - bounds[0][0], height = bounds[1][1] - bounds[0][1];
      map = new MapLibreMap({
        container: canvasRef.current,
        style: createMapStyle(districtData(features, latest.current.regions, latest.current.selected), sourceUrl),
        center: [(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2],
        zoom: 10, minZoom: 7, maxZoom: 18, attributionControl: false,
        dragRotate: false, pitchWithRotate: false, touchPitch: false, renderWorldCopies: false,
        maxBounds: [[bounds[0][0] - width * 0.6, bounds[0][1] - height * 0.6],
          [bounds[1][0] + width * 0.6, bounds[1][1] + height * 0.6]],
      });
      map.touchZoomRotate.disableRotation();
      map.addControl(new AttributionControl({ compact: true, customAttribution: boundaryAttribution }), 'bottom-right');
      map.getCanvas().setAttribute('aria-label', `${city} 행정동 지도. 방향키로 이동하고 더하기·빼기 키로 확대·축소하세요.`);
      mapRef.current = map;
      const fitOverview = () => {
        const camera = map.cameraForBounds(bounds, { padding: { top: 60, bottom: 90, left: 42, right: 42 }, maxZoom: 12.6 });
        if (!camera) return;
        initialCamera.current = camera;
        map.jumpTo(camera);
        map.setMinZoom(Math.max(7, camera.zoom - 0.6));
      };
      fitOverview();
      map.on('style.load', () => setReady(true));
      map.on('error', (event) => {
        if (event.sourceId === 'basemap' || /openfreemap|fetch|network|ajax/i.test(event.error?.message || '')) setBaseError(true);
      });
      map.on('sourcedata', (event) => {
        if (event.sourceId === 'basemap' && event.sourceDataType === 'content') setBaseError(false);
      });
      map.on('zoomend', () => setZoom(map.getZoom()));
      map.on('click', 'district-fill', (event) => {
        const name = event.features?.[0]?.properties.name;
        if (name) latest.current.onSelect(name);
      });
      map.on('mouseenter', 'district-fill', () => { map.getCanvas().style.cursor = 'pointer'; });
      map.on('mouseleave', 'district-fill', () => { map.getCanvas().style.cursor = ''; });
      let previousSize = [canvasRef.current.clientWidth, canvasRef.current.clientHeight];
      const resize = new ResizeObserver(() => {
        map.resize();
        const size = [canvasRef.current?.clientWidth, canvasRef.current?.clientHeight];
        if (size[0] !== previousSize[0] || size[1] !== previousSize[1]) {
          previousSize = size;
          const camera = map.cameraForBounds(bounds, { padding: { top: 60, bottom: 90, left: 42, right: 42 }, maxZoom: 12.6 });
          if (camera) initialCamera.current = camera;
          if (!latest.current.selected) fitOverview();
        }
      });
      resize.observe(canvasRef.current);
      setZoom(map.getZoom());
      return () => {
        resize.disconnect();
        markersRef.current.forEach(({ marker }) => marker.remove());
        markersRef.current = [];
        map.remove();
        mapRef.current = null;
      };
    } catch {
      map?.remove();
      mapRef.current = null;
      setRenderError(true);
    }
  }, [features, city]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map?.getSource('districts')) return;
    map.getSource('districts').setData(districtData(features, regions, selected));
  }, [ready, features, regions, selected]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    markersRef.current.forEach(({ marker }) => marker.remove());
    const byName = new Map(regions.map((region) => [region.name, region]));
    const priorities = regions.filter((region) => region.count > 0)
      .sort((a, b) => (a.minZ ?? Infinity) - (b.minZ ?? Infinity)).slice(0, 3);
    markersRef.current = features.map((feature) => {
      const region = byName.get(feature.properties.name);
      if (!region) return null;
      const bounds = geometryBounds(feature.geometry);
      const button = document.createElement('button');
      button.type = 'button';
      const priority = priorities.findIndex((item) => item.name === region.name);
      button.className = priority >= 0 ? 'vector-priority-marker' : 'vector-district-marker';
      button.style.setProperty('--marker-color', regionColor(region));
      button.setAttribute('aria-label', `${region.name}, ${region.status}, 후보 ${region.count}개`);
      if (priority >= 0) {
        const badge = document.createElement('span');
        badge.className = 'vector-priority-number';
        badge.textContent = String(priority + 1);
        const label = document.createElement('span');
        const name = document.createElement('b');
        name.textContent = region.name;
        const note = document.createElement('small');
        note.textContent = `${region.status} · ${region.count}개 지표`;
        label.append(name, note);
        button.append(badge, label);
      } else button.textContent = region.name;
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        latest.current.onSelect(region.name);
      });
      const marker = new Marker({ element: button, anchor: 'center' })
        .setLngLat([(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2]).addTo(map);
      return { marker, button, name: region.name, priority };
    }).filter(Boolean);
    const updateLabels = () => {
      const threshold = (initialCamera.current?.zoom || 10) + 0.7;
      markersRef.current.forEach(({ button, name, priority }) => {
        const isSelected = name === latest.current.selected;
        const show = flat || priority >= 0 || isSelected || map.getZoom() > threshold ||
          /압구정|청담|신사|논현1|역삼1|대치1|도곡1|수서|세곡|소양|신북|동면|동내|남산|서면/.test(name);
        button.hidden = !show;
        button.classList.toggle('selected', isSelected);
        button.setAttribute('aria-pressed', String(isSelected));
      });
    };
    updateLabels();
    map.on('zoomend', updateLabels);
    return () => {
      map.off('zoomend', updateLabels);
      markersRef.current.forEach(({ marker }) => marker.remove());
      markersRef.current = [];
    };
  }, [ready, features, regions, flat]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    markersRef.current.forEach(({ name, button }) => {
      button.classList.toggle('selected', name === selected);
      button.setAttribute('aria-pressed', String(name === selected));
      if (name === selected) button.hidden = false;
    });
    const feature = features.find((item) => item.properties.name === selected);
    if (feature) {
      // 상세 카드는 지도 오른쪽에 열리므로 선택 지역을 왼쪽에 남겨 둡니다.
      const width = canvasRef.current.clientWidth;
      map.fitBounds(geometryBounds(feature.geometry), {
        padding: { top: 60, bottom: 90, left: 42, right: width > 600 ? Math.min(300, width * 0.4) : 42 },
        maxZoom: 14, duration: reduceMotion() ? 0 : 650,
      });
    } else if (initialCamera.current) map.easeTo({ ...initialCamera.current, padding: 0, duration: reduceMotion() ? 0 : 450 });
  }, [ready, features, selected]);

  const reset = () => {
    onSelect('');
    if (initialCamera.current) mapRef.current?.easeTo({ ...initialCamera.current, padding: 0, duration: reduceMotion() ? 0 : 450 });
  };
  if (!features.length) return <div className="empty">연결된 지도 경계가 없습니다.</div>;
  if (renderError) return <div className="vector-map-fallback">
    <ReliefMap geometry={geometry} regions={regions} selected={selected} onSelect={onSelect} />
    <p role="status">이 브라우저에서는 기본 지역 지도로 표시합니다.</p>
  </div>;
  return <div className="mission-map road-map vector-map" aria-label={`${city} 관할 지역 확인 후보 지도`}>
    <div className="road-map-canvas" ref={canvasRef} />
    <div className="map-tools">
      <button onClick={() => mapRef.current?.zoomIn()} aria-label="지도 확대">+</button>
      <button onClick={() => mapRef.current?.zoomOut()} aria-label="지도 축소">−</button>
      <button onClick={reset} aria-label="지도 배율 초기화"><Icon name="map" size={15} /></button>
    </div>
    {!flat && <label className="vector-region-picker"><Icon name="map" size={14} />
      <select aria-label="지도에서 지역 선택" value={selected || ''} onChange={(event) => onSelect(event.target.value)}>
        <option value="">{city} 전체 보기</option>
        {regions.map((region) => <option key={region.name} value={region.name}>{region.name} · {region.status}</option>)}
      </select>
    </label>}
    <div className="map-jurisdiction">{city} 관할 지역 <span>{features.length}개 {city.endsWith('구') ? '행정동' : '읍면동'}</span></div>
    <div className="map-zoom-hint"><span>휠로 확대·축소 · 끌어서 이동</span>
      <output aria-label="지도 확대 단계">{zoom === null ? '—' : `줌 ${zoom.toFixed(1)}`}</output></div>
    {baseError && <div className="map-tile-error" role="status">지도 배경을 불러오지 못했습니다. 지역 선택은 계속 사용할 수 있습니다.
      <button onClick={() => { setBaseError(false); mapRef.current?.refreshTiles('basemap'); }}>다시 불러오기</button>
    </div>}
  </div>;
}
