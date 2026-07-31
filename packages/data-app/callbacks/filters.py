import json
import re
from pathlib import Path

import pandas as pd
from dash import Input, Output, State, ctx, html, no_update

from data.loader import (
    DEFAULT_FIELD_SOURCE,
    FIELD_SOURCE_KEY_MAP,
    LA_NAME_LOOKUP,
    PRESENCE_FIELDS,
    PROVIDER_JSON_DIR,
    build_provider_summary,
    compute_field_sources,
    compute_la_source_tiers,
    load_boundaries,
    load_care_types,
    load_fee_rates,
    load_providers,
    normalise_field_source,
    parse_field_sources,
)
from layouts.detail_table import (
    ALWAYS_ON_FIELDS,
    COLUMNS,
    DEFAULT_VISIBLE_FIELDS,
)
from layouts.field_bars_panel import build_field_bars
from layouts.map_panel import build_choropleth, highlight_selection
from layouts.treemap_panel import build_treemap

PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Load data once at import time
# ---------------------------------------------------------------------------
_providers = load_providers()
_care_types = load_care_types()
_fee_rates = load_fee_rates()
_boundaries = load_boundaries()
_summary = build_provider_summary(_providers, _care_types)
_la_source_tiers = compute_la_source_tiers(_providers)
_total_providers = len(_summary)


# ---------------------------------------------------------------------------
# Pre-compute field source lookup: {qualified_field: {provider_id: source}}
# Used by _filter_providers to filter by specific source on bar click.
# ---------------------------------------------------------------------------
def _build_field_source_lookup():
    lookup: dict[str, dict[str, str]] = {}

    # Provider-level fields
    prov_fs = _providers["metadata"].apply(parse_field_sources)
    for field in PRESENCE_FIELDS["provider"]:
        if field not in _providers.columns:
            continue
        mask = _providers[field].notna()
        if field == "latitude":
            mask = mask & (_providers[field] != 0)
        fs_key = FIELD_SOURCE_KEY_MAP.get(field, field)
        default_src = DEFAULT_FIELD_SOURCE.get(field, "unknown")
        sources = prov_fs[mask].apply(
            lambda fs, k=fs_key, d=default_src: normalise_field_source(fs.get(k, d))
        )
        provider_ids = _providers.loc[mask, "id"]
        lookup[f"provider.{field}"] = dict(zip(provider_ids, sources))

    # Care-type fields (first source per provider wins)
    ct_has_meta = "metadata" in _care_types.columns
    ct_fs = (
        _care_types["metadata"].apply(parse_field_sources)
        if ct_has_meta
        else pd.Series([{}] * len(_care_types), index=_care_types.index)
    )
    for field in PRESENCE_FIELDS["care_type"]:
        if field not in _care_types.columns:
            continue
        mask = _care_types[field].notna()
        ct_present = _care_types.loc[mask, ["provider_id"]].copy()
        ct_present["_source"] = ct_fs[mask].apply(
            lambda fs, k=field: normalise_field_source(fs.get(k, "unknown"))
        )
        per_provider = ct_present.drop_duplicates(subset="provider_id", keep="first")
        lookup[f"care_type.{field}"] = dict(
            zip(per_provider["provider_id"], per_provider["_source"])
        )

    # Fee-rate fields (linked via care_types; source key is "fee_data")
    if not _fee_rates.empty:
        fr_with_prov = _fee_rates.merge(
            _care_types[["id", "provider_id"]].rename(columns={"id": "care_type_id"}),
            on="care_type_id",
            how="left",
        )
        fr_has_meta = "metadata" in fr_with_prov.columns
        fr_fs = (
            fr_with_prov["metadata"].apply(parse_field_sources)
            if fr_has_meta
            else pd.Series([{}] * len(fr_with_prov), index=fr_with_prov.index)
        )
        for field in PRESENCE_FIELDS["fee_rate"]:
            if field not in fr_with_prov.columns:
                continue
            mask = fr_with_prov[field].notna()
            fr_present = fr_with_prov.loc[mask, ["provider_id"]].copy()
            fr_present["_source"] = fr_fs[mask].apply(
                lambda fs, k=field: normalise_field_source(
                    fs.get("fee_data", fs.get(k, "unknown"))
                )
            )
            per_provider = fr_present.drop_duplicates(
                subset="provider_id", keep="first"
            )
            lookup[f"fee_rate.{field}"] = dict(
                zip(per_provider["provider_id"], per_provider["_source"])
            )

    return lookup


_field_source_lookup = _build_field_source_lookup()

# Pre-compute figures for the unfiltered (initial) state
_cached_choropleth = build_choropleth(_la_source_tiers, _boundaries)
_cached_treemap = build_treemap(_summary, _care_types)
_cached_bars_children, _cached_bars_data = build_field_bars(
    compute_field_sources(_summary, _care_types, _fee_rates)
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _filter_providers(
    map_selection: list[str] | None,
    treemap_selection: dict | None,
    field_selection: dict | None,
) -> pd.DataFrame:
    """Apply all cross-panel filters to the provider summary dataframe."""
    df = _summary

    if map_selection:
        df = df[df["lad25cd"].isin(map_selection)]

    if treemap_selection:
        if "la_name" in treemap_selection and treemap_selection["la_name"]:
            la = treemap_selection["la_name"]
            if la != "(no LA)":
                df = df[df["la_name"] == la]
            else:
                df = df[df["lad25cd"].isna()]
        if (
            "institution_type" in treemap_selection
            and treemap_selection["institution_type"]
        ):
            inst = treemap_selection["institution_type"]
            if inst != "(no institution type)":
                df = df[df["institution_type"] == inst]
            else:
                df = df[df["institution_type"].isna()]

    if field_selection:
        raw_field = field_selection.get("field", "")
        source = field_selection.get("source")
        if source == "absent":
            # Filter to providers where this field is null / not populated
            if raw_field.startswith("provider."):
                col = raw_field.split(".", 1)[1]
                if col in df.columns:
                    df = df[df[col].isna()]
            else:
                # Sub-table: providers with no row populating this field
                present_ids = _field_source_lookup.get(raw_field, {})
                df = df[~df["id"].isin(present_ids)]
        elif source:
            # Filter to providers where this field came from this source
            lookup = _field_source_lookup.get(raw_field, {})
            matching_ids = {pid for pid, src in lookup.items() if src == source}
            df = df[df["id"].isin(matching_ids)]

    return df


def _apply_header_filters(
    filtered: pd.DataFrame, header_filters: list[dict]
) -> pd.DataFrame:
    """Apply header text filters (from Tabulator headerFilter) server-side."""
    if not header_filters:
        return filtered

    for hf in header_filters:
        field = hf.get("field", "")
        value = str(hf.get("value", ""))
        if not value.strip():
            continue

        needle = value.lower()

        if field.startswith("provider."):
            col = field.split(".", 1)[1]
            if col == "lad25cd":
                col = "la_name"
            if col in filtered.columns:
                filtered = filtered[
                    filtered[col]
                    .astype(str)
                    .str.lower()
                    .str.contains(needle, na=False, regex=False)
                ]

        elif field.startswith("care_type."):
            ct_col = field.split(".", 1)[1]
            if ct_col in _care_types.columns:
                matching_ct = _care_types[
                    _care_types[ct_col]
                    .astype(str)
                    .str.lower()
                    .str.contains(needle, na=False, regex=False)
                ]
                matching_pids = set(matching_ct["provider_id"])
                filtered = filtered[filtered["id"].isin(matching_pids)]

        elif field.startswith("fee_rate."):
            fr_col = field.split(".", 1)[1]
            if not _fee_rates.empty and fr_col in _fee_rates.columns:
                matching_fr = _fee_rates[
                    _fee_rates[fr_col]
                    .astype(str)
                    .str.lower()
                    .str.contains(needle, na=False, regex=False)
                ]
                matching_ct_ids = set(matching_fr["care_type_id"])
                matching_ct = _care_types[_care_types["id"].isin(matching_ct_ids)]
                matching_pids = set(matching_ct["provider_id"])
                filtered = filtered[filtered["id"].isin(matching_pids)]

    return filtered


def _has_active_filters(map_sel, treemap_sel, field_sel) -> bool:
    return bool(map_sel) or bool(treemap_sel) or bool(field_sel)


def _build_table_page(filtered: pd.DataFrame, page: int) -> tuple[list[dict], str]:
    """Build table rows with care-type children for a single page."""
    total = len(filtered)
    total_pages = max(1, -(-total // PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))

    start = page * PAGE_SIZE
    page_slice = filtered.iloc[start : start + PAGE_SIZE]

    # Only fetch care types / fee rates for the providers on this page.
    page_ids = set(page_slice["id"])
    page_ct = _care_types[_care_types["provider_id"].isin(page_ids)]
    ct_by_provider = page_ct.groupby("provider_id")

    page_ct_ids = set(page_ct["id"])
    page_fr = _fee_rates[_fee_rates["care_type_id"].isin(page_ct_ids)]
    fr_by_ct = page_fr.groupby("care_type_id") if not page_fr.empty else {}

    row_data = []
    for _, prow in page_slice.iterrows():
        pid = prow.get("id", "")
        provider_dict: dict = {"_provider_id": str(pid)}

        # Provider-level fields under qualified keys.
        for field in PRESENCE_FIELDS["provider"]:
            qf = f"provider.{field}"
            if field == "lad25cd":
                val = prow.get("la_name", prow.get("lad25cd", ""))
            else:
                val = prow.get(field, "")
            if pd.isna(val):
                val = ""
            provider_dict[qf] = val

        # Children: one per care_type row, with fee rates merged in.
        if pid and pid in ct_by_provider.groups:
            children = []
            for _, ct_row in ct_by_provider.get_group(pid).iterrows():
                child: dict = {}
                for field in PRESENCE_FIELDS["care_type"]:
                    val = ct_row.get(field, "")
                    if pd.isna(val):
                        val = ""
                    child[f"care_type.{field}"] = val

                # Fee rates as nested children of care type.
                ct_id = ct_row.get("id", "")
                if (
                    ct_id
                    and isinstance(fr_by_ct, pd.core.groupby.DataFrameGroupBy)
                    and ct_id in fr_by_ct.groups
                ):
                    fr_children = []
                    for _, fr_row in fr_by_ct.get_group(ct_id).iterrows():
                        fr_child: dict = {}
                        for field in PRESENCE_FIELDS["fee_rate"]:
                            v = fr_row.get(field)
                            fr_child[f"fee_rate.{field}"] = "" if pd.isna(v) else v
                        fr_children.append(fr_child)
                    if fr_children:
                        child["_children"] = fr_children

                children.append(child)
            provider_dict["_children"] = children

        row_data.append(provider_dict)

    page_info = f"Page {page + 1} of {total_pages:,} ({total:,} providers)"
    return row_data, page_info


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
def register_callbacks(app):
    # 1) Charts + reset page on filter change
    @app.callback(
        Output("map-graph", "figure"),
        Output("treemap-graph", "figure"),
        Output("field-bars-container", "children"),
        Output("field-bars-data", "children"),
        Output("filtered-count", "data"),
        Output("table-page", "data", allow_duplicate=True),
        Input("map-selection", "data"),
        Input("treemap-selection", "data"),
        Input("field-selection", "data"),
        State("field-columns", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def update_charts(map_sel, treemap_sel, field_sel, col_store):
        checked_fields = _extract_checked(col_store)

        # Derive map highlight from both map clicks and treemap LA selection
        highlight_lads = list(map_sel) if map_sel else []
        if treemap_sel and treemap_sel.get("la_name"):
            la_name = treemap_sel["la_name"]
            lad = next(
                (k for k, v in LA_NAME_LOOKUP.items() if v == la_name),
                None,
            )
            if lad and lad not in highlight_lads:
                highlight_lads.append(lad)
        map_fig = highlight_selection(_cached_choropleth, _boundaries, highlight_lads)

        # Navigate treemap to the selected LA without rebuilding its data
        if ctx.triggered_id == "map-selection":
            import copy

            treemap_fig = copy.deepcopy(_cached_treemap)
            if map_sel:
                la_name = LA_NAME_LOOKUP.get(map_sel[0], map_sel[0])
                treemap_fig.data[0].level = la_name
            else:
                treemap_fig.data[0].level = "England"
        else:
            treemap_fig = no_update

        if not _has_active_filters(map_sel, treemap_sel, field_sel):
            return (
                map_fig,
                _cached_treemap if treemap_fig is no_update else treemap_fig,
                _cached_bars_children,
                _cached_bars_data,
                _total_providers,
                0,
            )

        filtered = _filter_providers(map_sel, treemap_sel, field_sel)
        filtered_ids = set(filtered["id"])
        filtered_ct = _care_types[_care_types["provider_id"].isin(filtered_ids)]

        filtered_ct_ids = set(filtered_ct["id"])
        filtered_fr = _fee_rates[_fee_rates["care_type_id"].isin(filtered_ct_ids)]
        bars_children, bars_data = build_field_bars(
            compute_field_sources(filtered, filtered_ct, filtered_fr),
            selection=field_sel,
            checked_fields=checked_fields,
        )

        return map_fig, treemap_fig, bars_children, bars_data, len(filtered), 0

    # 2) Pagination buttons
    @app.callback(
        Output("table-page", "data"),
        Input("page-prev", "n_clicks"),
        Input("page-next", "n_clicks"),
        State("table-page", "data"),
        State("filtered-count", "data"),
        prevent_initial_call=True,
    )
    def change_page(prev_clicks, next_clicks, current_page, total):
        page = current_page or 0
        total_pages = max(1, -(-total // PAGE_SIZE))
        if ctx.triggered_id == "page-next":
            page = min(page + 1, total_pages - 1)
        elif ctx.triggered_id == "page-prev":
            page = max(page - 1, 0)
        return page

    # 3) Table data — server-side pagination (+ header filters)
    @app.callback(
        Output("detail-grid", "data"),
        Output("page-info", "children"),
        Output("filtered-count", "data", allow_duplicate=True),
        Input("table-page", "data"),
        Input("map-selection", "data"),
        Input("treemap-selection", "data"),
        Input("field-selection", "data"),
        Input("header-filters", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def update_table(page, map_sel, treemap_sel, field_sel, header_filter_data):
        filtered = _filter_providers(map_sel, treemap_sel, field_sel)
        header_filters = (header_filter_data or {}).get("filters", [])
        filtered = _apply_header_filters(filtered, header_filters)
        rows, page_info = _build_table_page(filtered, page or 0)
        return rows, page_info, len(filtered)

    # 4) Map click → toggle LA selection + clear treemap selection
    @app.callback(
        Output("map-selection", "data"),
        Output("treemap-selection", "data", allow_duplicate=True),
        Input("map-graph", "clickData"),
        State("map-selection", "data"),
        prevent_initial_call=True,
    )
    def on_map_click(click_data, current_selection):
        if not click_data or "points" not in click_data:
            return no_update, no_update
        point = click_data["points"][0]
        lad = point.get("location") or point.get("customdata", [None])[0]
        if not lad:
            return no_update, no_update

        current = current_selection or []
        if current == [lad]:
            return None, None  # clicking the same LA again clears both
        return [lad], None

    # 5) Column visibility — driven by checkbox JS → field-columns store
    @app.callback(
        Output("detail-grid", "columns"),
        Input("field-columns", "data"),
    )
    def update_columns(col_store):
        checked = _extract_checked(col_store)
        if checked is None:
            return [c for c in COLUMNS if c["field"] in DEFAULT_VISIBLE_FIELDS]
        visible = set(checked) | ALWAYS_ON_FIELDS
        return [c for c in COLUMNS if c["field"] in visible]

    # 6) Field bar click → source-level filter (toggle on repeat click)
    #    Driven by JS event delegation → field-bars-click dcc.Store.
    @app.callback(
        Output("field-selection", "data"),
        Input("field-bars-click", "data"),
        State("field-selection", "data"),
        prevent_initial_call=True,
    )
    def on_field_bar_click(click_data, current_sel):
        if not click_data:
            return no_update
        field = click_data.get("field")
        source = click_data.get("source")

        if not field or not source:
            return no_update

        new_sel = {"field": field, "source": source}
        # Toggle: clicking the same segment again clears the selection
        if current_sel and current_sel == new_sel:
            return None
        return new_sel

    # 7) Treemap navigation — sole handler for all treemap drill-down/up.
    #    Driven by the JS plotly_treemapclick event (assets/treemap_sync.js)
    #    which fires on every click including pathbar, unlike Dash's clickData
    #    which deduplicates identical values.
    @app.callback(
        Output("treemap-selection", "data"),
        Output("map-selection", "data", allow_duplicate=True),
        Input("treemap-level", "data"),
        State("treemap-selection", "data"),
        State("map-selection", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def on_treemap_level_change(level_data, current_sel, current_map_sel):
        level = level_data.get("level") if isinstance(level_data, dict) else level_data

        # Navigating to root — clear both selections.
        # Must check both stores: map-selection may be active even when
        # treemap-selection is already None (e.g. after a map click).
        if not level or level == "England":
            if not current_sel and not current_map_sel:
                return no_update, no_update
            return None, None

        # Parse the level path: "LA" or "LA/inst_type" or "LA/inst_type/care"
        parts = level.split("/") if level else []
        result = {}
        if len(parts) >= 1 and parts[0]:
            result["la_name"] = parts[0]
        if len(parts) >= 2 and parts[1]:
            result["institution_type"] = parts[1]

        if not result:
            return None, None

        # Derive map selection from LA name
        la_name = result.get("la_name")
        map_sel = no_update
        if la_name and la_name != "(no LA)":
            lad = next(
                (k for k, v in LA_NAME_LOOKUP.items() if v == la_name),
                None,
            )
            if lad:
                map_sel = [lad]

        return result, map_sel

    # 8) Provider JSON panel — triggered by table row click
    @app.callback(
        Output("provider-modal", "className"),
        Output("provider-modal-title", "children"),
        Output("provider-modal-body", "children"),
        Output("detail-grid", "rowClicked", allow_duplicate=True),
        Input("detail-grid", "rowClicked"),
        Input("provider-panel-close", "n_clicks"),
        Input("provider-panel-backdrop", "n_clicks"),
        prevent_initial_call=True,
    )
    def show_provider_json(row, _close, _backdrop):
        trigger = ctx.triggered_id
        if trigger in ("provider-panel-close", "provider-panel-backdrop"):
            return "provider-panel-closing", no_update, no_update, None
        if not row:
            return no_update, no_update, no_update, no_update
        pid = row.get("_provider_id")
        if not pid:
            return no_update, no_update, no_update, no_update
        # Validate provider ID: alphanumeric only.
        if not re.fullmatch(r"[A-Za-z0-9]+", str(pid)):
            return "provider-panel-ready", "Error", "Invalid provider ID.", None
        json_path = PROVIDER_JSON_DIR / f"p{pid}.json"
        if not json_path.exists():
            return (
                "provider-panel-ready",
                str(pid),
                html.Div(
                    [
                        html.P(f"File not found: p{pid}.json"),
                        html.P(
                            "Providers which don't meet the sufficiency criteria"
                            " won't have a JSON file created during export.",
                            style={"color": "#666", "fontSize": "13px"},
                        ),
                    ]
                ),
                None,
            )
        with open(json_path) as f:
            data = json.load(f)
        name = data.get("name", str(pid))
        formatted = json.dumps(data, indent=2, default=str)
        from dash import dcc

        return (
            "provider-panel-ready",
            name,
            dcc.Markdown(f"```json\n{formatted}\n```"),
            None,
        )

    # 9) Field bar hover is handled by assets/field_bars_hover.js


def _extract_checked(col_store) -> set[str] | None:
    """Extract the set of checked field names from the field-columns store."""
    if not col_store:
        return None
    if isinstance(col_store, dict):
        fields = col_store.get("fields")
        if fields:
            return set(fields)
        return None
    if isinstance(col_store, list):
        return set(col_store)
    return None
