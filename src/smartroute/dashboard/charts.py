"""Sampled-state replay; no fabricated packet animation."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

POSITIONS = {"S": (0, 0), "A": (1, 1), "B": (1, -1), "C": (2, 1), "D": (2, -1), "T": (3, 0)}


def topology_figure(config, snapshot=None, route=(), demands=None):
    figure = go.Figure()
    observations = {e.id: e for e in snapshot.links} if snapshot else {}
    coordinates = dict(POSITIONS)
    for index, node in enumerate(config.nodes):
        coordinates.setdefault(node, (index % 4, index // 4))
    for link in config.links:
        a, b = coordinates[link.src], coordinates[link.dst]
        edge = observations.get(link.id)
        up = edge.up if edge else True
        utilization = edge.busy_s / snapshot.interval_s if edge else 0
        color = "#fb7185" if not up else "#fbbf24" if utilization > 0.8 else "#35d4ae"
        projected = (demands or {}).get(link.id)
        label = (
            f"{link.id}<br>{(edge.capacity_bps if edge else link.capacity_bps) / 1e6:.2f} Mbit/s"
            f"<br>Service utilization: {utilization:.0%}<br>Resident bytes: {edge.resident_bytes if edge else 0}"
            f"<br>Status: {'up' if up else 'down'}"
        )
        if projected is not None:
            label += f"<br>Estimated offered ratio: {projected:.2f}"
        figure.add_trace(
            go.Scatter(
                x=[a[0], b[0]],
                y=[a[1], b[1]],
                mode="lines",
                line={
                    "color": color,
                    "width": 7 if link.id in route else 3,
                    "dash": "solid" if up else "dash",
                },
                text=[label, label],
                hoverinfo="text",
                showlegend=False,
            )
        )
        figure.add_annotation(
            x=0.35 * a[0] + 0.65 * b[0],
            y=0.35 * a[1] + 0.65 * b[1],
            ax=0.55 * a[0] + 0.45 * b[0],
            ay=0.55 * a[1] + 0.45 * b[1],
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.4,
            arrowwidth=2,
            arrowcolor=color,
        )
    figure.add_trace(
        go.Scatter(
            x=[coordinates[n][0] for n in config.nodes],
            y=[coordinates[n][1] for n in config.nodes],
            mode="markers+text",
            marker={"size": 44, "color": "#182c3b", "line": {"width": 2, "color": "#9eead1"}},
            text=list(config.nodes),
            textfont={"color": "#e6f5ef", "size": 16},
            textposition="middle center",
            hoverinfo="text",
            showlegend=False,
        )
    )
    figure.update_layout(
        height=380,
        margin={"l": 35, "r": 35, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False, "range": [-0.3, 3.3]},
        yaxis={"visible": False, "range": [-1.4, 1.4]},
        font={"color": "#d6e5df"},
    )
    return figure


def source_frame(result, flow_id):
    rates = []
    packets = [p for p in result.packets if p.flow_id == flow_id]
    times = np.array([p.generated_s for p in packets])
    prefix = np.cumsum([0] + [p.size_bytes * 8 for p in packets])
    forecasts = {(f.issued_s, f.flow_id): f for d in result.decisions for f in d.decision.forecasts}
    for snapshot in result.snapshots:
        flow = next(f for f in snapshot.flows if f.id == flow_id)
        row = {"issued_s": snapshot.time_s, "past-window observed Mbit/s": flow.offered_bps / 1e6}
        forecast = forecasts.get((snapshot.time_s, flow_id))
        if forecast:
            row["forecast next-horizon mean Mbit/s"] = forecast.rate_bps / 1e6
            row["status"] = forecast.status
        if (
            snapshot.time_s + snapshot.horizon_s
            <= result.config.warmup_s + result.config.measure_s + 1e-8
        ):
            a, b = np.searchsorted(times, [snapshot.time_s, snapshot.time_s + snapshot.horizon_s])
            row["actual next-horizon mean Mbit/s (offline)"] = (
                float(prefix[b] - prefix[a]) / snapshot.horizon_s / 1e6
            )
        rates.append(row)
    return pd.DataFrame(rates)
