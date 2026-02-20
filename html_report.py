import os
import re
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
        "<th>Wind Window</th>"
        "<th>Avg Wind (kn)</th>"
        "<th>Direction</th>"
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

        if site in chart_sites:
            anchor = _site_anchor_id(site)
            site_cell = f'<a href="#{anchor}" class="site-link">{site}</a>'
        else:
            site_cell = site

        rows.append(
            f'<tr class="{row_class}">'
            f"<td>{site_cell}</td>"
            f"<td>{row['Window']}</td>"
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

    # Build per-site chart HTML fragments
    chart_fragments = []  # list of (site_name, html_fragment)
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
        chart_fragments.append((site, fragment))
        include_js = False  # subsequent charts reuse the already-loaded plotly.js

    chart_sites = {site for site, _ in chart_fragments}

    # Build interactive summary table
    table_html = _build_summary_table(df_summary, chart_sites)

    # Build charts section with anchor IDs and back-to-top links
    chart_divs = []
    for site, frag in chart_fragments:
        anchor = _site_anchor_id(site)
        chart_divs.append(
            f'<div class="chart-wrapper" id="{anchor}">'
            f"{frag}"
            f'<div class="back-to-top-link"><a href="#summary">&#8593; Back to summary</a></div>'
            f"</div>"
        )
    charts_section = "\n".join(chart_divs)

    no_charts_msg = (
        ""
        if chart_fragments
        else "<p>No site data available to display.</p>"
    )

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
      padding: 16px;
      background: #f0f4f8;
      color: #222;
    }}
    h1 {{
      text-align: center;
      font-size: 1.6em;
      margin: 0 0 28px;
    }}
    h2 {{
      font-size: 1.1em;
      color: #2c5f8a;
      margin: 28px 0 10px;
      padding-bottom: 4px;
      border-bottom: 2px solid #2c5f8a;
    }}

    /* ── Summary Table ── */
    .summary-table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      box-shadow: 0 1px 6px rgba(0,0,0,0.1);
      border-radius: 6px;
      overflow: hidden;
      margin-bottom: 28px;
    }}
    .summary-table th {{
      background: #2c5f8a;
      color: #fff;
      padding: 10px 14px;
      text-align: left;
      font-size: 0.9em;
      white-space: nowrap;
    }}
    .summary-table td {{
      padding: 8px 14px;
      border-bottom: 1px solid #eee;
      font-size: 0.9em;
    }}
    .summary-table tr:last-child td {{ border-bottom: none; }}
    .summary-table tr:hover td {{ background: #eef4fb; cursor: default; }}

    /* Clickable site link */
    .site-link {{
      color: #2c5f8a;
      font-weight: 600;
      text-decoration: none;
      border-bottom: 1px dashed #2c5f8a;
      transition: color 0.2s, border-color 0.2s;
    }}
    .site-link:hover {{
      color: #1a3d5c;
      border-bottom-style: solid;
    }}

    /* Wind speed row colors */
    .wind-strong td {{ background: #fff3cd; }}
    .wind-strong:hover td {{ background: #ffe8a0 !important; }}
    .wind-moderate td {{ background: #d4edda; }}
    .wind-moderate:hover td {{ background: #b8dfc5 !important; }}
    .wind-light td {{ background: #fff; }}

    /* Wind speed badge */
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 0.85em;
    }}
    .badge-strong  {{ background: #f0ad4e; color: #5a3a00; }}
    .badge-moderate {{ background: #5cb85c; color: #fff; }}
    .badge-light   {{ background: #d9d9d9; color: #555; }}

    /* ── Chart Wrappers ── */
    .chart-wrapper {{
      background: #fff;
      border-radius: 6px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.1);
      margin-bottom: 20px;
      padding: 12px 12px 4px;
      overflow: hidden;
      border: 2px solid transparent;
      transition: border-color 0.3s;
    }}

    /* Highlight animation when navigated to via anchor */
    @keyframes highlight-chart {{
      0%   {{ border-color: #2c5f8a; box-shadow: 0 0 0 4px rgba(44,95,138,0.25); }}
      70%  {{ border-color: #2c5f8a; box-shadow: 0 0 0 4px rgba(44,95,138,0.1); }}
      100% {{ border-color: transparent; box-shadow: 0 1px 6px rgba(0,0,0,0.1); }}
    }}
    .chart-wrapper:target {{
      animation: highlight-chart 1.8s ease forwards;
    }}

    /* Back-to-summary link inside each chart */
    .back-to-top-link {{
      text-align: right;
      padding: 4px 6px 6px;
    }}
    .back-to-top-link a {{
      font-size: 0.8em;
      color: #888;
      text-decoration: none;
    }}
    .back-to-top-link a:hover {{ color: #2c5f8a; }}

    /* ── Floating back-to-top button ── */
    #btn-top {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: #2c5f8a;
      color: #fff;
      font-size: 1.3em;
      border: none;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(0,0,0,0.25);
      display: none;
      align-items: center;
      justify-content: center;
      transition: background 0.2s, transform 0.2s;
      z-index: 999;
    }}
    #btn-top:hover {{ background: #1a3d5c; transform: scale(1.1); }}

    @media (max-width: 600px) {{
      body {{ padding: 8px; }}
      h1 {{ font-size: 1.2em; }}
    }}
  </style>
</head>
<body>
  <h1>&#127940; Wind Forecast Report</h1>

  <h2 id="summary">Summary</h2>
  {table_html}

  <h2>Site Charts</h2>
  {no_charts_msg}
  {charts_section}

  <!-- Floating back-to-top button -->
  <button id="btn-top" title="Back to top">&#8679;</button>

  <script>
    // Show/hide floating back-to-top button
    const btnTop = document.getElementById('btn-top');
    window.addEventListener('scroll', () => {{
      btnTop.style.display = window.scrollY > 300 ? 'flex' : 'none';
    }});
    btnTop.addEventListener('click', () => {{
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }});

    // Add smooth offset scroll for anchor links (accounts for any sticky header)
    document.querySelectorAll('a[href^="#"]').forEach(link => {{
      link.addEventListener('click', e => {{
        const target = document.querySelector(link.getAttribute('href'));
        if (!target) return;
        e.preventDefault();
        const top = target.getBoundingClientRect().top + window.scrollY - 12;
        window.scrollTo({{ top, behavior: 'smooth' }});
        // Trigger :target-like highlight manually (re-add class trick)
        target.classList.remove('chart-wrapper');
        void target.offsetWidth; // reflow
        target.classList.add('chart-wrapper');
      }});
    }});
  </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML report saved to {output_path}")
    return output_path
