import requests
import os

# เปลี่ยนเป็น Railway URL หลัง deploy เสร็จ
# ตัวอย่าง: https://nexstock-production.up.railway.app
BASE_URL = os.getenv("NEXSTOCK_API_URL", "http://localhost:8000")


def get(path: str) -> dict | list | None:
    try:
        r = requests.get(f"{BASE_URL}{path}", timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def post(path: str, body: dict) -> dict | None:
    try:
        r = requests.post(f"{BASE_URL}{path}", json=body, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def delete(path: str) -> bool:
    try:
        r = requests.delete(f"{BASE_URL}{path}", timeout=10)
        return r.ok
    except Exception:
        return False
