"""Run with python -m streamlit run src/smartroute/dashboard/app.py."""

import json
from dataclasses import asdict

import plotly.express as px
import streamlit as st

from smartroute.cli import POLICIES
from smartroute.dashboard.charts import source_frame, topology_figure
from smartroute.dashboard.service import (
    MODEL,
    compare,
    export_json,
    forecast_frame,
    import_result,
    simulate,
    summary_frame,
    telemetry_frame,
)
from smartroute.engine.topology import SCENARIOS, TOPOLOGIES, catalog_config
from smartroute.intelligence.model_io import file_hash, source_hash
from smartroute.serialization import canonical, digest

st.set_page_config(page_title="SmartRoute · Routing laboratory", page_icon="◈", layout="wide")
st.markdown(
    """<style>
.stApp{background:#0c1720;color:#e3eee9}
h1{letter-spacing:-1.5px;font-weight:650!important}h2,h3{letter-spacing:-.5px}
[data-testid=stSidebar]{background:#101f29;border-right:1px solid #243641}
[data-testid=stMetric]{background:#142630;padding:18px;border:1px solid #2a4049;border-radius:12px}
[data-testid=stMetricLabel]{color:#a5bab4}.stButton>button[kind=primary]{background:#a4edc8;color:#10241b;border:0}
div[data-testid=stTabs] button{font-size:15px}.eyebrow{color:#9dd9bb;letter-spacing:2px;font-size:11px}
.intro{color:#9cb4ac;font-size:16px;max-width:820px}.tag{color:#a5edc9;border:1px solid #385e50;padding:5px 10px;border-radius:20px;font-size:12px}
</style>""",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False, max_entries=24)
def cached_run(config, policy, config_hash, model_hash, code_hash):
    return simulate(config, policy)


@st.cache_data(show_spinner=False, max_entries=8)
def cached_compare(config, config_hash, model_hash, code_hash):
    return compare(config)


with st.sidebar:
    st.markdown("### ◈ SmartRoute")
    st.caption("A NETWORK INTELLIGENCE LAB")
    st.divider()
    topology = st.selectbox("Topology", TOPOLOGIES)
    scenario = st.selectbox("Traffic scenario", SCENARIOS, index=1)
    seed = st.number_input("Traffic seed", min_value=0, max_value=9999, value=0, step=1)
    policy = st.selectbox("Routing policy", POLICIES, index=1)
    load = st.slider("Offered-load multiplier", 0.25, 2.0, 1.0, 0.05)
    event_time = (
        st.slider("Event time (seconds)", 0.0, 9.0, 4.0, 0.2)
        if scenario in ("capacity", "failure")
        else None
    )
    run_clicked = st.button("Run simulation", type="primary", width="stretch")
    comparison_clicked = st.button("Compare all five policies", width="stretch")
    if st.button("Reset replay", width="stretch"):
        for key in ("result", "comparison", "replay_index"):
            st.session_state.pop(key, None)
    st.divider()
    st.caption("Deterministic traffic · directed links · real finite queues")
    with st.expander("Open a saved replay"):
        upload = st.file_uploader("RunResult JSON", type="json")
        if st.button("Load replay") and upload:
            try:
                st.session_state.result = import_result(upload.getvalue())
                st.session_state.pop("replay_index", None)
            except Exception as exc:
                st.error(str(exc))

st.markdown('<span class="eyebrow">OBSERVE / PREDICT / ROUTE</span>', unsafe_allow_html=True)
title, badge = st.columns([5, 1])
title.title("A clearer path through congestion.")
badge.markdown('<br><span class="tag">● LOCAL SIMULATION</span>', unsafe_allow_html=True)
st.markdown(
    '<p class="intro">Explore how changing demand moves through a network. Replay real simulated state, inspect routing decisions, and compare prediction with conventional control.</p>',
    unsafe_allow_html=True,
)

try:
    config = catalog_config(topology, scenario, int(seed), load, event_time)
    model_hash = (
        file_hash(MODEL / "model.joblib") if (MODEL / "model.joblib").exists() else "absent"
    )
    code_hash = source_hash()
    if run_clicked:
        with st.spinner("Generating traffic and routing packets…"):
            st.session_state.result = cached_run(
                config, policy, digest(config), model_hash, code_hash
            )
            st.session_state.pop("replay_index", None)
    if comparison_clicked:
        with st.spinner("Running five policies on one immutable packet trace…"):
            st.session_state.comparison = cached_compare(
                config, digest(config), model_hash, code_hash
            )
            st.session_state.result = st.session_state.comparison[POLICIES.index(policy)]
            st.session_state.pop("replay_index", None)
except Exception as exc:
    st.error(f"Simulation could not run: {exc}")

result = st.session_state.get("result")
if result is None:
    st.divider()
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Your network, ready to explore")
        st.plotly_chart(topology_figure(config), width="stretch")
    with right:
        st.subheader("Start with a question")
        st.markdown(
            "1. Choose a traffic pattern and routing policy.\n2. Run the simulation.\n3. Scrub the replay to inspect queue pressure and route choices."
        )
        st.info(
            "Try **ramp** for growing demand, or **failure** to watch a broken path get repaired."
        )
        st.caption("No run has been generated yet. The diagram shows the configured topology.")
    st.stop()

if digest(config) != result.config_sha256 or policy != result.policy_name:
    st.info("Showing the saved run below. Use Run simulation to apply the current controls.")
st.caption(
    f"{result.config.topology_id} / {result.config.scenario_id} · seed {result.config.seed} · {result.policy_name} · trace {result.trace_sha256[:14]}"
)
m = result.metrics
columns = st.columns(5)
columns[0].metric(
    "Packet delivery", f"{m.delivery_ratio:.1%}" if m.delivery_ratio is not None else "—"
)
columns[1].metric("Cohort goodput", f"{m.throughput_bps / 1e6:.3f} Mbit/s")
columns[2].metric(
    "P95 latency · delivered",
    f"{m.p95_latency_s * 1000:.1f} ms" if m.p95_latency_s is not None else "—",
)
columns[3].metric("Route changes", str(m.route_changes))
columns[4].metric("Pending at cutoff", str(m.pending))
st.caption(
    f"Packets generated during [{result.config.warmup_s:g}, {result.config.warmup_s + result.config.measure_s:g}) seconds; delivery includes the {result.config.drain_s:g}-second drain. Goodput uses the {result.config.measure_s:g}-second generation cohort. Latency excludes dropped/pending packets."
)

replay, forecast_tab, decisions_tab, comparison_tab, exports = st.tabs(
    ["Network replay", "Demand & forecasts", "Route explanations", "Policy comparison", "Exports"]
)
with replay:
    index = st.slider("Replay control tick", 0, len(result.snapshots) - 1, 0, key="replay_index")
    snap, record = result.snapshots[index], result.decisions[index]
    flow_id = st.selectbox("Highlight flow", [f.id for f in snap.flows])
    choice = next(r for r in record.decision.routes if r.flow_id == flow_id)
    demands = {edge.id: 0.0 for edge in snap.links}
    forecast_lookup = {f.flow_id: f for f in record.decision.forecasts}
    for route in record.decision.routes:
        flow = next(f for f in snap.flows if f.id == route.flow_id)
        rate = forecast_lookup[flow.id].rate_bps if flow.id in forecast_lookup else flow.offered_bps
        for edge_id in route.link_ids:
            demands[edge_id] += rate / next(e.capacity_bps for e in snap.links if e.id == edge_id)
    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader(f"Network at {snap.time_s:.1f} s")
        st.plotly_chart(
            topology_figure(result.config, snap, choice.link_ids, demands), width="stretch"
        )
        st.caption(
            "Mint: serving · amber: >80% busy · coral dashed: down. Thick edges show the selected flow's post-decision route. Hover for capacity, resident bytes and estimated offered ratio."
        )
    with col2:
        st.subheader("Decision at this tick")
        st.write(" → ".join(choice.link_ids) or "No feasible path")
        st.write(f"**Reason:** {choice.reason}")
        forecast = forecast_lookup.get(flow_id)
        if forecast:
            st.write(f"**Forecast:** {forecast.rate_bps / 1e6:.3f} Mbit/s · {forecast.status}")
            st.caption(forecast.reason)
        st.write(
            f"Normal changes: **{m.route_changes - m.forced_route_changes}** · forced: **{m.forced_route_changes}**"
        )
        st.write(
            f"Cohort outcomes: {m.delivered} delivered / {m.dropped} dropped / {m.pending} pending"
        )
    st.dataframe(
        telemetry_frame(result).query("time_s == @snap.time_s"), hide_index=True, width="stretch"
    )
    st.caption(
        "Service utilization = exact serialization busy time / interval. Estimated offered ratios can exceed 1; resident bytes include the packet in service. Replay shows sampled simulated state."
    )

with forecast_tab:
    data = source_frame(result, flow_id)
    lines = [c for c in data.columns if "Mbit/s" in c]
    st.subheader("Source demand, observed and anticipated")
    st.plotly_chart(
        px.line(
            data,
            x="issued_s",
            y=lines,
            labels={
                "issued_s": "Forecast issuance time (seconds)",
                "value": "Source rate (Mbit/s)",
                "variable": "Series",
            },
            color_discrete_sequence=["#69dec0", "#c4b5fd", "#facc71"],
        ),
        width="stretch",
    )
    st.caption(
        "Observed rates summarize the preceding 0.2 seconds. Forecasts target the next 1-second mean at their issuance time. The offline target is computed after the run; it is never available to a policy."
    )
    if not record.decision.forecasts:
        st.info(
            "This conventional policy does not issue forecasts. Select a predictive policy to inspect its output and fallback reasons."
        )
    st.dataframe(forecast_frame(result), hide_index=True, width="stretch")

with decisions_tab:
    st.subheader("Why the route changed—or stayed")
    st.write(
        "Each dynamic controller removes a flow's current demand reservation, scores candidate paths after adding its demand, then reserves its chosen route before scoring the next flow."
    )
    st.code(
        "path cost = propagation + serialization + resident-byte penalty\n          + 0.02 × max(0, projected offered ratio − 0.70)² per link",
        language=None,
    )
    st.caption(
        "Ordinary changes need 10% cost improvement and a 1-second cooldown. A broken path bypasses these checks. Costs are controller estimates, not analytical latency predictions."
    )
    import pandas as pd

    decision_rows = [
        {"time_s": d.time_s, **asdict(r)}
        for d in result.decisions
        for r in d.decision.routes
        if r.flow_id == flow_id
    ]
    st.dataframe(pd.DataFrame(decision_rows), hide_index=True, width="stretch")
    st.subheader("Per-flow outcomes")
    flows_frame = pd.DataFrame([asdict(f) for f in result.flow_metrics])
    flows_frame["offered_normalized_delivery"] = (
        flows_frame.delivered / flows_frame.generated.replace(0, float("nan"))
    )
    st.dataframe(flows_frame, hide_index=True, width="stretch")

with comparison_tab:
    compared = st.session_state.get("comparison")
    if compared:
        if compared[0].config_sha256 != result.config_sha256:
            st.warning("This comparison uses a different configuration from the selected replay.")
        frame = summary_frame(compared)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.plotly_chart(
            px.bar(
                frame,
                x="policy",
                y="delivery_ratio",
                color="policy",
                range_y=[0, 1],
                labels={"delivery_ratio": "Cohort delivery ratio"},
            ),
            width="stretch",
        )
        st.caption(
            "All five policies share packet IDs, source arrival times and scheduled link events. A single run is an illustration; see docs/RESULTS.md for the paired test matrix."
        )
    else:
        st.info("Use Compare all five policies to run a paired experiment with these controls.")
    if (MODEL / "metadata.json").exists():
        metadata = json.loads((MODEL / "metadata.json").read_text())
        with st.expander("Model validation and limitations"):
            st.json(metadata["validation_scores"])
            st.write(
                "Warm-up and support checks fall back explicitly to persistence. Abrupt spikes without a precursor cannot be anticipated reliably. Better forecasting does not guarantee better routing."
            )

with exports:
    st.subheader("Take the evidence with you")
    st.download_button(
        "Result JSON / replay", export_json(result), "smartroute-result.json", "application/json"
    )
    st.download_button(
        "Expanded configuration JSON",
        canonical(result.config).encode(),
        "smartroute-config.json",
        "application/json",
    )
    st.download_button(
        "Summary CSV",
        summary_frame([result]).to_csv(index=False),
        "smartroute-summary.csv",
        "text/csv",
    )
    st.download_button(
        "Link telemetry CSV",
        telemetry_frame(result).to_csv(index=False),
        "smartroute-telemetry.csv",
        "text/csv",
    )
    st.download_button(
        "Forecasts CSV",
        forecast_frame(result).to_csv(index=False),
        "smartroute-forecasts.csv",
        "text/csv",
    )
    if st.session_state.get("comparison"):
        st.download_button(
            "Comparison CSV",
            summary_frame(st.session_state.comparison).to_csv(index=False),
            "smartroute-comparison.csv",
            "text/csv",
        )
