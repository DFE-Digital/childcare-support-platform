import dash_bootstrap_components as dbc
import dash_tabulator
from dash import dcc, html

from data.loader import PRESENCE_FIELDS

# Human-readable column titles keyed by qualified field name.
COLUMN_TITLES: dict[str, str] = {
    # provider
    "provider.name": "Provider",
    "provider.address_line1": "Address",
    "provider.address_line2": "Address 2",
    "provider.city": "City",
    "provider.postcode": "Postcode",
    "provider.latitude": "Latitude",
    "provider.longitude": "Longitude",
    "provider.bbox_geo_code": "Geo Code",
    "provider.bbox_geo_type": "Geo Type",
    "provider.phone": "Phone",
    "provider.email": "Email",
    "provider.website": "Website",
    "provider.has_garden": "Has Garden",
    "provider.has_kitchen": "Has Kitchen",
    "provider.ofsted_legacy_rating": "Ofsted Rating",
    "provider.ofsted_legacy_behaviour_and_attitudes": "Ofsted Behaviour & Attitudes",
    "provider.ofsted_legacy_early_years": "Ofsted Early Years",
    "provider.ofsted_legacy_leadership_and_management": "Ofsted Leadership & Mgmt",
    "provider.ofsted_legacy_personal_development": "Ofsted Personal Dev",
    "provider.ofsted_legacy_quality_of_education": "Ofsted Quality of Ed",
    "provider.ofsted_legacy_sixth_form": "Ofsted Sixth Form",
    "provider.ofsted_inspection_date": "Inspection Date",
    "provider.ofsted_framework": "Framework",
    "provider.ofsted_safeguarding_met": "Safeguarding",
    "provider.ofsted_ccr_met": "CCR Met",
    "provider.ofsted_vcr_met": "VCR Met",
    "provider.ofsted_oosc_met": "OOSC Met",
    "provider.ofsted_achievement": "Ofsted Achievement",
    "provider.ofsted_attendance_and_behaviour": "Ofsted Attendance & Behaviour",
    "provider.ofsted_behaviour_attitudes_routines": "Ofsted Behaviour Routines",
    "provider.ofsted_childrens_welfare_wellbeing": "Ofsted Welfare & Wellbeing",
    "provider.ofsted_curriculum_and_teaching": "Ofsted Curriculum & Teaching",
    "provider.ofsted_early_years": "Ofsted Early Years (New)",
    "provider.ofsted_inclusion": "Ofsted Inclusion",
    "provider.ofsted_leadership_and_governance": "Ofsted Leadership & Gov",
    "provider.ofsted_personal_development_wellbeing": "Ofsted Personal Dev & Wellbeing",
    "provider.ofsted_sixth_form": "Ofsted Sixth Form (New)",
    "provider.registered_places": "Reg. Places",
    "provider.staff_graduate_percentage": "Staff Graduate %",
    "provider.staff_turnover_percentage": "Staff Turnover %",
    "provider.institution_type": "Institution Type",
    "provider.lad25cd": "LA Name",
    "provider.is_insufficient": "Insufficient",
    # care_type
    "care_type.care_type": "Care Type",
    "care_type.opening_hour_open": "Opens",
    "care_type.opening_hour_close": "Closes",
    "care_type.operating_weeks_per_year": "Weeks/Year",
    "care_type.session_hours_morning": "AM Hours",
    "care_type.session_hours_afternoon": "PM Hours",
    "care_type.session_hours_full_day": "Full Day Hrs",
    "care_type.eligible_min_months": "Min Months",
    "care_type.eligible_min_years": "Min Years",
    "care_type.eligible_max_years": "Max Years",
    "care_type.eligible_attendees_only": "Attendees Only",
    "care_type.eligible_institutions": "Eligible Institutions",
    "care_type.eligible_other": "Eligible Other",
    "care_type.funded_hours_accepted": "Funded",
    "care_type.min_commitment_amount": "Min Commit Amount",
    "care_type.min_commitment_duration": "Min Commit Duration",
    "care_type.min_commitment_unit": "Min Commit Unit",
    "care_type.no_minimum_commitment": "No Min Commit",
    # fee_rate
    "fee_rate.morning_session": "Fee: AM",
    "fee_rate.afternoon_session": "Fee: PM",
    "fee_rate.full_day": "Fee: Full Day",
    "fee_rate.per_session": "Fee: Session",
    "fee_rate.per_hour": "Fee: Hour",
    "fee_rate.per_day": "Fee: Day",
    "fee_rate.age_band": "Fee: Age Band",
}

# Fields with wider columns.
_WIDE_FIELDS = {
    "provider.name",
    "provider.address_line1",
    "provider.email",
    "provider.website",
}


# Always-on columns — checkboxes are checked and disabled.
ALWAYS_ON_FIELDS: set[str] = {
    "provider.name",
    "provider.lad25cd",
    "care_type.care_type",
}

# Default visible columns on first load.
DEFAULT_VISIBLE_FIELDS: set[str] = ALWAYS_ON_FIELDS | {
    "provider.institution_type",
    "provider.postcode",
    "provider.phone",
    "provider.email",
    "provider.ofsted_legacy_rating",
    "provider.is_insufficient",
}


def _build_columns() -> list[dict]:
    """Generate Tabulator column definitions from PRESENCE_FIELDS, in order."""
    cols = []
    for table, fields in PRESENCE_FIELDS.items():
        for field in fields:
            qf = f"{table}.{field}"
            title = COLUMN_TITLES.get(qf, field.replace("_", " ").title())
            col: dict = {"title": title, "field": qf, "headerFilter": "input"}
            if qf in _WIDE_FIELDS:
                col["widthGrow"] = 2
            cols.append(col)
    return cols


COLUMNS = _build_columns()

# Initial visible subset.
DEFAULT_COLUMNS = [c for c in COLUMNS if c["field"] in DEFAULT_VISIBLE_FIELDS]

detail_table = dash_tabulator.DashTabulator(
    id="detail-grid",
    columns=DEFAULT_COLUMNS,
    data=[],
    options={
        "dataTree": True,
        "dataTreeStartExpanded": False,
        "dataTreeChildField": "_children",
        "dataTreeFilter": True,
        "headerFilterLiveFilterDelay": 300,
        "layout": "fitColumns",
        "selectable": False,
        "nestedFieldSeparator": False,
    },
    theme="tabulator_simple",
)

provider_modal = html.Div(
    [
        # Backdrop
        html.Div(
            id="provider-panel-backdrop",
            style={
                "position": "fixed",
                "inset": "0",
                "backgroundColor": "rgba(0,0,0,0.3)",
                "zIndex": "1049",
            },
        ),
        # Panel
        html.Div(
            [
                html.Div(
                    [
                        html.Strong(
                            id="provider-modal-title", style={"fontSize": "16px"}
                        ),
                        html.Button(
                            "✕",
                            id="provider-panel-close",
                            style={
                                "border": "none",
                                "background": "none",
                                "fontSize": "20px",
                                "cursor": "pointer",
                                "padding": "0 4px",
                                "lineHeight": "1",
                            },
                        ),
                    ],
                    style={
                        "display": "flex",
                        "justifyContent": "space-between",
                        "alignItems": "center",
                        "padding": "12px 16px",
                        "borderBottom": "1px solid #dee2e6",
                    },
                ),
                html.Div(
                    id="provider-modal-body",
                    style={
                        "padding": "16px",
                        "overflowY": "auto",
                        "flex": "1",
                    },
                ),
            ],
            style={
                "position": "fixed",
                "top": "0",
                "right": "0",
                "bottom": "0",
                "width": "50vw",
                "backgroundColor": "#fff",
                "zIndex": "1050",
                "display": "flex",
                "flexDirection": "column",
                "boxShadow": "-2px 0 8px rgba(0,0,0,0.15)",
            },
        ),
    ],
    id="provider-modal",
    className="provider-panel-closed",
)

bottom_bar = html.Div(
    [
        html.Div(
            [
                dbc.Button(
                    "Reset all filters",
                    id="reset-filters",
                    color="secondary",
                    size="sm",
                    className="me-2",
                ),
                dbc.Button(
                    "Expand rows",
                    id="expand-rows",
                    color="secondary",
                    size="sm",
                    className="me-2",
                ),
            ],
            style={"position": "absolute", "left": "12px"},
            className="d-flex align-items-center",
        ),
        html.Div(
            [
                dbc.Button(
                    "← Prev",
                    id="page-prev",
                    size="sm",
                    color="secondary",
                    className="me-2",
                ),
                html.Span(id="page-info"),
                dbc.Button(
                    "Next →",
                    id="page-next",
                    size="sm",
                    color="secondary",
                    className="ms-2",
                ),
            ],
            className="d-flex align-items-center",
        ),
        html.Div(
            [dbc.Label("Click provider row for JSON")],
            style={"position": "absolute", "right": "12px"},
            className="d-flex align-items-right",
        ),
    ],
    className="d-flex align-items-center justify-content-center px-3 py-2",
    style={
        "position": "fixed",
        "bottom": "0",
        "left": "0",
        "right": "0",
        "backgroundColor": "#fff",
        "borderTop": "1px solid #dee2e6",
        "zIndex": "1000",
    },
)
