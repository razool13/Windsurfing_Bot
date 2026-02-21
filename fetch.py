import requests
import os
import zipfile
from bs4 import BeautifulSoup


def download_latest_forecast_zip(config):
    def find_latest_zip_url(base_url="https://openskiron.org/he/%D7%A7%D7%91%D7%A6%D7%99%D7%9D-%D7%9C%D7%94%D7%95%D7%A8%D7%93%D7%94"):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(base_url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        zip_links = [
            a['href'] for a in soup.find_all('a', href=True)
            if "all_1km_files.zip" in a['href']
        ]

        if not zip_links:
            raise FileNotFoundError("לא נמצאו קבצים עם all_1km_files.zip באתר.")

        zip_links.sort(reverse=True)
        latest_zip_url = zip_links[0] if zip_links[0].startswith("http") else base_url + zip_links[0]

        print(f"✅ Found latest ZIP: {latest_zip_url}")
        return latest_zip_url

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
        for filename in os.listdir(extract_dir):
            file_path = os.path.join(extract_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                import shutil
                shutil.rmtree(file_path)
    else:
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
