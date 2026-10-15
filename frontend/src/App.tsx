import { useCallback, useEffect, useRef, useState } from 'react';
import { Background, BackgroundVariant, ConnectionMode, Controls, MiniMap, ReactFlow, ReactFlowProvider,
  applyEdgeChanges, applyNodeChanges, useReactFlow } from '@xyflow/react';
import type { Connection, EdgeChange, NodeChange } from '@xyflow/react';
import { Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, Check, ChevronDown, CircleHelp,
  Cable as CableIcon, Clock3, Download, Grip, Layers, Link2, Maximize, MousePointer2,
  Pause, Play, Plus, Radio, RotateCcw, Route, Settings2, ShieldCheck, StepForward, Trash2, Upload, X, Zap } from 'lucide-react';
import { edgeTypes, nodeTypes } from './Canvas';
import { DeviceIcon } from './Icons';
import { Globe } from './Globe';
import { api, blankNetwork, cleanNetwork, demoNetwork, download, parseNetwork, policies, removeDevice, routeNames, toApi } from './model';
import type { CableEdge, DeviceKind, DeviceNode, Flow, LiveState, Network, Policy, Transmission } from './model';

const DEVICE_KINDS: {kind:DeviceKind; label:string; detail:string}[] = [
  {kind:'router',label:'Router',detail:'Route between networks'}, {kind:'switch',label:'Switch',detail:'Connect local devices'},
  {kind:'computer',label:'Workstation',detail:'Generate source traffic'}, {kind:'server',label:'Server',detail:'Receive application traffic'},
  {kind:'cloud',label:'Cloud',detail:'Add an external network'},
];
type Selection = {type:'edge'|'node'|'flow'; id:string} | null;

function usePersistedNetwork() {
  const [network,setNetwork] = useState<Network>(() => {
    try { const saved=localStorage.getItem('smartroute-studio-v1'); if (saved) return parseNetwork(saved); } catch { /* Fall through to the editable demo. */ }
    return demoNetwork();
  });
  useEffect(() => { localStorage.setItem('smartroute-studio-v1',JSON.stringify(cleanNetwork(network))); }, [network]);
  return [network,setNetwork] as const;
}

function Studio() {
  const [network,setNetwork]=usePersistedNetwork();
  const [selection,setSelection]=useState<Selection>({type:'edge',id:'c2'});
  const [mode,setMode]=useState<'select'|'wire'>('select');
  const [wireStart,setWireStart]=useState<string|null>(null);
  const [live,setLive]=useState<LiveState|null>(null);
  const [packetEvents,setPacketEvents]=useState<(Transmission & {expires:number})[]>([]);
  const [running,setRunning]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [health,setHealth]=useState<'connecting'|'online'|'offline'>('connecting');
  const [bottomTab,setBottomTab]=useState<'activity'|'traffic'|'packets'>('activity');
  const [help,setHelp]=useState(false);
  const [speed,setSpeed]=useState(1);
  const networkRef=useRef(network), sessionRef=useRef<string|null>(null), inFlight=useRef(false), generation=useRef(0);
  const controlsRef=useRef(false), importRef=useRef<HTMLInputElement>(null);
  const flowInstance=useReactFlow<DeviceNode,CableEdge>();
  networkRef.current=network;

  useEffect(() => {
    let active=true;
    api<{status:string}>('/health').then(()=>active && setHealth('online')).catch(()=>active && setHealth('offline'));
    return ()=>{active=false;};
  },[]);
  useEffect(()=>{ if(!notice)return; const timer=setTimeout(()=>setNotice(''),4000); return ()=>clearTimeout(timer);},[notice]);
  useEffect(()=>{
    const handler=(event:KeyboardEvent)=>{
      if((event.target as HTMLElement)?.closest('input,select,textarea,[contenteditable=true]'))return;
      if(event.key.toLowerCase()==='c'){setMode('wire');setWireStart(null);}
      if(event.key.toLowerCase()==='v'){setMode('select');setWireStart(null);}
      if(event.key==='Escape'){setMode('select');setWireStart(null);setHelp(false);}
    };
    window.addEventListener('keydown',handler);return ()=>window.removeEventListener('keydown',handler);
  },[]);
  useEffect(()=>{const current=sessionRef; return ()=>{if(current.current) void api(`/sessions/${current.current}`,undefined,'DELETE').catch(()=>{});};},[]);

  const resetSession = useCallback(() => {
    generation.current++; setRunning(false); setLive(null); setPacketEvents([]); setError('');
    if(sessionRef.current) void api(`/sessions/${sessionRef.current}`,undefined,'DELETE').catch(()=>{});
    sessionRef.current=null; controlsRef.current=false;
  },[]);
  const isLocked=Boolean(sessionRef.current);
  const editStructure = useCallback((updater:(n:Network)=>Network) => {
    if(sessionRef.current){setNotice('Reset the simulation to change the topology. Traffic, capacity and link availability stay editable live.');return;}
    setNetwork(updater);setError('');
  },[setNetwork]);

  const step = useCallback(async () => {
    if(inFlight.current || !sessionRef.current)return;
    const token=generation.current, sessionId=sessionRef.current;
    inFlight.current=true;
    try {
      const changes=controlsRef.current ? {
        rates:Object.fromEntries(networkRef.current.flows.map(f=>[f.id,f.rate_mbps])),
        connections:Object.fromEntries(networkRef.current.edges.map(e=>[e.id,{capacity_mbps:e.data!.capacity_mbps,up:e.data!.up}])),
      } : {};
      controlsRef.current=false;
      const result=await api<LiveState>(`/sessions/${sessionId}/step`,changes);
      if(token===generation.current){
        setLive(result);setHealth('online');
        setPacketEvents(current=>{
          const now=performance.now(), retained=current.filter(p=>p.expires>now), added=new Set<string>();
          for(const event of result.transmissions){
            if(event.packet_id%3!==0 || added.has(event.link_id) || retained.filter(p=>p.link_id===event.link_id).length>=2)continue;
            retained.push({...event,expires:now+1100});added.add(event.link_id);
          }
          return retained;
        });
      }
    } catch(err) {
      if(token===generation.current){setError((err as Error).message);setRunning(false);}
    } finally{inFlight.current=false;}
  },[]);

  useEffect(()=>{ if(!running)return; const timer=setInterval(()=>void step(),250/speed); return ()=>clearInterval(timer); },[running,speed,step]);

  const start = async (single=false) => {
    setError('');
    if(sessionRef.current){if(single)await step();else setRunning(true);return;}
    setBusy(true);const token=generation.current;
    try{
      const result=await api<LiveState & {session_id:string}>('/sessions',toApi(networkRef.current));
      if(token!==generation.current){void api(`/sessions/${result.session_id}`,undefined,'DELETE');return;}
      sessionRef.current=result.session_id;setLive(result);await step();if(!single)setRunning(true);
    }catch(err){setError((err as Error).message);}finally{setBusy(false);}
  };

  const addDevice=(kind:DeviceKind,position?:{x:number;y:number})=>{
    editStructure(current=>{
      if(current.nodes.length>=32){setNotice('The local canvas supports up to 32 devices.');return current;}
      const id=`${kind}-${crypto.randomUUID().slice(0,8)}`;
      const count=current.nodes.filter(n=>n.data.kind===kind).length+1;
      const pos=position??flowInstance.screenToFlowPosition({x:window.innerWidth*.47,y:window.innerHeight*.47});
      const node:DeviceNode={id,type:'device',position:pos,data:{kind,label:`${DEVICE_KINDS.find(d=>d.kind===kind)!.label} ${count}`,address:`10.0.${Math.floor(current.nodes.length/250)}.${current.nodes.length+10}`}};
      setSelection({type:'node',id});return {...current,nodes:[...current.nodes,node]};
    });
  };

  const connect=useCallback((connection:Pick<Connection,'source'|'target'|'sourceHandle'|'targetHandle'>)=>{
    editStructure(current=>{
      if(connection.source===connection.target){setNotice('Choose two different devices.');return current;}
      if(current.edges.some(e=>(e.source===connection.source&&e.target===connection.target)||(e.source===connection.target&&e.target===connection.source))){setNotice('These devices are already connected. Select the wire to edit it.');return current;}
      if(current.edges.length>=64){setNotice('The local canvas supports up to 64 cables.');return current;}
      const id=`cable-${crypto.randomUUID().slice(0,8)}`;
      const edge:CableEdge={...connection,id,type:'cable',data:{capacity_mbps:1,latency_ms:5,buffer_bytes:64000,up:true}};
      setSelection({type:'edge',id});setWireStart(null);return {...current,edges:[...current.edges,edge]};
    });
  },[editStructure]);

  const updateCable=(id:string,values:Partial<NonNullable<CableEdge['data']>>)=>{
    setNetwork(n=>({...n,edges:n.edges.map(e=>e.id===id?{...e,data:{...e.data!,...values}}:e)}));controlsRef.current=true;
  };
  const updateFlow=(id:string,values:Partial<Flow>)=>{
    setNetwork(n=>({...n,flows:n.flows.map(f=>f.id===id?{...f,...values}:f)}));controlsRef.current=true;
  };
  const deleteSelection=()=>{
    if(!selection)return;
    editStructure(n=>selection.type==='node'?removeDevice(n,selection.id):selection.type==='edge'?{...n,edges:n.edges.filter(e=>e.id!==selection.id)}:{...n,flows:n.flows.filter(f=>f.id!==selection.id)});
    if(!isLocked)setSelection(null);
  };
  const loadPreset=(empty=false)=>{
    resetSession();setNetwork(empty?blankNetwork():demoNetwork());setSelection(empty?null:{type:'edge',id:'c2'});setMode('select');
    setTimeout(()=>void flowInstance.fitView({padding:.12,duration:400}),80);
  };
  const addFlow=()=>{
    if(network.nodes.length<2){setNotice('Add at least two devices before creating traffic.');return;}
    editStructure(n=>{
      if(n.flows.length>=8){setNotice('The local engine supports eight concurrent source flows.');return n;}
      const source=n.nodes.find(x=>x.data.kind==='computer')??n.nodes[0];
      const target=n.nodes.find(x=>x.data.kind==='server'&&x.id!==source.id)??n.nodes.find(x=>x.id!==source.id)!;
      const id=`flow-${crypto.randomUUID().slice(0,8)}`;setSelection({type:'flow',id});
      return {...n,flows:[...n.flows,{id,label:`Traffic ${n.flows.length+1}`,source:source.id,target:target.id,rate_mbps:.35,packet_bytes:1000,color:'#8b8bfe'}]};
    });
  };

  const selectedCable=selection?.type==='edge'?network.edges.find(e=>e.id===selection.id):undefined;
  const selectedNode=selection?.type==='node'?network.nodes.find(n=>n.id===selection.id):undefined;
  const selectedFlow=selection?.type==='flow'?network.flows.find(f=>f.id===selection.id):network.flows[0];
  const label=(id:string)=>network.nodes.find(n=>n.id===id)?.data.label??id;
  const currentRoutes=new Set(live?.decision?.routes.flatMap(r=>r.link_ids.map(id=>id.split(':')[0]))??[]);
  const renderedEdges=network.edges.map(e=>{
    const observations=live?.snapshot?.links.filter(l=>l.id.startsWith(`${e.id}:`))??[];
    return {...e,selected:selection?.type==='edge'&&selection.id===e.id,data:{...e.data!,onSelect:()=>setSelection({type:'edge',id:e.id}),active:currentRoutes.has(e.id),
      utilization:Math.max(0,...observations.map(l=>l.busy_s/.2)),resident_bytes:observations.reduce((a,l)=>a+l.resident_bytes,0),
      packets:running?packetEvents.filter(p=>p.link_id.startsWith(`${e.id}:`)):[]}};
  });
  const renderedNodes=network.nodes.map(n=>({...n,selected:selection?.type==='node'&&selection.id===n.id}));
  const totalDemand=network.flows.reduce((a,f)=>a+f.rate_mbps,0);
  const m=live?.metrics;
  const latestSwitch=live?.events.find(e=>e.time_s>0);
  const selectedUtilization = selectedCable ? Math.max(0, ...(live?.snapshot?.links.filter(l => l.id.startsWith(`${selectedCable.id}:`)).map(l => l.busy_s / .2) ?? [])) : 0;

  return <div className="studio-app">
    <header className="app-header">
      <a className="brand" href="/" aria-label="SmartRoute home"><span className="brand-mark"><Route size={21}/></span>smartroute<span className="brand-dot">®</span></a>
      <div className="header-separator"/><div className="header-nav"><button className="active"><span className="tiny-square"/>Network studio</button><button onClick={()=>setHelp(true)}>Quick guide <ArrowUpRight size={13}/></button></div>
      <div className="header-right"><span className={`engine-status ${health}`}><span/>{health==='online'?'LOCAL ENGINE ONLINE':health==='offline'?'ENGINE OFFLINE':'CONNECTING TO ENGINE'}</span><button className="icon-button" title="Quick guide" aria-label="Open help" onClick={()=>setHelp(true)}><CircleHelp size={18}/></button><span className="avatar">SR</span></div>
    </header>

    <section className="workspace-heading"><div><div className="eyebrow"><span/>YOUR NETWORK. A BETTER PATH.</div><h1>Build. Connect. <span>Reroute.</span></h1><p>A hands-on workspace for networks that adapt.</p></div>
      <div className="heading-globe"><Globe/><div className="globe-coordinate">LIVE TOPOLOGY<br/><span>DESIGNED TO ADAPT ↗</span></div></div>
    </section>

    <div className="workspace-toolbar"><div className="project-name"><Layers size={16}/><input aria-label="Network name" maxLength={64} value={network.name} onChange={e=>setNetwork(n=>({...n,name:e.target.value}))}/><ChevronDown size={13}/><span className="draft-tag">LOCAL DRAFT</span></div>
      <div className="toolbar-actions"><button className="text-button" onClick={()=>importRef.current?.click()} title="Import a saved SmartRoute network"><Upload size={14}/><span>Import</span></button>
        <button className="text-button" onClick={()=>{download('smartroute-network.json',cleanNetwork(network));setNotice('Network exported, including device positions and link capacities.');}}><Download size={14}/><span>Save network</span></button>
        <div className="toolbar-divider"/><button className="text-button" title="Reset simulation; keep the topology" onClick={resetSession}><RotateCcw size={14}/><span>Reset</span></button>
        <button className={`primary-button ${running?'pause-button':''}`} disabled={busy} onClick={()=>running?setRunning(false):void start()}>{running?<Pause size={14}/>:<Play size={14} fill="currentColor"/>}{busy?'Starting…':running?'Pause simulation':isLocked?'Resume simulation':'Start simulation'}</button>
      </div>
    </div>

    <main className="workspace-body">
      <aside className="device-palette"><div className="panel-caption"><span>DEVICE LIBRARY</span><span>05</span></div><p className="palette-intro">Drag a device onto the canvas<br/>to start building.</p>
        <div className="device-list">{DEVICE_KINDS.map(d=><button key={d.kind} className="palette-device" draggable={!isLocked} onDragStart={e=>{e.dataTransfer.setData('application/smartroute-device',d.kind);e.dataTransfer.effectAllowed='move';}} onClick={()=>addDevice(d.kind)} title={`Add ${d.label}`}><span className="palette-icon"><DeviceIcon kind={d.kind}/></span><span><b>{d.label}</b><small>{d.detail}</small></span><Grip size={13} className="drag-grip"/></button>)}</div>
        <div className="palette-divider"/><div className="panel-caption"><span>CONNECTIONS</span></div>
        <button className={`wire-tool ${mode==='wire'?'active':''}`} onClick={()=>{setMode(m=>m==='wire'?'select':'wire');setWireStart(null);}}><Link2 size={21}/><span><b>Copper cable</b><small>Click two devices to connect</small></span><span className="keycap">C</span></button>
        <div className="palette-divider"/><div className="panel-caption"><span>STARTING POINT</span></div>
        <button className="preset-button" onClick={()=>loadPreset()}><Route size={15}/><span>Adaptive routing demo</span><ArrowUpRight size={14}/></button>
        <button className="preset-button" onClick={()=>loadPreset(true)}><Plus size={15}/><span>Empty workspace</span><ArrowUpRight size={14}/></button>
        <div className="palette-note"><div className="note-marker">↗</div><b>More than one way home.</b><p>Add an alternative path, then increase traffic to see adaptive routing in action.</p><button onClick={()=>setHelp(true)}>How it works <ArrowRight size={13}/></button></div>
        <div className="palette-footer"><ShieldCheck size={13}/>Runs locally. Yours to explore.</div>
      </aside>

      <section className="canvas-column">
        <div className="canvas-stats"><div><span className="stat-label">SOURCE TRAFFIC</span><b>{totalDemand.toFixed(2)}<small>Mbps</small></b></div><div><span className="stat-label">DELIVERED</span><b>{m?m.delivered.toLocaleString():'—'}<small>packets</small></b></div><div><span className="stat-label">REROUTES</span><b className={m?.route_changes?'accent-text':''}>{m?m.route_changes:'—'}<small>decisions</small></b></div><div><span className="stat-label">AVG. LATENCY</span><b>{m?.mean_latency_s!=null?(m.mean_latency_s*1000).toFixed(1):'—'}<small>ms</small></b></div></div>
        <div className={`network-canvas ${mode==='wire'?'wiring':''}`} onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='move';}} onDrop={e=>{e.preventDefault();const kind=e.dataTransfer.getData('application/smartroute-device') as DeviceKind;if(DEVICE_KINDS.some(d=>d.kind===kind))addDevice(kind,flowInstance.screenToFlowPosition({x:e.clientX,y:e.clientY}));}}>
          <div className="canvas-topline"><div className="canvas-view-label"><span className="tiny-square"/>LOGICAL TOPOLOGY<span className="canvas-counts">{network.nodes.length} devices / {network.edges.length} links</span></div><div className="canvas-mode"><span className={running?'live-dot':''}/>{running?'SIMULATION LIVE':isLocked?'PAUSED':'EDIT MODE'}</div></div>
          <ReactFlow<DeviceNode,CableEdge> nodes={renderedNodes} edges={renderedEdges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} connectionMode={ConnectionMode.Loose}
            onNodesChange={(changes:NodeChange<DeviceNode>[])=>setNetwork(n=>({...n,nodes:applyNodeChanges(changes.filter(c=>c.type!=='remove'),n.nodes)}))}
            onEdgesChange={(changes:EdgeChange<CableEdge>[])=>{if(changes.some(c=>c.type==='remove')&&isLocked)return;setNetwork(n=>({...n,edges:applyEdgeChanges(changes,n.edges)}));}}
            onConnect={connect} onNodeClick={(_,node)=>{if(mode==='wire'){if(wireStart&&wireStart!==node.id)connect({source:wireStart,target:node.id,sourceHandle:'right',targetHandle:'left'});else{setWireStart(node.id);setNotice(`Now select another device to connect to ${node.data.label}.`);}}else setSelection({type:'node',id:node.id});}}
            onEdgeClick={(_,edge)=>setSelection({type:'edge',id:edge.id})} onPaneClick={()=>{setSelection(null);setWireStart(null);}}
            nodesConnectable={!isLocked} nodesDraggable={mode==='select'} fitView fitViewOptions={{padding:.12}} minZoom={.25} maxZoom={2} deleteKeyCode={null} colorMode="dark"
            proOptions={{hideAttribution:true}}><Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#303034"/>
            <Controls position="bottom-left" showInteractive={false}/><MiniMap nodeColor="#555565" nodeStrokeColor="#8b8bfe" maskColor="#0d0d0daa" position="bottom-right" pannable zoomable/>
          </ReactFlow>
          {network.nodes.length===0&&<div className="empty-canvas"><div className="empty-cross"><Plus size={28}/></div><h2>Every network starts somewhere.</h2><p>Drag in a router, add a device, and connect the dots.</p><button className="outline-button" onClick={()=>addDevice('router')}><Plus size={14}/>Add your first router</button></div>}
          <div className="canvas-tools"><button className={mode==='select'?'active':''} title="Select and move devices" aria-label="Select tool" onClick={()=>{setMode('select');setWireStart(null);}}><MousePointer2 size={16}/></button><button className={mode==='wire'?'active':''} title="Connect two devices" aria-label="Cable tool" onClick={()=>setMode('wire')}><CableIcon size={17}/></button><span/><button title="Fit network to view" aria-label="Fit network" onClick={()=>void flowInstance.fitView({padding:.12,duration:350})}><Maximize size={16}/></button><button title="Delete selected device or connection" aria-label="Delete selected" onClick={deleteSelection} disabled={!selection||isLocked}><Trash2 size={15}/></button></div>
          <div className="canvas-legend"><span><i className="legend-route"/>Active route</span><span><i className="legend-idle"/>Standby link</span><span><i className="legend-packet"/>Sampled packet</span></div>
          {wireStart&&<div className="wire-hint">Choose the second device <button onClick={()=>setWireStart(null)}><X size={12}/></button></div>}
          {running&&latestSwitch&&live!.time_s-latestSwitch.time_s<2&&<div className="reroute-toast"><Route size={15}/><span>Path updated<small>{latestSwitch.forced?'Broken link bypassed':'A lower-cost route is available'}</small></span><b>{latestSwitch.time_s.toFixed(1)}s</b></div>}
        </div>

        <section className="activity-panel"><div className="activity-header"><div className="bottom-tabs"><button className={bottomTab==='activity'?'active':''} onClick={()=>setBottomTab('activity')}><Activity size={13}/>Event log <span>{live?.events.length??0}</span></button><button className={bottomTab==='traffic'?'active':''} onClick={()=>setBottomTab('traffic')}>Traffic</button><button className={bottomTab==='packets'?'active':''} onClick={()=>setBottomTab('packets')}>Packet ledger</button></div><span className="elapsed-time"><Clock3 size={12}/>{live?live.time_s.toFixed(1):'0.0'}s simulated</span></div>
          {bottomTab==='activity'?<div className="event-log">{!live?.events.length?<div className="event-empty"><span className="log-timestamp">00:00.0</span><span className="log-dot"/><span>Network ready. Start the simulation to follow every routing decision.</span><span className="event-type">SYSTEM</span></div>:live.events.slice(0,12).map((event,i)=><div key={`${event.time_s}-${event.flow_id}-${i}`} className="event-row"><time>{event.time_s.toFixed(1).padStart(6,'0')}s</time><Route size={12} className={event.time_s>0?'accent-text':''}/><div><b>{event.time_s===0?'Initial route assigned':event.reason==='forced_disconnection'?'No available route':event.forced?'Link bypassed · route repaired':'Traffic rerouted'}</b><span>{routeNames(event.new_route,network)}</span></div><span className={`event-type ${event.time_s>0?'changed':''}`}>{event.reason==='initial'?'ROUTE':event.forced?'REPAIR':'ADAPT'}</span></div>)}</div>:
          bottomTab==='traffic'?<div className="traffic-overview"><TrafficChart history={live?.history??[]}/><div className="traffic-chart-labels"><span><i/>Offered traffic</span><span><i/>Delivered goodput</span><small>Live generation cohort · Mbps</small></div></div>:
          <div className="packet-summary">{[{label:'Generated',value:m?.generated},{label:'Delivered',value:m?.delivered},{label:'Dropped',value:m?.dropped},{label:'In flight / queued',value:m?.pending}].map(item=><div key={item.label}><span>{item.label}</span><b>{item.value??'—'}</b></div>)}<p>Generated = delivered + dropped + pending. Packet motion shows sampled wire-entry events, slowed for visibility.</p></div>}
          <div className="playback-bar"><div><button className="icon-button" title="Advance one observation interval" aria-label="Step simulation" disabled={running||busy} onClick={()=>void start(true)}><StepForward size={14}/></button><select aria-label="Simulation speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value={.5}>0.5× speed</option><option value={1}>1× speed</option><option value={2}>2× speed</option></select></div><span>{isLocked?'Traffic and link controls update at the next 200 ms observation.':'Drag to move · scroll to zoom · connect from any device port'}</span><span className="sim-time">{running?<Radio size={11}/>:<span className="status-dot"/>}{running?'LIVE':isLocked?'PAUSED':'READY'}</span></div>
        </section>
      </section>

      <aside className="inspector"><div className="inspector-head"><Settings2 size={14}/><span>INSPECTOR</span><span className="inspector-indicator"/></div>
        <div className="inspector-scroll">
          {selectedCable?<section className="property-section"><div className="section-eyebrow">CONNECTION PROPERTIES</div><div className="connection-heading"><span className="property-icon"><Link2 size={20}/></span><div><h2>{label(selectedCable.source)}</h2><span>↔ {label(selectedCable.target)}</span></div><button className={`power-toggle ${selectedCable.data!.up?'on':''}`} title="Toggle connection availability" aria-label="Connection enabled" aria-pressed={selectedCable.data!.up} onClick={()=>updateCable(selectedCable.id,{up:!selectedCable.data!.up})}><span/></button></div>
            <div className="duplex-note"><span className="status-dot"/>{selectedCable.data!.up?'Connected':'Link disabled'}<span>FULL DUPLEX</span></div>
            <label className="field-label" htmlFor="capacity">Maximum link traffic <span>CAPACITY</span></label><div className="unit-input"><input id="capacity" type="number" min="0.01" max="1000" step="0.1" value={selectedCable.data!.capacity_mbps} onChange={e=>{const v=Number(e.target.value);if(Number.isFinite(v)&&v>=.01&&v<=1000)updateCable(selectedCable.id,{capacity_mbps:v});}}/><span>Mbps</span></div>
            <input className="range-control" aria-label="Maximum link traffic slider" type="range" min=".05" max="10" step=".05" value={Math.min(selectedCable.data!.capacity_mbps,10)} onChange={e=>updateCable(selectedCable.id,{capacity_mbps:Number(e.target.value)})}/><div className="range-labels"><span>0.05 Mbps</span><span>10 Mbps</span></div>
            <div className="two-fields"><label>Delay <div className="small-unit-input"><input aria-label="Propagation delay" type="number" min="0" max="1000" disabled={isLocked} value={selectedCable.data!.latency_ms} onChange={e=>{const v=Number(e.target.value);if(v>=0&&v<=1000)updateCable(selectedCable.id,{latency_ms:v});}}/><span>ms</span></div></label><label>Buffer <div className="small-unit-input"><input aria-label="Buffer size in kilobytes" type="number" min="0" max="1000" disabled={isLocked} value={selectedCable.data!.buffer_bytes/1000} onChange={e=>{const v=Number(e.target.value);if(v>=0&&v<=1000)updateCable(selectedCable.id,{buffer_bytes:Math.round(v*1000)});}}/><span>KB</span></div></label></div>
            <div className="link-utilization"><div><span>Service utilization</span><b>{live?`${Math.round(selectedUtilization * 100)}%`:'—'}</b></div><div className="utilization-track"><i style={{width:`${Math.min(100, selectedUtilization * 100)}%`}}/></div></div>
          </section>:selectedNode?<section className="property-section"><div className="section-eyebrow">DEVICE PROPERTIES</div><div className="connection-heading"><span className="property-icon"><DeviceIcon kind={selectedNode.data.kind}/></span><div><h2>{selectedNode.data.label}</h2><span>{selectedNode.data.kind}</span></div></div><label className="field-label">Device name</label><input className="plain-input" aria-label="Device name" disabled={isLocked} maxLength={64} value={selectedNode.data.label} onChange={e=>setNetwork(n=>({...n,nodes:n.nodes.map(node=>node.id===selectedNode.id?{...node,data:{...node.data,label:e.target.value}}:node)}))}/><label className="field-label">IP label</label><input className="plain-input" aria-label="Device IP label" maxLength={64} value={selectedNode.data.address} onChange={e=>setNetwork(n=>({...n,nodes:n.nodes.map(node=>node.id===selectedNode.id?{...node,data:{...node.data,address:e.target.value}}:node)}))}/><p className="field-note">{network.edges.filter(e=>e.source===selectedNode.id||e.target===selectedNode.id).length} connected interfaces. Drag from a port to add a cable.</p><button className="danger-button" disabled={isLocked} onClick={deleteSelection}><Trash2 size={13}/>Remove device</button></section>:
          <section className="property-section idle-inspector"><span className="property-icon"><MousePointer2 size={21}/></span><h2>Make it your network.</h2><p>Select a device or connection to inspect and configure it.</p></section>}

          <section className="property-section traffic-section"><div className="section-eyebrow">TRAFFIC GENERATOR<button className="tiny-button" title="Add a traffic flow" aria-label="Add traffic flow" disabled={isLocked} onClick={addFlow}><Plus size={13}/></button></div>
            {network.flows.length>0?<><select className="flow-select" aria-label="Select traffic flow" value={selectedFlow?.id??network.flows[0].id} onChange={e=>setSelection({type:'flow',id:e.target.value})}>{network.flows.map(f=><option key={f.id} value={f.id}>{f.label}</option>)}</select>
              <div className="flow-endpoints"><select aria-label="Traffic source" disabled={isLocked} value={selectedFlow!.source} onChange={e=>{if(e.target.value!==selectedFlow!.target)updateFlow(selectedFlow!.id,{source:e.target.value});}}>{network.nodes.filter(n=>n.id!==selectedFlow!.target).map(n=><option key={n.id} value={n.id}>{n.data.label}</option>)}</select><ArrowRight size={12}/><select aria-label="Traffic destination" disabled={isLocked} value={selectedFlow!.target} onChange={e=>{if(e.target.value!==selectedFlow!.source)updateFlow(selectedFlow!.id,{target:e.target.value});}}>{network.nodes.filter(n=>n.id!==selectedFlow!.source).map(n=><option key={n.id} value={n.id}>{n.data.label}</option>)}</select></div>
              <div className="traffic-demand-label"><span>Offered traffic</span><b>{selectedFlow!.rate_mbps.toFixed(2)}<small>Mbps</small></b></div>
              <input type="range" className="range-control traffic-range" aria-label="Offered traffic" min="0" max="4" step=".05" value={Math.min(selectedFlow!.rate_mbps,4)} onChange={e=>updateFlow(selectedFlow!.id,{rate_mbps:Number(e.target.value)})}/><div className="range-labels"><span>0 Mbps</span><span>4 Mbps</span></div>
              <div className="traffic-presets"><button onClick={()=>updateFlow(selectedFlow!.id,{rate_mbps:.35})}>Low load</button><button onClick={()=>{updateFlow(selectedFlow!.id,{rate_mbps:1.8});setBottomTab('activity');}}>Stress test <Zap size={11}/></button><button onClick={()=>updateFlow(selectedFlow!.id,{rate_mbps:0})}>Stop flow</button></div>
              <div className="traffic-tip"><Zap size={13}/><p>Turn up the traffic. Watch the network find a better path.</p></div>
            </>:<><p className="field-note">Choose a source and destination, then generate traffic between them.</p><button className="outline-button" disabled={isLocked} onClick={addFlow}><Plus size={13}/>Add traffic flow</button></>}
          </section>

          <section className="property-section routing-section"><div className="section-eyebrow">ROUTING ENGINE<span className="mini-badge">AUTO</span></div><select className="policy-select" aria-label="Routing policy" disabled={isLocked} value={network.policy} onChange={e=>editStructure(n=>({...n,policy:e.target.value as Policy}))}>{policies.map(p=><option key={p.value} value={p.value}>{p.label}</option>)}</select><p className="field-note">{policies.find(p=>p.value===network.policy)?.detail}. {isLocked?'Reset to change policies.':'Routes react to demand, queue pressure, and link availability.'}</p>
            <div className="routing-features"><span><Check size={11}/>Loop-free paths</span><span><Check size={11}/>Automatic failover</span><span><Check size={11}/>1s switch cooldown</span></div>
            {live?.decision&&<div className="current-path"><span>CURRENT PATH</span><p>{routeNames(live.decision.routes.find(r=>r.flow_id===selectedFlow?.id)?.link_ids??[],network)}</p><small>{live.decision.routes.find(r=>r.flow_id===selectedFlow?.id)?.reason.replaceAll('_',' ')}</small>{live.decision.forecasts.find(f=>f.flow_id===selectedFlow?.id)&&<small>{live.decision.forecasts.find(f=>f.flow_id===selectedFlow?.id)!.status} · {live.decision.forecasts.find(f=>f.flow_id===selectedFlow?.id)!.reason}</small>}</div>}
          </section>
          {live&&<button className="export-session" onClick={async()=>{try{download('smartroute-session.json',await api(`/sessions/${sessionRef.current}/export`));setNotice('Exported live session with packet outcomes and the traffic edit log.');}catch(err){setError((err as Error).message);}}}><ArrowDownToLine size={13}/>Export simulation data<ArrowUpRight size={12}/></button>}
        </div>
      </aside>
    </main>

    <footer className="status-bar"><span><span className={`status-dot ${running?'blue':''}`}/>{running?'Simulation running':isLocked?'Simulation paused':'All changes saved locally'}</span><div><span>{network.nodes.length} DEVICES</span><span>{network.edges.length} CONNECTIONS</span><span>{network.flows.length} TRAFFIC FLOW{network.flows.length===1?'':'S'}</span></div><span>SMARTROUTE / NETWORK STUDIO <span className="version-label">v1.0</span></span></footer>
    {error&&<div className="error-banner" role="alert"><span><b>Unable to continue</b>{error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={16}/></button></div>}
    {notice&&<div className="notice-toast" role="status"><Check size={14}/>{notice}<button aria-label="Dismiss notice" onClick={()=>setNotice('')}><X size={13}/></button></div>}
    <input type="file" ref={importRef} accept=".json,application/json" hidden onChange={async e=>{const file=e.target.files?.[0];if(!file)return;try{if(file.size>512000)throw new Error('Network files must be smaller than 512 KB.');const imported=parseNetwork(await file.text());resetSession();setNetwork(imported);setSelection(null);setNotice('Network imported. Start a new simulation when you are ready.');setTimeout(()=>void flowInstance.fitView({padding:.12,duration:350}),80);}catch(err){setError((err as Error).message);}finally{e.target.value='';}}}/>
    {help&&<div className="modal-scrim" onClick={()=>setHelp(false)}><section className="help-modal" role="dialog" aria-modal="true" aria-labelledby="guide-title" onClick={e=>e.stopPropagation()}><button className="modal-close icon-button" aria-label="Close guide" onClick={()=>setHelp(false)}><X size={19}/></button><div className="eyebrow">A QUICK FIELD GUIDE</div><h2 id="guide-title">A network that finds its way.</h2><p>Build a topology, create traffic, and watch routing decisions emerge from real simulated demand.</p><ol><li><span>01</span><div><b>Place your devices.</b><p>Drag a router, workstation, switch or server from the library onto the canvas. Click a device to rename it.</p></div></li><li><span>02</span><div><b>Connect the dots.</b><p>Drag between device ports, or choose the cable tool and click two devices. Select a wire to set maximum traffic in Mbps.</p></div></li><li><span>03</span><div><b>Give packets another way through.</b><p>Create a second route. Start the simulation, then press Stress test or move the traffic slider. New packets can switch to a less congested path.</p></div></li><li><span>04</span><div><b>Break a link. See what happens.</b><p>Toggle a connection off to trigger failover. Inspect the event log and live packet counts; packets already in flight retain their original route.</p></div></li></ol><div className="help-footnote">Source traffic is configured per flow. Capacity limits each directed side of a full-duplex cable. Devices use source routing; IP labels are annotations. Live sessions retain queues while traffic changes. Packet motion samples real transmissions and slows them for visibility. Topology edits require a reset.</div><button className="primary-button" onClick={()=>setHelp(false)}>Back to the canvas <ArrowRight size={14}/></button></section></div>}
  </div>;
}

function TrafficChart({history}: {history:LiveState['history']}) {
  const max=Math.max(.5,...history.flatMap(h=>[h.offered_mbps,h.goodput_mbps]));
  const points=(key:'offered_mbps'|'goodput_mbps')=>history.map((h,i)=>`${8+i/Math.max(1,history.length-1)*684},${85-h[key]/max*72}`).join(' ');
  return <svg className="traffic-chart" viewBox="0 0 700 96" preserveAspectRatio="none" role="img" aria-label="Offered traffic and delivered goodput history"><path d="M0 85H700M0 49H700M0 13H700" stroke="#27272b" strokeWidth="1" strokeDasharray="3 4"/>{history.length>1?<><polyline points={points('offered_mbps')} fill="none" stroke="#8b8bfe" strokeWidth="1.8"/><polyline points={points('goodput_mbps')} fill="none" stroke="#7fd579" strokeWidth="1.5"/></>:<text x="350" y="50" textAnchor="middle" fill="#73737e" fontSize="11">Run the simulation to see traffic history</text>}</svg>;
}

export default function App(){return <ReactFlowProvider><Studio/></ReactFlowProvider>;}
