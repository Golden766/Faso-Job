from pathlib import Path
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
DEBUG = os.getenv('DEBUG', 'True').lower() in {'1', 'true', 'yes', 'on'}
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'offres',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'offres.twofactor_middleware.TwoFactorRequiredMiddleware',
]

ROOT_URLCONF = 'plateforme_offres.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'plateforme_offres.wsgi.application'

USE_POSTGRES = os.getenv('USE_POSTGRES', 'False').lower() in {'1', 'true', 'yes', 'on'}
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
# Les tests s'exécutent toujours dans une base SQLite en mémoire : ils ne doivent
# jamais créer ni supprimer de base sur l'instance PostgreSQL distante.
RUNNING_TESTS = 'test' in sys.argv

if RUNNING_TESTS:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
elif USE_POSTGRES and DATABASE_URL and 'YOUR_PROJECT' not in DATABASE_URL and 'YOUR_PASSWORD' not in DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': parsed.path.lstrip('/') or os.getenv('DB_NAME', 'postgres'),
            'USER': parsed.username or os.getenv('DB_USER', 'postgres'),
            'PASSWORD': parsed.password or os.getenv('DB_PASSWORD', 'postgres'),
            'HOST': parsed.hostname or os.getenv('DB_HOST', 'localhost'),
            'PORT': str(parsed.port or os.getenv('DB_PORT', '5432')),
            'OPTIONS': {'sslmode': 'require'},
        }
    }
elif USE_POSTGRES:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'plateforme_offres'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'OPTIONS': {'sslmode': 'require'} if 'supabase' in os.getenv('DB_HOST', '') else {},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000').split(',')
    if origin.strip()
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr'
LANGUAGES = [('fr', 'Français')]
TIME_ZONE = 'Africa/Ouagadougou'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Envoi d e-mails. Par defaut, tout est ecrit dans la console : aucun
# message ne sort de la machine en developpement. Pour un envoi reel,
# renseigner les variables EMAIL_* dans le fichier .env.
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587') or 587)
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in {'1', 'true', 'yes', 'on'}
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', '') or EMAIL_HOST_USER

# Adresse utilisee comme expediteur des notifications internes.
NOTIFICATION_SENDER = os.getenv('NOTIFICATION_SENDER', '') or DEFAULT_FROM_EMAIL

# Service d intelligence artificielle utilise par la veille.
#
# Les trois reglages sont lus dans le fichier .env : une valeur reelle
# ne doit jamais etre versionnee, et le changement de modele ne doit
# jamais demander une modification du code.
#
# Exemples d adresses compatibles avec l'interface OpenAI :
#   AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
#   AI_BASE_URL=https://openrouter.ai/api/v1
#
# Les modeles gratuits declines par ces services changeront : on change
# AI_MODEL dans le .env, le code suit.
AI_BASE_URL = '' if RUNNING_TESTS else os.getenv('AI_BASE_URL', '').strip()
AI_API_KEY = '' if RUNNING_TESTS else os.getenv('AI_API_KEY', '').strip()
AI_MODEL = '' if RUNNING_TESTS else os.getenv('AI_MODEL', '').strip()

# Delai maximal d'attente du service, en secondes.
AI_REQUEST_TIMEOUT = int(os.getenv('AI_REQUEST_TIMEOUT', '60') or 60)

# Certains services savent rendre un JSON strict. Ce reglage n est
# active que si le service le supporte.
AI_JSON_MODE = (
    False
    if RUNNING_TESTS
    else os.getenv('AI_JSON_MODE', 'False').lower() in {'1', 'true', 'yes', 'on'}
)

# Recherche sur le web, pour l assistant de decouverte des sources.
#
# C'est facultatif : sans ces reglages, l assistant s appuie sur les
# adresses que le modele propose. Avec eux, il elargit sa recherche.
#
# Deux solutions possibles, une seule a la fois :
#   - Brave Search (inscription gratuite) : renseignez la cle ;
#   - SearXNG (auto-heberge, gratuit)     : renseignez l adresse.
BRAVE_SEARCH_API_KEY = (
    '' if RUNNING_TESTS else os.getenv('BRAVE_SEARCH_API_KEY', '').strip()
)
SEARXNG_URL = '' if RUNNING_TESTS else os.getenv('SEARXNG_URL', '').strip()
