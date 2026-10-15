import { Cloud, Monitor, Router, Server, Network } from 'lucide-react';
import type { DeviceKind } from './model';

export function DeviceIcon({kind, size=24}: {kind:DeviceKind; size?:number}) {
  const Icon = {router:Router, switch:Network, computer:Monitor, server:Server, cloud:Cloud}[kind];
  return <Icon size={size} strokeWidth={1.5}/>;
}
