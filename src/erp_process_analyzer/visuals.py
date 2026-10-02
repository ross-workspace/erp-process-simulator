"""Process-map visualization shared by dashboard views."""

from __future__ import annotations

import math

import networkx as nx
import plotly.graph_objects as go

from .analyzer import Analysis

CANONICAL = {
    "Order Created": (0.0, 0.0),
    "Order Approved": (1.7, 0.0),
    "Picking Started": (3.4, 0.0),
    "Packed": (5.1, 0.0),
    "Shipped": (6.8, 0.0),
    "Invoice Created": (8.5, 0.0),
    "Payment Received": (10.2, 0.0),
    "Order Edited": (2.55, 1.1),
}

SHORT_LABELS = {
    "Order Created": "Created",
    "Order Approved": "Approved",
    "Order Edited": "Edited",
    "Picking Started": "Picking",
    "Packed": "Packed",
    "Shipped": "Shipped",
    "Invoice Created": "Invoice",
    "Payment Received": "Paid",
}

NODE_COLORS = {
    "Order Created": "#c7f0d1",
    "Order Approved": "#d7e6ff",
    "Picking Started": "#e5dcff",
    "Packed": "#e9e5ff",
    "Shipped": "#fbdadd",
    "Invoice Created": "#ffedb8",
    "Payment Received": "#c9efd5",
    "Order Edited": "#e9eef7",
}


def _positions(names: list[str], edges: list[tuple[str, str]]) -> dict[str, tuple[float, float]]:
    if set(names).issubset(CANONICAL):
        return {name: CANONICAL[name] for name in names}
    graph = nx.DiGraph()
    graph.add_nodes_from(names)
    graph.add_edges_from(edges)
    layout = nx.spring_layout(graph, seed=42, scale=4.0)
    return {name: (float(value[0]), float(value[1])) for name, value in layout.items()}


def make_process_map(analysis: Analysis, *, max_edges: int = 25) -> go.Figure:
    """Show a frequency-weighted directly-follows graph with deterministic layout."""

    activities = analysis.activities
    transitions = analysis.transitions.nlargest(max_edges, "cases") if not analysis.transitions.empty else analysis.transitions
    names = activities["activity"].tolist()
    edge_names = list(zip(transitions["from_activity"], transitions["to_activity"]))
    positions = _positions(names, edge_names)
    figure = go.Figure()

    max_count = int(transitions["cases"].max()) if len(transitions) else 1
    for edge in transitions.itertuples(index=False):
        x0, y0 = positions[edge.from_activity]
        x1, y1 = positions[edge.to_activity]
        prominence = edge.cases / max_count
        color = "#344e89" if prominence >= 0.32 else "#aebbd0"
        if edge.from_activity == edge.to_activity:
            figure.add_shape(
                type="path",
                path=f"M {x0+0.12},{y0+0.2} Q {x0+0.7},{y0+0.9} {x0+0.35},{y0-0.05}",
                line={"color": color, "width": 2},
            )
            continue
        distance = math.hypot(x1 - x0, y1 - y0)
        if distance == 0:
            continue
        inset = min(0.38 / distance, 0.22)
        sx, sy = x0 + (x1 - x0) * inset, y0 + (y1 - y0) * inset
        ex, ey = x1 - (x1 - x0) * inset, y1 - (y1 - y0) * inset
        figure.add_annotation(
            x=ex, y=ey, ax=sx, ay=sy,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowsize=1.15,
            arrowwidth=1.25 + 2.5 * prominence, arrowcolor=color,
        )
        figure.add_trace(
            go.Scatter(
                x=[(x0 + x1) / 2], y=[(y0 + y1) / 2],
                mode="markers", marker={"size": 25, "opacity": 0},
                hovertemplate=(
                    f"<b>{edge.from_activity} → {edge.to_activity}</b><br>"
                    f"{edge.cases:,} distinct cases · {edge.occurrences:,} occurrences<br>"
                    f"Median gap {edge.median_hours:.1f} h · P90 {edge.p90_hours:.1f} h<extra></extra>"
                ),
                showlegend=False,
            )
        )

    for activity in activities.itertuples(index=False):
        x, y = positions[activity.activity]
        short_name = SHORT_LABELS.get(activity.activity, activity.activity[:10])
        figure.add_trace(
            go.Scatter(
                x=[x], y=[y], mode="markers+text",
                marker={"size": 47, "symbol": "square", "color": NODE_COLORS.get(activity.activity, "#e8efff"), "line": {"color": "#a9bce5", "width": 1}},
                text=[f"<b>{short_name}</b><br>{activity.cases:,}"],
                textposition="middle center",
                textfont={"size": 8, "color": "#17233f"},
                hovertemplate=(
                    f"<b>{activity.activity}</b><br>"
                    f"{activity.cases:,} distinct cases · {activity.occurrences:,} occurrences<extra></extra>"
                ),
                showlegend=False,
            )
        )

    figure.update_layout(
        height=270,
        margin={"l": 25, "r": 25, "t": 18, "b": 18},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"visible": False, "range": [min(x for x, _ in positions.values()) - 0.9, max(x for x, _ in positions.values()) + 0.9]},
        yaxis={"visible": False, "range": [min(y for _, y in positions.values()) - 0.65, max(y for _, y in positions.values()) + 0.65]},
        hovermode="closest",
        dragmode="pan",
    )
    return figure
