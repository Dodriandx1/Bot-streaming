import os
import re
import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message

from config.settings import DOWNLOAD_DIR, BOT_SIGNATURE
from core.utils import make_bar
from core.queue import download_queue
from processors.uploader import safe_edit, upload_smart_file
from engines.mega_engine import mega_download
from engines.torrent_engine import procesar_torrent
from engines.social_engine import procesar_social
from engines.music_engine import procesar_audio

# ─── ESTADOS GLOBALES ───
active_tasks: dict = {}

# ─── FUNCIÓN PRINCIPAL DE PROCESAMIENTO ───
async def procesar_descarga(client: Client, message: Message, url: str,
                             uname: str, uid: int, queue_label: str,
                             want_subs: bool = False):
    """Detecta el tipo de enlace y delega al motor correspondiente."""

    # ─── Limpieza de dominios espejo ───
    mirrors = {
        "flashwish.com": "streamwish.com", "callistanise.com": "vidhide.com",
        "swishdesu.com": "streamwish.com", "filelions.com": "streamwish.com",
        "filelions.to": "streamwish.com", "vidhidepro.com": "vidhide.com",
        "vidhideplus.com": "vidhide.com",
    }
    for mirror, main in mirrors.items():
        if mirror in url.lower():
            url = url.replace(mirror, main)
            break

    # ─── Clasificación del enlace ───
    VIDEO_HOSTS = ["streamwish", "voe", "vidhide", "filemoon", "mixdrop",
                   "mp4upload", "streamtape", "flashwish", "callistanise",
                   "filelions", "swishdesu"]

    is_mega = "mega.nz" in url
    is_torrent = url.lower().startswith("magnet:") or url.lower().endswith(".torrent")
    is_audio = ("spotify.com" in url.lower() or "soundcloud.com" in url.lower()
                or "youtube.com" in url.lower() or "youtu.be" in url.lower())
    is_social = any(d in url.lower() for d in [
        "tiktok.com", "instagram.com", "twitter.com", "x.com", "facebook.com", "fb.com"
    ])
    is_video_host = any(h in url.lower() for h in VIDEO_HOSTS)

    task_id = f"{uid}_{int(time.time())}"

    # ─── ENRUTAMIENTO ───
    try:
        # ── MEGA ──
        if is_mega:
            msg = await message.reply_text(
                f"╭ Task By → 「{uname}」\n┊ 🔄 Conectando a MEGA...\n"
                f"╰ Mode     : #MEGA\n\n{BOT_SIGNATURE}")
            
            start_t = time.time()
            async def _progress(curr, total):
                from processors.uploader import upload_progress
                pct = (curr / total * 100) if total > 0 else 0
                bar = make_bar(pct)
                elapsed = time.time() - start_t
                speed = curr / elapsed if elapsed > 0 else 0
                from core.utils import get_readable_size, get_readable_time
                try:
                    await safe_edit(msg,
                        f"╭ Task By → 「{uname}」\n┊ [{bar}] {pct:.2f}%\n"
                        f"┊ Done     : {get_readable_size(curr)}\n"
                        f"┊ Total    : {get_readable_size(total)}\n"
                        f"┊ Speed    : {get_readable_size(speed)}/s\n"
                        f"╰ Mode     : #MEGA\n\n{BOT_SIGNATURE}")
                except Exception:
                    pass

            path, title = await mega_download(url, DOWNLOAD_DIR, task_id, progress_cb=_progress)
            await safe_edit(msg, f"╭ Task By → 「{uname}」\n┊ ⬆️ Subiendo a Telegram...\n╰──────────────\n\n{BOT_SIGNATURE}")
            await upload_smart_file(client, message, path, msg, uname, task_id, title=title)
            try: await msg.delete()
            except: pass

        # ── TORRENT ──
        elif is_torrent:
            await procesar_torrent(client, message, url, uname, task_id,
                                    is_magnet=url.lower().startswith("magnet:"))

        # ── AUDIO (YouTube, Spotify, SoundCloud) ──
        elif is_audio and not is_social:
            await procesar_audio(client, message, url, uname, task_id)

        # ── REDES SOCIALES Y VIDEO HOSTS ──
        elif is_social or is_video_host:
            await procesar_social(client, message, url, uname, uid, task_id,
                                   want_subs=want_subs)

        else:
            await message.reply_text(
                f"⚠️ Enlace no soportado:\n<code>{url[:100]}</code>\n\n{BOT_SIGNATURE}",
                parse_mode=enums.ParseMode.HTML)

    except Exception as e:
        err = str(e)[:200]
        try:
            await message.reply_text(
                f"❌ Error procesando enlace:\n<code>{err}</code>\n\n{BOT_SIGNATURE}",
                parse_mode=enums.ParseMode.HTML)
        except Exception:
            pass


# ─── FILTRO: EXCLUIR COMANDOS DEL DETECTOR DE TEXTO ───
_EXCLUDE_CMDS = [
    "start", "stat", "reset", "id", "addid", "rmid", "setplan",
    "plan", "getcode", "coms", "cancel", "cancelar", "admin", "remadmin",
    "users", "audio", "ping", "queue", "encode", "torrent", "cookies",
    "play", "playv", "search", "buscar", "musica", "música", "sm",
    "comic", "comicpdf", "pdf", "doc", "gdrive", "a", "anime",
    "perfil", "obs", "juntar", "recortar", "crearwm", "spam", "config",
    "crfiles", "crcookies", "help", "ayuda",
]


# ─── HANDLER PRINCIPAL: DETECTA ENLACES EN TEXTO ───
@bot.on_message(
    filters.text
    & ~filters.command(_EXCLUDE_CMDS)
    & ~filters.regex(r"^/cancel_"),
)
async def handle_text_input(client: Client, message: Message):
    """Detecta enlaces en el texto y los encola."""
    uid = message.from_user.id
    raw_text = (message.text or "").strip()

    # ── Verificación de autorización (importada desde core) ──
    from handlers.commands import is_user_authorized
    if not is_user_authorized(uid):
        return await message.reply_text(
            f"⛔ **No autorizado**\n\n"
            f"🆔 Tu ID: <code>{uid}</code>\n"
            f"Necesitas que un Admin te autorice.\n\n{BOT_SIGNATURE}",
            parse_mode=enums.ParseMode.HTML)

    # ── Detectar enlaces ──
    urls = re.findall(r"(?:https?://|magnet:\?)[^\s]+", raw_text)
    if not urls:
        return

    want_subs = bool(re.search(r"(?:^|\s)-lat(?:\s|$)", raw_text, re.IGNORECASE))
    uname = message.from_user.first_name

    for i, url in enumerate(urls, 1):
        url = re.sub(r"\s*-lat\s*$", "", url, flags=re.IGNORECASE).strip()
        label = f"Cola: {i}/{len(urls)}"
        await download_queue.put((client, message, url, uname, uid, label, want_subs))

    queued = len(urls)
    subs_note = " 🔤 (-lat)" if want_subs else ""
    q_size = download_queue.qsize()

    await message.reply_text(
        f"📥 <b>{queued} enlace(s) añadido(s) a la cola.</b>{subs_note}\n"
        f"🚦 Tareas en espera: {q_size}\n\n{BOT_SIGNATURE}",
        parse_mode=enums.ParseMode.HTML)
