# -*- coding: utf-8 -*-
import requests
import os
import time

def _normalize_images(images):
    if not images:
        return []
    if isinstance(images, (list, tuple)):
        return [img for img in images if img]
    return [images]
def send_image(bot_token, chat_id, image_path):
    if os.path.exists(image_path):
        with open(image_path, 'rb') as img:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                data={"chat_id": chat_id},
                files={"photo": img}
            )

#def send_image(config, image_path):
#    """
#    שולח תמונה כ-photo ל-Telegram עם הדפסת סטטוס.
#    """
#    bot_token = config["BOT_TOKEN"]
#    chat_id = config["CHAT_ID"]
#
#    if not os.path.exists(image_path):
#        print(f"❌ File does NOT exist: {image_path}")
#        return
#
#    size_bytes = os.path.getsize(image_path)
#    print(f"🖼️ File exists: {image_path} | Size: {size_bytes / (1024 * 1024):.2f} MB")
#
#    try:
#        with open(image_path, 'rb') as img:
#            response = requests.post(
#                f"https://api.telegram.org/bot{bot_token}/sendPhoto",
#                data={"chat_id": chat_id},
#                files={"photo": img}
#            )
#            print(f"📬 Telegram status: {response.status_code}")
#            print(response.text)
#    except Exception as e:
#        print(f"❌ Exception while sending {image_path}: {e}")

def send_document(bot_token, chat_id, file_path, caption=None):
    """Send a file as a document to a Telegram chat."""
    if not os.path.exists(file_path):
        print(f"❌ File does NOT exist: {file_path}")
        return
    with open(file_path, 'rb') as f:
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendDocument",
            data=data,
            files={"document": (os.path.basename(file_path), f)}
        )

def send_images_only(config, table_imgs, collage_imgs):
    table_imgs = _normalize_images(table_imgs)
    collage_imgs = _normalize_images(collage_imgs)

    total_tables = len(table_imgs)
    for idx, img_path in enumerate(table_imgs, start=1):
        print(f"📤 Sending table image {idx}/{total_tables} to Telegram...")
        send_image(config["BOT_TOKEN"], config["CHAT_ID"], img_path)

    total_collages = len(collage_imgs)
    for idx, img_path in enumerate(collage_imgs, start=1):
        print(f"📤 Sending collage image {idx}/{total_collages} to Telegram...")
        send_image(config["BOT_TOKEN"], config["CHAT_ID"], img_path)
    
def send_forecast_summary(config, df, table_img, collage_img):
    message = u"\U0001F3C4\u200D\u2642\uFE0F \u05EA\u05D7\u05D6\u05D9\u05EA \u05DC\u05D2\u05DC\u05D9\u05E9\u05EA \u05E8\u05D5\u05D7:"
    for _, row in df.head(config["TOP_SITES_TO_SEND"]).iterrows():
        message += f"\U0001F4CD {row['Site']} ({row['Dir']}): {row['Window']} | \u05DE\u05DE\u05D5\u05E6\u05E2 {row['Avg Wind (knots)']} \u05E7\u05E9\u05E8\n"

    requests.post(
        f"https://api.telegram.org/bot{config['BOT_TOKEN']}/sendMessage",
        data={"chat_id": config["CHAT_ID"], "text": message}
    )

    for img in _normalize_images(table_img):
        send_image(config["BOT_TOKEN"], config["CHAT_ID"], img)

    for img in _normalize_images(collage_img):
        send_image(config["BOT_TOKEN"], config["CHAT_ID"], img)
