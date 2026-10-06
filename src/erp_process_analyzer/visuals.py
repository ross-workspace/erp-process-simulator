"""Process-map rendering as a self-contained SVG.

Layout: the most common variant forms the main row, left to right. Other
activities sit in a row above, next to the step they usually follow. Forward
skips arc below the main row; edges that go back to an earlier step (loops
and rework) are drawn as dashed red arcs.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

import pandas as pd

from .analyzer import Analysis

STEP = 174
NODE_W, NODE_H = 128, 52
PAD_X = 24
EXTRA_Y = 52
MAIN_Y_WITH_EXTRAS, MAIN_Y_ALONE = 178, 64
BELOW_MAIN = 118  # room for skip arcs and their labels

MAIN_PALETTE = [
    ("#e1ebff", "#9db8f2"),
    ("#ebe4ff", "#b9a6f0"),
    ("#efeaff", "#c4b8f2"),
    ("#ffe3e6", "#f2a5ae"),
    ("#fff3cc", "#efcf6b"),
    ("#e0f2fe", "#93c9ec"),
]
TERMINAL = ("#dcf5e3", "#8fd3a3")
EXTRA = ("#eef1f6", "#c5cedd")

STRONG, WEAK, LOOP = "#2c4683", "#b4c0d4", "#e5484d"


def short_duration(hours: float | None) -> str:
    if hours is None or pd.isna(hours):
        return "—"
    if hours < 1:
        return f"{hours * 60:.0f} min"
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} d"


@dataclass(frozen=True)
class _Node:
    name: str
    x: float  # centre, in canvas units
    y: float
    rank: float  # position along the process, used to spot back edges
    main: bool
    fill: str
    stroke: str


def _main_path(analysis: Analysis) -> list[str]:
    if analysis.variants.empty:
        return analysis.activities["activity"].tolist()
    seen: list[str] = []
    for activity in analysis.variants.iloc[0]["variant"]:
        if activity not in seen:
            seen.append(activity)
    return seen


def _layout(analysis: Analysis, edges: pd.DataFrame) -> dict[str, _Node]:
    main = _main_path(analysis)
    index = {name: position for position, name in enumerate(main)}
    has_extras = bool(set(analysis.activities["activity"]) - set(main))
    main_y = MAIN_Y_WITH_EXTRAS if has_extras else MAIN_Y_ALONE
    nodes: dict[str, _Node] = {}
    for position, name in enumerate(main):
        terminal = position in (0, len(main) - 1)
        fill, stroke = TERMINAL if terminal else MAIN_PALETTE[(position - 1) % len(MAIN_PALETTE)]
        nodes[name] = _Node(name, PAD_X + NODE_W / 2 + position * STEP, main_y, position, True, fill, stroke)

    all_edges = analysis.transitions
    extras = [name for name in analysis.activities["activity"] if name not in index]
    wanted: list[tuple[float, str]] = []
    for name in extras:
        incoming = all_edges.loc[all_edges["to_activity"].eq(name) & all_edges["from_activity"].isin(index)]
        outgoing = all_edges.loc[all_edges["from_activity"].eq(name) & all_edges["to_activity"].isin(index)]
        if not incoming.empty:
            weights = incoming["cases"]
            rank = float((incoming["from_activity"].map(index) * weights).sum() / weights.sum()) + 0.5
        elif not outgoing.empty:
            weights = outgoing["cases"]
            rank = float((outgoing["to_activity"].map(index) * weights).sum() / weights.sum()) - 0.5
        else:
            rank = len(main)
        wanted.append((rank, name))

    taken: list[float] = []
    for rank, name in sorted(wanted):
        while any(abs(rank - other) < 0.95 for other in taken):
            rank += 1.0
        taken.append(rank)
        nodes[name] = _Node(name, PAD_X + NODE_W / 2 + rank * STEP, EXTRA_Y, rank, False, *EXTRA)
    return nodes


def _wrap(name: str) -> list[str]:
    if len(name) <= 18 or " " not in name:
        return [name]
    words, first = name.split(), ""
    while words and len(f"{first} {words[0]}".strip()) <= 18:
        first = f"{first} {words.pop(0)}".strip()
    return [first, " ".join(words)]


def _edge_path(a: _Node, b: _Node, depth: float) -> tuple[str, tuple[float, float]]:
    """Return an SVG path and the point used for its label."""

    if a.name == b.name:
        x, top = a.x + NODE_W / 2 - 18, a.y - NODE_H / 2
        return f"M {x - 14} {top} C {x - 20} {top - 38}, {x + 26} {top - 38}, {x + 8} {top - 2}", (x, top - 34)
    if a.main and b.main:
        if b.rank == a.rank + 1:
            x0, x1 = a.x + NODE_W / 2, b.x - NODE_W / 2 - 3
            return f"M {x0} {a.y} L {x1} {b.y}", ((x0 + x1) / 2, a.y - 9)
        if b.rank > a.rank:
            y = a.y + NODE_H / 2
            x0, x1 = a.x + 12, b.x - 12
            return f"M {x0} {y} C {x0} {y + depth}, {x1} {y + depth}, {x1} {y + 3}", ((x0 + x1) / 2, y + depth * 0.75 + 4)
        y = a.y - NODE_H / 2
        x0, x1 = a.x - 12, b.x + 12
        return f"M {x0} {y} C {x0} {y - depth}, {x1} {y - depth}, {x1} {y - 3}", ((x0 + x1) / 2, y - depth * 0.75 - 4)
    if a.main != b.main:
        upper, lower = (b, a) if a.main else (a, b)
        # Upward edges run on the left, downward on the right, so a pair of
        # edges between the same two nodes never overlaps.
        offset = -18 if a.main else 18
        x_low = lower.x + max(min((upper.x - lower.x) * 0.45, NODE_W / 2 - 14), -(NODE_W / 2 - 14)) + offset
        x_up = upper.x + offset
        y_low, y_up = lower.y - NODE_H / 2, upper.y + NODE_H / 2
        if a.main:
            path = f"M {x_low} {y_low} C {x_low} {y_low - 45}, {x_up} {y_up + 45}, {x_up} {y_up + 3}"
        else:
            path = f"M {x_up} {y_up} C {x_up} {y_up + 45}, {x_low} {y_low - 45}, {x_low} {y_low - 3}"
        return path, ((x_low + x_up) / 2 + 4, (y_low + y_up) / 2)
    direction = 1 if b.x > a.x else -1
    x0, x1 = a.x + direction * NODE_W / 2, b.x - direction * (NODE_W / 2 + 3)
    return f"M {x0} {a.y} L {x1} {b.y}", ((x0 + x1) / 2, a.y - 9)


def process_map_svg(analysis: Analysis, *, mode: str = "frequency", max_edges: int = 25) -> str:
    """Render the directly-follows graph. ``mode`` is "frequency" or "duration"."""

    if analysis.activities.empty:
        return "<p>No events to map.</p>"
    edges = analysis.transitions.nlargest(max_edges, "cases") if not analysis.transitions.empty else analysis.transitions
    nodes = _layout(analysis, edges)
    width = max(node.x for node in nodes.values()) + NODE_W / 2 + PAD_X
    height = max(node.y for node in nodes.values()) + BELOW_MAIN
    max_cases = int(edges["cases"].max()) if len(edges) else 1
    total = max(analysis.total_cases, 1)

    parts = [
        f'<svg class="pmap" viewBox="0 0 {width:.0f} {height:.0f}" xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="Process map" font-family="Inter, system-ui, sans-serif">',
        "<defs>",
    ]
    for key, color in (("strong", STRONG), ("weak", WEAK), ("loop", LOOP)):
        parts.append(
            f'<marker id="arrow-{key}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" '
            f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
    parts.append("</defs>")

    labels: list[str] = []
    skip_depth: dict[str, int] = {}
    for edge in edges.sort_values("cases").itertuples(index=False):
        a, b = nodes.get(edge.from_activity), nodes.get(edge.to_activity)
        if a is None or b is None:
            continue
        backward = b.rank <= a.rank
        prominence = edge.cases / max_cases
        kind = "loop" if backward else ("strong" if prominence >= 0.3 else "weak")
        color = {"loop": LOOP, "strong": STRONG, "weak": WEAK}[kind]
        span = abs(b.rank - a.rank)
        lane = "below" if not backward else "above"
        level = skip_depth.get(lane, 0)
        if a.main and b.main and span > 1:
            skip_depth[lane] = level + 1
        depth = (46 if backward else 52) + 10 * min(span, 4) + 12 * level
        path, (lx, ly) = _edge_path(a, b, depth)
        dash = ' stroke-dasharray="6 4"' if backward else ""
        stroke_width = 1.4 + 3.6 * prominence
        tooltip = (
            f"{edge.from_activity} → {edge.to_activity}\n"
            f"{edge.cases:,} cases · {edge.occurrences:,} occurrences\n"
            f"Median {short_duration(edge.median_hours)} · P90 {short_duration(edge.p90_hours)}"
        )
        parts.append(
            f'<g class="edge"><title>{escape(tooltip)}</title>'
            f'<path d="{path}" fill="none" stroke="transparent" stroke-width="14"/>'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{stroke_width:.2f}"{dash} '
            f'stroke-linecap="round" marker-end="url(#arrow-{kind})"/></g>'
        )
        label = f"{edge.cases:,}" if mode == "frequency" else short_duration(edge.median_hours)
        text_color = LOOP if backward else "#56647e"
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="11.5" font-weight="600" '
            f'fill="{text_color}" paint-order="stroke" stroke="#ffffff" stroke-width="4" stroke-linejoin="round">'
            f"{escape(label)}</text>"
        )

    activity_stats = analysis.activities.set_index("activity")
    for node in nodes.values():
        stats = activity_stats.loc[node.name]
        lines = _wrap(node.name)
        count = f"{int(stats['cases']):,}"
        if not node.main:
            count += f" ({stats['cases'] / total:.0%})"
        tooltip = f"{node.name}\n{int(stats['cases']):,} cases · {int(stats['occurrences']):,} events"
        left, top = node.x - NODE_W / 2, node.y - NODE_H / 2
        parts.append(
            f'<g class="node"><title>{escape(tooltip)}</title>'
            f'<rect x="{left:.1f}" y="{top:.1f}" width="{NODE_W}" height="{NODE_H}" rx="9" '
            f'fill="{node.fill}" stroke="{node.stroke}" stroke-width="1.2"/>'
        )
        first_y = node.y - (11 if len(lines) == 2 else 4)
        for offset, line in enumerate(lines):
            parts.append(
                f'<text x="{node.x:.1f}" y="{first_y + offset * 14:.1f}" text-anchor="middle" '
                f'font-size="13" font-weight="650" fill="#17233f">{escape(line)}</text>'
            )
        parts.append(
            f'<text x="{node.x:.1f}" y="{first_y + len(lines) * 14 + 3:.1f}" text-anchor="middle" '
            f'font-size="12.5" fill="#3d4a63">{escape(count)}</text></g>'
        )

    parts.extend(labels)
    parts.append("</svg>")
    return "".join(parts)
