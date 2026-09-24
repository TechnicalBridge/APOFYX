"""
Configuracion de Django para APOFYX.

Nada sensible vive aca: las credenciales se leen del archivo .env, que no se
versiona. Ver .env.example y docs/APOFYX.md seccion 14.8.
"""

from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    """Lee una variable del entorno, con valor por defecto."""
    return os.environ.get(name, default)


def env_bool(name, default=False):
    """Interpreta '1', 'true', 'yes', 'on' como verdadero."""
    valor = os.environ.get(name)
    if valor is None:
        return default
    return valor.strip().lower() in {"1", "true", "yes", "on"}


# --- Seguridad -------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-inseguro-cambiar")
DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

# Necesario cuando la app corre en un contenedor y se accede por localhost.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]


# --- Aplicaciones ----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Propias. El nombre de la app define el prefijo de las tablas:
    # crm -> crm_creditor,  assistant -> assistant_intent.
    "crm",
    "assistant",
    # cartera -> cartera_debtor, integracion -> integracion_apikey.
    "cartera",
    "integracion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    #  Con DEBUG=0 Django deja de servir los archivos estaticos: da por hecho
    #  que delante hay un nginx. En el contenedor no lo hay, asi que WhiteNoise
    #  los sirve desde el propio proceso. Va pegado a SecurityMiddleware, que
    #  es donde su documentacion lo pide.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --- Base de datos ---------------------------------------------------------
#
# El esquema ya existe: lo crea sql/AphofyxDB.sql. Los modelos son su espejo y
# se adoptan con  "manage.py migrate --fake-initial"  (ver docs seccion 14.3).
#
# Fuera de Docker la base esta en 127.0.0.1:3307; dentro, compose inyecta
# DB_HOST=db y DB_PORT=3306.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", "apofyx"),
        "USER": env("DB_USER", "apofyx_app"),
        "PASSWORD": env("DB_PASSWORD", "apofyx_pass"),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "3307"),
        "OPTIONS": {
            "charset": "utf8mb4",
            # Hace que MySQL aborte con error en vez de truncar datos en
            # silencio. Sin esto, un texto demasiado largo se guarda cortado.
            "sql_mode": "STRICT_TRANS_TABLES",
        },
        "TEST": {
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_0900_ai_ci",
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Autenticacion ---------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "panel:login"
LOGIN_REDIRECT_URL = "panel:dashboard"
LOGOUT_REDIRECT_URL = "site:home"


# --- Internacionalizacion --------------------------------------------------
#
# La base guarda en UTC, que es lo correcto. TIME_ZONE hace que la interfaz
# muestre hora de Santiago. Sin esto, las fechas del contenedor se ven 3 o 4
# horas adelantadas (ver docs seccion 14.8, problemas frecuentes).

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True


# --- Archivos estaticos ----------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

#  Con DEBUG=0, WhiteNoise sirve lo que dejo collectstatic en STATIC_ROOT y le
#  agrega el hash del contenido al nombre de cada archivo, para que el
#  navegador pueda guardarlos para siempre sin quedarse con una version vieja.
#  En desarrollo se queda el almacenamiento simple, que no obliga a correr
#  collectstatic despues de cada cambio en el CSS.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}


# --- Asistente conversacional ----------------------------------------------
#
# Motor hibrido (docs seccion 9.3): primero reglas desde MySQL; solo si el
# puntaje no alcanza el umbral se consulta a Gemini. Sin GEMINI_API_KEY el
# sitio funciona igual, respondiendo con la intencion 'fallback'.

ASSISTANT = {
    "UMBRAL_CONFIANZA": float(env("ASSISTANT_THRESHOLD", "2.5")),
    "MAX_MENSAJE": 500,
    "GEMINI_API_KEY": env("GEMINI_API_KEY", ""),
    # Un modelo "lite" a proposito: los flash recientes razonan y se comen el
    # presupuesto de salida, devolviendo frases cortadas (ver engine.py).
    "GEMINI_MODEL": env("GEMINI_MODEL", "gemini-3.1-flash-lite"),
    "GEMINI_MAX_TOKENS": int(env("GEMINI_MAX_TOKENS", "400")),
    # La API rechaza cualquier valor bajo 10.000 ms.
    "GEMINI_TIMEOUT_MS": int(env("GEMINI_TIMEOUT_MS", "12000")),
}


# --- DataBridge ------------------------------------------------------------
#
# A donde APOFYX le pasa la cartera que recibe de sus clientes (contrato de
# integracion, TB_web/docs/integracion/). Sin URL o sin clave, el reenvio
# queda APAGADO y APOFYX sigue trabajando solo: recibe, valida y gestiona su
# cartera, y el pago ocurre fuera, como antes. Es la regla R5 del contrato.

DATABRIDGE = {
    "URL": env("DATABRIDGE_URL", ""),
    # La clave que DataBridge le emitio a APOFYX. Solo va en el .env.
    "CLAVE": env("DATABRIDGE_CLAVE", ""),
    # Con quien se identifica APOFYX al declarar su mandato.
    "RUT_AGENCIA": env("APOFYX_RUT", "77305118-6"),
    # Pasados estos dias APOFYX devuelve el caso al acreedor (docs §2.2). Se
    # le informa a DataBridge en el mandato, porque el limite es de APOFYX.
    "MORA_MAXIMA_DIAS": int(env("APOFYX_MORA_MAXIMA", "120")),
    "TIMEOUT_S": int(env("DATABRIDGE_TIMEOUT_S", "10")),
    # Intentar el reenvio apenas se recibe la cartera. Si falla, queda en la
    # bandeja y lo retoma `manage.py despachar_reenvios`.
    "REENVIO_INMEDIATO": env_bool("DATABRIDGE_REENVIO_INMEDIATO", True),
    # Con el que DataBridge firma los eventos que le manda a APOFYX. Lo entrega
    # DataBridge al suscribirse (manage.py suscribirse_a_databridge). Vacio =
    # APOFYX no recibe eventos.
    "SECRETO_EVENTOS": env("DATABRIDGE_SECRETO_EVENTOS", ""),
}
