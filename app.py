import os
from pathlib import Path

from cdin import create_app


# Local development convenience: auto-load a local `.env` file if present.
# `.env` is ignored by git, so secrets won't be committed.
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=False)
except Exception:
    # If python-dotenv isn't installed or `.env` doesn't exist, continue normally.
    pass

app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, port=port)
