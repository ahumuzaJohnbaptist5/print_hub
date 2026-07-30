# core/settings.py
import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-fallback-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'  # ⭐ FORCED True for local

# ⭐ UPDATED FOR LOCAL + RENDER
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.pythonanywhere.com',
    'printlink.pythonanywhere.com',
    'www.printlink.pythonanywhere.com',
    '.trycloudflare.com',
    '.onrender.com',
    'print-hub-jbfe.onrender.com',
]

SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')  # ⭐ Changed to HTTP for local

# CSRF Settings - ⭐ DISABLED SSL FOR LOCAL
CSRF_TRUSTED_ORIGINS = [
    'https://printlink.pythonanywhere.com',
    'http://printlink.pythonanywhere.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://*.pythonanywhere.com',
    'https://*.onrender.com',
    'https://print-hub-jbfe.onrender.com',
]
CSRF_COOKIE_SECURE = False  # ⭐ Changed to False for local
CSRF_COOKIE_HTTPONLY = False  # ⭐ Changed to False for local
CSRF_COOKIE_SAMESITE = 'Lax'

# Session Security - ⭐ DISABLED SSL FOR LOCAL
SESSION_COOKIE_SECURE = False  # ⭐ Changed to False for local
SESSION_COOKIE_HTTPONLY = False  # ⭐ Changed to False for local
SESSION_COOKIE_SAMESITE = 'Lax'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'accounts',
    'orders',
    'stations',
    'payments',
    'finances',
    'notifications',
    'whatsapp_bot',
    # 'core.file_processor',  # ⭐ DISABLED for Render
    'referrals',  # ⭐ DISABLED for now
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # 'orders.context_processors.announcement',  # ⭐ TEMPORARILY DISABLED
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# ⭐ IMPROVED DATABASE CONFIGURATION
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=False,
    )
}

# ⭐ FALLBACK: If DATABASE_URL is not set, use SQLite
if not os.environ.get('DATABASE_URL'):
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'rate-limit-cache',
    }
}

# CORS - ⭐ UPDATED FOR LOCAL
CORS_ALLOW_ALL_ORIGINS = True  # ⭐ Changed to True for local testing
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://printlink.pythonanywhere.com',
    'https://*.pythonanywhere.com',
    'https://*.onrender.com',
    'https://print-hub-jbfe.onrender.com',
]

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kampala'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Login URLs
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Email (Console for PythonAnywhere, or configure SMTP)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'PrintHub <noreply@printlink.com>'

# Payment Settings
PAYMENT_EXPIRY_MINUTES = 30
DEFAULT_MTN_MERCHANT_PHONE = os.getenv('DEFAULT_MTN_MERCHANT_PHONE', '')
DEFAULT_MTN_MERCHANT_NAME = os.getenv('DEFAULT_MTN_MERCHANT_NAME', '')
DEFAULT_AIRTEL_MERCHANT_PHONE = os.getenv('DEFAULT_AIRTEL_MERCHANT_PHONE', '')
DEFAULT_AIRTEL_MERCHANT_NAME = os.getenv('DEFAULT_AIRTEL_MERCHANT_NAME', '')

# Printing
DEFAULT_SLA_MINUTES = 120
BASE_PRICE_BW = 200
COLOR_SURCHARGE = 100
SPIRAL_BINDING_FEE = 1000

# ⭐ SECURITY SETTINGS - ALL DISABLED FOR LOCAL
SECURE_PROXY_SSL_HEADER = None  # ⭐ Set to None for local
SECURE_SSL_REDIRECT = False  # ⭐ Force False
SECURE_BROWSER_XSS_FILTER = False  # ⭐ Disabled for local
SECURE_CONTENT_TYPE_NOSNIFF = False  # ⭐ Disabled for local
X_FRAME_OPTIONS = 'DENY'  # ⭐ Keep this

# Push Notifications (VAPID)
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')

# WhatsApp Cloud API
WHATSAPP_API_TOKEN = os.getenv('WHATSAPP_API_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'printhub_webhook_2024')
WHATSAPP_GROUP_IDS = os.getenv('WHATSAPP_GROUP_IDS', '').split(',') if os.getenv('WHATSAPP_GROUP_IDS') else []
WHATSAPP_BUSINESS_PHONE = os.getenv('WHATSAPP_BUSINESS_PHONE', '')
WHATSAPP_ADMIN_NUMBERS = os.getenv('WHATSAPP_ADMIN_NUMBERS', '').split(',') if os.getenv('WHATSAPP_ADMIN_NUMBERS') else []

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
if not LOGS_DIR.exists():
    LOGS_DIR.mkdir(parents=True)

# ============================================================
# RATE LIMITING
# ============================================================
RATELIMIT_ENABLE = False  # ⭐ Disabled for local testing
RATELIMIT_USE_CACHE = 'default'

# Referral Settings
REFERRAL_BONUS_AMOUNT = 2000  # UGX
REFERRAL_ORDER_BONUS = 1000   # UGX