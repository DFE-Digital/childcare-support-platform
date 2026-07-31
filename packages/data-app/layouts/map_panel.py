import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dcc

from data.loader import SOURCE_TIER_COLORS
from layouts.field_bars_panel import PANEL_HEIGHT

# Ordered for consistent legend
SOURCE_TIER_ORDER = [
    "LA + Ofsted + School",
    "LA + Ofsted",
    "LA only",
    "Ofsted + School",
    "Ofsted only",
    "Other",
    "No data",
]


def make_empty_map() -> go.Figure:
    fig = go.Figure(go.Scattermap(lat=[], lon=[], mode="markers"))
    fig.update_layout(
        map_style="white-bg",
        map_center={"lat": 54.5, "lon": -2.5},
        map_zoom=4.8,
        height=PANEL_HEIGHT,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
    )
    return fig


def build_choropleth(la_tiers: pd.DataFrame, boundaries: dict | None) -> go.Figure:
    """Build a choropleth map coloured by source tier per LA.

    la_tiers has columns: lad25cd, source_tier, providers, la_name.
    All boundary features are shown; LAs without data get "No data".
    """
    if boundaries is None:
        return make_empty_map()

    # Build a row for every feature in the GeoJSON
    all_lads = []
    for feature in boundaries["features"]:
        props = feature["properties"]
        all_lads.append(
            {
                "lad25cd": props["LAD25CD"],
                "la_name": props.get("LAD25NM", props["LAD25CD"]),
            }
        )
    all_df = pd.DataFrame(all_lads)

    # Filter to English LAs only
    all_df = all_df[all_df["lad25cd"].str.startswith("E")].copy()

    # Left join source tiers onto all English LAs
    if la_tiers is not None and not la_tiers.empty:
        merged = all_df.merge(
            la_tiers[["lad25cd", "source_tier", "providers"]],
            on="lad25cd",
            how="left",
        )
    else:
        merged = all_df.copy()
        merged["source_tier"] = None
        merged["providers"] = None

    merged["source_tier"] = merged["source_tier"].fillna("No data")
    merged["providers"] = merged["providers"].fillna(0).astype(int)

    # Categorical ordering for consistent legend
    merged["source_tier"] = pd.Categorical(
        merged["source_tier"], categories=SOURCE_TIER_ORDER, ordered=True
    )
    merged = merged.sort_values("source_tier")

    fig = px.choropleth_map(
        merged,
        geojson=boundaries,
        locations="lad25cd",
        featureidkey="properties.LAD25CD",
        color="source_tier",
        hover_name="la_name",
        hover_data={"lad25cd": False, "providers": False, "source_tier": False},
        color_discrete_map=SOURCE_TIER_COLORS,
        category_orders={"source_tier": SOURCE_TIER_ORDER},
        center={"lat": 53.0, "lon": -1.5},
        zoom=5.2,
        map_style="white-bg",
    )
    fig.update_layout(
        height=PANEL_HEIGHT,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        legend={
            "title_text": "",
            "orientation": "h",
            "yanchor": "top",
            "y": -0.02,
            "xanchor": "center",
            "x": 0.5,
        },
    )
    return fig


def highlight_selection(
    base_fig: go.Figure, boundaries: dict | None, selected: list[str]
) -> go.Figure:
    """Return a copy of base_fig with selected LAs outlined."""
    import copy

    fig = copy.deepcopy(base_fig)
    if not boundaries or not selected:
        return fig

    sel_set = set(selected)
    sel_geojson = {
        "type": "FeatureCollection",
        "features": [
            f
            for f in boundaries["features"]
            if f["properties"].get("LAD25CD") in sel_set
        ],
    }
    if not sel_geojson["features"]:
        return fig

    sel_df = pd.DataFrame({"lad25cd": list(sel_set), "val": [1] * len(sel_set)})
    fig.add_trace(
        go.Choroplethmap(
            geojson=sel_geojson,
            locations=sel_df["lad25cd"],
            z=sel_df["val"],
            featureidkey="properties.LAD25CD",
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            marker=dict(
                opacity=1,
                line=dict(width=3, color="#d62728"),
            ),
            showscale=False,
            showlegend=False,
            hoverinfo="skip",
        )
    )
    return fig


map_panel = dcc.Graph(
    id="map-graph",
    figure=make_empty_map(),
    config={"scrollZoom": True, "displayModeBar": False},
)
