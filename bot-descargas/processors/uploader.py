import os
import json
import time
import asyncio
import subprocess
from pyrogram import Client, enums
from pyrogram.types import Message

from config.settings import BOT_SIGNATURE
from core.utils import get_readable_size, get_readable_time, make_bar

# ─── ESTADÍSTICAS GLOBALES (se importan desde core/database en el futuro) ───
_stats = {"downloads": 0, "fallidos": 0, "cancelados": 0, "bytes": 0}
last_updates: dict = {}
active_tasks: dict = {}

# ─── EXTRACCIÓN DE MINIATURAS Y METADATOS ───
def extract_thumbnail(video_path: str):
    thumb = video_path + ".jpg"
    try:
        # Intento 1: Segundo 10
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-ss", "00:00:10", "-i", video_path,
             "-vframes", "1", "-vf", "scale=320:-1", "-q:v", "2", thumb, "-y"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15, check=True
        )
        if os.path.exists(thumb) and os.path.getsize(thumb) > 0:
            return thumb
        # Intento 2: Segundo 1 (videos cortos)
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-ss", "00:00:01", "-i", video_path,
             "-vframes", "1", "-vf", "scale=320:-1", "-q:v", "2", thumb, "-y"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=15, check=True
        )
        return thumb if os.path.exists(thumb) else None
    except Exception:
        return None

def get_video_meta(video_path: str) -> dict:
    try:
        cmd = ["ffprobe", "-v", "error",
               "-probesize", "50M", "-analyzeduration", "100M",
               "-select_streams", "v:0",
               "-show_entries", "format=duration:stream=width,height",
               "-of", "json", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        data = json.loads(result.stdout or "{}")
        width, height, duration = 1280, 720, 0
        if "format" in data and "duration" in data["format"]:
            try: duration = int(float(data["format"]["duration"]))
            except: pass
        if "streams" in data and len(data["streams"]) > 0:
            stream = data["streams"][0]
            width = int(stream.get("width", 1280))
            height = int(stream.get("height", 720))
            if duration == 0 and "duration" in stream:
                try: duration = int(float(stream["duration"]))
                except: pass
        return {"width": width, "height": height, "duration": duration}
    except Exception as e:
        print(f"[Meta Error]: {e}")
        return {"width": 1280, "height": 720, "duration": 0}

async def _ensure_jpeg(path: str) -> str:
    """Convierte .webp/.png/.bmp a .jpg para que Telegram acepte la foto."""
    lower = path.lower()
    if not lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".avif")):
        return path
    out = path.rsplit(".", 1)[0] + "_conv.jpg"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", path, "-q:v", "2", "-f", "mjpeg", out,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=30)
        if os.path.exists(out) and os.path.getsize(out) > 500:
            return out
    except Exception:
        pass
    return path

# ─── PANELES DE PROGRESO ───
async def safe_edit(msg: Message, text: str, reply_markup=None):
    try:
        await msg.edit_text(text, parse_mode=None, reply_markup=reply_markup)
    except Exception:
        pass

def upload_panel(uname, percentage, done_bytes, total_bytes, speed_bps, elapsed, eta, task_id):
    bar = make_bar(percentage)
    return (
        f"╭ Task By → 「{uname}」\n"
        f"┊ [{bar}] {percentage:.2f}%\n"
        f"┊ Status   : Upload\n"
        f"┊ Done     : {get_readable_size(done_bytes)}\n"
        f"┊ Total    : {get_readable_size(total_bytes)}\n"
        f"┊ Speed    : {get_readable_size(speed_bps)}/s\n"
        f"┊ ETA      : {get_readable_time(eta)}\n"
        f"┊ Past     : {get_readable_time(elapsed)}\n"
        f"┊ Engine   : Pyrogram\n"
        f"╰ Mode     : #TLGUP\n"
        f"⋗ Stop : /cancel_{task_id}\n\n"
        f"{BOT_SIGNATURE}"
    )

async def upload_progress(current, total, msg, start_t, uname, task_id):
    if active_tasks.get(task_id) == "CANCELLED":
        raise asyncio.CancelledError("USER_CANCELLED")
    now = time.time()
    if now - last_updates.get(task_id + "_up", 0) < 3 and current < total:
        return
    last_updates[task_id + "_up"] = now
    elapsed = now - start_t
    pct = (current / total * 100) if total > 0 else 0
    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0
    panel = upload_panel(uname, pct, current, total, speed, elapsed, eta, task_id)
    await safe_edit(msg, panel)

# ─── SUBIDA INTELIGENTE ───
async def upload_smart_file(client: Client, message: Message, path: str,
                             msg: Message, uname: str, task_id: str, title: str = ""):
    """Detecta el tipo de archivo y lo sube al chat correspondiente."""
    try:
        _stats["bytes"] += os.path.getsize(path)
    except Exception:
        pass

    fname = os.path.basename(path)
    display = title.strip() if title.strip() else fname
    lower = fname.lower()

    # ── VIDEO ──
    if lower.endswith((".mp4", ".mkv", ".webm", ".avi", ".mov")):
        caption = f"🎬 <b>{display}</b>\n\n{BOT_SIGNATURE}"
        start_t = time.time()
        thumb = extract_thumbnail(path)
        meta = get_video_meta(path)
        
        vid_kwargs = {
            "chat_id": message.chat.id,
            "video": path,
            "caption": caption,
            "parse_mode": enums.ParseMode.HTML,
            "supports_streaming": True,
            "progress": upload_progress,
            "progress_args": (msg, start_t, uname, task_id)
        }
        if thumb and os.path.exists(thumb): vid_kwargs["thumb"] = thumb
        if meta.get("width", 0) > 0: vid_kwargs["width"] = meta.get("width")
        if meta.get("height", 0) > 0: vid_kwargs["height"] = meta.get("height")
        if meta.get("duration", 0) > 0: vid_kwargs["duration"] = meta.get("duration")

        try:
            await client.send_video(**vid_kwargs)
        except Exception:
            await client.send_document(
                chat_id=message.chat.id, document=path, thumb=thumb,
                caption=f"⚠️ {caption}", parse_mode=enums.ParseMode.HTML,
                progress=upload_progress, progress_args=(msg, start_t, uname, task_id)
            )
        finally:
            if thumb and os.path.exists(thumb):
                try: os.remove(thumb)
                except: pass

    # ── IMAGEN ──
    elif lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp")):
        photo_path = await _ensure_jpeg(path)
        caption = f"🖼️ <b>{display}</b>\n\n{BOT_SIGNATURE}"
        start_t = time.time()
        try:
            await client.send_photo(
                chat_id=message.chat.id, photo=photo_path, caption=caption,
                parse_mode=enums.ParseMode.HTML,
                progress=upload_progress, progress_args=(msg, start_t, uname, task_id)
            )
        except Exception:
            pass
        finally:
            if photo_path != path and os.path.exists(photo_path):
                try: os.remove(photo_path)
                except: pass

    # ── GIF ──
    elif lower.endswith(".gif"):
        await client.send_animation(
            chat_id=message.chat.id, animation=path,
            caption=f"🎬 <b>{display}</b>\n\n{BOT_SIGNATURE}",
            parse_mode=enums.ParseMode.HTML,
            progress=upload_progress, progress_args=(msg, time.time(), uname, task_id)
        )

    # ── AUDIO ──
    elif lower.endswith((".mp3", ".m4a", ".wav", ".flac", ".ogg")):
        await client.send_audio(
            chat_id=message.chat.id, audio=path,
            caption=f"🎵 <b>{display}</b>\n\n{BOT_SIGNATURE}",
            parse_mode=enums.ParseMode.HTML,
            progress=upload_progress, progress_args=(msg, time.time(), uname, task_id)
        )

    # ── DOCUMENTO ──
    else:
        await client.send_document(
            chat_id=message.chat.id, document=path,
            caption=f"📄 <b>{display}</b>\n\n{BOT_SIGNATURE}",
            parse_mode=enums.ParseMode.HTML,
            progress=upload_progress, progress_args=(msg, time.time(), uname, task_id)
        )
