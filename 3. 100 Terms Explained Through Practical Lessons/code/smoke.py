"""Retry a local endpoint, then assert the actual response contract."""
import json
import time
from urllib.request import urlopen
for attempt in range(30):
    try:
        with urlopen("http://127.0.0.1:8000/", timeout=2) as r:
            assert r.status == 200
            data = json.load(r)
            assert data["message"] and data["version"]
        print("Smoke check passed")
        break
    except (OSError, AssertionError, ValueError):
        if attempt == 29:
            raise
        time.sleep(1)
