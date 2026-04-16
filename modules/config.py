import json
import os
from multiprocessing import Lock

CONFIG_FILE = "config.json"

# ✅ GLOBAL LOCK
config_lock = Lock()


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"region": None}

    with config_lock:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)


def save_config(data):
    with config_lock:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)


def save_region(x1, y1, x2, y2):
    config = load_config()
    config["region"] = [x1, y1, x2, y2]
    save_config(config)


def get_region():
    config = load_config()
    return config.get("region")


def clear_region():
    config = load_config()
    config["region"] = None
    save_config(config)