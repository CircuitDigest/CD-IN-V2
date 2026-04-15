import os

from flask import Flask, redirect

from .admin import bp as admin_bp
from .config import BASE_DIR, ensure_runtime_dirs
from .db import ensure_defaults, initialize_schema
from .microsite import bp as microsite_bp


def create_app() -> Flask:
    app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")

    # Ensure data/uploads directories and DB schema exist at startup.
    ensure_runtime_dirs()
    initialize_schema()
    ensure_defaults()

    app.register_blueprint(microsite_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def home():
        return redirect("https://circuitdigest.com", code=302)

    return app
