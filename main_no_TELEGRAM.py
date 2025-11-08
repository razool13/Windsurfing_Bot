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
        rows_per_image = CONFIG.get("TABLE_ROWS_PER_IMAGE", 20)
        table_imgs = dataframe_to_image(summary_df, CONFIG["TABLE_IMAGE"], rows_per_image)
        collage_limit = CONFIG.get("COLLAGE_MAX_SITES", 0)
        collage_limit = collage_limit if collage_limit and collage_limit > 0 else None
        collage_imgs = create_collage(
            summary_df,
            CONFIG["GRAPH_DIR"],
            CONFIG["COLLAGE_FILE"],
            top_n=collage_limit,
            graphs_per_collage=CONFIG.get("COLLAGE_GRAPHS_PER_IMAGE", 6),
        )

        # שולח גם את טבלת התמונה וגם את הקולאז'
        #send_forecast_summary(CONFIG, summary_df, table_imgs, collage_imgs)
        send_images_only(CONFIG, table_imgs, collage_imgs)

if __name__ == "__main__":
    main()
