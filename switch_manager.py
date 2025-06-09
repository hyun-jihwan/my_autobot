# switch_manager.py
import datetime
import json
import os

SWITCH_FLAG_FILE = "switch_flag.json"

def has_switched_today():
    if not os.path.exists(SWITCH_FLAG_FILE):
        return False

    with open(SWITCH_FLAG_FILE, "r") as f:
        data = json.load(f)
        last_switch = data.get("last_switch_date", "")
        return last_switch == datetime.date.today().isoformat()

def set_switch_today():
    with open(SWITCH_FLAG_FILE, "w") as f:
        data = {"last_switch_date": datetime.date.today().isoformat()}
        json.dump(data, f)
