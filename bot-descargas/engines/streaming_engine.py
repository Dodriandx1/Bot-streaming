"""
Motor de Streaming con Cookies (Crunchyroll, etc.)
"""
import os
import re
import time
import glob
import asyncio
import yt_dlp
from urllib.parse import unquote
from pyrogram import Client, enums
from pyrogram.types import Message

from config.settings import DOWNLOAD_DIR, BOT_SIGNATURE
from core.utils import make_bar
from processors.uploader import safe_edit, upload_smart_file, download_progress, _stats

active_tasks: dict = {}


def _find_cookie_for_domain(domain: str) -> str | None:
    bot_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    domain_key = domain.replace("www.", "").split(".")[0]
    candidates = [
        os.path.join(bot_dir, "cookies", f"{domain_key}.txt"),
        os.path.join(bot_dir, f"{domain_key}_cookies.txt"),
        os.path.join(bot_dir, "cookies.txt"),
    ]
    for path in candidates:
        if os.path.isfile(path) and os.path.getsize(path) > 32:
            return path
    return None


async def procesar_crunchyroll(client: Client, message: Message, url: str,
                                 uname: str, uid: int, want_subs: bool = False):
    task_id = f"{uid}_{int(time.time())}"
    active_tasks[task_id] = "RUNNING"
    msg = await message.reply_text(
        f"╭ Task By → 「{uname}」\n┊ [{make_bar(0)}] 0.00%\n"
        f"┊ Status   : Conectando a Crunchyroll...\n"
        f"╰ Mode     : #CRDWV2\n\n{BOT_SIGNATURE}")
    path = None
    video_title = "Episode"
    start_t = time.time()
    loop = asyncio.get_running_loop()

    try:
        cookie_path = _find_cookie_for_domain("crunchyroll")

        def ydl_hook(d):
            if active_tasks.get(task_id) == "CANCELLED":
                raise ValueError("USER_CANCELLED")
            if d["status"] == "downloading":
                curr = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if total > 0:
                    asyncio.run_coroutine_threadsafe(
                        download_progress(curr, total, msg, start_t, uname, task_id,
                                           "yt-dlp", "#CR1080P"), loop)

        opts = {
            "outtmpl": f"{DOWNLOAD_DIR}{task_id}_%(title)s.%(ext)s",
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "progress_hooks": [ydl_hook],
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "merge_output_format": "mp4",
            "retries": 20, "fragment_retries": 20,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/134.0.0.0 Safari/537.36"},
        }
        if cookie_path:
            opts["cookiefile"] = cookie_path
        if want_subs:
            opts.update({
                "writesubtitles": True, "writeautomaticsub": True,
                "subtitleslangs": ["es", "es-419", "es-MX"],
                "subtitlesformat": "srt/best"})

        await safe_edit(msg,
            f"╭ Task By → 「{uname}」\n┊ [{make_bar(0)}] 0.00%\n"
            f"┊ Status   : Descargando 1080p...\n"
            f"┊ 🍪 Cookies: {'✅' if cookie_path else '❌'}\n"
            f"╰ Mode     : #CRDWV2\n\n{BOT_SIGNATURE}")

        def run_ydl():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True)

        info = await asyncio.to_thread(run_ydl)
        video_title = (info.get("title") or "Episode") if info else "Episode"
        files = sorted(glob.glob(f"{DOWNLOAD_DIR}{task_id}_*.mp4"),
                       key=os.path.getsize, reverse=True)
        path = files[0] if files else None
    except Exception as e:
        err_str = str(e)
        if "drm" in err_str.lower() or "protected" in err_str.lower():
            await safe_edit(msg, f"❌ DRM protegido. Cookies caducadas.\n{BOT_SIGNATURE}")
        elif any(k in err_str.lower() for k in ("login", "sign in", "premium")):
            await safe_edit(msg, f"❌ Se requiere cuenta Premium.\n{BOT_SIGNATURE}")
        else:
            await safe_edit(msg, f"❌ Error: {err_str[:200]}\n{BOT_SIGNATURE}")
        active_tasks.pop(task_id, None)
        return
    finally:
        active_tasks.pop(task_id, None)

    if path and os.path.exists(path):
        await safe_edit(msg, f"╭ Task By → 「{uname}」\n┊ ⬆️ Subiendo...\n╰──────────────\n\n{BOT_SIGNATURE}")
        await upload_smart_file(client, message, path, msg, uname, task_id, title=video_title)
        _stats["downloads"] += 1
        try: await msg.delete()
        except Exception: pass
        try: os.remove(path)
        except Exception: pass
    else:
        await safe_edit(msg, f"❌ No se pudo descargar.\n{BOT_SIGNATURE}")


async def buscar_anime_metadata(query: str) -> dict:
    import httpx
    query = query.strip()
    if query.startswith(("http://", "https://")) and "crunchyroll.com/" in query.lower():
        slug = query.rstrip("/").split("/")[-1].split("?")[0]
        slug = unquote(slug).replace("-", " ").strip()
        query = re.sub(r"\s+", " ", slug).strip().title()
    if not query:
        return {}
    headers = {"User-Agent": "BotAnime/1.0"}
    async with httpx.AsyncClient(timeout=20.0, headers=headers) as h:
        try:
            r = await h.get("https://api.jikan.moe/v4/anime",
                              params={"q": query, "limit": 5, "sfw": "true"})
            if r.status_code == 200:
                data = r.json()
                if data.get("data"):
                    return data["data"][0]
        except Exception:
            pass
        try:
            aq = """query ($search: String) {
              Page(perPage: 1) { media(search: $search, type: ANIME) {
                title { romaji english native } synonyms seasonYear status } } }"""
            r = await h.post("https://graphql.anilist.co",
                              json={"query": aq, "variables": {"search": query}})
            if r.status_code == 200:
                media = r.json().get("data", {}).get("Page", {}).get("media", [])
                if media:
                    item = media[0]
                    t = item.get("title") or {}
                    return {"title": t.get("romaji") or t.get("english") or t.get("native"),
                            "title_english": t.get("english"),
                            "title_japanese": t.get("native"),
                            "titles": [{"type": "Synonym", "title": s}
                                       for s in item.get("synonyms", [])],
                            "year": item.get("seasonYear"),
                            "status": item.get("status")}
        except Exception:
            pass
    return {"title": query, "title_english": None, "title_japanese": None,
            "titles": [], "year": None, "status": "No disponible"}
