"""
Cloud-only entry point: fetch forecast data, process it, and generate
the HTML report.  No Telegram sending — designed for CI / GitHub Actions.
"""
from config import CONFIG
from forecast_parser import process_forecasts
from fetch import download_latest_forecast_zip
from html_report import generate_html_report
import os

_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wind Forecast Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f0f4f8; display: flex;
           justify-content: center; align-items: center; min-height: 100vh; margin: 0; }}
    .card {{ background: #fff; border-radius: 8px; padding: 40px; text-align: center;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1); max-width: 400px; }}
    h1 {{ color: #2c5f8a; font-size: 1.5em; }}
    p  {{ color: #666; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>&#127940; Wind Forecast</h1>
    <p>{message}</p>
    <p>Check back later — the report updates every 6 hours.</p>
  </div>
</body>
</html>"""


def write_fallback(message):
    os.makedirs("output", exist_ok=True)
    with open(CONFIG["HTML_REPORT"], "w", encoding="utf-8") as f:
        f.write(_FALLBACK_HTML.format(message=message))
    print(f"✅ Fallback report saved to {CONFIG['HTML_REPORT']}")


def main():
    # Step 1: download forecast data
    try:
        download_latest_forecast_zip(CONFIG)
    except Exception as e:
        print(f"❌ Failed to download forecast data: {e}")
        write_fallback("Forecast data is temporarily unavailable.")
        return

    # Step 2: process forecast CSVs
    try:
        summary_df = process_forecasts(CONFIG)
    except Exception as e:
        print(f"❌ Failed to process forecasts: {e}")
        write_fallback("Error processing forecast data.")
        return

    os.makedirs("output", exist_ok=True)

    if summary_df.empty:
        print("No forecasts found with strong wind.")
        write_fallback("No sites with sufficient wind forecasted for today.")
        return

    summary_df.to_csv(CONFIG["CSV_SUMMARY"], index=False)
    generate_html_report(summary_df, CONFIG, CONFIG["HTML_REPORT"])


if __name__ == "__main__":
    main()
