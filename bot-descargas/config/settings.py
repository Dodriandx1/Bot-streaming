import os
from zoneinfo import ZoneInfo
from datetime import datetime

# ─── CREDENCIALES API ───
API_ID    = int(os.environ.get("API_ID", "0"))
API_HASH  = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ─── BASE DE DATOS ───
MONGO_URI = os.environ.get("MONGO_URI", "")

# ─── CONFIGURACIÓN DE ADMINS ───
_raw_admin_ids = os.environ.get("ADMIN_IDS", "0")
ADMIN_ID  = int(_raw_admin_ids.split(",")[0].strip()) if _raw_admin_ids.strip() else 0
AUTH_FILE = os.environ.get("AUTH_FILE", "authorized_users.json")

# ─── DIRECTORIOS ───
DOWNLOAD_DIR = "/tmp/downloads/"
os.makedirs(DOWNLOAD_DIR, mode=0o777, exist_ok=True)

# ─── FIRMA DEL BOT ───
BOT_SIGNATURE = "✪ Bot By → @The_canst & @Ryota_YT"

# ─── ZONA HORARIA ───
ECUADOR_TZ = ZoneInfo("America/Guayaquil")
def now_ec() -> datetime:
    """Hora actual en la zona horaria de Ecuador (UTC-5), tz-aware."""
    return datetime.now(ECUADOR_TZ)

# ─── PLANES DE SUSCRIPCIÓN ───
PLANES = {
    "free": {
        "nombre": "Gratuito", "precio": 0, "moneda": "USD",
        "limite_total": 5, "limite_mensual": 50, "calidad_maxima": "480p",
        "torrent_soportado": False, "publicidad": True,
    },
    "basico": {
        "nombre": "Básico", "precio": 4.99, "moneda": "USD",
        "limite_total": 999999, "limite_mensual": 999999, "calidad_maxima": "720p",
        "torrent_soportado": False, "publicidad": False,
    },
    "premium": {
        "nombre": "Premium", "precio": 9.99, "moneda": "USD",
        "limite_total": 999999, "limite_mensual": 999999, "calidad_maxima": "1080p",
        "torrent_soportado": True, "publicidad": False,
    },
    "pro": {
        "nombre": "Pro", "precio": 19.99, "moneda": "USD",
        "limite_total": 999999, "limite_mensual": 999999, "calidad_maxima": "4K",
        "torrent_soportado": True, "publicidad": False,
    },
}

# Jerarquía de planes para comparar permisos
PLAN_HIERARCHY = {"free": 0, "basico": 1, "premium": 2, "pro": 3}
