import { describe, expect, it } from 'vitest';
import { cleanNetwork, demoNetwork, parseNetwork, removeDevice, routeNames, toApi } from './model';

describe('network editing and persistence',()=>{
  it('round-trips the complete editable network without runtime telemetry',()=>{
    const n=demoNetwork();
    n.edges[0].data!.packets=[];n.edges[0].data!.utilization=.8;
    const restored=parseNetwork(JSON.stringify(n));
    expect(restored).toEqual(cleanNetwork(n));
    expect(restored.edges[0].data).not.toHaveProperty('utilization');
    expect(toApi(restored).connections[1].capacity_mbps).toBe(1);
  });
  it('removes attached cables and affected traffic when deleting a device',()=>{
    const n=removeDevice(demoNetwork(),'pc1');
    expect(n.nodes).toHaveLength(5);expect(n.edges).toHaveLength(6);expect(n.flows).toHaveLength(0);
  });
  it('rejects duplicate cables and unsafe or invalid imported values',()=>{
    const duplicate=demoNetwork();duplicate.edges.push({...duplicate.edges[0],id:'duplicate'});
    expect(()=>parseNetwork(JSON.stringify(duplicate))).toThrow('invalid cable');
    for(const invalid of [0,-1,'100',null]){
      const n=demoNetwork();n.edges[0].data!.capacity_mbps=invalid as number;
      expect(()=>parseNetwork(JSON.stringify(n))).toThrow('invalid cable');
    }
  });
  it('rejects dangling flow endpoints and duplicate device IDs',()=>{
    const n=demoNetwork();n.flows[0].target='missing';
    expect(()=>parseNetwork(JSON.stringify(n))).toThrow('invalid traffic');
    const other=demoNetwork();other.nodes.push(other.nodes[0]);
    expect(()=>parseNetwork(JSON.stringify(other))).toThrow('duplicate device');
  });
  it('labels forward and reverse routes with their actual device sequence',()=>{
    expect(routeNames(['c2:fwd','c3:fwd'],demoNetwork())).toBe('Gateway → Core Alpha → Edge router');
    expect(routeNames(['c3:rev','c2:rev'],demoNetwork())).toBe('Edge router → Core Alpha → Gateway');
  });
});
