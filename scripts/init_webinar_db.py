#!/usr/bin/env python3
"""Initialize webinar database schema."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdin.config import ensure_runtime_dirs, get_webinar_db_path
from cdin.webinar_db import initialize_webinar_schema


def main() -> None:
    ensure_runtime_dirs()
    initialize_webinar_schema()
    print(f"Webinar DB initialized at: {get_webinar_db_path()}")


if __name__ == "__main__":
    main()
