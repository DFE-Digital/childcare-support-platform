import json

import pandas as pd
from dash import dcc, html

from data.loader import FIELD_SOURCE_COLORS, PRESENCE_FIELDS
from layouts.detail_table import ALWAYS_ON_FIELDS, DEFAULT_VISIBLE_FIELDS

PANEL_HEIGHT = 500

# Shared styles — kept here so the JS badge colours match.
_ROW_HEIGHT = 14
_BAR_HEIGHT = 10
_LABEL_WIDTH = 220
_CHECKBOX_WIDTH = 12


def build_field_bars(
    sources_df: pd.DataFrame,
    selection: dict | None = None,
    checked_fields: set[str] | None = None,
) -> tuple[list, str]:
    """Build HTML bar rows and a companion JSON metadata string.

    Returns ``(bar_children, segment_data_json)`` where *bar_children* is a
    list of ``html.Div`` elements (one per field) and *segment_data_json* is a
    JSON string ``[{field, source, count, pct}, ...]`` in the same DOM order
    as the ``.bar-segment`` divs.
    """
    if sources_df.empty:
        return [], "[]"

    # Deduplicated ordered field list.
    seen: set[str] = set()
    ordered_fields: list[str] = []
    for f in sources_df["field"]:
        if f not in seen:
            seen.add(f)
            ordered_fields.append(f)

    sel_field = selection.get("field") if selection else None
    sel_source = selection.get("source") if selection else None
    has_selection = sel_field is not None and sel_source is not None

    # Determine which checkboxes should be checked.
    if checked_fields is None:
        visible = DEFAULT_VISIBLE_FIELDS
    else:
        visible = set(checked_fields) | ALWAYS_ON_FIELDS

    segment_data: list[dict] = []
    bar_rows: list = []

    for field in ordered_fields:
        field_df = sources_df[sources_df["field"] == field].sort_values(
            "source", key=lambda s: s.apply(lambda v: (v == "absent", v))
        )

        is_always_on = field in ALWAYS_ON_FIELDS
        is_checked = field in visible

        chk_bg = "#1f77b4" if is_checked else "#fff"
        chk_border = "#1f77b4" if is_checked else "#999"
        checkbox = html.Div(
            "✓" if is_checked else "",
            id=f"field-chk-{field}",
            className="field-checkbox",
            style={
                "width": f"{_CHECKBOX_WIDTH}px",
                "height": f"{_CHECKBOX_WIDTH}px",
                "lineHeight": f"{_CHECKBOX_WIDTH}px",
                "flexShrink": "0",
                "marginRight": "2px",
                "border": f"1px solid {chk_border}",
                "borderRadius": "2px",
                "backgroundColor": chk_bg,
                "color": "#fff",
                "fontSize": "8px",
                "textAlign": "center",
                "cursor": "default" if is_always_on else "pointer",
                "userSelect": "none",
            },
            **{"data-field": field, "data-locked": "1" if is_always_on else ""},
        )

        segments: list = []
        for _, row in field_df.iterrows():
            source = row["source"]
            pct = row["pct"]
            count = int(row["count"])
            color = FIELD_SOURCE_COLORS.get(source, "#c7c7c7")

            if has_selection:
                is_selected = field == sel_field and source == sel_source
                opacity = 1.0 if is_selected else 0.3
            else:
                opacity = 1.0

            seg_style: dict = {
                "height": "100%",
                "backgroundColor": color,
                "opacity": opacity,
                "cursor": "pointer",
            }
            # Use flex:1 on the last segment to absorb rounding gaps.
            if source == "absent" or row.name == field_df.index[-1]:
                seg_style["flex"] = f"{pct} 0 0%"
            else:
                seg_style["width"] = f"{pct}%"

            if has_selection and field == sel_field and source == sel_source:
                seg_style["boxShadow"] = "inset 0 0 0 2px #fff"

            segments.append(html.Div(className="bar-segment", style=seg_style))
            segment_data.append(
                {"field": field, "source": source, "count": count, "pct": pct}
            )

        bar_rows.append(
            html.Div(
                [
                    checkbox,
                    html.Div(
                        segments,
                        className="bar-track",
                        style={
                            "display": "flex",
                            "flex": "1",
                            "minWidth": "0",
                            "height": f"{_BAR_HEIGHT}px",
                            "borderRadius": "2px",
                            "overflow": "hidden",
                        },
                    ),
                    html.Span(
                        field,
                        className="field-label",
                        title=field,
                        style={
                            "fontSize": "9px",
                            "width": f"{_LABEL_WIDTH}px",
                            "flexShrink": "0",
                            "paddingLeft": "4px",
                            "whiteSpace": "nowrap",
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "color": "#555",
                            "userSelect": "none",
                            "textAlign": "left",
                        },
                    ),
                ],
                className="field-bar-row",
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "height": f"{_ROW_HEIGHT}px",
                },
            )
        )

    return bar_rows, json.dumps(segment_data)


field_bars_panel = html.Div(
    [
        html.Div(
            id="field-bars-container",
            style={
                "overflowY": "auto",
                "overflowX": "hidden",
                "height": f"{PANEL_HEIGHT}px",
            },
        ),
        html.Div(id="field-bars-data", style={"display": "none"}),
        dcc.Store(id="field-bars-click", data=None),
        html.Div(
            id="field-bars-hover",
            style={
                "position": "fixed",
                "display": "none",
                "pointerEvents": "none",
                "backgroundColor": "rgba(255,255,255,0.95)",
                "border": "1px solid #ccc",
                "borderRadius": "4px",
                "padding": "4px 8px",
                "fontSize": "12px",
                "color": "#333",
                "zIndex": "2000",
                "whiteSpace": "nowrap",
                "boxShadow": "0 1px 4px rgba(0,0,0,0.15)",
            },
        ),
    ],
    style={"position": "relative"},
)
