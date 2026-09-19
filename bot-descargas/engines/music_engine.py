import os
import glob
import time
import asyncio
import yt_dlp
from pyrogram import Client, enums
from pyrogram.types import Message

from config.settings import DOWNLOAD_DIR, BOT_SIGNATURE
from core.utils import get_readable_size, make_bar
from processors.uploader import safe_edit, upload_progress, download_progress, _stats

def _youtube_cookie_file() -> str | None:
    """Devuelve el primer archivo cookies.txt válido."""
    bot_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(bot_dir, "cookies.txt"),
        "cookies.txt",
        "/tmp/cookies.txt",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.path.getsize(path) > 32:
            return path
    return None

async def procesar_audio(client: Client, message: Message, url: str, uname: str, task_id: str):
    """Descarga el audio de un enlace (YouTube, SoundCloud, etc.) como MP3."""
    msg = await message.reply_text(
        f"╭ Task By → 「{uname}」\n┊ 🎵 Iniciando descarga de audio...\n"
        f"╰ Mode     : #AudioMode\n\n{BOT_SIGNATURE}"
    )
    path = None
    try:
        active_tasks = {"dummy": "RUNNING"}  # Placeholder (en producción viene de core)
        loop = asyncio.get_running_loop()
        start_t = time.time()
        captured = {"title": "", "artist": ""}

        def ydl_hook(d):
            if d["status"] == "downloading":
                curr = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if total > 0:
                    asyncio.run_coroutine_threadsafe(
                        download_progress(curr, total, msg, start_t, uname, task_id, "yt-dlp", "#AudioMode"),
                        loop)

        def run_ydl_audio():
            opts = {
                "outtmpl": f"{DOWNLOAD_DIR}{task_id}_%(title)s.%(ext)s",
                "format": "bestaudio/best",
                "noplaylist": True,
                "progress_hooks": [ydl_hook],
                "quiet": True, "no_warnings": True,
                "rm_cachedir": True, "nocheckcertificate": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }],
            }
            cookie = _youtube_cookie_file()
            if cookie:
                opts["cookiefile"] = cookie

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info:
                    captured["title"] = info.get("title", "Audio")
                    captured["artist"] = info.get("uploader", "Desconocido")

        await asyncio.wait_for(asyncio.to_thread(run_ydl_audio), timeout=900)

        files = sorted(glob.glob(f"{DOWNLOAD_DIR}{task_id}_*.mp3"), key=os.path.getsize)
        if not files:
            raise Exception("No se pudo descargar o convertir el audio.")
        path = files[0]

        await safe_edit(msg, f"╭ Task By → 「{uname}」\n┊ ⬆️ Subiendo MP3...\n╰ Mode     : #AudioMode\n\n{BOT_SIGNATURE}")
        await client.send_audio(
            chat_id=message.chat.id, audio=path,
            title=captured["title"][:60], performer=captured["artist"][:60],
            caption=f"🎵 <b>{captured['title']}</b>\n\n{BOT_SIGNATURE}",
            parse_mode=enums.ParseMode.HTML
        )
        _stats["downloads"] += 1
        try: await msg.delete()
        except Exception: pass

    except (asyncio.CancelledError, Exception) as e:
        is_cancel = isinstance(e, asyncio.CancelledError) or "USER_CANCELLED" in str(e)
        err = "🛑 Descarga cancelada." if is_cancel else f"❌ Error: {str(e)[:200]}"
        try: await safe_edit(msg, f"╭ Task By → 「{uname}」\n┊ {err}\n╰──────────────\n\n{BOT_SIGNATURE}")
        except Exception: pass
    finally:
        for f in glob.glob(f"{DOWNLOAD_DIR}{task_id}_*"):
            try: os.remove(f)
            except Exception: pass

# ─── BÚSQUEDA EN YOUTUBE ───
async def _yt_search(query: str, n: int = 5) -> list[dict]:
    def _do():
        opts = {
            "quiet": True, "no_warnings": True,
            "extract_flat": True, "skip_download": True,
            "rm_cachedir": True, "nocheckcertificate": True,
            "extractor_args": {"youtube": {"player_client": ["ios", "android", "mweb"]}}
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
                if not info or "entries" not in info:
                    return []
                return [
                    {
                        "id": e.get("id", ""),
                        "title": (e.get("title") or "Sin título")[:80],
                        "uploader": (e.get("uploader") or e.get("channel") or "?")[:40],
                        "duration": e.get("duration") or 0,
                        "url": f"https://www.youtube.com/watch?v={e.get('id', '')}",
                    }
                    for e in (info.get("entries") or [])
                    if e and e.get("id")
                ]
        except Exception as e:
            print(f"Error en búsqueda ytsearch: {e}")
            return []
    return await asyncio.to_thread(_do)

def _fmt_dur(secs) -> str:
    if not secs: return "?:??"
    secs = int(secs)
    h, m, s = secs // 3600, (secs % 3600) // 60, secs % 60
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"
