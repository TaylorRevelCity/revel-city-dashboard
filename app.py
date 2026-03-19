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
    .block-container { padding-top: 1rem; max-width: 100%; padding-left: 2rem; padding-right: 2rem; }
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
                    console.log('PIE HOVER', i, pt.pointIndex, trace.type, trace.marker);
                    if (!origColors[i] && trace.marker && trace.marker.colors) {
                        origColors[i] = trace.marker.colors.slice();
                    }
                    var pieColors = origColors[i] || [];
                    var len = trace.labels ? trace.labels.length : 0;
                    var pulls = [];
                    var newColors = [];
                    for (var j = 0; j < len; j++) {
                        pulls.push(j === pt.pointIndex ? 0.06 : 0);
                        var c = pieColors[j] || '#999';
                        newColors.push(j === pt.pointIndex ? c : hexToRgba(c, 0.25));
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
    fig.update_layout(autosize=True)

    # Build trace name list for JS
    trace_names = [t.name or "" for t in fig.data]

    html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False, config={"displayModeBar": False, "responsive": True})
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
PERSON_COLORS = {
    "Scotty Patton": "#a0926c",   # tan
    "Wesley Werner": "#c2703e",   # burnt orange
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

tasks_raw = load_tasks()
contacts_raw = load_contacts()
leads_raw = load_connector_leads()
hot_sheet_raw = load_hot_sheet()
seller_leads_raw = load_seller_leads()

tab1, tab2 = st.tabs(["Connector Dashboard", "AM KPIs"])

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

    all_rms = sorted(leads["relationship_manager"].dropna().unique().tolist())
    with am_fil:
        with st.expander("Relationship Manager", expanded=False):
            prev_all_rm = st.session_state.get("rm_all_prev", True)
            all_rm_selected = st.checkbox("All", value=True, key="rm_all")
            if prev_all_rm and not all_rm_selected:
                for rm in all_rms:
                    st.session_state[f"rm_{rm}"] = False
            elif not prev_all_rm and all_rm_selected:
                for rm in all_rms:
                    st.session_state[f"rm_{rm}"] = True
            st.session_state["rm_all_prev"] = all_rm_selected
            selected_rms = []
            for rm in all_rms:
                default_rm = all_rm_selected if f"rm_{rm}" not in st.session_state else st.session_state[f"rm_{rm}"]
                checked_rm = st.checkbox(rm, value=default_rm, key=f"rm_{rm}", disabled=all_rm_selected)
                if all_rm_selected or checked_rm:
                    selected_rms.append(rm)

    if selected_rms:
        leads = leads[leads["relationship_manager"].isin(selected_rms)]

    # ── Helper: format currency as K ──
    def fmt_k(val):
        if pd.isna(val) or val == 0:
            return "$0"
        return f"${val/1000:,.1f}K"

    # ── KPI calculations ──
    ACTIVE_STATUSES = {"Under Contract", "Under Renovation", "List on Market"}
    active_addresses = set(
        hot_sheet_raw.loc[hot_sheet_raw["status"].isin(ACTIVE_STATUSES), "property_address"]
        .dropna().str.strip().str.lower()
    )
    # Build address→profit map from ConnectorLeads and SellerLeads (no double-count)
    profit_by_address = {}
    for _, row in leads_raw[["connector_property", "projected_profit"]].dropna(subset=["connector_property"]).iterrows():
        addr = row["connector_property"].strip().lower()
        if addr not in profit_by_address:
            profit_by_address[addr] = row["projected_profit"] or 0
    for _, row in seller_leads_raw[["property_address", "project_profit"]].dropna(subset=["property_address"]).iterrows():
        addr = row["property_address"].strip().lower()
        if addr not in profit_by_address:
            profit_by_address[addr] = row["project_profit"] or 0
    future_profit = sum(
        profit_by_address.get(addr, 0) or 0
        for addr in active_addresses
    )
    # Build address → (agreement_date, profit) map from both lead tables (ConnectorLeads takes precedence)
    deal_by_address = {}
    for _, row in leads_raw[["connector_property", "agreement_date", "projected_profit"]].dropna(subset=["connector_property"]).iterrows():
        addr = row["connector_property"].strip().lower()
        if addr not in deal_by_address:
            deal_by_address[addr] = {"date": row["agreement_date"], "profit": row["projected_profit"]}
    for _, row in seller_leads_raw[["property_address", "agreement_date", "project_profit"]].dropna(subset=["property_address"]).iterrows():
        addr = row["property_address"].strip().lower()
        if addr not in deal_by_address:
            deal_by_address[addr] = {"date": row["agreement_date"], "profit": row["project_profit"]}
    # Hot Sheet properties excluding Fell Out of Contract
    eligible_hs = set(
        hot_sheet_raw.loc[hot_sheet_raw["status"] != "Fell Out of Contract", "property_address"]
        .dropna().str.strip().str.lower()
    )
    ytd_profits = [
        float(deal_by_address[addr]["profit"])
        for addr in eligible_hs
        if addr in deal_by_address
        and pd.notna(deal_by_address[addr]["date"])
        and pd.Timestamp(deal_by_address[addr]["date"]).year == current_year
        and deal_by_address[addr]["profit"] is not None
        and pd.notna(deal_by_address[addr]["profit"])
    ]
    ytd_profit_per_deal = sum(ytd_profits) / len(ytd_profits) if ytd_profits else 0

    valid_offer_ask = leads[(leads["offer_amount"].notna()) & (leads["asking_price"].notna()) & (leads["asking_price"] > 0)]
    offer_to_ask = (valid_offer_ask["offer_amount"] / valid_offer_ask["asking_price"]).mean() * 100 if not valid_offer_ask.empty else 0

    valid_purch_ask = leads[(leads["purchase_price"].notna()) & (leads["asking_price"].notna()) & (leads["asking_price"] > 0)]
    purchase_to_ask = (valid_purch_ask["purchase_price"] / valid_purch_ask["asking_price"]).mean() * 100 if not valid_purch_ask.empty else 0

    qtr_leads = leads[(pd.to_datetime(leads["created_on"]).dt.date >= qtr_start) & (pd.to_datetime(leads["created_on"]).dt.date <= qtr_end)]
    qtr_purchases = qtr_leads[qtr_leads["purchase_price"].notna()]
    lead_conversion = (len(qtr_purchases) / len(qtr_leads) * 100) if len(qtr_leads) > 0 else 0

    # ── KPI cards row ──
    kc1, kc2, kc3, kc4, kc5 = st.columns(5)
    for col, label, value in [
        (kc1, "Future Projected Profit", fmt_k(future_profit)),
        (kc2, "Projected Year Profit/Deal", fmt_k(ytd_profit_per_deal if pd.notna(ytd_profit_per_deal) else 0)),
        (kc3, "Offer to Ask", f"{offer_to_ask:.1f}%"),
        (kc4, "Purchase to Ask", f"{purchase_to_ask:.1f}%"),
        (kc5, "Lead Conversion (Qtr)", f"{lead_conversion:.1f}%"),
    ]:
        col.markdown(
            f'<div style="background:#e8eaef;border-radius:8px;padding:12px;text-align:center;">'
            f'<div style="font-size:0.75rem;color:#666;">{label}</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:#1a1a2e;">{value}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 1 ──
    r1c1, r1c2 = st.columns(2)

    # 1) Properties Walked By Week
    with r1c1:
        st.markdown('<p class="chart-title">Properties Walked By Week</p>', unsafe_allow_html=True)
        walked = leads[leads["date_walked"].notna()].copy()
        if not walked.empty:
            walked["week"] = pd.to_datetime(walked["date_walked"]).dt.to_period("W-SUN").apply(lambda p: p.start_time)
            walked["property_walker"] = walked["property_walker"].fillna("Unknown")
            wk_data = walked.groupby(["week", "property_walker"]).size().reset_index(name="count")
            fig = go.Figure()
            legend_items = []
            for person in sorted(wk_data["property_walker"].unique()):
                color = PERSON_COLORS.get(person, "#999")
                legend_items.append((person, color))
                pdf = wk_data[wk_data["property_walker"] == person]
                fig.add_trace(go.Bar(
                    x=pdf["week"], y=pdf["count"], name=person,
                    marker=beveled_marker(color),
                    hovertemplate="<b>" + person + "</b><br>Week of %{x|%b %d, %Y}<br>Count: <b>%{y}</b><extra></extra>",
                ))
            fig.add_hline(y=7, line_dash="dash", line_color="#7a9a6d", line_width=2,
                          annotation_text="Weekly Goal", annotation_position="top left",
                          annotation_font=dict(color="#7a9a6d", size=11))
            fig.update_layout(**CHART_BG, barmode="group", height=340, bargap=0.15,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickformat="%b %d", gridcolor="#f0f0f0", zeroline=False,
                           tickangle=-30, tickfont=dict(size=10)),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=legend_items)

    # 2) Future Profit by AM
    with r1c2:
        st.markdown('<p class="chart-title">Future Profit by AM</p>', unsafe_allow_html=True)
        future = leads[leads["purchase_price"].isna()].copy()
        if not future.empty:
            future["relationship_manager"] = future["relationship_manager"].fillna("Unknown")
            fp = future.groupby("relationship_manager")["projected_profit"].sum().reset_index()
            fp = fp.sort_values("projected_profit", ascending=False)
            colors = [PERSON_COLORS.get(p, "#999") for p in fp["relationship_manager"]]
            fig = go.Figure(go.Bar(
                x=fp["relationship_manager"], y=fp["projected_profit"], name="Future Profit",
                marker=beveled_marker(colors),
                text=[fmt_k(v) for v in fp["projected_profit"]], textposition="outside",
                textfont=dict(size=11),
                hovertemplate="<b>%{x}</b><br>Projected Profit: <b>%{text}</b><extra></extra>",
            ))
            fig.add_hline(y=100000, line_dash="dash", line_color="#7a9a6d", line_width=2,
                          annotation_text="Profit Goal (100,000)", annotation_position="top left",
                          annotation_font=dict(color="#7a9a6d", size=11))
            fig.update_layout(**CHART_BG, height=340, showlegend=False,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickangle=-20, tickfont=dict(size=11), automargin=True),
                margin=dict(l=10, r=10, t=5, b=60))
            render_chart(fig, height=380)

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 2 ──
    r2c1, r2c2 = st.columns(2)

    # 3) Year to Date Properties Walked
    with r2c1:
        st.markdown('<p class="chart-title">Year to Date Properties Walked</p>', unsafe_allow_html=True)
        ytd_walked = leads[(leads["date_walked"].notna()) & (pd.to_datetime(leads["date_walked"]).dt.year == current_year)].copy()
        if not ytd_walked.empty:
            ytd_walked["property_walker"] = ytd_walked["property_walker"].fillna("Unknown")
            ytd_wk = ytd_walked.groupby("property_walker").size().reset_index(name="count").sort_values("count", ascending=False)
            colors = [PERSON_COLORS.get(p, "#999") for p in ytd_wk["property_walker"]]
            fig = go.Figure(go.Bar(
                x=ytd_wk["property_walker"], y=ytd_wk["count"],
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

    # 4) Avg Asking vs Offer vs Purchase (Past Qtr)
    with r2c2:
        st.markdown('<p class="chart-title">Avg Asking vs Offer vs Purchase (Past Qtr)</p>', unsafe_allow_html=True)
        qtr_data = leads[(pd.to_datetime(leads["created_on"]).dt.date >= qtr_start) & (pd.to_datetime(leads["created_on"]).dt.date <= qtr_end)].copy()
        avg_asking = qtr_data["asking_price"].mean() if not qtr_data.empty and qtr_data["asking_price"].notna().any() else 0
        avg_offer = qtr_data["offer_amount"].mean() if not qtr_data.empty and qtr_data["offer_amount"].notna().any() else 0
        avg_purchase = qtr_data["purchase_price"].mean() if not qtr_data.empty and qtr_data["purchase_price"].notna().any() else 0
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
                width=0.4,
            ))
        fig.update_layout(**CHART_BG, height=340, showlegend=False,
            yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
            xaxis=dict(title="", tickfont=dict(size=11)),
            margin=dict(l=10, r=10, t=5, b=30))
        render_chart(fig, height=380, legend=[
            ("Avg Asking", "#a0926c"), ("Avg Offer", "#c2703e"), ("Avg Purchase", "#7a9a6d")
        ])

    st.markdown("<div style='margin: 0.5rem 0;'></div>", unsafe_allow_html=True)

    # ── Row 3 ──
    r3c1, r3c2 = st.columns(2)

    # 5) Offers By Week
    with r3c1:
        st.markdown('<p class="chart-title">Offers By Week</p>', unsafe_allow_html=True)
        offers = leads[leads["offer_amount"].notna()].copy()
        if not offers.empty:
            offers["week"] = pd.to_datetime(offers["agreement_date"].fillna(offers["created_on"])).dt.to_period("W-SUN").apply(lambda p: p.start_time)
            offers["relationship_manager"] = offers["relationship_manager"].fillna("Unknown")
            off_data = offers.groupby(["week", "relationship_manager"]).size().reset_index(name="count")
            fig = go.Figure()
            legend_items = []
            for person in sorted(off_data["relationship_manager"].unique()):
                color = PERSON_COLORS.get(person, "#999")
                legend_items.append((person, color))
                pdf = off_data[off_data["relationship_manager"] == person]
                fig.add_trace(go.Bar(
                    x=pdf["week"], y=pdf["count"], name=person,
                    marker=beveled_marker(color),
                    hovertemplate="<b>" + person + "</b><br>Week of %{x|%b %d, %Y}<br>Offers: <b>%{y}</b><extra></extra>",
                ))
            fig.update_layout(**CHART_BG, barmode="group", height=340, bargap=0.15,
                yaxis=dict(gridcolor="#f0f0f0", title="", zeroline=False, automargin=True),
                xaxis=dict(title="", tickformat="%b %d", gridcolor="#f0f0f0", zeroline=False,
                           tickangle=-30, tickfont=dict(size=10)),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=legend_items)

    # 6) Purchase vs Leads
    with r3c2:
        st.markdown('<p class="chart-title">Purchase vs Leads</p>', unsafe_allow_html=True)
        pvl = leads.copy()
        if not pvl.empty:
            pvl["week"] = pd.to_datetime(pvl["created_on"]).dt.to_period("W-SUN").apply(lambda p: p.start_time)
            total_leads = pvl.groupby("week").size().reset_index(name="leads")
            purchases = pvl[pvl["purchase_price"].notna()].groupby("week").size().reset_index(name="purchases")
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
                           tickangle=-30, tickfont=dict(size=10)),
                showlegend=False,
                margin=dict(l=10, r=10, t=5, b=50))
            render_chart(fig, height=380, legend=[
                ("Total Leads", "#a0926c"), ("Purchases", "#7a9a6d")
            ])

