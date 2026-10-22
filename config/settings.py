import os
from pathlib import Path
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, 'unsafe-default-secret-key-replace-in-production'),
    TIME_ZONE=(str, 'Europe/Paris'),
    FERNET_KEY=(str, ''),
    DEFAULT_SUPERUSER_EMAIL=(str, 'vincent.foriel@gmail.com'),
)

# Read .env if it exists
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '0.0.0.0', 'web', 'testserver'])

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=['http://localhost:8000', 'http://127.0.0.1:8000'])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party apps
    'rest_framework',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Local apps
    'apps.accounts',
    'apps.events',
    'apps.notifications',
    'apps.scraping',
    'apps.core',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL', default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

# Custom User Model
AUTH_USER_MODEL = 'accounts.CustomUser'

# Authentication Backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth Configuration
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'  # Simplifies setup and local tests
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = env('TIME_ZONE', default='Europe/Paris')
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configuration
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = False

# Security & Fernet Key for reversible UniCA Credentials encryption
FERNET_KEY = env('FERNET_KEY', default='')

# Initial default superuser
DEFAULT_SUPERUSER_EMAIL = env('DEFAULT_SUPERUSER_EMAIL', default='vincent.foriel@gmail.com')

# WebPush VAPID
VAPID_PUBLIC_KEY = env('VAPID_PUBLIC_KEY', default='')
VAPID_PRIVATE_KEY = env('VAPID_PRIVATE_KEY', default='')
VAPID_ADMIN_EMAIL = env('VAPID_ADMIN_EMAIL', default='mailto:vincent.foriel@gmail.com')

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='UniCA Sport Notifier <notifications@sport-notifier.fr>')

# Socialaccount Providers (Google OAuth)
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': env('GOOGLE_OAUTH_CLIENT_ID', default=''),
            'secret': env('GOOGLE_OAUTH_CLIENT_SECRET', default=''),
            'key': ''
        }
    }
}

# Session & Security Settings
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Allows HTMX to read csrftoken cookie if needed
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Derrière Caddy (TLS terminé au proxy) : faire confiance à X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
