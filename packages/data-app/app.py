import os

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html

from layouts.map_panel import map_panel
from layouts.treemap_panel import treemap_panel
from layouts.field_bars_panel import field_bars_panel
from layouts.detail_table import bottom_bar, detail_table, provider_modal
from callbacks.filters import register_callbacks

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    requests_pathname_prefix=os.environ.get(
        "DASH_PATHNAME_PREFIX", "/dash/beststartinlife/dashboard/"
    ),
    title="BSIL Data Explorer",
    suppress_callback_exceptions=True,
)

server = app.server

app.layout = dbc.Container(
    [
        # Filter state stores
        dcc.Store(id="map-selection", data=None),
        dcc.Store(id="treemap-selection", data=None),
        dcc.Store(id="field-selection", data=None),
        # Server-side pagination state
        dcc.Store(id="table-page", data=0),
        dcc.Store(id="filtered-count", data=0),
        dcc.Store(id="treemap-level", data={"level": "England", "_ts": 0}),
        dcc.Store(id="field-columns", data=None),
        dcc.Store(id="header-filters", data={"filters": [], "_ts": 0}),
        # Top row: three panels
        dbc.Row(
            [
                dbc.Col(map_panel, width=4),
                dbc.Col(treemap_panel, width=4),
                dbc.Col(field_bars_panel, width=4),
            ],
            className="mb-2",
        ),
        # Table — scrolls naturally; bottom bar is fixed-position
        html.Div(detail_table, style={"paddingBottom": "48px"}),
        provider_modal,
        bottom_bar,
    ],
    fluid=True,
)

register_callbacks(app)


@app.callback(
    dash.Output("map-selection", "data", allow_duplicate=True),
    dash.Output("treemap-selection", "data", allow_duplicate=True),
    dash.Output("field-selection", "data", allow_duplicate=True),
    dash.Output("table-page", "data", allow_duplicate=True),
    dash.Output("header-filters", "data", allow_duplicate=True),
    dash.Input("reset-filters", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_):
    return None, None, None, 0, {"filters": [], "_ts": 0}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)  # nosec B104
