# VoteApp — Django Voting Application

A full-featured, secure voting application built with Django.

## Features

- **Voter Portal** — Dashboard, ballot casting, confirmation with reference ID, results view
- **Admin Panel** — Manage elections, candidates, voters, and view live results
- **Security** — One vote per election enforced, session management, CSRF protection
- **Role-based access** — Voters and Admins have separate UIs and permissions
- **Export** — Download voter lists and election results as CSV

## Pages

| Page | URL |
|------|-----|
| Login | `/accounts/login/` |
| Register | `/accounts/register/` |
| Voter Dashboard | `/elections/dashboard/` |
| Ballot | `/elections/<id>/ballot/` |
| Confirmation | `/elections/confirmation/<id>/` |
| Results (voter) | `/elections/<id>/results/` |
| Admin Dashboard | `/admin-panel/` |
| Election List | `/admin-panel/elections/` |
| Create Election | `/admin-panel/elections/create/` |
| Manage Election | `/admin-panel/elections/<id>/manage/` |
| Admin Results | `/admin-panel/elections/<id>/results/` |
| Voter List | `/admin-panel/voters/` |
| Invite Voter | `/admin-panel/voters/invite/` |
| Django Admin | `/django-admin/` |

## Quick Start

### Option 1: Automated setup

```bash
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py makemigrations accounts
python manage.py makemigrations elections
python manage.py migrate

# 4. Seed demo data (creates admin + voters + sample elections)
python manage.py seed_demo

# 5. Start the server
python manage.py runserver
```

Visit: http://127.0.0.1:8000

## Demo Accounts

| Role  | Email                  | Password  |
|-------|------------------------|-----------|
| Admin | admin@voteapp.com      | admin123  |
| Voter | alice@example.com      | voter123  |
| Voter | bob@example.com        | voter123  |
| Voter | carol@example.com      | voter123  |

## Project Structure

```
voteapp/
├── manage.py
├── requirements.txt
├── setup.sh
├── voteapp/           # Project config (settings, urls, wsgi)
├── accounts/          # Custom user model, login, register
├── elections/         # Elections, candidates, votes, voter UI
│   └── management/commands/seed_demo.py
├── admin_panel/       # Admin-only UI and management
├── templates/         # All HTML templates
│   ├── base.html
│   ├── accounts/
│   ├── elections/
│   └── admin_panel/
├── static/            # CSS and JS
└── media/             # Uploaded candidate photos
```

## Production Notes

- Change `SECRET_KEY` in `settings.py` (use an environment variable)
- Set `DEBUG = False` and configure `ALLOWED_HOSTS`
- Use PostgreSQL instead of SQLite
- Configure `STATIC_ROOT` and run `collectstatic`
- Use gunicorn + nginx for serving
