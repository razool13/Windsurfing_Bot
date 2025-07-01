from config import CONFIG
from forecast_parser import process_forecasts
from plot_utils import dataframe_to_image, create_collage
from telegram_utils import send_images_only
from fetch import download_latest_forecast_zip

import os

def main():
    # download_latest_forecast_zip(CONFIG)
    download_latest_forecast_zip(CONFIG)
    summary_df = process_forecasts(CONFIG)

    if summary_df.empty:
        print("📭 No forecasts found with strong wind.")
    else:
        os.makedirs("output", exist_ok=True)
        summary_df.to_csv(CONFIG["CSV_SUMMARY"], index=False)
        table_img = dataframe_to_image(summary_df, CONFIG["TABLE_IMAGE"])
        collage_img = create_collage(summary_df, CONFIG["GRAPH_DIR"], CONFIG["COLLAGE_FILE"])

        # שולח גם את טבלת התמונה וגם את הקולאז'
        #send_forecast_summary(CONFIG, summary_df, table_img, collage_img)
        send_images_only(CONFIG, table_img, collage_img)

if __name__ == "__main__":
    main()
