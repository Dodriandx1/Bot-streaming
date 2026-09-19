"""
Motor de PDFs y Documentos (MEGA, MediaFire, GDrive, directo)
"""
import os
import re
import time
import asyncio
import httpx
from bs4 import BeautifulSoup
from pyrogram import Client, enums
from pyrogram.types import Message

from config.settings import DOWNLOAD_DIR, BOT_SIGNATURE
from core.utils import make_bar, get_readable_size, get_readable_time
from processors.uploader import safe_edit, upload_progress, _stats
from engines.mega_engine import mega_download

active_tasks: dict = {}


def _is_pdf_url(url: str) -> bool:
    return url.lower().split("?")[0].endswith(".pdf")

def _is_gdrive_url(url: str) -> bool:
    return "drive.google.com" in url.lower() or "docs.google.com" in url.lower()

def _parse_gdrive_id(url: str) -> str | None:
    patterns = [
        r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/uc\?(?:.*&)?id=([a-zA-Z0-9_-]+)",
        r"docs\.google\.com/(?:document|spreadsheets|presentation)/d/([a-zA-Z0-9_-]+)"]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


async def _download_progress(curr, total, msg, start_t, uname, task_id, engine, mode):
    if active_tasks.get(task_id) == "CANCELLED":
        raise asyncio.CancelledError("USER_CANCELLED")
    pct = (curr / total * 100) if total > 0 else 0
    elapsed = time.time() - start_t
    speed = curr / elapsed if elapsed > 0 else 0
    try:
        await safe_edit(msg,
            f"╭ Task By → 「{uname}」\n"
            f"┊ [{make_bar(pct)}] {pct:.2f}%\n"
            f"┊ Done     : {get_readable_size(curr)}\n"
            f"┊ Total    : {get_readable_size(total)}\n"
            f"┊ Speed    : {get_readable_size(speed)}/s\n"
            f"╰ Mode     : {mode}\n\n{BOT_SIGNATURE}")
    except Exception:
        pass


async def procesar_pdf(client: Client, message: Message, url: str,
                        uname: str, uid: int, queue_label: str = ""):
    task_id = f"{uid}_{int(time.time())}"
    active_tasks[task_id] = "RUNNING"
    is_mega = "mega.nz" in url
    is_mf = "mediafire.com" in url
    is_gdrive = _is_gdrive_url(url)
    msg = await message.reply_text(
        f"╭ Task By → 「{uname}」\n┊ [{make_bar(0)}] 0.00%\n"
        f"┊ Status   : Analizando...\n╰ Mode     : #PDFMode\n\n{BOT_SIGNATURE}")
    path = None
    file_title = ""
    start_t = time.time()
    try:
        if is_mega:
            await safe_edit(msg,
                f"╭ Task By → 「{uname}」\n┊ 🔄 MEGA...\n╰ Mode     : #MEGA-PDF\n\n{BOT_SIGNATURE}")
            async def _mprog(curr, total):
                await _download_progress(curr, total, msg, start_t, uname, task_id, "MEGA", "#MEGA-PDF")
            path, file_title = await mega_download(url, DOWNLOAD_DIR, task_id, progress_cb=_mprog)

        elif is_gdrive:
            fid = _parse_gdrive_id(url)
            if not fid:
                raise ValueError("No se pudo extraer el ID de Google Drive.")
            await safe_edit(msg,
                f"╭ Task By → 「{uname}」\n┊ 🔄 Google Drive...\n╰ Mode     : #GDrive-PDF\n\n{BOT_SIGNATURE}")
            dl_url = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
            async with httpx.AsyncClient(timeout=None, follow_redirects=True,
                                          headers={"User-Agent": "Mozilla/5.0"}) as h:
                async with h.stream("GET", dl_url) as resp:
                    resp.raise_for_status()
                    cd = resp.headers.get("content-disposition", "")
                    fn = re.search(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\r\n]+)', cd, re.IGNORECASE)
                    filename = fn.group(1).strip().strip('"\'') if fn else f"gdrive_{fid}.pdf"
                    filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
                    path = os.path.join(DOWNLOAD_DIR, f"{task_id}_{filename}")
                    file_title = os.path.splitext(filename)[0]
                    total = int(resp.headers.get("content-length", 0))
                    curr = 0
                    with open(path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=4 * 1024 * 1024):
                            await asyncio.sleep(0)
                            if active_tasks.get(task_id) == "CANCELLED":
                                raise asyncio.CancelledError("USER_CANCELLED")
                            f.write(chunk)
                            curr += len(chunk)
                            await _download_progress(curr, total, msg, start_t, uname,
                                                       task_id, "GDrive", "#GDrive-PDF")

        elif is_mf:
            await safe_edit(msg,
                f"╭ Task By → 「{uname}」\n┊ 🔄 MediaFire...\n╰ Mode     : #MF-PDF\n\n{BOT_SIGNATURE}")
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as h:
                r = await h.get(url)
                soup = BeautifulSoup(r.text, "html.parser")
                btn = soup.find("a", {"id": "downloadButton"})
                if not btn:
                    raise Exception("MediaFire: botón no encontrado.")
                dl_link = btn.get("href")
                filename = dl_link.split("/")[-1].split("?")[0]
                path = os.path.join(DOWNLOAD_DIR, f"{task_id}_{filename}")
                file_title = os.path.splitext(filename)[0]
                async with h.stream("GET", dl_link) as resp:
                    total = int(resp.headers.get("content-length", 0))
                    curr = 0
                    with open(path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=4 * 1024 * 1024):
                            await asyncio.sleep(0)
                            if active_tasks.get(task_id) == "CANCELLED":
                                raise asyncio.CancelledError("USER_CANCELLED")
                            f.write(chunk)
                            curr += len(chunk)
                            await _download_progress(curr, total, msg, start_t, uname,
                                                       task_id, "MF", "#MF-PDF")

        else:
            await safe_edit(msg,
                f"╭ Task By → 「{uname}」\n┊ ⬇️ Descargando...\n╰ Mode     : #DirectPDF\n\n{BOT_SIGNATURE}")
            async with httpx.AsyncClient(timeout=None, follow_redirects=True,
                                          headers={"User-Agent": "Mozilla/5.0"}) as h:
                async with h.stream("GET", url) as resp:
                    resp.raise_for_status()
                    ct = resp.headers.get("content-type", "").lower()
                    if "text/html" in ct and not _is_pdf_url(url):
                        raise Exception("El enlace no apunta directamente a un archivo.")
                    cd = resp.headers.get("content-disposition", "")
                    fn = re.search(r'filename[*]?=["\']?(?:UTF-8\'\')?([^"\';\r\n]+)', cd, re.IGNORECASE)
                    if fn:
                        filename = fn.group(1).strip().strip('"\'')
                    else:
                        filename = url.split("/")[-1].split("?")[0]
                        if not filename or "." not in filename:
                            filename = "documento.pdf"
                    filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
                    path = os.path.join(DOWNLOAD_DIR, f"{task_id}_{filename}")
                    file_title = os.path.splitext(filename)[0]
                    total = int(resp.headers.get("content-length", 0))
                    curr = 0
                    with open(path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=4 * 1024 * 1024):
                            await asyncio.sleep(0)
                            if active_tasks.get(task_id) == "CANCELLED":
                                raise asyncio.CancelledError("USER_CANCELLED")
                            f.write(chunk)
                            curr += len(chunk)
                            await _download_progress(curr, total, msg, start_t, uname,
                                                       task_id, "HTTP", "#DirectPDF")

        if not path or not os.path.exists(path):
            raise Exception("El archivo no se descargó correctamente.")
        size_mb = os.path.getsize(path) / (1024 * 1024)
        fname = os.path.basename(path)
        display = file_title or os.path.splitext(fname)[0]
        ext = os.path.splitext(fname)[1].lower()
        doc_icon = "📕" if ext == ".pdf" else "📄"
        caption = (f"{doc_icon} <b>{display[:100]}</b>\n\n"
                    f"📦 Tamaño: {size_mb:.1f} MB\n\n{BOT_SIGNATURE}")
        await safe_edit(msg,
            f"╭ Task By → 「{uname}」\n┊ [{make_bar(100)}] 100%\n"
            f"┊ ⬆️ Subiendo...\n╰ Mode     : #PDFMode\n\n{BOT_SIGNATURE}")
        await client.send_document(
            chat_id=message.chat.id, document=path, file_name=fname,
            caption=caption, parse_mode=enums.ParseMode.HTML,
            progress=upload_progress,
            progress_args=(msg, start_t, uname, task_id))
        _stats["downloads"] += 1
        try: _stats["bytes"] += os.path.getsize(path)
        except Exception: pass
        await safe_edit(msg,
            f"╭ Task By → 「{uname}」\n┊ {doc_icon} {display[:60]}\n"
            f"┊ ✅ Enviado ({size_mb:.1f} MB)\n╰ Mode     : #PDFMode\n\n{BOT_SIGNATURE}")
        await asyncio.sleep(4)
        try: await msg.delete()
        except Exception: pass
    except (asyncio.CancelledError, Exception) as e:
        is_cancel = isinstance(e, asyncio.CancelledError) or "USER_CANCELLED" in str(e)
        err = "🛑 Cancelada." if is_cancel else f"❌ Error: {str(e)[:300]}"
        try:
            await safe_edit(msg, f"╭ Task By → 「{uname}」\n┊ {err}\n╰──────────────\n\n{BOT_SIGNATURE}")
        except Exception:
            pass
    finally:
        active_tasks.pop(task_id, None)
        if path and os.path.exists(path):
            try: os.remove(path)
            except Exception: pass
