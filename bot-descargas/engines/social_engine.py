import os
import re
import time
import glob
import asyncio
import httpx
import yt_dlp
from bs4 import BeautifulSoup
from pyrogram import Client, enums
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo

from config.settings import DOWNLOAD_DIR, BOT_SIGNATURE
from core.utils import get_readable_size, make_bar
from processors.uploader import safe_edit, upload_smart_file, _stats
from processors.video_processor import probe_video

# ─── ESTADOS GLOBALES ───
active_tasks: dict = {}
_ydl_stop: dict = {}

# ─── UTILIDAD: DESCARGA VERIFICADA ───
async def _is_image_complete(path: str, timeout: float = 20.0) -> bool:
    """Verifica que una imagen se pueda decodificar sin errores."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-v", "error", "-i", path, "-f", "null", "-",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode == 0 and not stderr.strip()
    except Exception:
        return True

async def _download_media_verified(url: str, dest_path: str,
                                     headers: dict | None = None,
                                     timeout: float = 120.0,
                                     max_retries: int = 3,
                                     validate_image: bool = False) -> bool:
    """Descarga con reintentos y verificación de integridad."""
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as h:
                async with h.stream("GET", url, headers=headers) as resp:
                    if resp.status_code != 200:
                        raise Exception(f"HTTP {resp.status_code}")
                    cl = resp.headers.get("content-length")
                    expected = int(cl) if cl and cl.isdigit() else None
                    received = 0
                    with open(dest_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(1024 * 512):
                            f.write(chunk)
                            received += len(chunk)
            if received < 1000:
                raise Exception(f"archivo muy pequeño ({received} bytes)")
            if expected is not None and received != expected:
                raise Exception(f"descarga incompleta: {received}/{expected}")
            if validate_image and not await _is_image_complete(dest_path):
                raise Exception("imagen truncada/corrupta")
            return True
        except Exception as exc:
            print(f"[download/verify] intento {attempt}/{max_retries}: {exc}")
            try:
                if os.path.exists(dest_path): os.remove(dest_path)
            except Exception: pass
            if attempt < max_retries:
                await asyncio.sleep(1.2 * attempt)
    return False


# ─── DETECCIÓN DE PLATAFORMA ───
def _get_platform_icon(url: str) -> str:
    u = url.lower()
    if "tiktok.com" in u: return "🎵"
    if "instagram.com" in u: return "📸"
    if "twitter.com" in u or "x.com" in u: return "🐦"
    if "facebook.com" in u or "fb.com" in u: return "📘"
    if "reddit.com" in u: return "🤖"
    if "pinterest.com" in u: return "📌"
    return "🌐"

def _is_tiktok(url: str) -> bool:
    return "tiktok.com" in url.lower()

def _is_instagram(url: str) -> bool:
    return "instagram.com" in url.lower()

def _is_video_host(url: str) -> bool:
    VIDEO_HOSTS = ["streamwish", "voe", "vidhide", "filemoon", "mixdrop",
                   "mp4upload", "streamtape", "flashwish", "callistanise",
                   "filelions", "swishdesu"]
    return any(h in url.lower() for h in VIDEO_HOSTS)


# ─── TIKTOK (con API TikWM) ───
async def _procesar_tiktok(client, message, url, uname, task_id, msg):
    api_req = f"https://www.tikwm.com/api/?url={url}&hd=1"
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as h:
        tk_data = (await h.get(api_req)).json()

    if tk_data.get("code") != 0:
        raise Exception("Fallo en la extracción del enlace de TikTok.")

    data = tk_data.get("data", {})
    video_title = data.get("title", "TikTok")
    images = data.get("images")
    video_url = data.get("hdplay") or data.get("play")

    # Carrusel de imágenes
    if images and isinstance(images, list):
        total = len(images)
        files = []
        for idx, img_url in enumerate(images):
            if active_tasks.get(task_id) == "CANCELLED":
                raise asyncio.CancelledError("USER_CANCELLED")
            await safe_edit(msg,
                f"╭ Task By → 「{uname}」\n┊ 🎵 Álbum TikTok\n"
                f"┊ 📥 Foto {idx+1}/{total}...\n╰──────────────\n\n{BOT_SIGNATURE}")
            img_path = os.path.join(DOWNLOAD_DIR, f"{task_id}_{idx}.jpg")
            if await _download_media_verified(img_url, img_path, timeout=60, validate_image=True):
                files.append(img_path)

        if files:
            album_caption = f"🖼️ <b>{video_title}</b>\n\n{BOT_SIGNATURE}"
            group = []
            for idx, f in enumerate(files):
                cap = album_caption if idx == 0 else None
                group.append(InputMediaPhoto(f, caption=cap, parse_mode=enums.ParseMode.HTML))
            for i in range(0, len(group), 10):
                await client.send_media_group(message.chat.id, group[i:i+10])
            _stats["downloads"] += 1
            await msg.delete()
            for f in files:
                try: os.remove(f)
                except: pass
            return

    # Video único
    if video_url:
        path = os.path.join(DOWNLOAD_DIR, f"{task_id}.mp4")
        if not await _download_media_verified(video_url, path, timeout=120):
            raise Exception("No se pudo descargar el video de TikTok.")
        await upload_smart_file(client, message, path, msg, uname, task_id, title=video_title)
        try: await msg.delete()
        except: pass
        return

    raise Exception("No se pudo extraer el contenido de TikTok.")


# ─── YT-DLP GENÉRICO (Redes Sociales + Video Hosts) ───
async def _procesar_con_ytdlp(client, message, url, uname, task_id, msg, want_subs=False):
    """Descarga usando yt-dlp para Instagram, Twitter, Facebook y video hosts."""
    loop = asyncio.get_running_loop()
    start_t = time.time()
    captured = {"title": ""}
    stop_evt = _ydl_stop.setdefault(task_id, asyncio.Event())

    from processors.uploader import download_progress as dl_prog

    def ydl_hook(d):
        if active_tasks.get(task_id) == "CANCELLED":
            raise ValueError("USER_CANCELLED")
        if d["status"] == "downloading":
            curr = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            if total > 0:
                asyncio.run_coroutine_threadsafe(
                    dl_prog(curr, total, msg, start_t, uname, task_id, "yt-dlp", "#Social"),
                    loop)

    def _extract():
        base_opts = {
            "outtmpl": f"{DOWNLOAD_DIR}{task_id}_%(autonumber)03d.%(ext)s",
            "noplaylist": False,
            "playlist_items": "1-30",
            "progress_hooks": [ydl_hook],
            "quiet": True, "no_warnings": True,
            "merge_output_format": "mp4",
            "concurrent_fragment_downloads": 4,
            "retries": 5, "fragment_retries": 5,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/125.0.0.0 Safari/537.36",
                "Referer": url,
            },
        }
        # Cookies opcionales
        if os.path.exists("cookies.txt"):
            base_opts["cookiefile"] = "cookies.txt"

        if _is_video_host(url):
            base_opts["format"] = "best"

        with yt_dlp.YoutubeDL(base_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                captured["title"] = info.get("title", "") or info.get("description", "")[:80]

    await asyncio.wait_for(asyncio.to_thread(_extract), timeout=900)

    # Recoger archivos descargados
    files = sorted(glob.glob(f"{DOWNLOAD_DIR}{task_id}_*"), key=os.path.getsize)
    if not files:
        raise Exception("No se pudo extraer el contenido. Posible bloqueo de IP.")

    # Video único
    if len(files) == 1:
        path = files[0]
        await upload_smart_file(client, message, path, msg, uname, task_id,
                                 title=captured["title"] or "Video")
        try: await msg.delete()
        except: pass
        return

    # Carrusel / Álbum
    album_caption = f"📸 <b>{captured['title']}</b>\n\n{BOT_SIGNATURE}" if captured["title"] else BOT_SIGNATURE
    group = []
    for idx, f in enumerate(files):
        fl = f.lower()
        cap = album_caption if idx == 0 else None
        parse = enums.ParseMode.HTML if cap else None
        if fl.endswith((".jpg", ".jpeg", ".png", ".webp")):
            if not await _is_image_complete(f):
                continue
            group.append(InputMediaPhoto(f, caption=cap, parse_mode=parse))
        elif fl.endswith((".mp4", ".mkv", ".webm")):
            group.append(InputMediaVideo(f, caption=cap, parse_mode=parse, supports_streaming=True))

    if group:
        for i in range(0, len(group), 10):
            await client.send_media_group(message.chat.id, group[i:i+10])
        _stats["downloads"] += 1
        await msg.delete()

    for f in files:
        try: os.remove(f)
        except: pass


# ─── FALLBACK PARA INSTAGRAM (Scraping HTML) ───
async def _instagram_fallback(client, message, url, uname, task_id, msg):
    """Si yt-dlp falla con Instagram, scrapea el HTML del embed."""
    sc = re.search(r'/(?:p|reel|tv|reels)/([A-Za-z0-9_-]+)', url)
    if not sc:
        raise Exception("No se pudo extraer el shortcode de Instagram.")
    shortcode = sc.group(1)

    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

    media_urls = []
    for path in ["p", "reel"]:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as h:
                r = await h.get(
                    f"https://www.instagram.com/{path}/{shortcode}/embed/captioned/",
                    headers={"User-Agent": ua})
            if r.status_code != 200: continue
            text = r.text.replace("\\u0026", "&").replace("&amp;", "&")
            for vu in re.findall(r'(https://(?:video|scontent)[^\s"\'<>\\]+\.mp4[^\s"\'<>\\]*)', text):
                if "cdninstagram" in vu or "fbcdn" in vu:
                    media_urls.append((vu, True)); break
            if not media_urls:
                imgs = re.findall(r'(https://scontent[^\s"\'<>\\]+\.(?:jpg|jpeg)[^\s"\'<>\\]*)', text)
                ok = [u for u in imgs if "_s640x640" not in u and "s150x150" not in u]
                if ok: media_urls.append((ok[0], False))
                elif imgs: media_urls.append((imgs[0], False))
            if media_urls: break
        except Exception as e:
            print(f"[Instagram/embed] {path}: {e}")

    if not media_urls:
        raise Exception("No se pudo extraer el contenido de Instagram.")

    files = []
    for idx, (murl, is_vid) in enumerate(media_urls):
        ext = ".mp4" if is_vid else ".jpg"
        fp = os.path.join(DOWNLOAD_DIR, f"{task_id}_ig{idx:03d}{ext}")
        if await _download_media_verified(murl, fp, headers={"User-Agent": ua},
                                            timeout=120, validate_image=not is_vid):
            files.append((fp, is_vid))

    if not files:
        raise Exception("No se pudo descargar el contenido de Instagram.")

    if len(files) == 1:
        fp, _ = files[0]
        await upload_smart_file(client, message, fp, msg, uname, task_id, title="Instagram")
    else:
        album_caption = f"📸 Instagram\n\n{BOT_SIGNATURE}"
        group = []
        for i, (fp, is_vid) in enumerate(files):
            cap = album_caption if i == 0 else None
            parse = enums.ParseMode.HTML if cap else None
            if is_vid:
                group.append(InputMediaVideo(fp, caption=cap, parse_mode=parse))
            else:
                group.append(InputMediaPhoto(fp, caption=cap, parse_mode=parse))
        for i in range(0, len(group), 10):
            await client.send_media_group(message.chat.id, group[i:i+10])

    _stats["downloads"] += 1
    try: await msg.delete()
    except: pass
    for fp, _ in files:
        try: os.remove(fp)
        except: pass


# ─── FUNCIÓN PRINCIPAL ───
async def procesar_social(client: Client, message: Message, url: str,
                            uname: str, uid: int, task_id: str,
                            want_subs: bool = False):
    """Enruta el enlace al motor adecuado según la plataforma."""
    active_tasks[task_id] = "RUNNING"
    icon = _get_platform_icon(url)

    if _is_video_host(url):
        mode = f"{icon} #VideoHoster"
    elif _is_tiktok(url):
        mode = f"{icon} #TikTok"
    elif _is_instagram(url):
        mode = f"{icon} #Instagram"
    else:
        mode = f"{icon} #SocialMedia"

    msg = await message.reply_text(
        f"╭ Task By → 「{uname}」\n"
        f"┊ [{make_bar(0)}] 0.00%\n"
        f"┊ Status   : Extrayendo...\n"
        f"╰ Mode     : {mode}\n\n{BOT_SIGNATURE}")

    try:
        # ── TikTok ──
        if _is_tiktok(url):
            await _procesar_tiktok(client, message, url, uname, task_id, msg)

        # ── Instagram (con fallback) ──
        elif _is_instagram(url):
            try:
                await _procesar_con_ytdlp(client, message, url, uname, task_id, msg, want_subs)
            except Exception as e:
                print(f"[Instagram] yt-dlp falló, usando fallback: {e}")
                await _instagram_fallback(client, message, url, uname, task_id, msg)

        # ── Otras redes sociales y video hosts (yt-dlp genérico) ──
        else:
            await _procesar_con_ytdlp(client, message, url, uname, task_id, msg, want_subs)

    except asyncio.CancelledError:
        await safe_edit(msg, f"🛑 Descarga cancelada.\n\n{BOT_SIGNATURE}")
    except Exception as e:
        await safe_edit(msg, f"❌ Error: {str(e)[:200]}\n\n{BOT_SIGNATURE}")
    finally:
        active_tasks.pop(task_id, None)
        _ydl_stop.pop(task_id, None)
        for f in glob.glob(f"{DOWNLOAD_DIR}{task_id}_*"):
            try: os.remove(f)
            except: pass
