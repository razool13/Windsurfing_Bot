import os
import re
import json
from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from forecast_parser import parse_datetime
from plot_utils import direction_to_arrow


def _load_site_data(config, sites):
    """Re-read CSV files for the given set of site names."""
    site_data = {}
    for root, _, files in os.walk(config["EXTRACT_DIR"]):
        for file in files:
            if not file.endswith(".csv"):
                continue
            site = os.path.splitext(file)[0]
            if site not in sites:
                continue
            path = os.path.join(root, file)
            try:
                df = pd.read_csv(
                    path,
                    skiprows=2,
                    names=["datetime_raw", "wind_speed", "wind_dir", "wind_gust"],
                )
                df["datetime"] = df["datetime_raw"].apply(parse_datetime)
                df = df.dropna(subset=["datetime"])
                df[["wind_speed", "wind_dir", "wind_gust"]] = df[
                    ["wind_speed", "wind_dir", "wind_gust"]
                ].apply(pd.to_numeric, errors="coerce")
                df = df.dropna()
                site_data[site] = df.sort_values("datetime").reset_index(drop=True)
            except Exception as e:
                print(f"⚠️  Could not load {site}: {e}")
    return site_data


def _wind_assessment(df):
    forecast_start_date = df["datetime"].min().date()
    tomorrow = forecast_start_date + timedelta(days=1)
    df_tomorrow = df[df["datetime"].dt.date == tomorrow]
    strong = df_tomorrow[df_tomorrow["wind_speed"] > 20]
    moderate = df_tomorrow[
        (df_tomorrow["wind_speed"] > 15) & (df_tomorrow["wind_speed"] <= 20)
    ]
    if len(strong) >= 2:
        return "Good for windsurfing tomorrow!"
    if len(moderate) >= 2:
        return "Good for WinG tomorrow!"
    return "Not enough wind for good windsurfing tomorrow."


def _site_anchor_id(site_name):
    """Convert site name to a valid HTML anchor ID."""
    return "chart-" + re.sub(r"[^\w-]", "-", site_name).strip("-").lower()


def _calculate_site_stats(df):
    """Calculate statistics for a site."""
    return {
        "avg_wind": float(df["wind_speed"].mean()),
        "max_wind": float(df["wind_speed"].max()),
        "max_gust": float(df["wind_gust"].max()),
        "direction": float(df["wind_dir"].mean()),
    }


def _make_site_figure(df, site_name):
    """Return a Plotly Figure for one site's wind data."""
    times = df["datetime"]
    speed = df["wind_speed"]
    gust = df["wind_gust"]
    direction = df["wind_dir"]
    arrows = direction.apply(direction_to_arrow)
    msg = _wind_assessment(df)

    fig = go.Figure()

    # Wind speed — colored scatter + gray line
    fig.add_trace(
        go.Scatter(
            x=times,
            y=speed,
            mode="lines+markers",
            name="Wind Speed",
            marker=dict(
                color=speed,
                colorscale="Plasma",
                size=8,
                showscale=True,
                colorbar=dict(title="knots", len=0.6, thickness=12),
            ),
            line=dict(color="gray", width=1.5),
            customdata=np.stack([gust, direction, arrows], axis=-1),
            hovertemplate=(
                "<b>%{x|%d-%m %H:%M}</b><br>"
                "Speed: %{y:.1f} kn<br>"
                "Gust: %{customdata[0]:.1f} kn<br>"
                "Direction: %{customdata[1]:.0f}° %{customdata[2]}"
                "<extra></extra>"
            ),
        )
    )

    # Wind gust dashed red line
    fig.add_trace(
        go.Scatter(
            x=times,
            y=gust,
            mode="lines",
            name="Wind Gust",
            line=dict(color="red", dash="dash", width=1.5),
            hovertemplate="Gust: %{y:.1f} kn<extra></extra>",
        )
    )

    # Wind direction arrow annotations above each point
    for i in range(len(df)):
        fig.add_annotation(
            x=times.iloc[i],
            y=speed.iloc[i],
            text=str(arrows.iloc[i]),
            showarrow=False,
            yshift=14,
            font=dict(size=10),
        )

    fig.update_layout(
        title=dict(text=f"<b>{site_name}</b> | {msg}", font=dict(size=14)),
        xaxis_title="Time",
        yaxis_title="Wind Speed (knots)",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=60, t=70, b=80),
        height=370,
    )
    fig.update_xaxes(tickformat="%d-%m %H:%M", tickangle=-45, tickfont=dict(size=9))
    return fig


def _build_summary_table(df_summary, chart_sites):
    """Build interactive HTML table with clickable site links and wind-speed color coding."""
    header = (
        "<thead><tr>"
        "<th>Site</th>"
        "<th>Window</th>"
        "<th>Duration</th>"
        "<th>Avg Wind</th>"
        "<th>Dir</th>"
        "</tr></thead>"
    )
    rows = []
    for _, row in df_summary.iterrows():
        site = row["Site"]
        wind = row["Avg Wind (knots)"]
        arrow = direction_to_arrow(row["Dir"])
        window = row.get("Window", "")
        duration = row.get("Duration", 0)
        duration_str = f"{duration:.0f}h" if duration else ""

        if wind > 20:
            row_class = "wind-strong"
            badge = f'<span class="badge badge-strong">{wind:.1f}</span>'
        elif wind > 15:
            row_class = "wind-moderate"
            badge = f'<span class="badge badge-moderate">{wind:.1f}</span>'
        else:
            row_class = "wind-light"
            badge = f'<span class="badge badge-light">{wind:.1f}</span>'

        rows.append(
            f'<tr class="{row_class} table-row">'
            f"<td><strong>{site}</strong></td>"
            f"<td>{window}</td>"
            f"<td>{duration_str}</td>"
            f"<td>{badge}</td>"
            f"<td>{arrow}</td>"
            f"</tr>"
        )

    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return f'<table class="summary-table">{header}{tbody}</table>'


def generate_html_report(df_summary, config, output_path):
    """
    Generate a self-contained HTML report with interactive Plotly charts.
    The output HTML file can be opened in any browser on any platform / OS,
    with no external dependencies required.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    sites = set(df_summary["Site"].tolist())
    site_data = _load_site_data(config, sites)

    # Build per-site chart data (figure JSON and stats)
    chart_data = {}  # dict: site_name -> {figure, stats}
    for _, row in df_summary.iterrows():
        site = row["Site"]
        if site not in site_data:
            continue
        fig = _make_site_figure(site_data[site], site)
        fig_json = json.loads(fig.to_json())
        stats = _calculate_site_stats(site_data[site])
        chart_data[site] = {
            "figure": fig_json,
            "stats": stats,
        }

    chart_sites = set(chart_data.keys())

    # Build interactive summary table
    table_html = _build_summary_table(df_summary, chart_sites)

    # Convert chart data to JavaScript-safe JSON
    chart_data_json = json.dumps(chart_data)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wind Forecast Report</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    html {{ scroll-behavior: smooth; }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: Arial, Helvetica, sans-serif;
      margin: 0;
      padding: 0;
      background: #f0f4f8;
      color: #222;
      transition: background 0.3s, color 0.3s;
    }}
    body.dark-mode {{
      background: #1a1a1a;
      color: #e0e0e0;
    }}

    /* ── Header ── */
    .header {{
      background: linear-gradient(135deg, #2c5f8a 0%, #1a3d5c 100%);
      color: #fff;
      padding: 12px 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .dark-mode .header {{
      background: linear-gradient(135deg, #0d2d47 0%, #000 100%);
    }}
    h1 {{
      font-size: 1.3em;
      margin: 0;
      flex: 1;
      text-align: center;
    }}
    .btn {{
      padding: 6px 14px;
      border: none;
      border-radius: 4px;
      background: rgba(255,255,255,0.2);
      color: #fff;
      cursor: pointer;
      font-size: 0.9em;
      transition: background 0.2s;
    }}
    .btn:hover {{
      background: rgba(255,255,255,0.3);
    }}

    /* ── Container Layout (sidebar + main) ── */
    .container {{
      display: flex;
      height: calc(100vh - 52px);
      overflow: hidden;
    }}

    /* ── Left Sidebar (Table) ── */
    .sidebar {{
      flex: 0 0 420px;
      background: #fff;
      border-right: 1px solid #ddd;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .dark-mode .sidebar {{
      background: #2a2a2a;
      border-right-color: #444;
    }}
    .sidebar-header {{
      padding: 12px 14px 8px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex-shrink: 0;
    }}
    .sidebar-title-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .sidebar-title-row h2 {{
      margin: 0;
      font-size: 1em;
      color: #2c5f8a;
    }}
    .dark-mode .sidebar-title-row h2 {{
      color: #5eb3e6;
    }}
    .search-box {{
      width: 100%;
      padding: 6px 10px;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-size: 0.85em;
    }}
    .dark-mode .search-box {{
      background: #3a3a3a;
      border-color: #555;
      color: #e0e0e0;
    }}
    .table-scroll {{
      flex: 1;
      overflow-y: auto;
      overflow-x: hidden;
    }}

    /* ── Summary Table ── */
    .summary-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.8em;
    }}
    .summary-table th {{
      background: #2c5f8a;
      color: #fff;
      padding: 7px 6px;
      text-align: left;
      font-size: 0.8em;
      white-space: nowrap;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .dark-mode .summary-table th {{
      background: #0d2d47;
    }}
    .summary-table td {{
      padding: 6px 6px;
      border-bottom: 1px solid #eee;
      cursor: pointer;
      transition: background 0.15s;
      white-space: nowrap;
    }}
    .dark-mode .summary-table td {{
      border-bottom-color: #444;
    }}
    .summary-table tr:last-child td {{ border-bottom: none; }}
    .summary-table tr.table-row:hover td {{ background: #eef4fb; }}
    .dark-mode .summary-table tr.table-row:hover td {{ background: #3a4a5a; }}

    .summary-table tr.table-row.active td {{
      background: #d4e8f7;
      font-weight: 600;
    }}
    .dark-mode .summary-table tr.table-row.active td {{
      background: #2a5a8a;
    }}

    /* Wind speed row colors */
    .wind-strong td {{ background: #fff3cd; }}
    .wind-moderate td {{ background: #d4edda; }}
    .wind-light td {{ background: #f5f5f5; }}
    .dark-mode .wind-strong td {{ background: #5a4a20; }}
    .dark-mode .wind-moderate td {{ background: #2a5a3a; }}
    .dark-mode .wind-light td {{ background: #3a3a3a; }}

    .badge {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 0.8em;
    }}
    .badge-strong  {{ background: #f0ad4e; color: #5a3a00; }}
    .badge-moderate {{ background: #5cb85c; color: #fff; }}
    .badge-light   {{ background: #d9d9d9; color: #555; }}

    /* ── Main Content Area (Right) ── */
    .main-content {{
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      background: #f0f4f8;
    }}
    .dark-mode .main-content {{
      background: #1a1a1a;
    }}

    /* ── Info Card ── */
    .info-card {{
      background: #fff;
      border-radius: 6px;
      padding: 12px 16px;
      margin-bottom: 12px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.1);
      border-left: 4px solid #2c5f8a;
    }}
    .dark-mode .info-card {{
      background: #2a2a2a;
      border-left-color: #5eb3e6;
    }}
    .info-card-title {{
      font-size: 1.1em;
      font-weight: 600;
      margin: 0 0 8px;
      color: #2c5f8a;
    }}
    .dark-mode .info-card-title {{
      color: #5eb3e6;
    }}
    .info-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      font-size: 0.85em;
    }}
    .info-item {{
      display: flex;
      gap: 6px;
    }}
    .info-item .label {{
      color: #666;
      font-weight: 600;
    }}
    .dark-mode .info-item .label {{
      color: #aaa;
    }}
    .info-item .value {{
      color: #2c5f8a;
      font-weight: 700;
    }}
    .dark-mode .info-item .value {{
      color: #5eb3e6;
    }}

    /* ── Chart Container ── */
    .chart-container {{
      background: #fff;
      border-radius: 6px;
      padding: 10px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.1);
      min-height: 380px;
    }}
    .dark-mode .chart-container {{
      background: #2a2a2a;
    }}

    .empty-state {{
      text-align: center;
      padding: 60px 20px;
      color: #999;
    }}
    .dark-mode .empty-state {{
      color: #666;
    }}

    /* ── Responsive Design ── */
    @media (max-width: 900px) {{
      .container {{
        flex-direction: column;
        height: auto;
      }}
      .sidebar {{
        flex: 0 0 auto;
        max-height: 45vh;
        border-right: none;
        border-bottom: 1px solid #ddd;
      }}
      .dark-mode .sidebar {{
        border-bottom-color: #444;
      }}
      .main-content {{
        min-height: 50vh;
      }}
      h1 {{
        font-size: 1.1em;
      }}
    }}
  </style>
</head>
<body>
  <!-- Header -->
  <div class="header">
    <h1>&#127940; Wind Forecast</h1>
    <button class="btn" id="toggle-dark" title="Toggle dark mode">&#127769;</button>
  </div>

  <!-- Container: Sidebar + Main -->
  <div class="container">
    <!-- Left Sidebar (Table) -->
    <div class="sidebar">
      <div class="sidebar-header">
        <div class="sidebar-title-row">
          <h2>Sites</h2>
        </div>
        <input type="text" class="search-box" id="search-box" placeholder="Search sites...">
      </div>
      <div class="table-scroll">
        {table_html}
      </div>
    </div>

    <!-- Right Main Content (Chart) -->
    <div class="main-content">
      <div class="info-card" id="info-card" style="display: none;">
        <div class="info-card-title" id="info-title">Select a site</div>
        <div class="info-grid" id="info-grid"></div>
      </div>
      <div class="chart-container" id="chart-container">
        <div class="empty-state">Select a site from the list to view its forecast</div>
      </div>
    </div>
  </div>

  <script>
    const chartData = {chart_data_json};

    // Dark mode toggle
    const toggleDark = document.getElementById('toggle-dark');
    if (localStorage.getItem('darkMode') === 'true') document.body.classList.add('dark-mode');
    toggleDark.addEventListener('click', () => {{
      document.body.classList.toggle('dark-mode');
      localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
    }});

    // Search
    document.getElementById('search-box').addEventListener('input', (e) => {{
      const query = e.target.value.toLowerCase();
      document.querySelectorAll('.summary-table tbody tr.table-row').forEach(row => {{
        row.style.display = row.textContent.toLowerCase().includes(query) ? '' : 'none';
      }});
    }});

    // Click handlers
    document.querySelectorAll('.summary-table tbody tr.table-row').forEach((row, idx) => {{
      row.addEventListener('click', () => {{
        selectChart(idx, row.cells[0].textContent.trim());
      }});
    }});

    function selectChart(index, siteName) {{
      document.querySelectorAll('.summary-table tbody tr.table-row').forEach(r => r.classList.remove('active'));
      const rows = document.querySelectorAll('.summary-table tbody tr.table-row');
      if (rows[index]) rows[index].classList.add('active');

      const chart = chartData[siteName];
      if (!chart) return;

      // Render chart
      const container = document.getElementById('chart-container');
      container.innerHTML = '<div id="plotly-chart" style="width:100%;"></div>';
      const fig = chart.figure;
      Plotly.newPlot('plotly-chart', fig.data, fig.layout, {{responsive: true}});

      // Update info card
      const info = chart.stats;
      document.getElementById('info-card').style.display = 'block';
      document.getElementById('info-title').textContent = siteName;
      document.getElementById('info-grid').innerHTML =
        '<div class="info-item"><span class="label">Avg Wind:</span><span class="value">' + info.avg_wind.toFixed(1) + ' kn</span></div>' +
        '<div class="info-item"><span class="label">Max Wind:</span><span class="value">' + info.max_wind.toFixed(1) + ' kn</span></div>' +
        '<div class="info-item"><span class="label">Max Gust:</span><span class="value">' + info.max_gust.toFixed(1) + ' kn</span></div>' +
        '<div class="info-item"><span class="label">Direction:</span><span class="value">' + info.direction.toFixed(0) + '\u00b0</span></div>';
    }}

    // Auto-select first site
    const firstRow = document.querySelector('.summary-table tbody tr.table-row');
    if (firstRow) firstRow.click();
  </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML report saved to {output_path}")
    return output_path
