"""
Configuración de FFmpeg por usuario
──────────────────────────────────────
Guarda y recupera los ajustes de conversión de video de cada usuario.
También maneja el menú interactivo de /config.
"""

import os
import json
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)

from config.settings import BOT_SIGNATURE

# ─── ARCHIVO DE CONFIGURACIÓN ───
CONFIG_FILE = "ffmpeg_user_configs.json"

# ─── CONFIGURACIÓN POR DEFECTO ───
_DEFAULT_CONFIG = {
    "quality":  "original",     # original | alta | media | baja | rapida | ultra
    "vcodec":   "h264",         # h264 | h265 | copy
    "acodec":   "aac",          # aac | mp3 | opus | copy
    "wm_ass_path": None,        # Ruta al archivo .ass de marca de agua
    "spam_wm":  "No",           # "Sí" | "No"
}

# ─── CACHÉ EN MEMORIA ───
_user_configs: dict = {}


# ═══════════════════════════════════════════════════════════════════
#  PERSISTENCIA
# ═══════════════════════════════════════════════════════════════════

def _load_configs():
    global _user_configs
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                _user_configs = json.load(f)
        except Exception:
            _user_configs = {}


def _save_configs():
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(_user_configs, f, indent=2)
    except Exception as e:
        print(f"[ffmpeg_config] error guardando: {e}")


_load_configs()


# ═══════════════════════════════════════════════════════════════════
#  API PÚBLICA
# ═══════════════════════════════════════════════════════════════════

def get_default_config(uid: int) -> dict:
    """Devuelve la configuración de un usuario (crea una por defecto si no existe)."""
    uid_str = str(uid)
    if uid_str not in _user_configs:
        _user_configs[uid_str] = dict(_DEFAULT_CONFIG)
        _save_configs()
    # Fusionar con defaults por si añadimos nuevos campos después
    merged = dict(_DEFAULT_CONFIG)
    merged.update(_user_configs[uid_str])
    return merged


def set_config_value(uid: int, key: str, value):
    """Establece un valor de configuración para un usuario."""
    uid_str = str(uid)
    if uid_str not in _user_configs:
        _user_configs[uid_str] = dict(_DEFAULT_CONFIG)
    _user_configs[uid_str][key] = value
    _save_configs()


# ═══════════════════════════════════════════════════════════════════
#  MENÚ INTERACTIVO DE /config
# ═══════════════════════════════════════════════════════════════════

_QUALITY_LABELS = {
    "original": "🎬 Original (CRF 18)",
    "alta":     "✨ Alta (CRF 20)",
    "media":    "⚖️ Media (CRF 23)",
    "baja":     "📉 Baja (CRF 28)",
    "rapida":   "⚡ Rápida (CRF 26)",
    "ultra":    "🚀 Ultra Rápida (CRF 30)",
}
_VCODEC_LABELS = {
    "h264": "🎞️ H.264 (compatible)",
    "h265": "🎥 H.265 / HEVC",
    "copy": "📦 Copiar (sin recodificar)",
}
_ACODEC_LABELS = {
    "aac":  "🎵 AAC 192k",
    "mp3":  "🎵 MP3 192k",
    "opus": "🎵 Opus 128k",
    "copy": "📦 Copiar (sin recodificar)",
}


def _config_main_text(uid: int) -> str:
    cfg = get_default_config(uid)
    wm_activo = cfg.get("spam_wm", "No") == "Sí" and cfg.get("wm_ass_path")
    wm_path = cfg.get("wm_ass_path") or "—"
    wm_name = os.path.basename(wm_path) if wm_path != "—" else "—"
    return (
        f"╭─「 ⚙️ Configuración FFmpeg 」\n"
        f"├──────────────────────────\n"
        f"┊ 🎬 <b>Calidad:</b> {_QUALITY_LABELS.get(cfg['quality'], '—')}\n"
        f"┊ 🎞️ <b>Video:</b>   {_VCODEC_LABELS.get(cfg['vcodec'], '—')}\n"
        f"┊ 🎵 <b>Audio:</b>   {_ACODEC_LABELS.get(cfg['acodec'], '—')}\n"
        f"├──────────────────────────\n"
        f"┊ 💧 <b>Marca de agua:</b> {'✅ ' + wm_name if wm_activo else '❌ Desactivada'}\n"
        f"╰──────────────────────────\n\n{BOT_SIGNATURE}"
    )


def _config_kb(uid: int) -> InlineKeyboardMarkup:
    cfg = get_default_config(uid)
    wm_on = cfg.get("spam_wm", "No") == "Sí"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Calidad", callback_data="cfg_quality")],
        [InlineKeyboardButton("🎞️ Códec de Video", callback_data="cfg_vcodec"),
         InlineKeyboardButton("🎵 Códec de Audio", callback_data="cfg_acodec")],
        [InlineKeyboardButton(
            f"💧 Marca de agua: {'ON ✅' if wm_on else 'OFF ❌'}",
            callback_data="cfg_toggle_wm")],
        [InlineKeyboardButton("📖 Ayuda de comandos", callback_data="cfg_help")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="close_panel")],
    ])


async def send_main_config_menu(client: Client, message: Message, uid: int):
    """Muestra el menú principal de configuración."""
    await message.reply_text(
        _config_main_text(uid),
        parse_mode=enums.ParseMode.HTML,
        reply_markup=_config_kb(uid),
    )


def register_ffmpeg_config_handlers(bot: Client, is_admin_fn, signature: str):
    """Registra los handlers de callback para el menú /config."""

    @bot.on_callback_query(filters.regex(r"^cfg_quality$"))
    async def cb_cfg_quality(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        rows = [[InlineKeyboardButton(label, callback_data=f"cfg_set:quality:{key}")]
                for key, label in _QUALITY_LABELS.items()]
        rows.append([InlineKeyboardButton("⬅️ Volver", callback_data="cfg_back")])
        await cb.message.edit_text(
            "╭─「 🎬 Calidad de Video 」\n┊\n"
            "┊ Selecciona el preset de calidad:\n"
            "┊ (CRF más bajo = mejor calidad, archivo más grande)\n"
            f"╰──────────────────────────\n\n{signature}",
            reply_markup=InlineKeyboardMarkup(rows))
        await cb.answer()

    @bot.on_callback_query(filters.regex(r"^cfg_vcodec$"))
    async def cb_cfg_vcodec(client: Client, cb: CallbackQuery):
        rows = [[InlineKeyboardButton(label, callback_data=f"cfg_set:vcodec:{key}")]
                for key, label in _VCODEC_LABELS.items()]
        rows.append([InlineKeyboardButton("⬅️ Volver", callback_data="cfg_back")])
        await cb.message.edit_text(
            "╭─「 🎞️ Códec de Video 」\n┊\n"
            "┊ Elige el códec de salida:\n"
            "┊ • H.264 = máxima compatibilidad\n"
            "┊ • H.265 = mejor compresión (más lento)\n"
            "┊ • Copiar = no recodifica (solo remux)\n"
            f"╰──────────────────────────\n\n{signature}",
            reply_markup=InlineKeyboardMarkup(rows))
        await cb.answer()

    @bot.on_callback_query(filters.regex(r"^cfg_acodec$"))
    async def cb_cfg_acodec(client: Client, cb: CallbackQuery):
        rows = [[InlineKeyboardButton(label, callback_data=f"cfg_set:acodec:{key}")]
                for key, label in _ACODEC_LABELS.items()]
        rows.append([InlineKeyboardButton("⬅️ Volver", callback_data="cfg_back")])
        await cb.message.edit_text(
            "╭─「 🎵 Códec de Audio 」\n┊\n"
            "┊ Elige el códec de audio:\n"
            f"╰──────────────────────────\n\n{signature}",
            reply_markup=InlineKeyboardMarkup(rows))
        await cb.answer()

    @bot.on_callback_query(filters.regex(r"^cfg_set:(quality|vcodec|acodec):(.+)$"))
    async def cb_cfg_set(client: Client, cb: CallbackQuery):
        key = cb.matches[0].group(1)
        value = cb.matches[0].group(2)
        set_config_value(cb.from_user.id, key, value)
        await cb.answer(f"✅ Actualizado")
        await cb.message.edit_text(
            _config_main_text(cb.from_user.id),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=_config_kb(cb.from_user.id))

    @bot.on_callback_query(filters.regex(r"^cfg_toggle_wm$"))
    async def cb_cfg_toggle_wm(client: Client, cb: CallbackQuery):
        uid = cb.from_user.id
        cfg = get_default_config(uid)
        if not cfg.get("wm_ass_path"):
            await cb.answer(
                "⚠️ Primero sube un archivo .ass o créalo con /crearwm",
                show_alert=True)
            return
        new_state = "No" if cfg.get("spam_wm", "No") == "Sí" else "Sí"
        set_config_value(uid, "spam_wm", new_state)
        await cb.answer(f"Marca de agua: {'ACTIVADA ✅' if new_state == 'Sí' else 'DESACTIVADA ❌'}")
        await cb.message.edit_text(
            _config_main_text(uid),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=_config_kb(uid))

    @bot.on_callback_query(filters.regex(r"^cfg_back$"))
    async def cb_cfg_back(client: Client, cb: CallbackQuery):
        await cb.message.edit_text(
            _config_main_text(cb.from_user.id),
            parse_mode=enums.ParseMode.HTML,
            reply_markup=_config_kb(cb.from_user.id))
        await cb.answer()

    @bot.on_callback_query(filters.regex(r"^cfg_help$"))
    async def cb_cfg_help(client: Client, cb: CallbackQuery):
        await cb.message.edit_text(
            f"╭─「 📖 Ayuda de Configuración 」\n┊\n"
            f"┊ 🎬 <b>Calidad:</b> Ajusta el CRF de compresión.\n"
            f"┊ • Original = sin pérdida visible\n"
            f"┊ • Ultra Rápida = archivo más pequeño, más rápido\n┊\n"
            f"┊ 🎞️ <b>Códec de Video:</b>\n"
            f"┊ • H.264 = compatible con todo\n"
            f"┊ • H.265 = mejor compresión, más lento\n"
            f"┊ • Copiar = no recodifica (solo remux)\n┊\n"
            f"┊ 🎵 <b>Códec de Audio:</b>\n"
            f"┊ • AAC = estándar, buena calidad\n"
            f"┊ • MP3 = máxima compatibilidad\n"
            f"┊ • Opus = mejor compresión\n"
            f"┊ • Copiar = no recodifica el audio\n┊\n"
            f"┊ 💧 <b>Marca de agua:</b>\n"
            f"┊ • Activa/desactiva tu .ass personal\n"
            f"┊ • Sube uno o créalo con /crearwm\n"
            f"╰──────────────────────────\n\n{signature}",
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Volver", callback_data="cfg_back")]]))
        await cb.answer()
