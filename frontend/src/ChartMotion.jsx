import './chart-motion.css';
import React,{createContext,useContext,useEffect,useLayoutEffect,useState} from 'react';

const Progress=createContext(1);
const DURATION=1000;

// One clock keeps the visible case’s graphs synchronized; text always shows final values.
// Hidden cases, ordinary rerenders and resizes never start another animation.
export function ChartMotion({active=true,replayKey,children}) {
  const [reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [sample,setSample]=useState({key:replayKey,value:0});
  useEffect(()=>{
    const media=window.matchMedia('(prefers-reduced-motion: reduce)');
    const update=()=>setReduced(media.matches);
    media.addEventListener('change',update);
    return()=>media.removeEventListener('change',update);
  },[]);
  useLayoutEffect(()=>{
    if(!active||reduced)return;
    let frame,cancelled=false;
    const started=performance.now();
    setSample({key:replayKey,value:0});
    const tick=now=>{
      if(cancelled)return;
      const fraction=Math.max(0,Math.min(1,(now-started)/DURATION));
      setSample({key:replayKey,value:fraction===1?1:1-(1-fraction)**3});
      if(fraction<1)frame=requestAnimationFrame(tick);
    };
    frame=requestAnimationFrame(tick);
    return()=>{cancelled=true;cancelAnimationFrame(frame);};
  },[active,replayKey,reduced]);
  const value=!active||reduced?1:sample.key===replayKey?sample.value:0;
  return <Progress.Provider value={value}>{children}</Progress.Provider>;
}

export const useChartProgress=()=>useContext(Progress);
