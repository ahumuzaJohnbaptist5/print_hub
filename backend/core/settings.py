# core/settings.py
import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables (for local .env, ignored in production)
load_dotenv(BASE_DIR / '.env')

# ==============================================================================
# 1. CORE SECURITY SETTINGS (Strict Production Defaults)
# ==============================================================================
# Will intentionally crash on startup if SECRET_KEY is missing in Render/.env
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set for Django application. Set it in .env or Render Dashboard.")

# Default to False in production. Only set DEBUG=True explicitly in local .env
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Must be explicitly set in Render Dashboard or .env
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000')

# ==============================================================================
# 2. APPLICATION DEFINITION
# ==============================================================================
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
    'cloudinary',            # Required for production file storage
    'cloudinary_storage',    # Required for production file storage
    'accounts',
    'orders',
    'stations',
    'payments',
    'finances',
    'notifications',
    'whatsapp_bot',
    'referrals',
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
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# ==============================================================================
# 3. DATABASE (Strict PostgreSQL via Neon)
# ==============================================================================
# Will crash if DATABASE_URL is missing. No SQLite fallback in production.
if os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,  # Neon requires SSL
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ==============================================================================
# 4. SECURITY & COOKIES (Bulletproof for Render)
# ==============================================================================
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000').split(',')
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://localhost:8000').split(',')

# Enforce secure cookies in production
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False  # Keep False for DRF/JS compatibility
CSRF_COOKIE_SAMESITE = 'Lax'

SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# HSTS and SSL Redirects (Only in production)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if not DEBUG else None
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_BROWSER_XSS_FILTER = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = not DEBUG
X_FRAME_OPTIONS = 'DENY'

# ==============================================================================
# 5. CORS (Strict Origins Only)
# ==============================================================================
CORS_ALLOW_ALL_ORIGINS = DEBUG  # NEVER true in production
CORS_ALLOW_CREDENTIALS = True

# ==============================================================================
# 6. REST FRAMEWORK
# ==============================================================================
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

# ==============================================================================
# 7. STATIC & MEDIA FILES (Cloudinary for Production)
# ==============================================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Cloudinary Configuration (Mandatory for Render)
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', ''),
}

if not DEBUG and CLOUDINARY_STORAGE['CLOUD_NAME']:
    STORAGES = {
        "default": {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ==============================================================================
# 8. GENERAL SETTINGS
# ==============================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.CustomUser'
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kampala'
USE_I18N = True
USE_TZ = True

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# ==============================================================================
# 9. EXTERNAL SERVICES (Email, Payments, WhatsApp, Rate Limiting)
# ==============================================================================
# ⭐ UPDATED: Now reads from Environment Variables for SMTP!
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'PrintHub <noreply@printlink.com>')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = os.environ.get('EMAIL_PORT', 587)
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

PAYMENT_EXPIRY_MINUTES = 30
DEFAULT_MTN_MERCHANT_PHONE = os.getenv('DEFAULT_MTN_MERCHANT_PHONE', '')
DEFAULT_MTN_MERCHANT_NAME = os.getenv('DEFAULT_MTN_MERCHANT_NAME', '')
DEFAULT_AIRTEL_MERCHANT_PHONE = os.getenv('DEFAULT_AIRTEL_MERCHANT_PHONE', '')
DEFAULT_AIRTEL_MERCHANT_NAME = os.getenv('DEFAULT_AIRTEL_MERCHANT_NAME', '')

DEFAULT_SLA_MINUTES = 120
BASE_PRICE_BW = 200
COLOR_SURCHARGE = 100
SPIRAL_BINDING_FEE = 1000

VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')

WHATSAPP_API_TOKEN = os.getenv('WHATSAPP_API_TOKEN', '')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
WHATSAPP_VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'printhub_webhook_2024')
WHATSAPP_GROUP_IDS = os.getenv('WHATSAPP_GROUP_IDS', '').split(',') if os.getenv('WHATSAPP_GROUP_IDS') else []
WHATSAPP_BUSINESS_PHONE = os.getenv('WHATSAPP_BUSINESS_PHONE', '')
WHATSAPP_ADMIN_NUMBERS = os.getenv('WHATSAPP_ADMIN_NUMBERS', '').split(',') if os.getenv('WHATSAPP_ADMIN_NUMBERS') else []

RATELIMIT_ENABLE = os.environ.get('RATELIMIT_ENABLE', 'False').lower() == 'true'
RATELIMIT_USE_CACHE = 'default'

REFERRAL_BONUS_AMOUNT = 2000
REFERRAL_ORDER_BONUS = 1000

# ==============================================================================
# 10. LOGGING
# ==============================================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}