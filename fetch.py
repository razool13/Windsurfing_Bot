import os, shutil
import gdown

def download_latest_forecast_zip(config):
    """Download the latest per-site forecast CSV files from the public Google Drive folder.

    The folder holds the CSV files directly (the same files that used to live inside the
    openskiron ZIP), so no archive extraction is needed. Files are downloaded straight into
    EXTRACT_DIR, where process_forecasts() picks them up via os.walk.
    """
    extract_dir = config["EXTRACT_DIR"]
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir)

    folder_url = config["DRIVE_FOLDER_URL"]
    print(f"Downloading forecast CSVs from Google Drive folder: {folder_url}")
    gdown.download_folder(
        url=folder_url,
        output=extract_dir,
        quiet=False,
        use_cookies=False,
    )

    csv_count = sum(
        1
        for _, _, files in os.walk(extract_dir)
        for f in files
        if f.endswith(".csv")
    )
    if csv_count == 0:
        raise FileNotFoundError(
            f"No CSV files downloaded from Drive folder into {extract_dir}"
        )
    print(f"Downloaded {csv_count} CSV file(s).")
