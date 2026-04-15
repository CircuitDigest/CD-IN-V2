import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads", "instagram-microsite")

DEFAULT_DB_PATH = os.path.join(DATA_DIR, "microsite.db")
LEGACY_IMPORT_DB_PATH = os.path.join(BASE_DIR, "old-db.db")


def get_db_path() -> str:
    return os.environ.get("MICROSITE_DB_PATH", DEFAULT_DB_PATH)


def ensure_runtime_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
