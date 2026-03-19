import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from datetime import date, timedelta
from utils.bq_client import run_query, TABLES

st.set_page_config(page_title="Revel City Dashboard", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { background-color: #f8f9fb; font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 0; max-width: 100%; padding-left: 2rem; padding-right: 2rem; }
    .section-banner {
        background: #e8eaef; border-radius: 8px;
        padding: 10px 20px; text-align: center;
        margin-top: -16px;
    }
    .section-banner h2 { font-size: 1.2rem; font-weight: 700; color: #1a1a2e; margin: 0; }
    .chart-title {
        font-size: 0.92rem; font-weight: 700; color: #202124;
        text-align: center; margin-bottom: 0; padding: 0;
    }
    #MainMenu, footer, header { visibility: hidden; }
    .kpi-card { position: relative; cursor: default; }
    .kpi-card::after {
        content: attr(data-tooltip);
        position: absolute;
        bottom: calc(100% + 8px);
        left: 50%;
        transform: translateX(-50%);
        background: rgba(28,28,38,0.95);
        color: #f0f0f0;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 0.72rem;
        line-height: 1.5;
        white-space: normal;
        width: 240px;
        text-align: left;
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.15s ease;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .kpi-card:hover::after { opacity: 1; }
    /* Tighten spacing around charts */
    .stPlotlyChart { margin-top: -10px; }
    /* White background for columns */
    [data-testid="stColumn"] > div {
        background: #ffffff;
        border-radius: 8px;
        padding: 10px 10px 4px 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        height: 100%;
    }
    /* Make columns equal height and vertically center content */
    [data-testid="stHorizontalBlock"] {
        align-items: stretch;
    }
    [data-testid="stColumn"] > div {
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
    }
    /* Close expander on outside click - handled by JS below */
    /* Expander dropdown overlay */
    [data-testid="stExpander"] {
        position: relative;
        z-index: 100;
        height: 42px;
        overflow: visible;
    }
    [data-testid="stExpander"] details {
        position: absolute;
        width: 100%;
        background: white;
        border-radius: 8px;
    }
    [data-testid="stExpander"] details[open] {
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        border: 1px solid #ddd;
    }
    [data-testid="stExpander"] details > div[data-testid="stExpanderDetails"] {
        max-height: 250px;
        overflow-y: auto;
        padding: 4px 8px;
    }
    /* Slider track: grey base, colored active range */
    [data-testid="stSlider"] [data-testid="stSliderTrack"] > div:first-child {
        background-color: #ddd !important;
    }
    [data-testid="stSlider"] [data-testid="stSliderTrack"] > div:nth-child(2) {
        background-color: #a0926c !important;
    }
    [data-testid="stSlider"] [data-testid="stSliderTrack"] > div:nth-child(3) {
        background-color: #ddd !important;
    }
</style>
""", unsafe_allow_html=True)

# Auto-close expander on outside click
components.html("""
<script>
(function() {
    function init() {
        var doc = window.parent.document;
        doc.addEventListener('mousedown', function(e) {
            setTimeout(function() {
                doc.querySelectorAll('[data-testid="stExpander"] details[open]').forEach(function(det) {
                    if (!det.contains(e.target) && !e.target.closest('[data-testid="stExpander"]')) {
                        det.removeAttribute('open');
                    }
                });
            }, 50);
        });
    }
    init();
})();
</script>
""", height=0)

CHART_BG = dict(
    paper_bgcolor="white", plot_bgcolor="white",
    font=dict(color="#3c4043", size=12, family="Inter, Arial, sans-serif"),
    hoverlabel=dict(bgcolor="rgba(255,255,255,1)", font_size=13, font_family="Inter, Arial", font_color="#333", bordercolor="#ccc"),
    hovermode="closest",
)

def beveled_marker(color):
    """Marker with soft highlight border for beveled look."""
    return dict(
        color=color,
        line=dict(color="rgba(255,255,255,0.35)", width=2),
    )

def render_chart(fig, height=300, legend=None, legend_position="top"):
    """Render Plotly chart as HTML with hover highlight effects.

    legend: optional list of (label, color) tuples to render as an HTML legend
            that highlights on hover. Pass trace index mapping via trace names.
    legend_position: "top" (default) or "bottom"
    """
    hover_js = """
    <script>
    (function() {
        function initHover() {
        var plot = document.getElementById('{div_id}');
        if (!plot || !plot.data) { setTimeout(initHover, 100); return; }
        var origColors = {};
        var traceNames = {trace_names};

        function saveOrigColors() {
            if (Object.keys(origColors).length > 0) return;
            for (var i = 0; i < plot.data.length; i++) {
                var t = plot.data[i];
                if (t.marker && t.marker.color) {
                    origColors[i] = t.marker.color;
                }
            }
        }

        function hexToRgba(color, alpha) {
            if (!color) return 'rgba(153,153,153,' + alpha + ')';
            if (color.startsWith('rgba')) {
                return color.replace(/,[^,)]+\)$/, ',' + alpha + ')');
            }
            if (color.startsWith('rgb(')) {
                return color.replace('rgb(', 'rgba(').replace(')', ',' + alpha + ')');
            }
            var hex = color.replace('#', '');
            if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
            var r = parseInt(hex.substring(0,2), 16);
            var g = parseInt(hex.substring(2,4), 16);
            var b = parseInt(hex.substring(4,6), 16);
            if (isNaN(r) || isNaN(g) || isNaN(b)) return 'rgba(153,153,153,' + alpha + ')';
            return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
        }

        function fadeLegendItems(hoveredName) {
            var items = document.querySelectorAll('.custom-legend-item');
            items.forEach(function(el) {
                if (hoveredName === null) {
                    el.style.opacity = '1';
                } else {
                    el.style.opacity = el.getAttribute('data-name') === hoveredName ? '1' : '0.25';
                }
            });
        }

        function handleHover(data) {
            saveOrigColors();
            var pt = data.points[0];
            var n = plot.data.length;
            var hoveredName = traceNames[pt.curveNumber] || null;

            fadeLegendItems(hoveredName);

            for (var i = 0; i < n; i++) {
                var trace = plot.data[i];

                if (trace.type === 'bar' && trace.marker) {
                    var isHoveredTrace = (i === pt.curveNumber);
                    var baseColor = origColors[i] || trace.marker.color;
                    var isHorizontal = trace.orientation === 'h';
                    var cats = isHorizontal ? (trace.y || []) : (trace.x || []);
                    var hoveredCat = isHorizontal ? pt.y : pt.x;
                    var colors = [];
                    var hoveredIdx = pt.pointIndex !== undefined ? pt.pointIndex : pt.pointNumber;
                    for (var j = 0; j < cats.length; j++) {
                        var c = typeof baseColor === 'string' ? baseColor : (baseColor[j] || baseColor);
                        if (isHoveredTrace && j === hoveredIdx) {
                            colors.push(c);
                        } else {
                            colors.push(hexToRgba(c, 0.2));
                        }
                    }
                    Plotly.restyle(plot, {'marker.color': [colors]}, [i]);
                } else if (trace.type === 'scatter' || trace.type === 'scattergl') {
                    if (i === pt.curveNumber) {
                        var sizes = [];
                        var opacs = [];
                        var pts = trace.x ? trace.x.length : 0;
                        for (var j = 0; j < pts; j++) {
                            sizes.push(j === pt.pointIndex ? 12 : 6);
                            opacs.push(j === pt.pointIndex ? 1 : 0.3);
                        }
                        Plotly.restyle(plot, {'marker.size': [sizes], 'marker.opacity': [opacs], 'opacity': 1}, [i]);
                    } else {
                        Plotly.restyle(plot, {'opacity': 0.15}, [i]);
                    }
                } else if (trace.type === 'pie' || trace.type === 'domain') {
                    if (!origColors[i] && trace.marker && trace.marker.colors) {
                        origColors[i] = trace.marker.colors.slice();
                    }
                    var pieColors = origColors[i] || [];
                    var hoveredPt = pt.pointNumber !== undefined ? pt.pointNumber : pt.pointIndex;
                    var len = trace.labels ? trace.labels.length : 0;
                    var pulls = [];
                    var newColors = [];
                    for (var j = 0; j < len; j++) {
                        pulls.push(j === hoveredPt ? 0.06 : 0);
                        var c = pieColors[j] || '#999';
                        newColors.push(j === hoveredPt ? c : hexToRgba(c, 0.25));
                    }
                    Plotly.restyle(plot, {'pull': [pulls], 'marker.colors': [newColors]}, [i]);
                }
            }
        }
        plot.on('plotly_hover', handleHover);
        plot.on('plotly_click', function(data) {
            var pt = data.points[0];
            var trace = plot.data[pt.curveNumber];
            if (trace.type === 'pie' || trace.type === 'domain') {
                handleHover(data);
            }
        });

        plot.on('plotly_unhover', function() {
            fadeLegendItems(null);
            var n = plot.data.length;
            for (var i = 0; i < n; i++) {
                var trace = plot.data[i];
                if (trace.type === 'bar' && origColors[i] !== undefined) {
                    var baseColor = origColors[i];
                    Plotly.restyle(plot, {'marker.color': [baseColor]}, [i]);
                } else if (trace.type === 'pie' || trace.type === 'domain') {
                    var len2 = trace.labels ? trace.labels.length : 0;
                    var zeros = [];
                    for (var j = 0; j < len2; j++) { zeros.push(0); }
                    var restoreColors = origColors[i] || trace.marker.colors;
                    Plotly.restyle(plot, {'pull': [zeros], 'marker.colors': [restoreColors]}, [i]);
                } else if (trace.type === 'scatter' || trace.type === 'scattergl') {
                    var pts2 = trace.x ? trace.x.length : 0;
                    var resetSizes = []; var resetOpacs = [];
                    for (var j = 0; j < pts2; j++) { resetSizes.push(6); resetOpacs.push(1); }
                    Plotly.restyle(plot, {'marker.size': [resetSizes], 'marker.opacity': [resetOpacs], 'opacity': 1}, [i]);
                } else {
                    Plotly.restyle(plot, {'opacity': 1}, [i]);
                }
            }
        });
    }
    initHover();
    })();
    </script>
    """
    import json, re
    fig.update_layout(autosize=True, dragmode=False)

    # Build trace name list for JS
    trace_names = [t.name or "" for t in fig.data]

    html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False, config={"displayModeBar": False, "responsive": True, "scrollZoom": False, "doubleClick": False, "dragmode": False})
    match = re.search(r'id="([^"]+)"', html)
    div_id = match.group(1) if match else ""

    # Build HTML legend if provided
    legend_html = ""
    if legend:
        items = "".join(
            f'<span class="custom-legend-item" data-name="{label}" style="transition:opacity 0.15s;display:inline-flex;align-items:center;gap:4px;">'
            f'<span style="display:inline-block;width:12px;height:12px;background:{color};border-radius:2px;"></span>{label}</span>'
            for label, color in legend
        )
        legend_html = f'<div style="display:flex;flex-wrap:wrap;justify-content:center;gap:10px 18px;font-size:0.78rem;color:#555;margin-bottom:4px;">{items}</div>'

    js = hover_js.replace("{div_id}", div_id).replace("{trace_names}", json.dumps(trace_names))
    html += js
    top_legend = legend_html if legend_position == "top" else ""
    bottom_legend = legend_html if legend_position == "bottom" else ""
    wrapper = f'''<div style="background:white; width:100%; overflow:visible;">
        {top_legend}
        {html}
        {bottom_legend}
        <script>
        (function() {{
            var d = document.getElementById("{div_id}");
            if (d) Plotly.Plots.resize(d);
            window.addEventListener("resize", function() {{ if (d) Plotly.Plots.resize(d); }});
        }})();
        </script>
    </div>'''
    components.html(wrapper, height=height)

# Consistent person colors across all charts
NAME_NORMALIZE = {
    "wes werner": "Wesley Warner",
    "wesley werner": "Wesley Warner",
    "wes warner": "Wesley Warner",
    "cameron cathcart": "Camron Cathcart",
}

def normalize_name(name):
    if not name:
        return "Unknown"
    return NAME_NORMALIZE.get(name.strip().lower(), name.strip())

PERSON_COLORS = {
    "Scotty Patton": "#a0926c",   # tan
    "Wesley Warner": "#c2703e",   # burnt orange
    "Tony Franks": "#7a9a6d",     # sage green
    "Camron Cathcart": "#8b6f5e", # warm brown
    "Taylor Shelpuk": "#d4a857",  # gold
    "Unknown": "#6b8f9e",         # muted teal
}

@st.cache_data(ttl=300)
def load_tasks():
    return run_query(f"SELECT * FROM `{TABLES['tasks']}`")

@st.cache_data(ttl=300)
def load_contacts():
    return run_query(f"SELECT * FROM `{TABLES['connector_contacts']}`")

@st.cache_data(ttl=300)
def load_connector_leads():
    return run_query(f"SELECT * FROM `{TABLES['connector_leads']}`")

@st.cache_data(ttl=300)
def load_hot_sheet():
    return run_query(f"SELECT * FROM `{TABLES['hot_sheet']}`")

@st.cache_data(ttl=300)
def load_seller_leads():
    return run_query(f"SELECT * FROM `{TABLES['seller_leads']}`")

@st.cache_data(ttl=300)
def load_am_tasks():
    return run_query(f"SELECT * FROM `{TABLES['am_tasks']}`")

@st.cache_data(ttl=300)
def load_am_rehab():
    return run_query(f"""
        SELECT *, SAFE_CAST(amount AS FLOAT64) AS amount_num
        FROM `{TABLES['am_rehab_costs']}`
    """)

tasks_raw = load_tasks()
contacts_raw = load_contacts()
leads_raw = load_connector_leads()
hot_sheet_raw = load_hot_sheet()
seller_leads_raw = load_seller_leads()
am_tasks_raw = load_am_tasks()
rehab_raw = load_am_rehab()

import base64 as _b64
with open("assets/Revel City Homebuyers Logo_full color.png", "rb") as _f:
    _logo_b64 = _b64.b64encode(_f.read()).decode()
st.markdown(
    f'<div style="padding:8px 0 4px 0; text-align:right;">'
    f'<img src="data:image/png;base64,{_logo_b64}" style="height:80px;">'
    f'</div>',
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["Connector Contacts", "AM KPIs", "AM Rehab"])

with tab1:
    # ═══════════════════════════════════════════════════
    # HEADER + FILTERS
    # ═══════════════════════════════════════════════════
    all_people = sorted(set(
        tasks_raw["assigned_to"].dropna().unique().tolist() +
        contacts_raw["relationship_manager"].dropna().unique().tolist()
    ))

    ban1, fil1, fil2 = st.columns([3, 2, 2])
    ban1.markdown('''<div class="section-banner"><h2>Connector Tasks and Contacts</h2></div>
<style>
    div[data-testid="stColumn"]:has(.section-banner) > div {
        background: #e8eaef !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    div[data-testid="stColumn"]:has(.section-banner) .section-banner {
        background: transparent; padding: 0;
    }
</style>
''', unsafe_allow_html=True)
    with fil1:
        with st.expander("Acquisition Manager", expanded=False):
            # Track previous All state to detect toggle
            prev_all = st.session_state.get("am_all_prev", True)
            all_selected = st.checkbox("All", value=True, key="am_all")
            # If All was just unchecked, clear all individual checkboxes
            if prev_all and not all_selected:
                for person in all_people:
                    st.session_state[f"am_{person}"] = False
            # If All was just checked, set all individual checkboxes
            elif not prev_all and all_selected:
                for person in all_people:
                    st.session_state[f"am_{person}"] = True
            st.session_state["am_all_prev"] = all_selected
            selected_people = []
            for person in all_people:
                default = all_selected if f"am_{person}" not in st.session_state else st.session_state[f"am_{person}"]
                checked = st.checkbox(person, value=default, key=f"am_{person}", disabled=all_selected)
                if all_selected or checked:
                    selected_people.append(person)
    min_date, max_date = tasks_raw["due_date"].min(), tasks_raw["due_date"].max()
    date_range = None
    if pd.notna(min_date) and pd.notna(max_date):
        min_d = pd.Timestamp(min_date).date()
        max_d = pd.Timestamp(max_date).date()
        date_range = fil2.slider(
            "Date Range",
            min_value=min_d, max_value=max_d,
            value=(min_d, max_d),
            format="MM/DD/YYYY",
        )

    tasks = tasks_raw.copy()
    if selected_people:
        tasks = tasks[tasks["assigned_to"].isin(selected_people)]
    if date_range and len(date_range) == 2:
        tasks = tasks[(tasks["due_date"] >= pd.Timestamp(date_range[0])) & (tasks["due_date"] <= pd.Timestamp(date_range[1]))]

    contacts = contacts_raw.copy()
    if selected_people:
        contacts = contacts[contacts["relationship_manager"].isin(selected_people)]

    c1, c2, c3 = st.columns(3)

    # 1) Outstanding Follow-Ups
    with c1:
        st.markdown('<p class="chart-title">Outstanding Follow-Ups</p>', unsafe_allow_html=True)
        outstanding = tasks[tasks["follow_up_status"].isin(["Incomplete", "Late"])].copy()
        if not outstanding.empty:
            outstanding["display_status"] = outstanding.apply(
                lambda r: "Open to Steal" if r["follow_up_status"] == "Late" and r.get("check_in") == "Open to Steal Relationship" else r["follow_up_status"],
                axis=1,
            )
            ost = outstanding.groupby(["assigned_to", "display_status"]).size().reset_index(name="count")
            order = ost.groupby("assigned_to")["count"].sum().sort_values(ascending=True).index.tolist()
            fig = go.Figure()
            for status, color in [("Incomplete", "#d4a857"), ("Late", "#b54734"), ("Open to Steal", "#c2703e")]:
                s = ost[ost["display_status"] == status]
                fig.add_trace(go.Bar(
                    y=s["assigned_to"], x=s["count"], name=status, orientation="h",
                    marker=beveled_marker(color),
                    text=s["count"], textposition="inside",
                    textfont=dict(size=14, color="white"), insidetextanchor="middle", width=0.5,
                    hovertemplate="<b>%{y}</b><br>" + status + ": <b>%{x}</b><extra></extra>",
                ))
            fig.update_layout(**CHART_BG, barmode="stack", height=300,
                yaxis=dict(categoryorder="array", categoryarray=order, tickfont=dict(size=12), automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#e8e8e8", tickfont=dict(size=11, color="#999")),
                showlegend=False,
                margin=dict(l=120, r=15, t=5, b=30))
            render_chart(fig, height=320, legend=[
                ("Incomplete", "#d4a857"), ("Late", "#b54734"), ("Open to Steal", "#c2703e")
            ])

    # 2) Completed Follow-Ups
    with c2:
        st.markdown('<p class="chart-title">Completed Follow-Ups</p>', unsafe_allow_html=True)
        completed = tasks[tasks["follow_up_status"] == "Complete"]
        if not completed.empty:
            comp = completed.groupby("assigned_to").size().reset_index(name="count").sort_values("count", ascending=True)
            fig = go.Figure(go.Bar(
                y=comp["assigned_to"], x=comp["count"], orientation="h",
                marker=beveled_marker("#7a9a6d"),
                text=comp["count"], textposition="inside",
                textfont=dict(size=14, color="white"), insidetextanchor="middle", width=0.5,
                hovertemplate="<b>%{y}</b><br>Completed: <b>%{x}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=300, showlegend=False,
                yaxis=dict(tickfont=dict(size=12), automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#e8e8e8", tickfont=dict(size=11, color="#999"), automargin=True),
                margin=dict(l=5, r=15, t=10, b=30))
            render_chart(fig, height=320)

    # 3) Upcoming Follow-Ups
    with c3:
        st.markdown('<p class="chart-title">Upcoming Follow-Ups</p>', unsafe_allow_html=True)
        task_time = tasks[(tasks["due_date"] >= pd.Timestamp(date.today())) & (tasks["follow_up_status"].isin(["Incomplete", "Late"]))].copy()
        task_time["assigned_to"] = task_time["assigned_to"].fillna("Unassigned")
        if not task_time.empty:
            task_time["day"] = pd.to_datetime(task_time["due_date"]).dt.date
            upc = task_time.groupby(["day", "assigned_to"]).size().reset_index(name="count")
            fig = px.line(upc, x="day", y="count", color="assigned_to", markers=True,
                          color_discrete_map=PERSON_COLORS)
            fig.update_traces(
                line=dict(width=2),
                marker=dict(size=6, line=dict(color="rgba(0,0,0,0.2)", width=1.5)),
                hovertemplate="<b>%{fullData.name}</b><br>%{x|%b %d, %Y}<br>Tasks: <b>%{y}</b><extra></extra>",
            )
            fig.update_layout(**CHART_BG, height=300,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True, dtick=5),
                xaxis=dict(title="", tickformat="%b %Y", gridcolor="#f0f0f0", zeroline=False, dtick="M1"),
                legend=dict(orientation="h", y=-0.3, x=0, title="", font=dict(size=10)),
                margin=dict(l=10, r=15, t=10, b=5))
            render_chart(fig, height=350)

    # ═══════════════════════════════════════════════════
    # SECTION 2: Connector Contacts
    # ═══════════════════════════════════════════════════
    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    c4, c5, c6 = st.columns(3)

    # 4) Outstanding Tasks vs Connector Contacts
    with c4:
        st.markdown('<p class="chart-title">Outstanding Tasks vs Connector Contacts</p>', unsafe_allow_html=True)
        if not contacts.empty:
            by_mgr = contacts.groupby("relationship_manager").agg(
                total=("podio_item_id", "count"),
                level_assigned=("level", lambda x: x.notna().sum()),
            ).reset_index().sort_values("total", ascending=False)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=by_mgr["relationship_manager"], y=by_mgr["level_assigned"],
                name="Level Assigned",
                marker=beveled_marker("#a0926c"),
                text=by_mgr["level_assigned"], textposition="outside",
                textfont=dict(size=12), width=0.3,
                hovertemplate="<b>%{x}</b><br>Level Assigned: <b>%{y}</b><extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=by_mgr["relationship_manager"], y=by_mgr["total"],
                name="Total Connectors",
                marker=beveled_marker("#c2703e"),
                text=by_mgr["total"], textposition="outside",
                textfont=dict(size=12), width=0.3,
                hovertemplate="<b>%{x}</b><br>Total Connectors: <b>%{y}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, barmode="group", height=340, bargroupgap=0.08,
                yaxis=dict(gridcolor="#f0f0f0", title="", range=[0, by_mgr["total"].max() * 1.2], zeroline=False, automargin=True),
                xaxis=dict(title="", tickangle=-20, tickfont=dict(size=11), automargin=True),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=60))
            render_chart(fig, height=370, legend=[
                ("Level Assigned", "#a0926c"), ("Total Connectors", "#c2703e")
            ])

    # 5) Connector Type
    with c5:
        st.markdown('<p class="chart-title">Connector Type</p>', unsafe_allow_html=True)
        if not contacts.empty:
            tc = contacts["connector_type"].fillna("Unknown").value_counts().reset_index()
            tc.columns = ["connector_type", "count"]
            cmap = {"Wholesaler": "#a0926c", "Agent": "#c2703e", "Investor": "#7a9a6d",
                    "Other": "#d4a857", "Attorney": "#8b6f5e", "Unknown": "#6b8f9e"}
            pie_colors = [cmap.get(t, "#999") for t in tc["connector_type"]]
            fig = go.Figure(go.Pie(
                labels=tc["connector_type"], values=tc["count"], hole=0.5,
                marker=dict(
                    colors=pie_colors,
                    line=dict(color="rgba(255,255,255,0.4)", width=2.5),
                ),
                textinfo="value", textposition="inside",
                textfont=dict(size=16, color="white"),
                hovertemplate="<b>%{label}</b><br>Count: <b>%{value}</b><br>%{percent}<extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340,
                legend=dict(orientation="h", y=-0.08, xanchor="center", x=0.5, font=dict(size=11), title=""),
                margin=dict(l=10, r=10, t=10, b=10))

            import json as _json
            pie_html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False,
                                   config={"displayModeBar": False, "responsive": True})
            import re as _re
            _m = _re.search(r'id="([^"]+)"', pie_html)
            _div_id = _m.group(1) if _m else ""
            _colors_json = _json.dumps(pie_colors)
            pie_js = f'''<script>
        (function() {{
            function init() {{
                var plot = document.getElementById("{_div_id}");
                if (!plot || !plot.on) {{ setTimeout(init, 200); return; }}
                var origColors = {_colors_json};
                plot.on("plotly_hover", function(data) {{
                    var pt = data.points[0];
                    var idx = pt.pointNumber;
                    var len = origColors.length;
                    var newColors = [];
                    var pulls = [];
                    for (var j = 0; j < len; j++) {{
                        pulls.push(j === idx ? 0.06 : 0);
                        if (j === idx) {{
                            newColors.push(origColors[j]);
                        }} else {{
                            var hex = origColors[j].replace("#","");
                            var r = parseInt(hex.substring(0,2),16);
                            var g = parseInt(hex.substring(2,4),16);
                            var b = parseInt(hex.substring(4,6),16);
                            newColors.push("rgba("+r+","+g+","+b+",0.2)");
                        }}
                    }}
                    Plotly.restyle(plot, {{"pull": [pulls], "marker.colors": [newColors]}}, [0]);
                }});
                plot.on("plotly_unhover", function() {{
                    var len = origColors.length;
                    var zeros = [];
                    for (var j = 0; j < len; j++) zeros.push(0);
                    Plotly.restyle(plot, {{"pull": [zeros], "marker.colors": [origColors]}}, [0]);
                }});
            }}
            init();
        }})();
        </script>'''
            wrapper = f'<div style="background:white;width:100%;overflow:visible;">{pie_html}{pie_js}</div>'
            components.html(wrapper, height=370)

    # 6) New Connector Contacts
    with c6:
        st.markdown('<p class="chart-title">New Connector Contacts</p>', unsafe_allow_html=True)
        if not contacts.empty:
            ct = contacts.copy()
            ct["month"] = pd.to_datetime(ct["created_on"]).values.astype("datetime64[M]")
            ct["relationship_manager"] = ct["relationship_manager"].fillna("Unknown")
            six_months_ago = pd.Timestamp(date.today()) - pd.DateOffset(months=6)
            ct = ct[ct["month"] >= six_months_ago]
            new_c = ct.groupby(["month", "relationship_manager"]).size().reset_index(name="count")
            fig = go.Figure()
            legend_items = []
            for person in sorted(new_c["relationship_manager"].unique()):
                color = PERSON_COLORS.get(person, "#999")
                legend_items.append((person, color))
                pdf = new_c[new_c["relationship_manager"] == person]
                fig.add_trace(go.Bar(
                    x=pdf["month"], y=pdf["count"], name=person,
                    marker=beveled_marker(color),
                    hovertemplate="<b>" + person + "</b><br>%{x|%b %Y}<br>Count: <b>%{y}</b><extra></extra>",
                ))
            fig.update_layout(**CHART_BG, barmode="stack", height=300, bargap=0.3,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickformat="%b %Y", gridcolor="#f0f0f0", zeroline=False, dtick="M1",
                           tickangle=-30, tickfont=dict(size=10)),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=legend_items, legend_position="bottom")

# ═══════════════════════════════════════════════════
# TAB 2: AM KPIs
# ═══════════════════════════════════════════════════
with tab2:
    today = date.today()
    current_year = today.year
    # Quarter boundaries (current quarter for lead conversion)
    q_month = ((today.month - 1) // 3) * 3 + 1
    qtr_start = date(current_year, q_month, 1)
    qtr_end = today

    leads = leads_raw.copy()

    # ── Header row: banner + RM filter ──
    am_ban, am_fil = st.columns([4, 3])
    am_ban.markdown('''<div class="section-banner"><h2>AM KPIs</h2></div>
<style>
    div[data-testid="stColumn"]:has(.section-banner) > div {
        background: #e8eaef !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    div[data-testid="stColumn"]:has(.section-banner) .section-banner {
        background: transparent; padding: 0;
    }
</style>
''', unsafe_allow_html=True)

    all_ams = sorted(set(
        list(am_tasks_raw["assigned_to"].dropna().map(normalize_name)) +
        list(leads_raw["relationship_manager"].dropna().map(normalize_name)) +
        list(seller_leads_raw["created_by"].dropna().map(normalize_name)) +
        list(hot_sheet_raw["lead_manager"].dropna().map(normalize_name))
    ) - {"Unknown"})
    with am_fil:
        with st.expander("Acquisition Manager", expanded=False):
            prev_all_rm = st.session_state.get("rm_all_prev", True)
            all_rm_selected = st.checkbox("All", value=True, key="rm_all")
            if prev_all_rm and not all_rm_selected:
                for am in all_ams:
                    st.session_state[f"rm_{am}"] = False
            elif not prev_all_rm and all_rm_selected:
                for am in all_ams:
                    st.session_state[f"rm_{am}"] = True
            st.session_state["rm_all_prev"] = all_rm_selected
            selected_ams = []
            for am in all_ams:
                default_rm = all_rm_selected if f"rm_{am}" not in st.session_state else st.session_state[f"rm_{am}"]
                checked_rm = st.checkbox(am, value=default_rm, key=f"rm_{am}", disabled=all_rm_selected)
                if all_rm_selected or checked_rm:
                    selected_ams.append(am)

    if not all_rm_selected and selected_ams:
        leads = leads_raw[leads_raw["relationship_manager"].apply(normalize_name).isin(selected_ams)].copy()
        am_tasks = am_tasks_raw[am_tasks_raw["assigned_to"].apply(normalize_name).isin(selected_ams)].copy()
        sl_chart = seller_leads_raw[seller_leads_raw["created_by"].apply(normalize_name).isin(selected_ams)].copy()
        hs_chart = hot_sheet_raw[hot_sheet_raw["lead_manager"].apply(normalize_name).isin(selected_ams)].copy()
    else:
        leads = leads_raw.copy()
        am_tasks = am_tasks_raw.copy()
        sl_chart = seller_leads_raw.copy()
        hs_chart = hot_sheet_raw.copy()

    # ── Helper: format currency as K ──
    def fmt_k(val):
        if pd.isna(val) or val == 0:
            return "$0"
        return f"${val/1000:,.1f}K"

    # ── KPI calculations ──
    ACTIVE_STATUSES = {"Under Contract", "Under Renovation", "List on Market"}
    active_addresses = set(
        hs_chart.loc[hs_chart["status"].isin(ACTIVE_STATUSES), "property_address"]
        .dropna().str.strip().str.lower()
    )
    # Build address→profit map from ConnectorLeads and SellerLeads (no double-count)
    profit_by_address = {}
    for _, row in leads[["connector_property", "projected_profit"]].dropna(subset=["connector_property"]).iterrows():
        addr = row["connector_property"].strip().lower()
        if addr not in profit_by_address:
            profit_by_address[addr] = row["projected_profit"] or 0
    for _, row in sl_chart[["property_address", "project_profit"]].dropna(subset=["property_address"]).iterrows():
        addr = row["property_address"].strip().lower()
        if addr not in profit_by_address:
            profit_by_address[addr] = row["project_profit"] or 0
    future_profit = sum(
        profit_by_address.get(addr, 0) or 0
        for addr in active_addresses
    )
    # Build address → (closing_date, profit) map from both lead tables (ConnectorLeads takes precedence)
    # ConnectorLeads uses closing_date; SellerLeads falls back to agreement_date
    deal_by_address = {}
    for _, row in leads[["connector_property", "closing_date", "projected_profit"]].dropna(subset=["connector_property"]).iterrows():
        addr = row["connector_property"].strip().lower()
        if addr not in deal_by_address:
            deal_by_address[addr] = {"date": row["closing_date"], "profit": row["projected_profit"]}
    for _, row in sl_chart[["property_address", "agreement_date", "project_profit"]].dropna(subset=["property_address"]).iterrows():
        addr = row["property_address"].strip().lower()
        if addr not in deal_by_address:
            deal_by_address[addr] = {"date": row["agreement_date"], "profit": row["project_profit"]}
    # Hot Sheet properties excluding Fell Out of Contract
    eligible_hs = set(
        hs_chart.loc[hs_chart["status"] != "Fell Out of Contract", "property_address"]
        .dropna().str.strip().str.lower()
    )
    def closing_year(d):
        if d is None or (hasattr(d, '__class__') and pd.isna(d)):
            return None
        return (pd.Timestamp(d) + pd.DateOffset(months=3)).year
    ytd_profits = [
        float(deal_by_address[addr]["profit"])
        for addr in eligible_hs
        if addr in deal_by_address
        and closing_year(deal_by_address[addr]["date"]) == current_year
        and deal_by_address[addr]["profit"] is not None
        and pd.notna(deal_by_address[addr]["profit"])
    ]
    ytd_profit_per_deal = sum(ytd_profits) / len(ytd_profits) if ytd_profits else 0

    cl_offers = leads[
        (leads["offer_amount"].notna()) & (leads["asking_price"].notna()) & (leads["asking_price"] > 0) &
        (pd.to_datetime(leads["created_on"], errors="coerce").dt.year == current_year)
    ][["offer_amount", "asking_price"]]
    sl_offers = sl_chart[
        (sl_chart["offer_amount"].notna()) & (sl_chart["asking_price"].notna()) & (sl_chart["asking_price"] > 0) &
        (pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.year == current_year)
    ][["offer_amount", "asking_price"]]
    all_offers = pd.concat([cl_offers, sl_offers], ignore_index=True)
    offer_to_ask = (all_offers["offer_amount"] / all_offers["asking_price"]).mean() * 100 if not all_offers.empty else 0

    cl_purch = leads[
        (leads["purchase_price"].notna()) & (leads["asking_price"].notna()) & (leads["asking_price"] > 0) &
        (pd.to_datetime(leads["created_on"], errors="coerce").dt.year == current_year)
    ][["purchase_price", "asking_price"]]
    sl_purch = sl_chart[
        (sl_chart["purchase_price"].notna()) & (sl_chart["asking_price"].notna()) & (sl_chart["asking_price"] > 0) &
        (pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.year == current_year)
    ][["purchase_price", "asking_price"]]
    all_purch = pd.concat([cl_purch, sl_purch], ignore_index=True)
    purchase_to_ask = (all_purch["purchase_price"] / all_purch["asking_price"]).mean() * 100 if not all_purch.empty else 0

    cl_qtr = leads[(pd.to_datetime(leads["created_on"], errors="coerce").dt.date >= qtr_start) & (pd.to_datetime(leads["created_on"], errors="coerce").dt.date <= qtr_end)]
    sl_qtr = sl_chart[(pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.date >= qtr_start) & (pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.date <= qtr_end)]
    qtr_leads_all = pd.concat([cl_qtr[["purchase_price"]], sl_qtr[["purchase_price"]]], ignore_index=True)
    lead_conversion = (qtr_leads_all["purchase_price"].notna().sum() / len(qtr_leads_all) * 100) if len(qtr_leads_all) > 0 else 0

    # ── KPI cards row ──
    kc1, kc2, kc3, kc4, kc5 = st.columns(5)
    kpi_tooltips = [
        "Sum of projected profit for all active Hot Sheet properties (status: Under Contract, Under Renovation, or List on Market).",
        f"Average projected profit per deal for properties closing in {current_year}, based on Hot Sheet closing dates (shifted +3 months for fiscal year).",
        f"Average offer amount ÷ asking price for all leads with both fields filled in, created in {current_year}.",
        f"Average purchase price ÷ asking price for all leads with both fields filled in, created in {current_year}.",
        f"% of leads created this quarter (Q{(today.month-1)//3+1} {current_year}) that resulted in a purchase price being set.",
    ]
    for col, label, value, tip in zip(
        [kc1, kc2, kc3, kc4, kc5],
        ["Future Projected Profit", "Projected Year Profit/Deal", "Offer to Ask", "Purchase to Ask", "Lead Conversion (Qtr)"],
        [fmt_k(future_profit), fmt_k(ytd_profit_per_deal if pd.notna(ytd_profit_per_deal) else 0), f"{offer_to_ask:.1f}%", f"{purchase_to_ask:.1f}%", f"{lead_conversion:.1f}%"],
        kpi_tooltips,
    ):
        col.markdown(
            f'<div class="kpi-card" data-tooltip="{tip}" style="background:#e8eaef;border-radius:8px;padding:12px;text-align:center;">'
            f'<div style="font-size:0.75rem;color:#666;">{label}</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:#1a1a2e;">{value}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 1 ──
    r1c1, r1c2, r1c3 = st.columns(3)

    # 1) Properties Walked By Week
    with r1c1:
        st.markdown('<p class="chart-title">Properties Walked By Week</p>', unsafe_allow_html=True)
        walked = am_tasks[
            (am_tasks["follow_up_type"] == "Property Walk") &
            (am_tasks["follow_up_status"] == "Complete") &
            (pd.to_datetime(am_tasks["due_date"]).dt.date >= qtr_start)
        ].copy()
        if not walked.empty:
            walked["week"] = pd.to_datetime(walked["due_date"]).dt.to_period("W-SUN").dt.start_time
            walked["assigned_to"] = walked["assigned_to"].apply(normalize_name)
            wk_data = walked.groupby(["week", "assigned_to"]).size().reset_index(name="count")
            fig = go.Figure()
            legend_items = []
            for person in sorted(wk_data["assigned_to"].unique()):
                color = PERSON_COLORS.get(person, "#999")
                legend_items.append((person, color))
                pdf = wk_data[wk_data["assigned_to"] == person]
                fig.add_trace(go.Bar(
                    x=pdf["week"], y=pdf["count"], name=person,
                    marker=beveled_marker(color),
                    hovertemplate="<b>" + person + "</b><br>Week of %{x|%b %d, %Y}<br>Count: <b>%{y}</b><extra></extra>",
                ))
            fig.add_hline(y=7, line_dash="dash", line_color="#7a9a6d", line_width=2,
                          annotation_text="Weekly Goal", annotation_position="top left",
                          annotation_font=dict(color="#7a9a6d", size=11))
            x_min = wk_data["week"].min() - pd.Timedelta(days=4)
            x_max = wk_data["week"].max() + pd.Timedelta(days=10)
            fig.update_layout(**CHART_BG, barmode="group", height=340, bargap=0.15,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickformat="%b %d", gridcolor="#f0f0f0", zeroline=False,
                           tickangle=-30, tickfont=dict(size=10), range=[x_min, x_max],
                           dtick=7 * 24 * 60 * 60 * 1000, ticklabelmode="period"),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=legend_items)

    # 2) Future Profit by AM
    with r1c2:
        st.markdown('<p class="chart-title">Future Profit by AM</p>', unsafe_allow_html=True)
        # Build address → (am, profit) from both tables; ConnectorLeads takes precedence
        am_profit_by_address = {}
        for _, row in leads[["connector_property", "relationship_manager", "projected_profit"]].dropna(subset=["connector_property"]).iterrows():
            addr = row["connector_property"].strip().lower()
            if addr not in am_profit_by_address:
                am_profit_by_address[addr] = {"am": normalize_name(row["relationship_manager"]), "profit": row["projected_profit"] or 0}
        for _, row in sl_chart[["property_address", "created_by", "project_profit"]].dropna(subset=["property_address"]).iterrows():
            addr = row["property_address"].strip().lower()
            if addr not in am_profit_by_address:
                am_profit_by_address[addr] = {"am": normalize_name(row["created_by"]), "profit": row["project_profit"] or 0}
        am_totals = {}
        for addr in active_addresses:
            if addr in am_profit_by_address:
                entry = am_profit_by_address[addr]
                am = normalize_name(entry["am"])
                am_totals[am] = am_totals.get(am, 0) + (entry["profit"] or 0)
        if am_totals:
            fp = pd.DataFrame(list(am_totals.items()), columns=["relationship_manager", "projected_profit"])
            fp = fp[fp["projected_profit"] > 0].sort_values("projected_profit", ascending=False)
            colors = [PERSON_COLORS.get(p, "#999") for p in fp["relationship_manager"]]
            fig = go.Figure(go.Bar(
                x=fp["relationship_manager"], y=fp["projected_profit"], name="Future Profit",
                marker=beveled_marker(colors),
                text=[fmt_k(v) for v in fp["projected_profit"]], textposition="outside",
                textfont=dict(size=11),
                hovertemplate="<b>%{x}</b><br>Projected Profit: <b>%{text}</b><extra></extra>",
            ))
            fig.add_hline(y=100000, line_dash="dash", line_color="#7a9a6d", line_width=2,
                          annotation_text="Profit Goal ($100K)", annotation_position="top right",
                          annotation_font=dict(color="#7a9a6d", size=11))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickangle=-20, tickfont=dict(size=11), automargin=True),
                margin=dict(l=10, r=10, t=5, b=60))
            render_chart(fig, height=380)

    # 3) Year to Date Properties Walked
    with r1c3:
        st.markdown('<p class="chart-title">Year to Date Properties Walked</p>', unsafe_allow_html=True)
        ytd_walked = am_tasks[
            (am_tasks["follow_up_type"] == "Property Walk") &
            (am_tasks["follow_up_status"] == "Complete") &
            (pd.to_datetime(am_tasks["due_date"]).dt.year == current_year)
        ].copy()
        if not ytd_walked.empty:
            ytd_walked["assigned_to"] = ytd_walked["assigned_to"].apply(normalize_name)
            ytd_wk = ytd_walked.groupby("assigned_to").size().reset_index(name="count").sort_values("count", ascending=False)
            colors = [PERSON_COLORS.get(p, "#999") for p in ytd_wk["assigned_to"]]
            fig = go.Figure(go.Bar(
                x=ytd_wk["assigned_to"], y=ytd_wk["count"],
                marker=beveled_marker(colors),
                text=ytd_wk["count"], textposition="outside",
                textfont=dict(size=12),
                hovertemplate="<b>%{x}</b><br>Properties Walked: <b>%{y}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickangle=-20, tickfont=dict(size=11), automargin=True),
                margin=dict(l=10, r=10, t=5, b=60))
            render_chart(fig, height=380)

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 2 ──
    r2c1, r2c2, r2c3 = st.columns(3)

    # 4) Avg Asking vs Offer vs Purchase (Current Qtr)
    with r2c1:
        st.markdown('<p class="chart-title">Avg Asking vs Offer vs Purchase (Current Qtr)</p>', unsafe_allow_html=True)
        cl_qtr_data = leads[(pd.to_datetime(leads["created_on"]).dt.date >= qtr_start) & (pd.to_datetime(leads["created_on"]).dt.date <= qtr_end)]
        sl_qtr_data = sl_chart[(pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.date >= qtr_start) & (pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.date <= qtr_end)]
        combined_asking = pd.concat([cl_qtr_data["asking_price"], sl_qtr_data["asking_price"]], ignore_index=True)
        combined_offer = pd.concat([cl_qtr_data["offer_amount"], sl_qtr_data["offer_amount"]], ignore_index=True)
        combined_purchase = pd.concat([cl_qtr_data["purchase_price"], sl_qtr_data["purchase_price"]], ignore_index=True)
        avg_asking = combined_asking.mean() if combined_asking.notna().any() else 0
        avg_offer = combined_offer.mean() if combined_offer.notna().any() else 0
        avg_purchase = combined_purchase.mean() if combined_purchase.notna().any() else 0
        bar_labels = ["Avg Asking", "Avg Offer", "Avg Purchase"]
        bar_values = [avg_asking if pd.notna(avg_asking) else 0, avg_offer if pd.notna(avg_offer) else 0, avg_purchase if pd.notna(avg_purchase) else 0]
        bar_colors = ["#a0926c", "#c2703e", "#7a9a6d"]
        fig = go.Figure()
        for lbl, val, clr in zip(bar_labels, bar_values, bar_colors):
            fig.add_trace(go.Bar(
                x=[lbl], y=[val], name=lbl,
                marker=beveled_marker(clr),
                text=[fmt_k(val)], textposition="outside",
                textfont=dict(size=11),
                hovertemplate="<b>" + lbl + "</b><br>%{y:$,.0f}<extra></extra>",
                width=0.8,
            ))
        fig.update_layout(**CHART_BG, height=340, showlegend=False,
            yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
            xaxis=dict(title="", tickfont=dict(size=11)),
            margin=dict(l=10, r=10, t=5, b=30))
        render_chart(fig, height=380, legend=[
            ("Avg Asking", "#a0926c"), ("Avg Offer", "#c2703e"), ("Avg Purchase", "#7a9a6d")
        ])

    # 5) Offers By Week
    with r2c2:
        st.markdown('<p class="chart-title">Offers By Week (Current Qtr)</p>', unsafe_allow_html=True)
        cl_offers_qtr = leads[
            (leads["offer_amount"].notna()) &
            (pd.to_datetime(leads["created_on"], errors="coerce").dt.date >= qtr_start) &
            (pd.to_datetime(leads["created_on"], errors="coerce").dt.date <= qtr_end)
        ][["created_on", "relationship_manager"]].copy()
        cl_offers_qtr["am"] = cl_offers_qtr["relationship_manager"].apply(normalize_name)
        sl_offers_qtr = sl_chart[
            (sl_chart["offer_amount"].notna()) &
            (pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.date >= qtr_start) &
            (pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.date <= qtr_end)
        ][["created_on", "created_by"]].copy()
        sl_offers_qtr["am"] = sl_offers_qtr["created_by"].apply(normalize_name)
        offers = pd.concat([
            cl_offers_qtr[["created_on", "am"]],
            sl_offers_qtr[["created_on", "am"]]
        ], ignore_index=True)
        if not offers.empty:
            offers["week"] = pd.to_datetime(offers["created_on"], errors="coerce").dt.to_period("W-SUN").dt.start_time
            off_data = offers.groupby(["week", "am"]).size().reset_index(name="count")
            fig = go.Figure()
            legend_items = []
            for person in sorted(off_data["am"].unique()):
                color = PERSON_COLORS.get(person, "#999")
                legend_items.append((person, color))
                pdf = off_data[off_data["am"] == person]
                fig.add_trace(go.Bar(
                    x=pdf["week"], y=pdf["count"], name=person,
                    marker=beveled_marker(color),
                    hovertemplate="<b>" + person + "</b><br>Week of %{x|%b %d, %Y}<br>Offers: <b>%{y}</b><extra></extra>",
                ))
            fig.update_layout(**CHART_BG, barmode="group", height=340, bargap=0.15,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickformat="%b %d", gridcolor="#f0f0f0", zeroline=False,
                           tickangle=-30, tickfont=dict(size=10),
                           dtick=7 * 24 * 60 * 60 * 1000, ticklabelmode="period"),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=legend_items)

    # 6) Purchase vs Leads
    with r2c3:
        st.markdown('<p class="chart-title">Purchase vs Leads (Current Qtr)</p>', unsafe_allow_html=True)
        all_hs_addresses = set(
            hs_chart.loc[hs_chart["status"] != "Fell Out of Contract", "property_address"]
            .dropna().str.strip().str.lower()
        )
        cl_pvl = leads[
            (pd.to_datetime(leads["created_on"], errors="coerce").dt.date >= qtr_start) &
            (pd.to_datetime(leads["created_on"], errors="coerce").dt.date <= qtr_end)
        ][["created_on", "purchase_price", "connector_property"]].copy()
        cl_pvl["address"] = cl_pvl["connector_property"].str.strip().str.lower()
        sl_pvl = sl_chart[
            (pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.date >= qtr_start) &
            (pd.to_datetime(sl_chart["created_on"], errors="coerce").dt.date <= qtr_end)
        ][["created_on", "purchase_price", "property_address"]].copy()
        sl_pvl["address"] = sl_pvl["property_address"].str.strip().str.lower()
        pvl = pd.concat([
            cl_pvl[["created_on", "purchase_price", "address"]],
            sl_pvl[["created_on", "purchase_price", "address"]]
        ], ignore_index=True)
        if not pvl.empty:
            pvl["week"] = pd.to_datetime(pvl["created_on"], errors="coerce").dt.to_period("W-SUN").dt.start_time
            total_leads = pvl.groupby("week").size().reset_index(name="leads")
            purchases = pvl[
                pvl["purchase_price"].notna() &
                pvl["address"].isin(all_hs_addresses)
            ].groupby("week").size().reset_index(name="purchases")
            merged = total_leads.merge(purchases, on="week", how="left").fillna(0)
            merged["purchases"] = merged["purchases"].astype(int)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=merged["week"], y=merged["leads"], name="Total Leads",
                marker=beveled_marker("#a0926c"),
                hovertemplate="Week of %{x|%b %d, %Y}<br>Leads: <b>%{y}</b><extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=merged["week"], y=merged["purchases"], name="Purchases",
                marker=beveled_marker("#7a9a6d"),
                hovertemplate="Week of %{x|%b %d, %Y}<br>Purchases: <b>%{y}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, barmode="group", height=340, bargap=0.15,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickformat="%b %d", gridcolor="#f0f0f0", zeroline=False,
                           tickangle=-30, tickfont=dict(size=10),
                           dtick=7 * 24 * 60 * 60 * 1000, ticklabelmode="period"),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=[
                ("Total Leads", "#a0926c"), ("Purchases", "#7a9a6d")
            ])

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 3 ──
    r3c1, r3c2, r3c3, r3c4 = st.columns(4)

    PIE_COLORS = ["#a0926c", "#7a9a6d", "#c2703e", "#6b8cae", "#c47eb0", "#7eb5c4", "#e8b86d", "#8b7ab5", "#999"]

    # 7) Deals (Last 6 Months)
    with r3c1:
        st.markdown('<p class="chart-title">Deals</p>', unsafe_allow_html=True)
        six_months_ago = (pd.Timestamp(today) - pd.DateOffset(months=6)).date()
        hs_deals = hs_chart[hs_chart["status"] != "Fell Out of Contract"][["property_address", "closing_date", "lead_manager"]].copy()
        hs_deals = hs_deals.dropna(subset=["closing_date"])
        hs_deals["closing_date"] = pd.to_datetime(hs_deals["closing_date"], errors="coerce")
        hs_deals = hs_deals[hs_deals["closing_date"].dt.date >= six_months_ago]
        hs_deals["am"] = hs_deals["lead_manager"].apply(normalize_name)
        hs_deals["month"] = hs_deals["closing_date"].dt.to_period("M").dt.start_time
        if not hs_deals.empty:
            deal_data = hs_deals.groupby(["month", "am"]).size().reset_index(name="count")
            fig = go.Figure()
            legend_items = []
            for person in sorted(deal_data["am"].unique()):
                color = PERSON_COLORS.get(person, "#999")
                legend_items.append((person, color))
                pdf = deal_data[deal_data["am"] == person]
                fig.add_trace(go.Bar(
                    x=pdf["month"], y=pdf["count"], name=person,
                    marker=beveled_marker(color),
                    hovertemplate="<b>" + person + "</b><br>%{x|%b %Y}<br>Deals: <b>%{y}</b><extra></extra>",
                ))
            fig.update_layout(**CHART_BG, barmode="stack", height=340, bargap=0.2,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True, dtick=1),
                xaxis=dict(title="", tickformat="%b %Y", gridcolor="#f0f0f0", zeroline=False,
                           tickangle=-30, tickfont=dict(size=10), dtick="M1"),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=legend_items)

    # 8) Lead Conversion by Quarter
    with r3c2:
        st.markdown('<p class="chart-title">Lead Conversion by Quarter</p>', unsafe_allow_html=True)
        def quarter_bounds(year, q):
            start_month = (q - 1) * 3 + 1
            end_month = start_month + 2
            import calendar
            end_day = calendar.monthrange(year, end_month)[1]
            return date(year, start_month, 1), date(year, end_month, end_day)
        current_q = (today.month - 1) // 3 + 1
        quarters = []
        y, q = current_year, current_q
        for _ in range(4):
            quarters.append((y, q))
            q -= 1
            if q == 0:
                q = 4
                y -= 1
        quarters.reverse()
        qtr_rows = []
        all_leads_qtr = pd.concat([
            leads[["created_on", "purchase_price"]],
            sl_chart[["created_on", "purchase_price"]]
        ], ignore_index=True)
        all_leads_qtr["created_on"] = pd.to_datetime(all_leads_qtr["created_on"], errors="coerce")
        for y, q in quarters:
            qs, qe = quarter_bounds(y, q)
            mask = (all_leads_qtr["created_on"].dt.date >= qs) & (all_leads_qtr["created_on"].dt.date <= min(qe, today))
            subset = all_leads_qtr[mask]
            total = len(subset)
            purchased = subset["purchase_price"].notna().sum()
            conversion = (purchased / total * 100) if total > 0 else 0
            qtr_rows.append({"quarter": f"Q{q} {y}", "conversion": round(conversion, 1), "total": total, "purchased": purchased})
        qdf = pd.DataFrame(qtr_rows)
        fig = go.Figure(go.Bar(
            x=qdf["quarter"], y=qdf["conversion"],
            marker=beveled_marker("#a0926c"),
            text=[f"{v:.1f}%" for v in qdf["conversion"]], textposition="outside",
            textfont=dict(size=12),
            hovertemplate="<b>%{x}</b><br>Conversion: <b>%{text}</b><br>Purchased: <b>%{customdata[0]}</b> of <b>%{customdata[1]}</b> leads<extra></extra>",
            customdata=qdf[["purchased", "total"]].values,
        ))
        fig.update_layout(**CHART_BG, height=340, showlegend=False,
            yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True,
                       ticksuffix="%", range=[0, max(qdf["conversion"].max() * 1.3, 5)]),
            xaxis=dict(title="", tickfont=dict(size=12)),
            margin=dict(l=10, r=10, t=5, b=30))
        render_chart(fig, height=380)

    # 9) Exit Strategy
    with r3c3:
        st.markdown('<p class="chart-title">Exit Strategy</p>', unsafe_allow_html=True)
        exit_all = pd.concat([
            leads["potential_exit"].dropna(),
            sl_chart["potential_exit"].dropna()
        ], ignore_index=True)
        exit_all = exit_all.str.strip().str.title()
        exit_counts = exit_all.value_counts().reset_index()
        exit_counts.columns = ["strategy", "count"]
        if not exit_counts.empty:
            colors = PIE_COLORS[:len(exit_counts)]
            fig = go.Figure(go.Pie(
                labels=exit_counts["strategy"], values=exit_counts["count"],
                marker=dict(colors=colors, line=dict(color="white", width=2)),
                textinfo="percent", textfont=dict(size=11),
                hovertemplate="<b>%{label}</b><br>%{value} leads (%{percent})<extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                margin=dict(l=10, r=10, t=5, b=10))
            render_chart(fig, height=380, legend=list(zip(exit_counts["strategy"], colors)), legend_position="bottom")

    # 10) Lost Deals
    with r3c4:
        st.markdown('<p class="chart-title">Lost Deals</p>', unsafe_allow_html=True)
        lost_all = pd.concat([
            leads["closed_lost_detail"].dropna(),
            sl_chart["closed_lost_detail"].dropna()
        ], ignore_index=True)
        lost_all = lost_all.str.strip().str.replace(r'\s*-\s*', '-', regex=True).str.title()
        lost_counts = lost_all.value_counts().reset_index()
        lost_counts.columns = ["reason", "count"]
        if not lost_counts.empty:
            colors = PIE_COLORS[:len(lost_counts)]
            fig = go.Figure(go.Pie(
                labels=lost_counts["reason"], values=lost_counts["count"],
                marker=dict(colors=colors, line=dict(color="white", width=2)),
                textinfo="percent", textfont=dict(size=11),
                hovertemplate="<b>%{label}</b><br>%{value} leads (%{percent})<extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                margin=dict(l=10, r=10, t=5, b=10))
            render_chart(fig, height=380, legend=list(zip(lost_counts["reason"], colors)), legend_position="bottom")

# ═══════════════════════════════════════════════════
# TAB 3: AM Rehab
# ═══════════════════════════════════════════════════
with tab3:

    # ── Data prep ──
    rehab = rehab_raw.copy()
    rehab["date_visited"] = pd.to_datetime(rehab["date_visited"], errors="coerce")
    rehab["property_walker"] = rehab["property_walker"].apply(normalize_name)

    # ── Header + Filters ──
    rb_ban, rb_fil1, rb_fil2 = st.columns([3, 2, 2])
    rb_ban.markdown('''<div class="section-banner"><h2>AM Rehab</h2></div>
<style>
    div[data-testid="stColumn"]:has(.section-banner) > div {
        background: #e8eaef !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    div[data-testid="stColumn"]:has(.section-banner) .section-banner {
        background: transparent; padding: 0;
    }
</style>
''', unsafe_allow_html=True)

    all_walkers = sorted(rehab["property_walker"].dropna().unique().tolist())
    with rb_fil1:
        with st.expander("Acquisition Manager", expanded=False):
            prev_rw = st.session_state.get("rw_all_prev", True)
            all_rw = st.checkbox("All", value=True, key="rw_all")
            if prev_rw and not all_rw:
                for w in all_walkers: st.session_state[f"rw_{w}"] = False
            elif not prev_rw and all_rw:
                for w in all_walkers: st.session_state[f"rw_{w}"] = True
            st.session_state["rw_all_prev"] = all_rw
            selected_walkers = []
            for w in all_walkers:
                default_w = all_rw if f"rw_{w}" not in st.session_state else st.session_state[f"rw_{w}"]
                checked_w = st.checkbox(w, value=default_w, key=f"rw_{w}", disabled=all_rw)
                if all_rw or checked_w:
                    selected_walkers.append(w)

    reno_levels = sorted(rehab["renovation_level"].dropna().unique().tolist())
    with rb_fil2:
        with st.expander("Renovation Level", expanded=False):
            prev_rl = st.session_state.get("rl_all_prev", True)
            all_rl = st.checkbox("All", value=True, key="rl_all")
            if prev_rl and not all_rl:
                for lvl in reno_levels: st.session_state[f"rl_{lvl}"] = False
            elif not prev_rl and all_rl:
                for lvl in reno_levels: st.session_state[f"rl_{lvl}"] = True
            st.session_state["rl_all_prev"] = all_rl
            selected_levels = []
            for lvl in reno_levels:
                default_rl = all_rl if f"rl_{lvl}" not in st.session_state else st.session_state[f"rl_{lvl}"]
                checked_rl = st.checkbox(lvl, value=default_rl, key=f"rl_{lvl}", disabled=all_rl)
                if all_rl or checked_rl:
                    selected_levels.append(lvl)

    if not all_rw and selected_walkers:
        rehab = rehab[rehab["property_walker"].isin(selected_walkers)]
    if not all_rl and selected_levels:
        rehab = rehab[rehab["renovation_level"].isin(selected_levels)]

    # ── Per-property aggregates ──
    totals = rehab.groupby("property_address")["amount_num"].sum().reset_index(name="total_cost")
    cat_totals = rehab.groupby(["property_address", "cost_category"])["amount_num"].sum().unstack(fill_value=0).reset_index()
    for col in ["Holding", "Misc", "Renovation"]:
        if col not in cat_totals.columns:
            cat_totals[col] = 0
    props = rehab.drop_duplicates("property_address")[
        ["property_address", "property_walker", "date_visited", "renovation_level",
         "purchase_price", "list_price_arv", "holding_days", "bedroom_num", "bathroom_num"]
    ].merge(totals, on="property_address").merge(cat_totals[["property_address", "Holding", "Misc", "Renovation"]], on="property_address")
    props["list_price_arv"] = pd.to_numeric(props["list_price_arv"], errors="coerce").fillna(0)
    props["purchase_price"] = pd.to_numeric(props["purchase_price"], errors="coerce").fillna(0)
    props["implied_margin"] = props["list_price_arv"] - props["purchase_price"] - props["total_cost"]

    # ── KPI cards ──
    rk1, rk2, rk3, rk4, rk5 = st.columns(5)
    rehab_kpi_tooltips = [
        "Number of unique properties with a completed Jotform / AM Rehab Calc submitted.",
        "Average total estimated cost (Holding + Misc + Renovation) across all walked properties.",
        "Average renovation-only costs (excludes Holding and Misc) across all walked properties.",
        "Average After Repair Value (ARV / list price) across all walked properties.",
        "Average implied profit margin: ARV minus purchase price minus total rehab cost.",
    ]
    jotforms_count = props["property_address"].nunique()
    avg_total = props["total_cost"].mean() if not props.empty else 0
    avg_reno = props["Renovation"].mean() if not props.empty else 0
    avg_arv = props["list_price_arv"].mean() if not props.empty else 0
    avg_margin = props["implied_margin"].mean() if not props.empty else 0
    for col, label, value, tip in zip(
        [rk1, rk2, rk3, rk4, rk5],
        ["Jotforms Completed", "Avg Total Rehab Cost", "Avg Renovation Cost", "Avg ARV", "Avg Implied Margin"],
        [str(jotforms_count), fmt_k(avg_total), fmt_k(avg_reno), fmt_k(avg_arv), fmt_k(avg_margin)],
        rehab_kpi_tooltips,
    ):
        col.markdown(
            f'<div class="kpi-card" data-tooltip="{tip}" style="background:#e8eaef;border-radius:8px;padding:12px;text-align:center;">'
            f'<div style="font-size:0.75rem;color:#666;">{label}</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:#1a1a2e;">{value}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 1 ──
    rb1c1, rb1c2, rb1c3 = st.columns(3)

    # 1) Total Estimated Cost by Property
    with rb1c1:
        st.markdown('<p class="chart-title">Total Estimated Cost by Property</p>', unsafe_allow_html=True)
        if not props.empty:
            ps = props.sort_values("total_cost", ascending=True)
            # Shorten address for display
            ps["label"] = ps["property_address"].str.split(",").str[0]
            colors = [PERSON_COLORS.get(w, "#999") for w in ps["property_walker"]]
            fig = go.Figure(go.Bar(
                y=ps["label"], x=ps["total_cost"], orientation="h",
                marker=beveled_marker(colors),
                text=[fmt_k(v) for v in ps["total_cost"]], textposition="outside",
                textfont=dict(size=10),
                hovertemplate="<b>%{y}</b><br>Total Cost: <b>%{text}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                yaxis=dict(tickfont=dict(size=10), automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#e8e8e8", tickfont=dict(size=10)),
                margin=dict(l=10, r=60, t=5, b=30))
            render_chart(fig, height=380)

    # 2) Cost Category Breakdown by Property
    with rb1c2:
        st.markdown('<p class="chart-title">Cost Breakdown by Property</p>', unsafe_allow_html=True)
        if not props.empty:
            ps2 = props.sort_values("total_cost", ascending=True)
            ps2["label"] = ps2["property_address"].str.split(",").str[0]
            fig = go.Figure()
            for cat, color in [("Renovation", "#c2703e"), ("Misc", "#a0926c"), ("Holding", "#7a9a6d")]:
                fig.add_trace(go.Bar(
                    y=ps2["label"], x=ps2[cat], name=cat, orientation="h",
                    marker=beveled_marker(color),
                    hovertemplate="<b>%{y}</b><br>" + cat + ": <b>%{x:$,.0f}</b><extra></extra>",
                ))
            fig.update_layout(**CHART_BG, barmode="stack", height=340, showlegend=False,
                yaxis=dict(tickfont=dict(size=10), automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#e8e8e8", tickfont=dict(size=10)),
                margin=dict(l=10, r=20, t=5, b=30))
            render_chart(fig, height=380, legend=[("Renovation", "#c2703e"), ("Misc", "#a0926c"), ("Holding", "#7a9a6d")])

    # 3) Renovation Level Distribution
    with rb1c3:
        st.markdown('<p class="chart-title">Renovation Level</p>', unsafe_allow_html=True)
        if not props.empty:
            rl = props["renovation_level"].fillna("Unknown").value_counts().reset_index()
            rl.columns = ["level", "count"]
            RENO_COLORS = {"Light": "#7a9a6d", "Medium": "#a0926c", "Heavy": "#c2703e", "Unknown": "#6b8f9e"}
            rl_colors = [RENO_COLORS.get(l, "#999") for l in rl["level"]]
            fig = go.Figure(go.Pie(
                labels=rl["level"], values=rl["count"],
                marker=dict(colors=rl_colors, line=dict(color="white", width=2)),
                textinfo="percent+value", textfont=dict(size=12),
                hovertemplate="<b>%{label}</b><br>%{value} properties (%{percent})<extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                margin=dict(l=10, r=10, t=5, b=10))
            render_chart(fig, height=380, legend=list(zip(rl["level"], rl_colors)), legend_position="bottom")

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 2 ──
    rb2c1, rb2c2, rb2c3 = st.columns(3)

    # 4) Top Renovation Line Items
    with rb2c1:
        st.markdown('<p class="chart-title">Avg Cost by Renovation Area</p>', unsafe_allow_html=True)
        reno_items = rehab[rehab["cost_category"] == "Renovation"].copy()
        if not reno_items.empty:
            avg_by_area = reno_items.groupby("area")["amount_num"].mean().reset_index(name="avg_cost")
            avg_by_area = avg_by_area[avg_by_area["avg_cost"] > 0].sort_values("avg_cost", ascending=True)
            fig = go.Figure(go.Bar(
                y=avg_by_area["area"], x=avg_by_area["avg_cost"], orientation="h",
                marker=beveled_marker("#c2703e"),
                text=[fmt_k(v) for v in avg_by_area["avg_cost"]], textposition="outside",
                textfont=dict(size=10),
                hovertemplate="<b>%{y}</b><br>Avg Cost: <b>%{text}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                yaxis=dict(tickfont=dict(size=10), automargin=True),
                xaxis=dict(showgrid=True, gridcolor="#e8e8e8", tickfont=dict(size=10)),
                margin=dict(l=10, r=60, t=5, b=30))
            render_chart(fig, height=380)

    # 5) ARV vs All-In Cost
    with rb2c2:
        st.markdown('<p class="chart-title">ARV vs All-In Cost by Property</p>', unsafe_allow_html=True)
        if not props.empty:
            ps3 = props.sort_values("list_price_arv", ascending=False)
            ps3["label"] = ps3["property_address"].str.split(",").str[0]
            ps3["all_in"] = ps3["purchase_price"] + ps3["total_cost"]
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=ps3["label"], y=ps3["list_price_arv"], name="ARV",
                marker=beveled_marker("#7a9a6d"),
                text=[fmt_k(v) for v in ps3["list_price_arv"]], textposition="outside",
                textfont=dict(size=10), width=0.35,
                hovertemplate="<b>%{x}</b><br>ARV: <b>%{text}</b><extra></extra>",
            ))
            fig.add_trace(go.Bar(
                x=ps3["label"], y=ps3["all_in"], name="All-In Cost",
                marker=beveled_marker("#c2703e"),
                text=[fmt_k(v) for v in ps3["all_in"]], textposition="outside",
                textfont=dict(size=10), width=0.35,
                hovertemplate="<b>%{x}</b><br>All-In: <b>%{text}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, barmode="group", height=340, showlegend=False,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickangle=-20, tickfont=dict(size=10), automargin=True),
                margin=dict(l=10, r=10, t=5, b=60))
            render_chart(fig, height=380, legend=[("ARV", "#7a9a6d"), ("All-In Cost", "#c2703e")])

    # 6) Jotforms Completed by AM
    with rb2c3:
        st.markdown('<p class="chart-title">Jotforms Completed by AM</p>', unsafe_allow_html=True)
        if not props.empty:
            by_walker = props.groupby("property_walker").size().reset_index(name="count").sort_values("count", ascending=False)
            colors = [PERSON_COLORS.get(w, "#999") for w in by_walker["property_walker"]]
            fig = go.Figure(go.Bar(
                x=by_walker["property_walker"], y=by_walker["count"],
                marker=beveled_marker(colors),
                text=by_walker["count"], textposition="outside",
                textfont=dict(size=12),
                hovertemplate="<b>%{x}</b><br>Jotforms: <b>%{y}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickangle=-20, tickfont=dict(size=11), automargin=True),
                margin=dict(l=10, r=10, t=5, b=60))
            render_chart(fig, height=380)

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 3 ──
    rb3c1, rb3c2 = st.columns(2)

    # 7) Walks by Week
    with rb3c1:
        st.markdown('<p class="chart-title">Walks by Week</p>', unsafe_allow_html=True)
        walks_dated = props.dropna(subset=["date_visited"]).copy()
        if not walks_dated.empty:
            walks_dated["week"] = walks_dated["date_visited"].dt.to_period("W-SUN").dt.start_time
            wk = walks_dated.groupby(["week", "property_walker"]).size().reset_index(name="count")
            fig = go.Figure()
            legend_items = []
            for person in sorted(wk["property_walker"].unique()):
                color = PERSON_COLORS.get(person, "#999")
                legend_items.append((person, color))
                pdf = wk[wk["property_walker"] == person]
                fig.add_trace(go.Bar(
                    x=pdf["week"], y=pdf["count"], name=person,
                    marker=beveled_marker(color),
                    hovertemplate="<b>" + person + "</b><br>Week of %{x|%b %d, %Y}<br>Walks: <b>%{y}</b><extra></extra>",
                ))
            x_min = wk["week"].min() - pd.Timedelta(days=4)
            x_max = wk["week"].max() + pd.Timedelta(days=10)
            fig.update_layout(**CHART_BG, barmode="stack", height=340, bargap=0.2, showlegend=False,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True, dtick=1),
                xaxis=dict(title="", tickformat="%b %d", gridcolor="#f0f0f0", zeroline=False,
                           tickangle=-30, tickfont=dict(size=10), range=[x_min, x_max],
                           dtick=7 * 24 * 60 * 60 * 1000, ticklabelmode="period"),
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=legend_items)

    # 8) Avg Rehab Cost Over Time
    with rb3c2:
        st.markdown('<p class="chart-title">Avg Total Rehab Cost by Month</p>', unsafe_allow_html=True)
        if not walks_dated.empty:
            walks_dated["month"] = walks_dated["date_visited"].dt.to_period("M").dt.start_time
            monthly = walks_dated.groupby("month").agg(
                avg_cost=("total_cost", "mean"),
                count=("property_address", "count")
            ).reset_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=monthly["month"], y=monthly["avg_cost"],
                marker=beveled_marker("#a0926c"),
                text=[fmt_k(v) for v in monthly["avg_cost"]], textposition="outside",
                textfont=dict(size=11),
                customdata=monthly["count"],
                hovertemplate="%{x|%b %Y}<br>Avg Cost: <b>%{text}</b><br>Properties: <b>%{customdata}</b><extra></extra>",
            ))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickformat="%b %Y", gridcolor="#f0f0f0", zeroline=False,
                           tickangle=-30, tickfont=dict(size=10), dtick="M1"),
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380)

