# switch_manager.py
import datetime
import json
import os

SWITCH_FLAG_FILE = "switch_flag.json"

def has_switched_today():
    if not os.path.exists(SWITCH_FLAG_FILE):
        return False

    try:
        with open(SWITCH_FLAG_FILE, "r") as f:
            data = json.load(f)
            last_switch = data.get("last_switch_date", "")
            today = datetime.datetime.now().date().isoformat()
            return last_switch == today
    except Exception as e:
        print(f"⚠️ switch_flag.json 읽기 실패: {e}")
        return False

def set_switch_today():
    try:
        today = datetime.datetime.now().date().isoformat()
        with open(SWITCH_FLAG_FILE, "w") as f:
            json.dump({"last_switch_date": today}, f)
    except Exception as e:
        print(f"❌ switch_flag.json 저장 실패: {e}")
