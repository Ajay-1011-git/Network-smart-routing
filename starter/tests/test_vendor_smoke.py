import unittest
import simpy
from smartroute._vendor.ns_py.packet import Packet
from smartroute._vendor.ns_py.port import Port
from smartroute._vendor.ns_py.wire import Wire

class VendorSmoke(unittest.TestCase):
    def trial(self, capacity):
        env = simpy.Environment()
        arrivals = []
        class Sink:
            def put(self, packet):
                arrivals.append((packet.packet_id, env.now))
        port = Port(env, rate=80, qlimit=capacity)
        wire = Wire(env, lambda: 0.01)
        port.out, wire.out = wire, Sink()
        for packet_id in range(3):
            port.put(Packet(0, 10, packet_id))
        env.run(until=4)
        return port, arrivals

    def test_finite_buffer_and_serialization(self):
        port, arrivals = self.trial(2)
        self.assertEqual(port.packets_dropped, 1)
        self.assertEqual([p for p, _ in arrivals], [0, 1])
        self.assertAlmostEqual(arrivals[0][1], 1.01)
        self.assertAlmostEqual(arrivals[1][1], 2.01)
        self.assertEqual(port.byte_size, 0)

    def test_zero_capacity(self):
        port, arrivals = self.trial(0)
        self.assertEqual(port.packets_dropped, 3)
        self.assertEqual(arrivals, [])

    def test_repeated_run(self):
        p1, a1 = self.trial(2)
        p2, a2 = self.trial(2)
        self.assertEqual(a1, a2)
        self.assertEqual(p1.packets_dropped, p2.packets_dropped)
