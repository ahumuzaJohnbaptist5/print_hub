# PrintHub

PrintHub is a campus print ordering platform for Kabale University students. Students upload documents, pay via MTN/Airtel Mobile Money (Flutterwave), and pick up prints at a campus station.

## Stack

- **Backend:** Django (Python), deployed on PythonAnywhere
- **Frontend (legacy):** React + Vite on Vercel at [print-hub-sigma.vercel.app](https://print-hub-sigma.vercel.app)
- **Current path:** Django server-rendered templates (recommended for new development)

## Local setup

### Prerequisites

- Python 3.10+
- pip

### 1. Clone and enter the project

```bash
git clone <repository-url>
cd print_hub
```

### 2. Create a virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate    # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp ../.env.example ../.env
# Edit ../.env with your values (SECRET_KEY, Flutterwave keys, etc.)
```

For local development, set at minimum:

```
SECRET_KEY=dev-secret-key-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

### 5. Run migrations

```bash
python3 manage.py migrate
```

This also seeds the three pickup stations: Main Campus, Engineering Faculty, and In Town.

### 6. Create a superuser (optional)

```bash
python3 manage.py createsuperuser
```

To grant admin or agent roles, set the `role` field on the user in Django admin (`client`, `admin`, or `agent`).

### 7. Run the development server

```bash
python3 manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000).

## Django-only user flow

1. **Register** at `/auth/register/` — all new users are created as `client`
2. **Upload** a document at `/upload/` — select station, pages, color, double-sided
3. **Pay** from the dashboard via "Pay Now" → Flutterwave Mobile Money
4. **Track** order status at `/track/` using order ID or email
5. **Admin/Agent** dashboards at `/admin-dashboard/` and `/orders/agent/`

Uploaded files are **not** served publicly. Downloads require authentication via `/orders/<id>/file/`.

## Deployment split

| Component | Platform | Notes |
|-----------|----------|-------|
| Django backend | PythonAnywhere | WSGI via Gunicorn (`Procfile`), SQLite or external DB via `DATABASE_URL` |
| React frontend | Vercel | Legacy SPA; requires a REST API that is not wired in this Django-only path |

**Going Django-only:** Point your domain to PythonAnywhere, set production env vars, run `collectstatic`, and configure media file storage on the PA filesystem.

**Keeping Vercel React:** You would need to restore REST API endpoints and set `CORS_ALLOWED_ORIGINS` to your Vercel URL.

## Environment variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key (required in production) |
| `DEBUG` | `True` or `False` |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins for React API (if used) |
| `FLUTTERWAVE_SECRET_KEY` | Flutterwave secret key for payment verification |
| `FLUTTERWAVE_PUBLIC_KEY` | Flutterwave public key for checkout |
| `DATABASE_URL` | Database connection string (defaults to SQLite) |

## Running tests

```bash
cd backend
python3 manage.py test
```

## Project structure

```
print_hub/
├── backend/           # Django project
│   ├── accounts/      # User auth (CustomUser model)
│   ├── orders/        # Orders, uploads, payments
│   ├── stations/      # Pickup locations
│   ├── templates/     # Django HTML templates
│   └── core/          # Settings, URLs
├── frontend/          # Legacy React app (Vercel)
└── .env.example       # Environment variable template
```
