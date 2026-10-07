import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import boundaries from './data/administrative-regions.json';
import { Icon } from './components';

const palette = {
  quiet: ['#e8eef9', '#bdcde3', '#93aecb'],
  rose: ['#ff97b6', '#ff527f', '#ce3565'],
  orange: ['#ffe3a6', '#f4ba62', '#bd873a'],
  sky: ['#c2ddff', '#91baf0', '#6289bb'],
};
const tone = (region) => region.count ? region.status === '연속 후보' ? 'orange' : 'rose' : region.pending ? 'sky' : 'quiet';
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const constrain = (view) => {
  const horizontal = (view.zoom - 1) * 450 + 30;
  const vertical = (view.zoom - 1) * 300 + 25;
  return { ...view, x: clamp(view.x, -horizontal, horizontal), y: clamp(view.y, -vertical, vertical) };
};

// 실제 지형 높이가 아닌, 행정동 경계를 판 형태로 표현하는 입체 투영입니다.
// WGS84 경계와 실제 분석값을 사용하며, 높이는 후보 상태를 강조하는 시각 효과입니다.
export function ReliefMap({ geometry, regions, selected, onSelect }) {
  const [view, setView] = useState({ zoom: 1, x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const stageRef = useRef(null);
  const svgRef = useRef(null);
  const dragRef = useRef(null);
  const id = useId().replace(/:/g, '');
  const scene = useMemo(() => {
    const city = boundaries.features.find((feature) => geometry?.units.some((unit) => unit.n === feature.properties.name))?.properties.city;
    const features = boundaries.features.filter((feature) => feature.properties.city === city && geometry?.units.some((unit) => unit.n === feature.properties.name));
    if (!features.length) return { city, units: [] };
    const mercator = ([lng, lat]) => [lng, -Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) * 180 / Math.PI];
    const coordinates = (feature) => (feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates] : feature.geometry.coordinates);
    const points = features.flatMap((feature) => coordinates(feature).flat(2).map(mercator));
    const minX = Math.min(...points.map((point) => point[0])), minY = Math.min(...points.map((point) => point[1]));
    const skew = ([x, y]) => [(x - minX) - 0.22 * (y - minY), 0.14 * (x - minX) + 0.78 * (y - minY)];
    const projected = points.map(skew);
    const left = Math.min(...projected.map((point) => point[0])), top = Math.min(...projected.map((point) => point[1]));
    const width = Math.max(...projected.map((point) => point[0])) - left;
    const height = Math.max(...projected.map((point) => point[1])) - top;
    const scale = Math.min(740 / width, 490 / height);
    const project = (point) => {
      const [x, y] = skew(mercator(point));
      return [(900 - width * scale) / 2 + (x - left) * scale, 44 + (y - top) * scale];
    };
    const units = features.map((feature) => {
      const polygons = coordinates(feature).map((polygon) => polygon.map((ring) => ring.map(project)));
      const rings = polygons.flat();
      const path = rings.map((ring) => ring.map(([x, y], index) => `${index ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`).join('') + 'Z').join('');
      // 가장 큰 외곽 링의 면적 중심점을 라벨 위치로 사용합니다.
      const areas = polygons.map((polygon) => polygon[0].reduce((sum, point, index, ring) => {
        const next = ring[(index + 1) % ring.length];
        return sum + point[0] * next[1] - next[0] * point[1];
      }, 0));
      const ring = polygons[areas.reduce((largest, area, index) => Math.abs(area) > Math.abs(areas[largest]) ? index : largest, 0)][0];
      let area = 0, xSum = 0, ySum = 0;
      ring.forEach(([x, y], index) => {
        const [nx, ny] = ring[(index + 1) % ring.length];
        const cross = x * ny - nx * y;
        area += cross; xSum += (x + nx) * cross; ySum += (y + ny) * cross;
      });
      return { name: feature.properties.name, path, x: xSum / (3 * area), y: ySum / (3 * area) };
    }).sort((a, b) => a.y - b.y);
    return { city, units };
  }, [geometry]);
  const pointAt = (event) => {
    const svg = svgRef.current, matrix = svg?.getScreenCTM();
    if (!matrix) return null;
    const point = svg.createSVGPoint();
    point.x = event.clientX; point.y = event.clientY;
    return point.matrixTransform(matrix.inverse());
  };
  const zoomAt = (factor, point = { x: 450, y: 300 }) => setView((previous) => {
    const zoom = clamp(previous.zoom * factor, 1, 3), ratio = zoom / previous.zoom;
    return constrain({ zoom, x: point.x - 450 - (point.x - 450 - previous.x) * ratio,
      y: point.y - 300 - (point.y - 300 - previous.y) * ratio });
  });
  useEffect(() => { setView({ zoom: 1, x: 0, y: 0 }); }, [geometry]);
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const wheel = (event) => {
      const point = pointAt(event);
      if (!point) return;
      event.preventDefault();
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 500 : 1);
      zoomAt(Math.exp(-clamp(delta, -100, 100) * 0.002), point);
    };
    stage.addEventListener('wheel', wheel, { passive: false });
    return () => stage.removeEventListener('wheel', wheel);
  }, [geometry]);
  const rows = new Map(regions.map((region) => [region.name, region]));
  const priorities = regions.filter((region) => region.count).sort((a, b) => (a.minZ ?? Infinity) - (b.minZ ?? Infinity));
  const choose = (event, name) => { if (event.type !== 'click' || !dragRef.current?.moved) onSelect(name); };
  if (!scene.units.length) return <div className="empty">연결된 지도 경계가 없습니다.</div>;
  return (
    <div className={`mission-map relief-map ${dragging ? 'dragging' : ''}`} ref={stageRef}>
      <div className="map-tools">
        <button onClick={() => zoomAt(1.2)} aria-label="지도 확대">+</button>
        <button onClick={() => zoomAt(1 / 1.2)} aria-label="지도 축소">−</button>
        <button onClick={() => setView({ zoom: 1, x: 0, y: 0 })} aria-label="지도 배율 초기화"><Icon name="map" size={15} /></button>
      </div>
      <svg ref={svgRef} viewBox="0 0 900 600" className="relief-scene" role="group" aria-label={`${scene.city} 행정동 입체 확인 후보 지도`}
        onDragStart={(event) => event.preventDefault()}
        onPointerDown={(event) => {
          if (event.button !== 0) return;
          event.preventDefault();
          const point = pointAt(event);
          if (point) dragRef.current = { point, moved: false, pointerId: event.pointerId };
        }}
        onPointerMove={(event) => {
          const drag = dragRef.current;
          if (!drag || drag.pointerId !== event.pointerId || !event.buttons) return;
          const point = pointAt(event);
          if (!point) return;
          const x = point.x - drag.point.x, y = point.y - drag.point.y;
          if (!drag.moved && Math.hypot(x, y) < 4) return;
          drag.moved = true; drag.point = point;
          event.currentTarget.setPointerCapture(event.pointerId); setDragging(true);
          setView((previous) => constrain({ ...previous, x: previous.x + x, y: previous.y + y }));
        }}
        onPointerUp={(event) => {
          setDragging(false);
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
        }} onPointerCancel={() => { dragRef.current = null; setDragging(false); }}>
        <defs>
          {Object.entries(palette).map(([color, values]) => <linearGradient id={`${id}-${color}`} key={color} x1="0" y1="0" x2="1" y2="1">
            <stop stopColor={values[0]} /><stop offset="1" stopColor={values[1]} />
          </linearGradient>)}
          <filter id={`${id}-shadow`} x="-30%" y="-30%" width="160%" height="180%"><feDropShadow dx="2" dy="15" stdDeviation="9" floodColor="#3c527b" floodOpacity=".24" /></filter>
          <filter id={`${id}-glow`} x="-40%" y="-40%" width="180%" height="180%"><feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#70dcff" floodOpacity=".65" /></filter>
          <filter id={`${id}-rose-glow`} x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="3" stdDeviation="6" floodColor="#ff527f" floodOpacity=".55" /></filter>
        </defs>
        <g transform={`translate(${450 + view.x} ${300 + view.y}) scale(${view.zoom}) translate(-450 -300)`}>
          <g aria-hidden="true" filter={`url(#${id}-shadow)`}>
            {scene.units.map((unit) => <path key={unit.name} d={unit.path} transform="translate(0 20)" fill="#a4bad3" stroke="#a4bad3" strokeWidth="1" />)}
          </g>
          {scene.units.map((unit) => {
            const region = rows.get(unit.name);
            if (!region) return null;
            const color = tone(region), lift = region.count ? 15 : selected === unit.name ? 8 : 0;
            return <g key={unit.name} className={`relief-district ${selected === unit.name ? 'selected' : ''} ${region.count ? 'candidate' : ''}`}
              role="button" tabIndex="0" aria-label={`${unit.name}, ${region.status}, 후보 ${region.count}개`} aria-pressed={selected === unit.name}
              onClick={(event) => choose(event, unit.name)} onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(event, unit.name); }
              }}>
              <title>{unit.name} · {region.status}</title>
              {/* 같은 경계를 층으로 쌓아 판의 측면을 표현합니다. 높이는 분석 수치가 아닙니다. */}
              {[20, 16, 12, 8, 4, 0, -4, -8, -12].filter((level) => level >= -lift).map((level) =>
                <path key={level} d={unit.path} transform={`translate(0 ${level})`} fill={palette[color][2]} stroke={palette[color][2]} strokeWidth="1" fillRule="evenodd" aria-hidden="true" />)}
              <path d={unit.path} transform="translate(0 17)" fill="none" stroke="#b0edff" strokeWidth="2" filter={`url(#${id}-glow)`} aria-hidden="true" />
              <path className="relief-top" d={unit.path} transform={`translate(0 ${-lift})`} fill={`url(#${id}-${color})`} stroke="#ffffff" strokeWidth="2" strokeLinejoin="round" fillRule="evenodd" filter={region.count ? `url(#${id}-rose-glow)` : undefined} />
              <text x={unit.x} y={unit.y - lift} textAnchor="middle" dominantBaseline="middle">{unit.name}</text>
            </g>;
          })}
          {scene.units.filter((unit) => priorities.slice(0, 3).some((region) => region.name === unit.name)).map((unit) => {
            const region = rows.get(unit.name), color = palette[tone(region)][2];
            const x = unit.x, y = unit.y - 48;
            const labelX = x > 640 ? -175 : 24;
            return <g key={unit.name} className="relief-priority" transform={`translate(${x} ${y})`} role="button" tabIndex="0" aria-label={`${unit.name} ${region.status} 상세`}
              onClick={(event) => choose(event, unit.name)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(event, unit.name); } }}>
              <circle r="16" fill={color} stroke="white" strokeWidth="3" /><text textAnchor="middle" dominantBaseline="middle" fill="white" fontSize="16" fontWeight="800">{priorities.indexOf(region) + 1}</text>
              <rect x={labelX} y="-24" width="150" height="76" rx="12" fill="white" stroke="#dce4f3" />
              <text x={labelX + 12} y="-5" fill="#18334f" fontSize="13" fontWeight="700">{unit.name}</text>
              <text x={labelX + 12} y="13" fill={color} fontSize="10">{region.status} · {region.count}개 지표</text>
              <rect x={labelX + 10} y="25" width="130" height="20" rx="7" fill="#edf3ff" />
              <text x={labelX + 75} y="39" textAnchor="middle" fill="#3168da" fontSize="10">상세 보기 →</text>
            </g>;
          })}
        </g>
      </svg>
      <div className="map-jurisdiction">{scene.city} 관할 지역 <span>{scene.units.length}개 {scene.city.endsWith('구') ? '행정동' : '읍면동'}</span></div>
      <div className="map-zoom-hint"><span>휠로 확대·축소 · 끌어서 이동</span><output aria-label="지도 배율">{Math.round(view.zoom * 100)}%</output></div>
      <div className="relief-map-note">높이는 시각 효과 · 경계: <a href="https://sgis.kostat.go.kr" target="_blank" rel="noopener noreferrer">SGIS</a> / <a href="https://github.com/vuski/admdongkor" target="_blank" rel="noopener noreferrer">admdongkor</a> · CC BY 4.0</div>
    </div>
  );
}
