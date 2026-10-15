import React,{useEffect,useMemo,useRef,useState} from 'react';
import {Map as MapLibreMap,Marker,AttributionControl,setWorkerUrl} from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import 'maplibre-gl/dist/maplibre-gl.css';
import boundaries from './data/administrative-regions.json';
import {createMapStyle,featureBounds} from './missionMapStyle';
import {CLUSTER_COLORS,boundaryCenter} from './regionInsights.mjs';
setWorkerUrl(workerUrl);

function mappedFeatures(regions,selected){
 const byName=new Map(regions.map(r=>[r.name,r]));
 return boundaries.features.filter(f=>f.properties.city==='강남구'&&byName.has(f.properties.name)).map(f=>({...f,properties:{...f.properties,color:CLUSTER_COLORS[byName.get(f.properties.name).cluster],fillOpacity:.65,lineColor:'#ffffff',lineWidth:1.4,selected:f.properties.name===selected}}));
}
function FallbackMap({features,selected,onSelect}){
 const merc=([x,y])=>[x,-Math.log(Math.tan(Math.PI/4+y*Math.PI/360))*180/Math.PI];
 const rings=f=>(f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates]).flat();
 const points=features.flatMap(f=>rings(f).flat().map(merc));
 const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
 const minX=Math.min(...xs),minY=Math.min(...ys),w=Math.max(...xs)-minX,h=Math.max(...ys)-minY,scale=Math.min(680/w,520/h);
 const project=p=>{const [x,y]=merc(p);return [60+(680-w*scale)/2+(x-minX)*scale,30+(520-h*scale)/2+(y-minY)*scale];};
 return <svg className="ri-fallback-map" viewBox="0 0 800 590" aria-label="원본 행정동 경계 지도">{features.map(f=>{const name=f.properties.name;const path=rings(f).map(r=>r.map((p,i)=>`${i?'L':'M'}${project(p).join(' ')}`).join('')+'Z').join('');const [x,y]=project(boundaryCenter(f));return <g key={name} role="button" tabIndex={0} aria-label={name} onClick={()=>onSelect(name)} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect(name);}}}><path d={path} fill={f.properties.color} stroke={name===selected?'#155bd8':'#fff'} strokeWidth={name===selected?3:1.5}/><text x={x} y={y} textAnchor="middle" paintOrder="stroke" stroke="white" strokeWidth="5" fill="#243b5f" fontSize="13">{name}</text></g>;})}</svg>;
}
export default function ClusterMap({regions,selected,onSelect}){
 const container=useRef(null),mapRef=useRef(null),latest=useRef({regions,selected,onSelect});
 latest.current={regions,selected,onSelect};
 const [failed,setFailed]=useState(false),[ready,setReady]=useState(false);
 const features=useMemo(()=>mappedFeatures(regions,selected),[regions,selected]);
 const signature=regions.map(r=>r.name).join('/');
 useEffect(()=>{
  if(!features.length||!container.current)return;
  let map;const markers=[];setReady(false);setFailed(false);
  try{
   const initial=mappedFeatures(latest.current.regions,latest.current.selected);
   const style=createMapStyle({type:'FeatureCollection',features:initial});
   const fill=style.layers.find(l=>l.id==='district-fill');fill.paint['fill-color']=['get','color'];fill.paint['fill-opacity']=['get','fillOpacity'];
   map=new MapLibreMap({container:container.current,style,center:[127.065,37.5],zoom:11,dragRotate:false,pitchWithRotate:false,attributionControl:false});
   mapRef.current=map;map.touchZoomRotate.disableRotation();
   map.addControl(new AttributionControl({compact:true,customAttribution:'경계: SGIS / admdongkor · CC BY 4.0'}),'bottom-right');
   // 출처 표시는 라이선스상 남기되, 넓은 지도에서도 펼쳐지지 않게 항상 접어 둡니다(ⓘ를 누르면 펼쳐짐).
   const foldAttribution=()=>{const a=container.current?.querySelector('.maplibregl-ctrl-attrib');a?.removeAttribute('open');a?.classList.remove('maplibregl-compact-show');};
   foldAttribution();
   const fit=()=>map.fitBounds(featureBounds(initial),{padding:{top:34,bottom:36,left:34,right:34},duration:0,maxZoom:12.5});
   map.on('load',()=>{
    fit();setReady(true);foldAttribution();
    for(const f of initial){const name=f.properties.name;const el=document.createElement('button');el.type='button';el.className='ri-map-label';el.textContent=name;el.setAttribute('aria-label',`지도에서 ${name} 선택`);el.addEventListener('click',()=>latest.current.onSelect(name));
     const marker=new Marker({element:el}).setLngLat(boundaryCenter(f)).addTo(map);markers.push({marker,el,name});}
    for(const {el,name} of markers){el.classList.toggle('selected',name===latest.current.selected);el.setAttribute('aria-pressed',String(name===latest.current.selected));}
   });
   map.on('click','district-fill',e=>{const n=e.features?.[0]?.properties.name;if(n)latest.current.onSelect(n);});
   map.on('mouseenter','district-fill',()=>map.getCanvas().style.cursor='pointer');
   map.on('mouseleave','district-fill',()=>map.getCanvas().style.cursor='');
   map.on('moveend',()=>{for(const {el,name} of markers){el.classList.toggle('selected',name===latest.current.selected);el.setAttribute('aria-pressed',String(name===latest.current.selected));}});
   const observer=new ResizeObserver(()=>{map.resize();fit();foldAttribution();});observer.observe(container.current);map._riResize=observer;
   map._riMarkers=markers;
  }catch{map?.remove();mapRef.current=null;setFailed(true);}
  return ()=>{map?._riResize?.disconnect();markers.forEach(m=>m.marker.remove());map?.remove();mapRef.current=null;};
 },[signature]);
 useEffect(()=>{const map=mapRef.current;if(!ready||!map?.getSource('districts'))return;map.getSource('districts').setData({type:'FeatureCollection',features});for(const {el,name} of map._riMarkers||[]){el.classList.toggle('selected',name===selected);el.setAttribute('aria-pressed',String(name===selected));}},[features,selected,ready]);
 if(!features.length)return <p>연결된 행정동 경계가 없습니다.</p>;
 if(failed)return <FallbackMap features={features} selected={selected} onSelect={onSelect}/>;
 return <div className="ri-map" aria-label="행정동별 지역 유형 지도"><div ref={container} className="ri-map-canvas"/><div className="ri-map-tools"><button aria-label="군집 지도 확대" onClick={()=>mapRef.current?.zoomIn()}>＋</button><button aria-label="군집 지도 축소" onClick={()=>mapRef.current?.zoomOut()}>−</button><button aria-label="군집 지도 전체 보기" onClick={()=>mapRef.current?.fitBounds(featureBounds(features),{padding:34,duration:0})}>⌂</button></div></div>;
}
