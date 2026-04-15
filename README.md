# CD-IN-V2 Flask App

Flask app for CircuitDigest website routing, Instagram microsite management, and webinar platform flows.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_microsite_db.py
python scripts/import_old_microsite_data.py
python scripts/init_webinar_db.py
```

Set environment variables (use single quotes for hash values with `$`):

```bash
export FLASK_SECRET_KEY='replace-with-random-secret'
export ADMIN_USERNAME='replace-with-admin-username'
export ADMIN_PASSWORD_HASH='replace-with-generated-hash'
# optional, default is data/microsite.db
export MICROSITE_DB_PATH='/absolute/path/to/microsite.db'
export WEBINAR_DB_PATH='/absolute/path/to/webinar.db'
PORT=5002 python app.py
```

## Routes

- `/` -> redirects to `https://circuitdigest.com`
- `/instagram-microsite` -> public microsite page
- `/api/microsite/click` -> click tracking endpoint
- `/admin` -> admin login/dashboard
- `/admin/instagram-microsite` -> microsite content manager
- `/webinar-registration` -> public webinar registration page
- `/admin/webinar` -> webinar admin settings/registrations/messaging

## Database workflow

- `scripts/init_microsite_db.py` creates schema and seeds defaults.
- `scripts/import_old_microsite_data.py` imports config/categories/projects from `old-db.db` into the new DB.
- `scripts/init_webinar_db.py` creates webinar schema in a separate DB.
- `scripts/run_webinar_reminders.py` executes scheduled reminder sending logic once.
- `scripts/test_webinar_msg91.py` verifies MSG91 email/WhatsApp templates with your credentials.

## PythonAnywhere deployment checklist

```bash
cd /home/circuitdigest/CD-IN-V2
git pull
source /home/circuitdigest/.virtualenvs/cd-in-v2/bin/activate
pip install -r requirements.txt
python scripts/init_microsite_db.py
python scripts/import_old_microsite_data.py   # run on first migration or when re-sync needed
python scripts/init_webinar_db.py
```

Configure cron for webinar reminders (every 10 minutes recommended):

```bash
*/10 * * * * /home/circuitdigest/.virtualenvs/cd-in-v2/bin/python /home/circuitdigest/CD-IN-V2/scripts/run_webinar_reminders.py
```

In WSGI set:

- `FLASK_SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD_HASH`
- `MICROSITE_DB_PATH` (recommended persistent path)
- `WEBINAR_DB_PATH` (recommended persistent path)
- `MSG91_EMAIL_AUTHKEY`
- `MSG91_EMAIL_DOMAIN`
- `MSG91_EMAIL_FROM`
- `MSG91_WHATSAPP_AUTHKEY`
- `MSG91_WHATSAPP_NUMBER`
- `MSG91_WHATSAPP_TEMPLATE_NAMESPACE` (if your templates require namespace)

Then reload web app.

### Verify MSG91 credentials/templates quickly

```bash
source .venv/bin/activate
export TEST_EMAIL='your-email@example.com'
export TEST_PHONE='919876543210'
python scripts/test_webinar_msg91.py
```
