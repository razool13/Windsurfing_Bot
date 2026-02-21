import os
import re
import json
from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

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
        "<th>Avg Wind</th>"
        "<th>Dir</th>"
        "</tr></thead>"
    )
    rows = []
    for _, row in df_summary.iterrows():
        site = row["Site"]
        wind = row["Avg Wind (knots)"]
        arrow = direction_to_arrow(row["Dir"])

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

    # Build per-site chart data (both HTML and stats)
    chart_data = {}  # dict: site_name -> {html, stats}
    include_js = True  # embed plotly.js only once (in the first chart)
    for _, row in df_summary.iterrows():
        site = row["Site"]
        if site not in site_data:
            continue
        fig = _make_site_figure(site_data[site], site)
        fragment = pio.to_html(
            fig,
            include_plotlyjs=include_js,
            full_html=False,
            config={"responsive": True},
        )
        stats = _calculate_site_stats(site_data[site])
        chart_data[site] = {
            "html": fragment,
            "stats": stats,
        }
        include_js = False  # subsequent charts reuse the already-loaded plotly.js

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
      padding: 16px;
      text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .dark-mode .header {{
      background: linear-gradient(135deg, #0d2d47 0%, #000 100%);
    }}
    h1 {{
      font-size: 1.6em;
      margin: 0;
      flex: 1;
      text-align: center;
    }}
    .header-buttons {{
      display: flex;
      gap: 8px;
    }}
    .btn {{
      padding: 8px 16px;
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

    /* ── Container Layout (flex) ── */
    .container {{
      display: flex;
      gap: 0;
      min-height: calc(100vh - 70px);
    }}

    /* ── Left Sidebar (Table) ── */
    .sidebar {{
      flex: 0 0 350px;
      background: #fff;
      border-right: 1px solid #ddd;
      overflow-y: auto;
      padding: 16px;
      box-shadow: 2px 0 4px rgba(0,0,0,0.05);
    }}
    .dark-mode .sidebar {{
      background: #2a2a2a;
      border-right-color: #444;
    }}
    .sidebar-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}
    .sidebar-header h2 {{
      margin: 0;
      font-size: 1.1em;
      color: #2c5f8a;
    }}
    .dark-mode .sidebar-header h2 {{
      color: #5eb3e6;
    }}
    .search-box {{
      width: 100%;
      padding: 8px;
      border: 1px solid #ddd;
      border-radius: 4px;
      margin-bottom: 12px;
      font-size: 0.9em;
    }}
    .dark-mode .search-box {{
      background: #3a3a3a;
      border-color: #555;
      color: #e0e0e0;
    }}

    /* ── Summary Table ── */
    .summary-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85em;
    }}
    .summary-table th {{
      background: #2c5f8a;
      color: #fff;
      padding: 8px 8px;
      text-align: left;
      font-size: 0.8em;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .dark-mode .summary-table th {{
      background: #0d2d47;
    }}
    .summary-table td {{
      padding: 6px 8px;
      border-bottom: 1px solid #eee;
      cursor: pointer;
      transition: background 0.15s;
    }}
    .dark-mode .summary-table td {{
      border-bottom-color: #444;
    }}
    .summary-table tr:last-child td {{ border-bottom: none; }}
    .summary-table tr.table-row:hover td {{ background: #eef4fb; }}
    .dark-mode .summary-table tr.table-row:hover td {{ background: #3a4a5a; }}

    /* Selected row in table */
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

    /* Wind speed badge */
    .badge {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 0.75em;
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
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.1);
      border-left: 4px solid #2c5f8a;
    }}
    .dark-mode .info-card {{
      background: #2a2a2a;
      border-left-color: #5eb3e6;
    }}
    .info-card-title {{
      font-size: 1.2em;
      font-weight: 600;
      margin: 0 0 12px;
      color: #2c5f8a;
    }}
    .dark-mode .info-card-title {{
      color: #5eb3e6;
    }}
    .info-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      font-size: 0.9em;
    }}
    .info-item {{
      display: flex;
      justify-content: space-between;
      padding: 6px 0;
      border-bottom: 1px solid #eee;
    }}
    .dark-mode .info-item {{
      border-bottom-color: #444;
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
      padding: 12px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.1);
      overflow: hidden;
    }}
    .dark-mode .chart-container {{
      background: #2a2a2a;
    }}

    /* ── Empty State ── */
    .empty-state {{
      text-align: center;
      padding: 60px 20px;
      color: #999;
    }}
    .dark-mode .empty-state {{
      color: #666;
    }}

    /* ── Responsive Design ── */
    @media (max-width: 1024px) {{
      .sidebar {{
        flex: 0 0 300px;
      }}
      .info-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 768px) {{
      .container {{
        flex-direction: column;
      }}
      .sidebar {{
        flex: 0 0 auto;
        max-height: 300px;
        border-right: none;
        border-bottom: 1px solid #ddd;
      }}
      .dark-mode .sidebar {{
        border-bottom-color: #444;
      }}
      .summary-table {{
        font-size: 0.75em;
      }}
      .summary-table th, .summary-table td {{
        padding: 4px 4px;
      }}
      h1 {{
        font-size: 1.2em;
      }}
    }}
  </style>
</head>
<body>
  <!-- Header -->
  <div class="header">
    <h1>&#127940; Wind Forecast</h1>
    <div class="header-buttons">
      <button class="btn" id="toggle-dark" title="Toggle dark mode">🌙</button>
    </div>
  </div>

  <!-- Container -->
  <div class="container">
    <!-- Left Sidebar -->
    <div class="sidebar">
      <div class="sidebar-header">
        <h2>Sites</h2>
      </div>
      <input type="text" class="search-box" id="search-box" placeholder="Search sites...">
      {table_html}
    </div>

    <!-- Right Main Content -->
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
    // Chart data embedded
    const chartData = {chart_data_json};

    // Dark mode toggle
    const toggleDark = document.getElementById('toggle-dark');
    const isDarkMode = localStorage.getItem('darkMode') === 'true';
    if (isDarkMode) document.body.classList.add('dark-mode');

    toggleDark.addEventListener('click', () => {{
      document.body.classList.toggle('dark-mode');
      localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
    }});

    // Search functionality
    const searchBox = document.getElementById('search-box');
    searchBox.addEventListener('input', (e) => {{
      const query = e.target.value.toLowerCase();
      document.querySelectorAll('.summary-table tbody tr.table-row').forEach(row => {{
        const siteName = row.textContent.toLowerCase();
        row.style.display = siteName.includes(query) ? '' : 'none';
      }});
    }});

    // Click handlers for table rows
    document.querySelectorAll('.summary-table tbody tr.table-row').forEach((row, idx) => {{
      row.addEventListener('click', () => {{
        selectChart(idx, row.cells[0].textContent.trim());
      }});
    }});

    function selectChart(index, siteName) {{
      // Update active row
      document.querySelectorAll('.summary-table tbody tr.table-row').forEach(r => r.classList.remove('active'));
      document.querySelectorAll('.summary-table tbody tr.table-row')[index].classList.add('active');

      // Update chart
      const chart = chartData[siteName];
      if (!chart) return;

      document.getElementById('chart-container').innerHTML = chart.html;

      // Update info card
      const info = chart.stats;
      document.getElementById('info-card').style.display = 'block';
      document.getElementById('info-title').textContent = siteName;
      document.getElementById('info-grid').innerHTML = `
        <div class="info-item">
          <span class="label">Avg Wind:</span>
          <span class="value">${{info.avg_wind.toFixed(1)}} kn</span>
        </div>
        <div class="info-item">
          <span class="label">Max Wind:</span>
          <span class="value">${{info.max_wind.toFixed(1)}} kn</span>
        </div>
        <div class="info-item">
          <span class="label">Max Gust:</span>
          <span class="value">${{info.max_gust.toFixed(1)}} kn</span>
        </div>
        <div class="info-item">
          <span class="label">Direction:</span>
          <span class="value">${{info.direction}}°</span>
        </div>
      `;

      // Re-attach Plotly listeners if needed
      if (window.Plotly) {{
        setTimeout(() => window.Plotly.Plots.resize('plotly-div'), 100);
      }}
    }}

    // Auto-select first site on load
    const firstRow = document.querySelector('.summary-table tbody tr.table-row');
    if (firstRow) {{
      firstRow.click();
    }}
  </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML report saved to {output_path}")
    return output_path
