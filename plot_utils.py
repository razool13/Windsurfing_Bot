import glob
import matplotlib.pyplot as plt
from PIL import Image
import os
import numpy as np

def direction_to_arrow(degrees):
    if degrees is None:
        return ''
    degrees = (float(degrees) + 180) % 360  # כיוון הנשיבה
    if 337.5 <= degrees or degrees < 22.5:
        return '⬆'
    elif 22.5 <= degrees < 67.5:
        return '↗'
    elif 67.5 <= degrees < 112.5:
        return '→'
    elif 112.5 <= degrees < 157.5:
        return '↘'
    elif 157.5 <= degrees < 202.5:
        return '⬇'
    elif 202.5 <= degrees < 247.5:
        return '↙'
    elif 247.5 <= degrees < 292.5:
        return '←'
    else:
        return '↖'

def dataframe_to_image(df, output_path, max_rows_per_image=20):
    df_filtered = df[["Site", "Window", "Avg Wind (knots)","Dir"]].copy()
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    base_name, ext = os.path.splitext(output_path)
    if not ext:
        ext = ".png"

    if os.path.exists(output_path):
        os.remove(output_path)  # מחיקת קובץ קיים כדי להבטיח רענון
    for stale_file in glob.glob(f"{base_name}_part*{ext}"):
        os.remove(stale_file)

    df_filtered = df_filtered.reset_index(drop=True)
    if "Dir" in df_filtered.columns:
        df_filtered["Raw Dir"] = df_filtered["Dir"]  # שמירת הזווית המקורית
        df_filtered["Dir"] = df_filtered["Dir"].apply(direction_to_arrow)

    max_rows = max(1, int(max_rows_per_image))
    chunks = [
        df_filtered.iloc[start:start + max_rows].reset_index(drop=True)
        for start in range(0, len(df_filtered), max_rows)
    ]
    image_paths = []

    for idx, chunk in enumerate(chunks, start=1):
        fig, ax = plt.subplots(figsize=(chunk.shape[1]*2.5, chunk.shape[0]*0.6 + 1))
        ax.axis('off')
        table = ax.table(cellText=chunk.values, colLabels=chunk.columns, cellLoc='center', loc='center')
        table.scale(1.2, 2)
        for key, cell in table.get_celld().items():
            cell.set_fontsize(12)

        plt.tight_layout()
        target_path = output_path if len(chunks) == 1 else f"{base_name}_part{idx}{ext}"
        plt.savefig(target_path, bbox_inches='tight', pad_inches=0.5, dpi=300)
        plt.close()
        print(f"✅ Saved table image to {target_path}")
        image_paths.append(target_path)

    return image_paths

def create_collage(df, graph_dir, output_path_1, top_n=5, cols=2, max_dim_px=1280):
    """
    יוצר קולאז' של תמונות ומוודא שהתמונה הסופית תיהיה תקינה לשליחה כ-photo.
    """
    if not output_path_1.lower().endswith('.png'):
        output_path_1 = os.path.splitext(output_path_1)[0] + '.png'

    if os.path.exists(output_path_1):
        os.remove(output_path_1)

    # שליפת התמונות
    images = []
    for _, row in df.head(top_n).iterrows():
        image_path = os.path.join(graph_dir, row["Site"] + ".png")
        if os.path.exists(image_path):
            images.append(Image.open(image_path).convert("RGBA"))

    if not images:
        print("⚠️ No images found for collage.")
        return None

    # קבעת גודל מקסימלי פר תמונה
    base_width = min(img.width for img in images)
    base_height = min(img.height for img in images)

    # קבעת גודל הקולאז'
    rows = (len(images) + cols - 1) // cols
    collage_width = cols * base_width
    collage_height = rows * base_height

    # קנה מידה אם הקולאז' חורג מהממדים המומלצים
    scale_factor = min(max_dim_px / collage_width, max_dim_px / collage_height, 1.0)
    resized_width = int(collage_width * scale_factor)
    resized_height = int(collage_height * scale_factor)

    collage_array = Image.new("RGBA", (collage_width, collage_height), (255, 255, 255, 0))

    for idx, img in enumerate(images):
        x = (idx % cols) * base_width
        y = (idx // cols) * base_height
        collage_array.paste(img.resize((base_width, base_height)), (x, y))

    collage_array = collage_array.resize((resized_width, resized_height), Image.LANCZOS)
    collage_array.convert("RGB").save(output_path_1, format='PNG')
    print(f"✅ Saved resized collage PNG to {output_path_1} | {resized_width}x{resized_height}px")

    return output_path_1
