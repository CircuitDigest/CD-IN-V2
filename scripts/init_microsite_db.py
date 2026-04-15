#!/usr/bin/env python3
"""Initialize microsite database schema and defaults."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cdin.config import ensure_runtime_dirs, get_db_path
from cdin.db import ensure_defaults, initialize_schema


def main() -> None:
    ensure_runtime_dirs()
    initialize_schema()
    ensure_defaults()
    print(f"Microsite DB initialized at: {get_db_path()}")


if __name__ == "__main__":
    main()
