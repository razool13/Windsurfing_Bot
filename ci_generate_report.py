from config import CONFIG
from forecast_parser import process_forecasts
from fetch import download_latest_forecast_zip
from html_report import generate_html_report
import os

_FALLBACK = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Wind Forecast</title></head>
<body style="font-family:Arial;text-align:center;padding:60px">
<h1>Wind Forecast</h1><p>{msg}</p><p>Updates every 6 hours.</p>
</body></html>"""

def write_fallback(msg):
    os.makedirs("output", exist_ok=True)
    with open(CONFIG["HTML_REPORT"], "w", encoding="utf-8") as f:
        f.write(_FALLBACK.format(msg=msg))

def main():
    try:
        download_latest_forecast_zip(CONFIG)
    except Exception as e:
        print(f"Download failed: {e}")
        write_fallback("Forecast data temporarily unavailable.")
        return

    try:
        summary_df = process_forecasts(CONFIG)
    except Exception as e:
        print(f"Processing failed: {e}")
        write_fallback("Error processing forecast data.")
        return

    os.makedirs("output", exist_ok=True)
    if summary_df.empty:
        write_fallback("No sites with sufficient wind today.")
        return

    summary_df.to_csv(CONFIG["CSV_SUMMARY"], index=False)
    generate_html_report(summary_df, CONFIG, CONFIG["HTML_REPORT"])

if __name__ == "__main__":
    main()
