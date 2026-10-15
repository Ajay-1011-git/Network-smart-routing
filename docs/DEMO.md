# Local demonstration

Start from the README's locked environment. Launch:

```sh
python -m streamlit run src/smartroute/dashboard/app.py --server.address 127.0.0.1
```

1. Choose diamond / ramp / seed 0 / reactive and press Run simulation.
   Scrub replay ticks to inspect real resident bytes and service utilization.
2. Choose predictive-learned and run. In Demand & forecasts, compare the past observed
   window, next-horizon prediction and offline next-horizon target, all aligned at issuance.
   The first ten windows show an explicit persistence warm-up reason.
3. Choose failure and event time 4 seconds. At tick 20, inspect the down link and the
   forced route explanation. Queued packets may still serialize before an egress drop.
4. Press Compare all five policies. Packet/event hashes match across the comparison.
   Inspect delivery and pending alongside latency, including neutral/negative results.
5. Export result JSON, configuration, summary, telemetry, forecasts and comparison CSVs.
   Open the result JSON under Open a saved replay to reproduce the stored state.

Changing controls leaves the previous run labeled until Run/Compare is pressed. There
are no fixture results or fabricated animations. A replay represents simulated events
and sampled observations, not real packet capture.

Automated Streamlit AppTest exercises a real ramp run, scrubber tick selection, changed
controls, a real failure run and forecast reasons. Browser review additionally exercises
learned failure routing, explanations, topology state and a JSON download. Verification
details and evidence hashes are recorded in docs/evidence/acceptance.json.
