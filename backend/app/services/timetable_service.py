import json
from app.utils.redis_client import redis_client

def get_timetable_layout():
    layout_json = redis_client.get("timetable_layout")

    if layout_json is None:
        raise ValueError("No timetable layout found in Redis. Did you submit page 1?")
    return json.loads(layout_json)
