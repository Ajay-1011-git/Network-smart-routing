# Reused ns.py components

Source: https://github.com/TL-System/ns.py
Commit: 7218b680a72a59b30bc3271d8ca0965d8556cee9
License: Apache-2.0; full upstream LICENSE included.

Files: ns/packet/packet.py, ns/port/port.py, ns/port/wire.py.
Modification: relocate files to smartroute._vendor.ns_py and change the Packet import in port.py and wire.py to a relative import. Source headers added for provenance. No other behavior changes.

These selected files depend on SimPy and the Python standard library. They were smoke-tested on Python 3.12.14 with SimPy 4.1.1. This does not validate the complete upstream package, every queue boundary, dynamic failures, or the planned SmartRoute application. The complete upstream 0.5.0 package currently declares Python >=3.14, !=3.14.1; this extraction intentionally avoids adopting that package's entire environment.

Review upstream NOTICE and per-file notices again before redistribution; preserve any applicable notices found. Do not add TCP, proxy traffic, RED, or other upstream components without a separate need and audit.

SmartRoute modification: optional on_service_start(packet, time, captured_rate) and
on_service_end(packet, time) callbacks surround the existing service timeout.
Admission, FIFO, resident accounting, timeout and handoff behavior are unchanged.
