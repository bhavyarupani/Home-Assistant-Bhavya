import os
import random

time_phase = data.get("time_phase")
weather = data.get("weather")

base_path = "/config/www/backgrounds"
folder_path = f"{base_path}/{time_phase}/{weather}"

try:
    files = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith((".jpg", ".png", ".webp"))
    ]

    if not files:
        logger.warning(f"No images found in {folder_path}")
        return

    chosen = random.choice(files)

    hass.services.call(
        "input_text",
        "set_value",
        {
            "entity_id": "input_text.global_dashboard_background",
            "value": f"/local/backgrounds/{time_phase}/{weather}/{chosen}"
        },
        False
    )

except Exception as e:
    logger.error(f"Background picker error: {e}")
