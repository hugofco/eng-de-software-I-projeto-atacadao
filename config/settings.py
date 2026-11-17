"""
Configurações do projeto WFM Atacadão.

Princípio: **funcionar sem configurar nada** (SQLite + DEBUG) e ser configurável
por variáveis de ambiente (ou arquivo .env) para PostgreSQL/produção.
Veja .env.example para a lista completa.
"""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Leitura de variáveis de ambiente (com mini-suporte a .env, sem dependências)
# --------------------------------------------------------------------------
def _carregar_dotenv(caminho: Path) -> None:
    """Lê linhas CHAVE=valor de um .env. Variáveis já definidas no ambiente vencem."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


_carregar_dotenv(BASE_DIR / ".env")


def env_bool(nome: str, padrao: bool = False) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "sim", "on"}


def env_lista(nome: str, padrao: str = "") -> list[str]:
    return [i.strip() for i in os.environ.get(nome, padrao).split(",") if i.strip()]


# --------------------------------------------------------------------------
# Segurança básica
# --------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", True)

_CHAVE_DEV = "dev-inseguro-nao-use-em-producao"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _CHAVE_DEV)
if not DEBUG and SECRET_KEY == _CHAVE_DEV:
    raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY quando DJANGO_DEBUG=False.")

ALLOWED_HOSTS = env_lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_lista("DJANGO_CSRF_TRUSTED_ORIGINS")

# Endurecimento quando atrás de HTTPS (ligue com DJANGO_HTTPS=True)
if env_bool("DJANGO_HTTPS"):
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# --------------------------------------------------------------------------
# Aplicações (Monolito Modular: um app Django por módulo de negócio)
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Módulos do WFM
    "apps.core",          # Filial, Setor, Cargo, Terminal, painel inicial, diretório
    "apps.accounts",      # Funcionario (usuário), login, RS01-RS03
    "apps.tarefas",       # RS04, RS05, RS10, RS13
    "apps.escalas",       # RS06, RS07, RS11, RS12, RS17
    "apps.ponto",         # RS09, RS14
    "apps.comunicacao",   # RS08, RS15, RS16
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # estáticos em produção (gunicorn)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
                # Contador de não lidos exibido no menu
                "apps.comunicacao.context_processors.nao_lidos",
            ],
        },
    },
]


# --------------------------------------------------------------------------
# Banco de dados: SQLite (início rápido) ou PostgreSQL (alvo do projeto)
# --------------------------------------------------------------------------
if os.environ.get("DB_ENGINE", "sqlite").lower() == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "wfm"),
            "USER": os.environ.get("POSTGRES_USER", "wfm"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "wfm"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --------------------------------------------------------------------------
# Autenticação: CPF ou matrícula como identificador (seção 2.4 do documento)
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.Funcionario"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.MatriculaOuCpfBackend"]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Hash rápido SOMENTE ao rodar `manage.py test` (acelera a suíte; nunca em uso normal).
if len(sys.argv) > 1 and sys.argv[1] == "test":
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


# --------------------------------------------------------------------------
# Internacionalização e RELÓGIO
# --------------------------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
# USE_TZ=True: datas/horas são gravadas em UTC no banco e convertidas só na
# exibição. É o que atende a seção 2.4 ("relógio do servidor central (UTC)").
USE_TZ = True


# --------------------------------------------------------------------------
# Arquivos estáticos (apenas um CSS, sem JavaScript)
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"


# --------------------------------------------------------------------------
# Regras do domínio WFM
# --------------------------------------------------------------------------
# Exige que o registro de ponto venha de um Terminal cadastrado (IP fixo).
WFM_ENFORCE_TERMINAL_IP = env_bool("WFM_ENFORCE_TERMINAL_IP", False)
# Ler o IP real de X-Forwarded-For. Só ligue atrás de um proxy confiável, senão
# o cliente poderia forjar o cabeçalho e burlar a verificação de terminal.
WFM_TRUST_X_FORWARDED_FOR = env_bool("WFM_TRUST_X_FORWARDED_FOR", False)
