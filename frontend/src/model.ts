import type { Edge, Node } from '@xyflow/react';

export type DeviceKind = 'router' | 'switch' | 'computer' | 'server' | 'cloud';
export type DeviceData = { label: string; kind: DeviceKind; address: string; [key: string]: unknown };
export type CableData = { capacity_mbps: number; latency_ms: number; buffer_bytes: number; up: boolean;
  utilization?: number; resident_bytes?: number; active?: boolean; packets?: Transmission[]; [key: string]: unknown };
export type DeviceNode = Node<DeviceData, 'device'>;
export type CableEdge = Edge<CableData, 'cable'>;
export type Flow = { id: string; label: string; source: string; target: string; rate_mbps: number; packet_bytes: number; color: string };
export type Policy = 'reactive' | 'static' | 'predictive-trend' | 'predictive-learned';
export type Network = { version: 1; name: string; nodes: DeviceNode[]; edges: CableEdge[]; flows: Flow[]; policy: Policy };
export type Transmission = { packet_id: number; flow_id: string; link_id: string; source: string; target: string; time_s: number; arrival_s: number; route_version: number };
export type RouteEvent = { time_s: number; flow_id: string; old_route: string[]; new_route: string[]; reason: string; forced: boolean;
  old_cost_s: number | null; new_cost_s: number | null; projected_peak_load: number | null };
export type LinkObservation = { id: string; src: string; dst: string; up: boolean; capacity_bps: number; resident_bytes: number; buffer_bytes: number;
  busy_s: number; attempted_bits: number; admitted_bits: number; served_bits: number; dropped_packets: number };
export type LiveState = {
  session_id?: string; time_s: number; tick: number; policy: string;
  metrics: { generated: number; delivered: number; dropped: number; pending: number; delivery_ratio: number | null;
    throughput_bps: number; mean_latency_s: number | null; p95_latency_s: number | null; route_changes: number; forced_route_changes: number; fairness: number | null };
  snapshot: { time_s: number; interval_s: number; links: LinkObservation[]; flows: {id: string; offered_bps: number; route: string[]}[] } | null;
  decision: { routes: { flow_id: string; link_ids: string[]; reason: string; old_cost_s: number | null; new_cost_s: number | null; projected_peak_load: number | null }[];
    forecasts: { flow_id: string; rate_bps: number; status: string; reason: string }[] } | null;
  transmissions: Transmission[]; events: RouteEvent[]; decision_runtime_ms: number;
  history: { time_s: number; offered_mbps: number; goodput_mbps: number; pending: number; route_changes: number }[];
};

function device(id: string, label: string, kind: DeviceKind, x: number, y: number, address: string): DeviceNode {
  return { id, type: 'device', position: { x, y }, data: { label, kind, address } };
}
function cable(id: string, source: string, target: string, capacity = 1, latency = 2): CableEdge {
  return { id, source, target, sourceHandle:'right', targetHandle:'left', type: 'cable', data: { capacity_mbps: capacity, latency_ms: latency, buffer_bytes: 64000, up: true } };
}

export const policies: { value: Policy; label: string; detail: string }[] = [
  { value: 'reactive', label: 'Adaptive routing', detail: 'Responds to observed demand and real queues' },
  { value: 'predictive-trend', label: 'Predictive · trend', detail: 'Anticipates demand with a causal trend' },
  { value: 'predictive-learned', label: 'Predictive · learned', detail: 'Uses the trained Ridge forecasting model' },
  { value: 'static', label: 'Static routing', detail: 'Fixed delay weights; repairs broken paths' },
];

export function demoNetwork(): Network {
  return { version: 1, name: 'Adaptive routing lab', policy: 'reactive', nodes: [
    device('pc1', 'Workstation', 'computer', 40, 210, '192.168.1.10'),
    device('r1', 'Gateway', 'router', 230, 210, '10.0.0.1'),
    device('r2', 'Core Alpha', 'router', 440, 60, '10.0.0.2'),
    device('r3', 'Core Beta', 'router', 440, 360, '10.0.0.3'),
    device('r4', 'Edge router', 'router', 650, 210, '10.0.0.4'),
    device('srv1', 'Application', 'server', 850, 210, '192.168.2.20'),
  ], edges: [
    cable('c1', 'pc1', 'r1', 10, 1), cable('c2', 'r1', 'r2', 1, 2),
    cable('c3', 'r2', 'r4', 1, 2), cable('c4', 'r1', 'r3', 2.5, 12),
    cable('c5', 'r3', 'r4', 2.5, 12), cable('c6', 'r4', 'srv1', 10, 1),
    cable('c7', 'r2', 'r3', 1.5, 6),
  ], flows: [{ id: 'flow1', label: 'Application traffic', source: 'pc1', target: 'srv1', rate_mbps: .35, packet_bytes: 1000, color: '#8b8bfe' }] };
}

export function blankNetwork(): Network { return { version: 1, name: 'Untitled network', nodes: [], edges: [], flows: [], policy: 'reactive' }; }

export function toApi(network: Network) {
  return { nodes: network.nodes.map(n => ({id: n.id, label: n.data.label, kind: n.data.kind, position: n.position})),
    connections: network.edges.map(e => ({ id: e.id, source: e.source, target: e.target, ...e.data })),
    flows: network.flows.map(f => ({id: f.id, source: f.source, target: f.target, rate_mbps: f.rate_mbps, packet_bytes: f.packet_bytes})), policy: network.policy };
}

export function cleanNetwork(network: Network): Network {
  return { ...network, nodes: network.nodes.map(({ id, type, position, data }) => ({ id, type, position, data })),
    edges: network.edges.map(({ id, source, target, sourceHandle, targetHandle, data }) => ({ id, source, target, sourceHandle, targetHandle, type: 'cable',
      data: { capacity_mbps: data!.capacity_mbps, latency_ms: data!.latency_ms, buffer_bytes: data!.buffer_bytes, up: data!.up } })) };
}

export function parseNetwork(text: string): Network {
  const value = JSON.parse(text);
  if (value.version !== 1 || !Array.isArray(value.nodes) || !Array.isArray(value.edges) || !Array.isArray(value.flows)
    || typeof value.name !== 'string' || !policies.some(p => p.value === value.policy)) throw new Error('This is not a SmartRoute network file (version 1).');
  if (value.nodes.length > 32 || value.edges.length > 64 || value.flows.length > 8) throw new Error('Network exceeds the 32 device / 64 cable / 8 flow limits.');
  const ids = new Set<string>();
  const validId = (id: unknown) => typeof id === 'string' && /^[a-zA-Z0-9_-]{1,80}$/.test(id);
  for (const n of value.nodes) {
    if (!validId(n.id) || ids.has(n.id) || !['router','switch','computer','server','cloud'].includes(n.data?.kind)
      || typeof n.data?.label !== 'string' || !n.data.label.trim() || n.data.label.length > 64 || typeof n.data?.address !== 'string'
      || !Number.isFinite(n.position?.x) || !Number.isFinite(n.position?.y)) throw new Error('The file contains an invalid or duplicate device.');
    ids.add(n.id);
  }
  const edgeIds = new Set<string>(), pairs = new Set<string>();
  for (const e of value.edges) {
    const pair = [e.source, e.target].sort().join(':');
    if (!validId(e.id) || edgeIds.has(e.id) || !ids.has(e.source) || !ids.has(e.target) || e.source === e.target || pairs.has(pair)
      || [e.sourceHandle,e.targetHandle].some(h => h != null && !['left','right','top','bottom'].includes(h))
      || !Number.isFinite(e.data?.capacity_mbps) || e.data.capacity_mbps < .01 || e.data.capacity_mbps > 1000
      || !Number.isFinite(e.data?.latency_ms) || e.data.latency_ms < 0 || e.data.latency_ms > 1000
      || !Number.isInteger(e.data?.buffer_bytes) || e.data.buffer_bytes < 0 || e.data.buffer_bytes > 1000000 || typeof e.data?.up !== 'boolean') throw new Error('The file contains an invalid cable.');
    edgeIds.add(e.id); pairs.add(pair);
  }
  const flowIds = new Set<string>();
  for (const f of value.flows) {
    if (!validId(f.id) || flowIds.has(f.id) || !ids.has(f.source) || !ids.has(f.target) || f.source === f.target
      || typeof f.label !== 'string' || typeof f.color !== 'string' || !Number.isFinite(f.rate_mbps) || f.rate_mbps < 0 || f.rate_mbps > 10
      || !Number.isInteger(f.packet_bytes) || f.packet_bytes < 64 || f.packet_bytes > 9000) throw new Error('The file contains invalid traffic settings.');
    flowIds.add(f.id);
  }
  return cleanNetwork({ ...value, nodes: value.nodes.map((n: DeviceNode) => ({...n, type:'device'})), edges: value.edges.map((e: CableEdge) => ({...e, type:'cable'})) });
}

export function removeDevice(network: Network, id: string): Network {
  return {...network, nodes: network.nodes.filter(n => n.id !== id), edges: network.edges.filter(e => e.source !== id && e.target !== id), flows: network.flows.filter(f => f.source !== id && f.target !== id)};
}

export function routeNames(route: string[], network: Network): string {
  if (!route.length) return 'No available path';
  const devices: string[] = [];
  for (const id of route) {
    const [cableId, direction] = id.split(':');
    const edge = network.edges.find(e => e.id === cableId);
    if (!edge) continue;
    if (!devices.length) devices.push(direction === 'rev' ? edge.target : edge.source);
    devices.push(direction === 'rev' ? edge.source : edge.target);
  }
  return devices.map(id => network.nodes.find(n => n.id === id)?.data.label ?? id).join(' → ');
}

export async function api<T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST'): Promise<T> {
  const response = await fetch(`/api${path}`, {method, headers: {'Content-Type': 'application/json'}, ...(body === undefined ? {} : {body: JSON.stringify(body)})});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The simulation service is unavailable.');
  return data;
}

export function download(name: string, data: unknown) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}));
  link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
