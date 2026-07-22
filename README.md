# PrintHub - Kabale University Printing Service 
 
Upload documents, pay with MTN/Airtel mobile money, and pick up prints at campus stations. 
 
## Quick Start (Local Development) 
 
### 1. Clone & Setup 
```bash 
git clone https://github.com/ahumuzaJohnbaptist5/print_hub.git 
cd print_hub/backend 
python -m venv venv 
venv\Scripts\activate 
``` 
 
### 2. Install Dependencies 
```bash 
pip install Django djangorestframework django-cors-headers whitenoise python-dotenv Pillow 
``` 
 
### 3. Environment Setup 
Create `.env` file in `backend/`: 
```env 
DEBUG=True 
DJANGO_SECRET_KEY=anything123 
SITE_URL=http://localhost:8000 
``` 
 
### 4. Run Migrations 
```bash 
python manage.py migrate 
``` 
 
### 5. Create Superuser 
```bash 
python manage.py shell 
``` 
```python 
from django.contrib.auth import get_user_model 
User = get_user_model() 
User.objects.create_superuser(username='admin', email='admin@printhub.com', password='admin123', role='admin', email_verified=True, is_staff=True, is_superuser=True) 
exit() 
``` 
 
### 6. Run Server 
```bash 
python manage.py runserver 
``` 
Open http://localhost:8000 
 
## Share Online 
 
### Cloudflare Tunnel 
1. Download cloudflared from https://github.com/cloudflare/cloudflared/releases 
2. Put `cloudflared.exe` on Desktop 
3. Run: `.\cloudflared tunnel --url http://localhost:8000` 
 
## Features 
- Document upload (PDF, DOCX, PPTX, TXT, images) 
- Auto page count detection 
- Live price calculator 
- MTN & Airtel mobile money payments 
- Order tracking with real-time status 
- Agent commission system 
- Admin financial dashboard 
- Push notifications 
- Dark/light theme 
- PWA support (install as app) 
 
## Production 
Hosted at https://printlink.pythonanywhere.com 
 
## Support 
Email: printhub2027@gmail.com 
