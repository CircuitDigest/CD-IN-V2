import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads", "instagram-microsite")
WEBINAR_UPLOADS_DIR = os.path.join(BASE_DIR, "uploads", "webinar")
SUBMIT_PROJECT_IDEA_UPLOADS_DIR = os.path.join(BASE_DIR, "uploads", "project-idea")

DEFAULT_DB_PATH = os.path.join(DATA_DIR, "microsite.db")
DEFAULT_WEBINAR_DB_PATH = os.path.join(DATA_DIR, "webinar.db")
DEFAULT_SUBMIT_PROJECT_IDEA_DB_PATH = os.path.join(DATA_DIR, "submit_project_idea.db")
LEGACY_IMPORT_DB_PATH = os.path.join(BASE_DIR, "old-db.db")


def get_db_path() -> str:
    return os.environ.get("MICROSITE_DB_PATH", DEFAULT_DB_PATH)


def ensure_runtime_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(WEBINAR_UPLOADS_DIR, exist_ok=True)
    os.makedirs(SUBMIT_PROJECT_IDEA_UPLOADS_DIR, exist_ok=True)


def get_webinar_db_path() -> str:
    return os.environ.get("WEBINAR_DB_PATH", DEFAULT_WEBINAR_DB_PATH)


def get_submit_project_idea_db_path() -> str:
    return os.environ.get("SUBMIT_PROJECT_IDEA_DB_PATH", DEFAULT_SUBMIT_PROJECT_IDEA_DB_PATH)
