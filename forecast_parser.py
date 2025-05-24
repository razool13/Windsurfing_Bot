import pandas as pd
import os
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt

def parse_datetime(val):
    try:
        day = int(val[2:4])
        hour = int(val[5:7])
        minute = int(val[7:9]) if len(val) == 9 else 0
        return datetime(datetime.today().year, datetime.today().month, day, hour, minute)
    except:
        return None

def circular_mean(degrees_series):
    radians = np.deg2rad(degrees_series)
    sin_sum = np.sum(np.sin(radians))
    cos_sum = np.sum(np.cos(radians))
    mean_angle = np.arctan2(sin_sum, cos_sum)
    return (np.rad2deg(mean_angle) + 360) % 360

def is_valid_window(df, config):
    df = df.set_index("datetime")
    df = df.between_time(f"{config['DAY_START_HOUR']}:00", f"{config['DAY_END_HOUR']}:00")
    df = df[df["wind_speed"] >= config["MIN_WIND_KNOTS"]]

    if len(df) >= config["MIN_BLOCK_LENGTH"]:
        avg_speed = df["wind_speed"].mean()
        start_time = df.index.min().strftime('%d/%m %H:%M')
        end_time = df.index.max().strftime('%H:%M')
        return f"{start_time}-{end_time}", round(avg_speed, 1), circular_mean(df["wind_dir"])
    return None, None, None

def save_site_plot(df, site_name, output_dir):
    import matplotlib.dates as mdates
    from datetime import timedelta

    df = df.copy()
    df = df.rename(columns={"datetime": "Datetime", "wind_speed": "WindSpeed", "wind_dir": "WindDir", "wind_gust": "WindGust"})
    df = df.sort_values("Datetime")

    forecast_start_date = df["Datetime"].min().date()
    tomorrow = forecast_start_date + timedelta(days=1)
    df_tomorrow = df[df["Datetime"].dt.date == tomorrow]
    strong_hours = df_tomorrow[df_tomorrow["WindSpeed"] > 20]
    msg = "Good for windsurfing tomorrow!" if len(strong_hours) >= 2 else "Not enough wind for good windsurfing tomorrow."

    fig, ax = plt.subplots(figsize=(12, 5), dpi=300)
    sc = ax.scatter(df["Datetime"], df["WindSpeed"], c=df["WindSpeed"], cmap="plasma")
    ax.plot(df["Datetime"], df["WindGust"], linestyle="--", color="red", label="Wind Gust")
    ax.plot(df["Datetime"], df["WindSpeed"], linestyle="-", color="gray", label="Wind Speed")

    arrow_length = -0.2
    times_numeric = mdates.date2num(df["Datetime"])
    u = arrow_length * np.sin(np.deg2rad(df["WindDir"].values + 180))
    v = arrow_length * np.cos(np.deg2rad(df["WindDir"].values + 180))

    norm = plt.Normalize(df["WindSpeed"].min(), df["WindSpeed"].max())
    colors = plt.cm.plasma(norm(df["WindSpeed"].values))
    arrow_dirs = ["↓", "←", "↑", "→", "↙", "↖", "↗", "↘"]
    arrow_labels = [arrow_dirs[int(((d + 22) % 360) // 45)] for d in df["WindDir"]]
    ax.quiver(times_numeric, df["WindSpeed"].values, u, v, angles='xy', scale_units='xy', scale=5, color=colors, width=0.003)

    for i in range(len(df)):
        ax.text(times_numeric[i], df['WindSpeed'].iloc[i] + 1.0, arrow_labels[i], fontsize=6, ha='center', va='bottom', color='black')
        ax.text(times_numeric[i], df['WindSpeed'].iloc[i] + 0.3, str(int(df['WindSpeed'].iloc[i])), fontsize=6, ha='center', va='bottom', color='black')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m %H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.set_xlim(df["Datetime"].min(), df["Datetime"].max())
    plt.xticks(rotation=90)
    ax.set_xlabel("Time")
    ax.set_ylabel("Wind Speed (knots)")
    plt.title(f"{site_name} | {msg}")
    plt.colorbar(sc, label="Wind Speed (knots)")
    plt.legend()
    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, site_name + ".png"), dpi=300)
    plt.close()

def process_forecasts(config):
    summary_blocks = []
    for root, _, files in os.walk(config["EXTRACT_DIR"]):
        for file in files:
            if file.endswith(".csv"):
                path = os.path.join(root, file)
                try:
                    df = pd.read_csv(path, skiprows=2, names=["datetime_raw", "wind_speed", "wind_dir", "wind_gust"])
                    df["datetime"] = df["datetime_raw"].apply(parse_datetime)
                    df = df.dropna(subset=["datetime"])
                    df[["wind_speed", "wind_dir", "wind_gust"]] = df[["wind_speed", "wind_dir", "wind_gust"]].apply(pd.to_numeric, errors='coerce')
                    df = df.dropna()

                    site = os.path.splitext(file)[0]
                    window, avg, dir_mean = is_valid_window(df, config)
                    if window:
                        save_site_plot(df, site, config["GRAPH_DIR"])
                        summary_blocks.append({
                            "Site": site,
                            "Window": window,
                            "Avg Wind (knots)": avg,
                            "Dir": round(dir_mean)
                        })
                except Exception as e:
                    print(f"⚠️ Error in {file}: {e}")
    return pd.DataFrame(summary_blocks)
