import { memo } from 'react';
import { BaseEdge, EdgeLabelRenderer, Handle, Position, getBezierPath } from '@xyflow/react';
import type { EdgeProps, NodeProps } from '@xyflow/react';
import { DeviceIcon } from './Icons';
import type { CableEdge, DeviceNode } from './model';

export const Device = memo(function Device({data, selected}:NodeProps<DeviceNode>) {
  return <div className={`device-node ${selected?'is-selected':''}`}>
    <div className="device-hardware"><DeviceIcon kind={data.kind} size={29}/><span className="hardware-led"/></div>
    <div className="device-label">{data.label}</div><div className="device-ip">{data.address}</div>
    <Handle type="source" position={Position.Left} id="left" className="device-port"/>
    <Handle type="source" position={Position.Right} id="right" className="device-port"/>
    <Handle type="source" position={Position.Top} id="top" className="device-port"/>
    <Handle type="source" position={Position.Bottom} id="bottom" className="device-port"/>
  </div>;
});

export const Cable = memo(function Cable({id,sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition,data,selected}:EdgeProps<CableEdge>) {
  const [path,x,y] = getBezierPath({sourceX,sourceY,targetX,targetY,sourcePosition,targetPosition,curvature:.15});
  const active = data?.active && data.up;
  const overloaded=(data?.utilization ?? 0)>.88;
  const color=!data?.up?'#a66c80':overloaded?'#d4ba7d':active?'#8b8bfe':'#55555c';
  const packets=(data?.packets ?? []).slice(0,3);
  return <>
    {active && <path d={path} fill="none" stroke="#4141fc" strokeOpacity=".10" strokeWidth="12"/>}
    <BaseEdge id={id} path={path} style={{stroke:color,strokeWidth:selected?2.8:active?2.2:1.3,strokeDasharray:data?.up?'none':'5 6'}} interactionWidth={24}/>
    {packets.map((p,i) => <circle key={`${p.packet_id}-${p.link_id}`} r="3.2" fill={color} className="packet-dot">
      <animateMotion dur={`${.7+i*.1}s`} repeatCount="1" fill="freeze" path={path} keyPoints={p.link_id.endsWith(':rev')?'1;0':'0;1'} keyTimes="0;1" calcMode="linear"/>
    </circle>)}
    <EdgeLabelRenderer><button className={`cable-label nodrag nopan ${active?'active':''} ${selected?'selected':''} ${!data?.up?'disabled':''}`}
      onClick={()=>{if(typeof data?.onSelect==='function')data.onSelect();}}
      style={{transform:`translate(-50%, -50%) translate(${x}px,${y}px)`}} title="Select wire to edit capacity" data-edge-id={id}>
      {!data?.up?'OFFLINE':`${data?.capacity_mbps} Mbps`}{active && <span className="cable-activity"/>}
    </button></EdgeLabelRenderer>
  </>;
});

export const nodeTypes = {device:Device};
export const edgeTypes = {cable:Cable};
