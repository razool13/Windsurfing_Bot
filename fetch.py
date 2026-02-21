import requests, os, zipfile
from datetime import date, timedelta

def download_latest_forecast_zip(config):
    def find_latest_zip_url():
        base = "https://openskiron.org/kite_gribs"
        for days_ago in range(5):
            d = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
            url = f"{base}/{d}-all_1km_files.zip"
            try:
                r = requests.head(url, timeout=15, allow_redirects=True)
                if r.status_code == 200:
                    print(f"Found: {url}")
                    return url
            except Exception as e:
                print(f"  {url} -> {e}")
        raise FileNotFoundError("No recent ZIP found (tried 5 days)")

    url = find_latest_zip_url()
    print("Downloading...")
    r = requests.get(url, timeout=120)
    if r.status_code != 200:
        raise Exception(f"Download failed: {r.status_code}")

    zip_path = config["ZIP_FILE"]
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with open(zip_path, "wb") as f:
        f.write(r.content)

    import shutil
    extract_dir = config["EXTRACT_DIR"]
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)
    print("Extracted.")
