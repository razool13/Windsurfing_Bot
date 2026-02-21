import requests
import os
import zipfile
from datetime import date, timedelta


def download_latest_forecast_zip(config):
    def find_latest_zip_url():
        base = "https://openskiron.org/kite_gribs"
        for days_ago in range(5):
            d = (date.today() - timedelta(days=days_ago)).strftime("%Y%m%d")
            url = f"{base}/{d}-all_1km_files.zip"
            try:
                resp = requests.head(url, timeout=15, allow_redirects=True)
                if resp.status_code == 200:
                    print(f"✅ Found latest ZIP: {url}")
                    return url
                print(f"   {url} → {resp.status_code}")
            except Exception as e:
                print(f"   {url} → error: {e}")
        raise FileNotFoundError("Could not find a recent ZIP on openskiron.org (tried last 5 days)")

    zip_path = config["ZIP_FILE"]
    extract_dir = config["EXTRACT_DIR"]

    url = find_latest_zip_url()
    print("📥 Downloading ZIP file...")
    r = requests.get(url, timeout=120)
    print(f"HTTP Status: {r.status_code}")
    if r.status_code != 200:
        print(f"❌ Failed to download ZIP from {url}")
        return

    if os.path.exists(zip_path):
        os.remove(zip_path)

    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with open(zip_path, 'wb') as f:
        f.write(r.content)

    print("💾 Extracting ZIP...")
    if os.path.exists(extract_dir):
        import shutil
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    print("✅ Extraction complete.")


def scan_for_encoding_issues(directory, encoding="utf-8"):
    for root, _, files in os.walk(directory):
        for fname in files:
            if fname.endswith(".py"):
                path = os.path.join(root, fname)
                try:
                    with open(path, encoding=encoding) as f:
                        f.read()
                except UnicodeDecodeError as e:
                    print(f"❌ בעיית קידוד בקובץ: {path}")
                    print(f"   מיקום: byte {e.start} → {e.reason}")
                except Exception as e:
                    print(f"⚠️ שגיאה אחרת בקובץ {path}: {e}")
