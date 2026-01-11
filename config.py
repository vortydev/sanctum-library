# config.py
import os
import dotenv
from pathlib import Path

# ========== Load environment ==========
dotenv.load_dotenv()

VERSION = os.getenv("VERSION")
ENV_MODE = os.getenv("ENV_MODE", "dev")

LOCAL_TZ = os.getenv("LOCAL_TZ", "America/Toronto")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
FLASK_ROOT = os.getenv("FLASK_ROOT", "")
PER_PAGE = int(os.getenv("DEFAULT_PER_PAGE", "20"))

# TTL (seconds). 0 or missing = never expire.
TTL_THUMBS = int(os.getenv("IMMICH_THUMB_TTL_SECONDS", "0") or "0")
TTL_META = int(os.getenv("IMMICH_META_TTL_SECONDS", "300") or "300")  # 5 min default

# Paths for saving outputs
BASE_DIR = Path(os.getenv("LIBRARY_DATA_DIR", "data")).resolve()
META_DIR = BASE_DIR / "meta"
ITEMS_DIR = BASE_DIR / "items"

# Ensure dirs exist
for d in (META_DIR, ITEMS_DIR,):
    Path(d).mkdir(parents=True, exist_ok=True)