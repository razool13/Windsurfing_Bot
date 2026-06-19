import os

CONFIG = {
    "DRIVE_FOLDER_URL": "https://drive.google.com/drive/folders/1bM40e7nwFQByOAibeuX9o6cvq2tbAKUw",
    "EXTRACT_DIR": "data/unzipped_forecasts",
    "GRAPH_DIR": "data/graphs",
    "COLLAGE_FILE": "output/forecast_collage.jpg",
    "CSV_SUMMARY": "output/wind_windows_summary.csv",
    "TABLE_IMAGE": "output/summary_table.png",
    "HTML_REPORT": "output/index.html",
    "TABLE_ROWS_PER_IMAGE": 15,
    "COLLAGE_MAX_SITES": 0,
    "COLLAGE_GRAPHS_PER_IMAGE": 6,
    "BOT_TOKEN": os.environ.get("BOT_TOKEN", ""),
    "CHAT_ID_raz": os.environ.get("CHAT_ID_RAZ", ""),
    "CHAT_ID": os.environ.get("CHAT_ID", ""),
    "MIN_WIND_KNOTS": 15,
    "MIN_BLOCK_LENGTH": 2,
    "DAY_START_HOUR": 6,
    "DAY_END_HOUR": 20,
    "TOP_SITES_TO_SEND": 6
}
