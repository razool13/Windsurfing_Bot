from config import CONFIG
from forecast_parser import process_forecasts
from plot_utils import dataframe_to_image, create_collage
from fetch import download_latest_forecast_zip
from html_report import generate_html_report

import os

def main():
    try:
        download_latest_forecast_zip(CONFIG)
    except Exception as e:
        print(f"Download failed: {e}")
        return

    try:
        summary_df = process_forecasts(CONFIG)
    except Exception as e:
        print(f"Processing failed: {e}")
        return

    if summary_df.empty:
        print("No forecasts found with strong wind.")
        return

    os.makedirs("output", exist_ok=True)
    summary_df.to_csv(CONFIG["CSV_SUMMARY"], index=False)

    rows_per_image = CONFIG.get("TABLE_ROWS_PER_IMAGE", 20)
    dataframe_to_image(summary_df, CONFIG["TABLE_IMAGE"], rows_per_image)

    collage_limit = CONFIG.get("COLLAGE_MAX_SITES", 0)
    collage_limit = collage_limit if collage_limit and collage_limit > 0 else None
    create_collage(
        summary_df,
        CONFIG["GRAPH_DIR"],
        CONFIG["COLLAGE_FILE"],
        top_n=collage_limit,
        graphs_per_collage=CONFIG.get("COLLAGE_GRAPHS_PER_IMAGE", 6),
    )

    generate_html_report(summary_df, CONFIG, CONFIG["HTML_REPORT"])
    print(f"Report saved to {CONFIG['HTML_REPORT']}")

if __name__ == "__main__":
    main()
