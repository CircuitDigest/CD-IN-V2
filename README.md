# CD-IN-V2 Flask App

Flask app for CircuitDigest website routing and Instagram microsite management.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_microsite_db.py
python scripts/import_old_microsite_data.py
```

Set environment variables (use single quotes for hash values with `$`):

```bash
export FLASK_SECRET_KEY='replace-with-random-secret'
export ADMIN_USERNAME='replace-with-admin-username'
export ADMIN_PASSWORD_HASH='replace-with-generated-hash'
# optional, default is data/microsite.db
export MICROSITE_DB_PATH='/absolute/path/to/microsite.db'
PORT=5002 python app.py
```

## Routes

- `/` -> redirects to `https://circuitdigest.com`
- `/instagram-microsite` -> public microsite page
- `/api/microsite/click` -> click tracking endpoint
- `/admin` -> admin login/dashboard
- `/admin/instagram-microsite` -> microsite content manager

## Database workflow

- `scripts/init_microsite_db.py` creates schema and seeds defaults.
- `scripts/import_old_microsite_data.py` imports config/categories/projects from `old-db.db` into the new DB.

## PythonAnywhere deployment checklist

```bash
cd /home/circuitdigest/CD-IN-V2
git pull
source /home/circuitdigest/.virtualenvs/cd-in-v2/bin/activate
pip install -r requirements.txt
python scripts/init_microsite_db.py
python scripts/import_old_microsite_data.py   # run on first migration or when re-sync needed
```

In WSGI set:

- `FLASK_SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD_HASH`
- `MICROSITE_DB_PATH` (recommended persistent path)

Then reload web app.
