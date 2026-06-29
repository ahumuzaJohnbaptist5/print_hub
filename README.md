# PrintHub

PrintHub is a campus print ordering platform for Kabale University students. Students upload documents online, pick them up at a campus station, and pay in person after reviewing their prints.

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
# Edit ../.env with your values
```

For local development:

```
SECRET_KEY=dev-secret-key-change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000
CORS_ALLOWED_ORIGINS=http://localhost:5173
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

In development, verification emails print to the console.

### 5. Run migrations

```bash
python3 manage.py migrate
```

This seeds three pickup stations: Main Campus, Engineering Faculty, and In Town.

### 6. Create a superuser (optional)

```bash
python3 manage.py createsuperuser
```

Set `role` to `admin` in Django admin. Agents are assigned to stations via the Admin Dashboard.

### 7. Run the development server

```bash
python3 manage.py runserver
```

Open [http://localhost:8000](http://localhost:8000).

## Email verification flow

1. User registers at `/auth/register/`
2. A verification email is sent with a link to `/auth/verify-email/<token>/`
3. User clicks the link — account is activated (`email_verified=True`)
4. User logs in at `/auth/login/` — unverified accounts are blocked

For production, configure SMTP in `.env`:

| Variable | Description |
|----------|-------------|
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | e.g. `smtp.gmail.com` |
| `EMAIL_PORT` | e.g. `587` |
| `EMAIL_USE_TLS` | `True` |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password or app password |
| `DEFAULT_FROM_EMAIL` | Sender address |

## Assigning agents to stations

1. Log in as an **admin** user
2. Go to `/admin-dashboard/`
3. Scroll to **Manage Agents**
4. Select a station from the dropdown next to each agent and click **Assign**

Agents without a station see a message on `/orders/agent/` and cannot process orders until assigned.

## Django user flow

1. **Register** → verify email → **Login**
2. **Upload** at `/upload/` with live price preview
3. **Track** order at `/track/` with visual status timeline
4. **Pay at pickup** — review prints, pay in cash, staff marks order as paid
5. View **receipt** at `/orders/<id>/receipt/` after payment is recorded
6. **Admin/Agent** dashboards for order management and marking payments

## Pricing

| Mode | Price per page |
|------|----------------|
| Black & White | UGX 200 |
| Color | UGX 300 |

Double-sided printing uses half the page count (rounded up) for billing.

## Environment variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` or `False` |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins |
| `CORS_ALLOWED_ORIGINS` | Comma-separated origins for React API |
| `DATABASE_URL` | Database connection string |
| `EMAIL_*` | Email configuration (see above) |
| `DEFAULT_FROM_EMAIL` | Outgoing email sender |

## Running tests

```bash
cd backend
python3 manage.py test --verbosity=2
```

CI runs automatically via GitHub Actions (`.github/workflows/django-ci.yml` and `frontend-ci.yml`).

## Deployment split

| Component | Platform | Notes |
|-----------|----------|-------|
| Django backend | PythonAnywhere | WSGI via Gunicorn, SQLite or external DB |
| React frontend | Vercel | Legacy SPA |

Uploaded files are served via authenticated download at `/orders/<id>/file/` — not publicly accessible.

## Project structure

```
print_hub/
├── backend/
│   ├── accounts/      # Auth, email verification
│   ├── orders/        # Orders, payments, receipts
│   ├── stations/      # Pickup locations
│   ├── templates/     # Django HTML templates
│   └── core/          # Settings, URLs
├── frontend/          # Legacy React app
├── .github/workflows/ # CI pipelines
└── .env.example
```
