"""
Cloud-only entry point: fetch forecast data, process it, and generate
the HTML report.  No Telegram sending — designed for CI / GitHub Actions.
"""
from config import CONFIG
from forecast_parser import process_forecasts
from fetch import download_latest_forecast_zip
from html_report import generate_html_report
import os


def main():
    download_latest_forecast_zip(CONFIG)
    summary_df = process_forecasts(CONFIG)

    if summary_df.empty:
        print("No forecasts found with strong wind.")
    else:
        os.makedirs("output", exist_ok=True)
        summary_df.to_csv(CONFIG["CSV_SUMMARY"], index=False)
        generate_html_report(summary_df, CONFIG, CONFIG["HTML_REPORT"])


if __name__ == "__main__":
    main()
