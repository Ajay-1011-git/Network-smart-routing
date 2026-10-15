"""Admission/egress gates around reused Port and Wire components."""

from smartroute._vendor.ns_py.port import Port
from smartroute._vendor.ns_py.wire import Wire
from smartroute.contracts import LinkObservation


class _Gate:
    def __init__(self, callback):
        self.put = callback


class LinkAdapter:
    def __init__(self, env, spec, advance, drop):
        self.env, self.spec, self.drop = env, spec, drop
        self.up, self.capacity = True, spec.capacity_bps
        self.attempted = self.admitted = self.served = self.dropped = 0
        self.spans = []
        self.port = Port(
            env,
            rate=self.capacity,
            qlimit=spec.buffer_bytes,
            limit_bytes=True,
            on_service_start=self.start,
            on_service_end=self.finish,
        )
        self.wire = Wire(env, lambda: spec.propagation_s)
        self.port.out = _Gate(self.egress)
        self.wire.out = _Gate(advance)

    def start(self, packet, time, rate):
        self.spans.append((time, time + packet.size * 8 / rate))

    def finish(self, packet, time):
        self.served += int(packet.size * 8)

    def egress(self, packet):
        if self.up:
            self.wire.put(packet)
        else:
            self.dropped += 1
            self.drop(packet, "link_down")

    def put(self, packet):
        self.attempted += int(packet.size * 8)
        if not self.up:
            self.dropped += 1
            self.drop(packet, "link_down")
            return
        before = self.port.packets_dropped
        self.port.put(packet)
        if self.port.packets_dropped != before:
            self.dropped += 1
            self.drop(packet, "buffer_overflow")
        else:
            self.admitted += int(packet.size * 8)

    def observe(self, start, end):
        busy = sum(max(0.0, min(end, b) - max(start, a)) for a, b in self.spans)
        self.spans = [(a, b) for a, b in self.spans if b > end]
        spec = self.spec
        observation = LinkObservation(
            spec.id,
            spec.src,
            spec.dst,
            self.up,
            self.capacity,
            spec.propagation_s,
            spec.buffer_bytes,
            int(self.port.byte_size),
            self.attempted,
            self.admitted,
            self.served,
            self.dropped,
            busy,
        )
        self.attempted = self.admitted = self.served = self.dropped = 0
        return observation
