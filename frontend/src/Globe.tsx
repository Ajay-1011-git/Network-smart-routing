import { useMemo } from 'react';

// Original ASCII-style globe: projected meridians, latitude rings and coarse
// continent silhouettes expressed as point density, following DESIGN.md.
export function Globe({compact=false}: {compact?:boolean}) {
  const points = useMemo(() => {
    const result: {x:number;y:number;land:boolean;z:number}[] = [];
    const ellipses = [[-105,44,42,24],[-72,8,18,30],[-59,-27,19,29],[15,49,34,19],[20,7,25,33],[72,43,58,24],[106,10,32,17],[134,-25,21,16],[47,-20,7,15]];
    for (let latitude=-76; latitude<=76; latitude+=5) for (let longitude=-180;longitude<180;longitude+=5) {
      const lon=(longitude+15)*Math.PI/180, lat=latitude*Math.PI/180;
      const z=Math.cos(lat)*Math.cos(lon);
      if (z<-.08) continue;
      const land=ellipses.some(([cx,cy,rx,ry]) => ((longitude-cx)/rx)**2+((latitude-cy)/ry)**2 < 1);
      result.push({x:120+Math.cos(lat)*Math.sin(lon)*108,y:120-Math.sin(lat)*108,land,z});
    }
    return result;
  }, []);
  return <svg className={`ascii-globe ${compact?'compact':''}`} viewBox="0 0 240 240" role="img" aria-label="ASCII-inspired network globe">
    <circle cx="120" cy="120" r="109" fill="none" stroke="currentColor" strokeOpacity=".22"/>
    <g aria-hidden="true">{points.map((p,i) => p.land ? <text key={i} x={p.x} y={p.y} fontSize="4.8" textAnchor="middle" opacity={.36+p.z*.6}>{['+','·',':'][i%3]}</text> :
      <rect key={i} x={p.x} y={p.y} width=".8" height=".8" opacity={.08+p.z*.1}/>)}</g>
    <ellipse cx="120" cy="120" rx="109" ry="33" fill="none" stroke="currentColor" strokeOpacity=".15" transform="rotate(-18 120 120)"/>
    <circle cx="177" cy="65" r="2.8" fill="#7fd579"/><circle cx="177" cy="65" r="7" fill="none" stroke="#7fd579" strokeOpacity=".45"/>
  </svg>;
}
