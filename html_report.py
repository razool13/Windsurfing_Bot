import os
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
    chart_fragments = []
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
        chart_fragments.append(fragment)
        include_js = False  # subsequent charts reuse the already-loaded plotly.js

    # Build summary table
    df_table = df_summary[["Site", "Window", "Avg Wind (knots)", "Dir"]].copy()
    df_table["Dir"] = df_table["Dir"].apply(direction_to_arrow)
    df_table.columns = ["Site", "Wind Window", "Avg Wind (kn)", "Direction"]
    table_html = df_table.to_html(
        index=False,
        classes="summary-table",
        border=0,
        escape=False,
    )

    charts_section = "\n".join(
        f'<div class="chart-wrapper">{frag}</div>' for frag in chart_fragments
    )

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
    .summary-table tr:hover td {{ background: #eef4fb; }}
    .chart-wrapper {{
      background: #fff;
      border-radius: 6px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.1);
      margin-bottom: 20px;
      padding: 12px 12px 4px;
      overflow: hidden;
    }}
    @media (max-width: 600px) {{
      body {{ padding: 8px; }}
      h1 {{ font-size: 1.2em; }}
    }}
  </style>
</head>
<body>
  <h1>&#127940; Wind Forecast Report</h1>

  <h2>Summary</h2>
  {table_html}

  <h2>Site Charts</h2>
  {no_charts_msg}
  {charts_section}
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML report saved to {output_path}")
    return output_path
