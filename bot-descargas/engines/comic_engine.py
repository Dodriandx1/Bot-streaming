"""
Motor de Cómics / Mangas (scraper + PDF)
"""
import os
import re
import time
import asyncio
import httpx
from bs4 import BeautifulSoup
from pyrogram import Client, enums
from pyrogram.types import Message, InputMediaPhoto, InputMediaDocument

from config.settings import DOWNLOAD_DIR, BOT_SIGNATURE
from processors.uploader import safe_edit, _stats

active_tasks: dict = {}

_COMIC_DOMAINS = (
    "toonx.net", "jav.guru", "javmiku.com", "javnorth.com",
    "hentaiheroes.com", "nhentai.net",
)

def _is_comic_page_url(url: str) -> bool:
    low = url.lower()
    return low.startswith(("http://", "https://")) and any(d in low for d in _COMIC_DOMAINS)

_COMIC_SELECTORS = [
    "div.pp-gallery-view", "div.pp-comic-content", "div.reading-content",
    "div.chapter-content", "div#chapter-images", "div.comic-reading",
    "div.comic-images", "div#comic", "div.entry-content", "div.post-content",
    "div.td-post-content", "article.post", "main article", "article", "main",
]

_UI_IMG_PATTERNS = re.compile(
    r"(logo|banner|icon|avatar|header|footer|sidebar|widget|advert|sponsor|"
    r"social|share|button|pixel|1x1|blank|comment|gravatar|emoji|wp-includes|themes/)",
    re.IGNORECASE)


async def _scrape_comic_images(page_url: str) -> tuple[list[str], str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8"}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as h:
        r = await h.get(page_url)
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    title = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    elif soup.title:
        title = soup.title.get_text(strip=True)
    images: list[str] = []
    for sel in _COMIC_SELECTORS:
        container = soup.select_one(sel)
        if not container:
            continue
        candidates = []
        for img in container.find_all("img"):
            src = (img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                   or img.get("data-original") or img.get("data-url") or "").strip()
            if not src or not src.startswith("http"):
                continue
            if _UI_IMG_PATTERNS.search(src):
                continue
            try:
                if int(img.get("width", "0")) < 100 or int(img.get("height", "0")) < 100:
                    continue
            except ValueError:
                pass
            candidates.append(src)
        if candidates:
            images = candidates
            break
    if not images:
        page_host = page_url.split("/")[2]
        for img in soup.find_all("img"):
            src = (img.get("src") or img.get("data-src") or "").strip()
            if not src.startswith("http"):
                continue
            img_host = src.split("/")[2] if "//" in src else ""
            if img_host == page_host and "wp-content/uploads" in src and not _UI_IMG_PATTERNS.search(src):
                images.append(src)
    seen = set()
    unique = []
    for u in images:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique, title


async def _images_to_pdf(image_files: list[str], output_path: str) -> None:
    if not image_files:
        raise ValueError("No hay imágenes para el PDF.")
    proc = await asyncio.create_subprocess_exec(
        "convert", *image_files, "-quality", "100", "-compress", "Zip",
        "-density", "150", output_path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
    if proc.returncode != 0 or not os.path.exists(output_path):
        detail = stderr.decode(errors="replace").strip()[-300:]
        raise RuntimeError(f"No se pudo crear el PDF: {detail}")


async def procesar_comic(client: Client, message: Message, url: str,
                          uname: str, uid: int, msg: Message | None = None,
                          as_pdf: bool = False):
    task_id = f"{uid}_{int(time.time())}"
    active_tasks[task_id] = "RUNNING"
    owned_msg = msg is None
    if msg is None:
        msg = await message.reply_text(
            f"╭ Task By → 「{uname}」\n┊ 🔍 Analizando...\n"
            f"╰ Mode     : #ComicScraper\n\n{BOT_SIGNATURE}")
    tmp_files: list[str] = []
    try:
        await safe_edit(msg,
            f"╭ Task By → 「{uname}」\n┊ 🔍 Extrayendo imágenes...\n"
            f"╰ Mode     : #ComicScraper\n\n{BOT_SIGNATURE}")
        img_urls, page_title = await _scrape_comic_images(url)
        if not img_urls:
            raise Exception("No se encontraron imágenes. La página puede requerir JS o login.")
        total = len(img_urls)
        await safe_edit(msg,
            f"╭ Task By → 「{uname}」\n┊ 🖼️ {total} imágenes\n┊ ⬇️ Descargando...\n"
            f"╰ Mode     : #ComicScraper\n\n{BOT_SIGNATURE}")
        sem = asyncio.Semaphore(4)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                   "Referer": url}

        async def _dl_one(idx: int, img_url: str) -> str | None:
            async with sem:
                if active_tasks.get(task_id) == "CANCELLED":
                    return None
                ext = os.path.splitext(img_url.split("?")[0])[1].lower()
                if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                    ext = ".jpg"
                fpath = os.path.join(DOWNLOAD_DIR, f"{task_id}_comic_{idx:04d}{ext}")
                candidates = [img_url]
                if "cdn.javmiku.com/" in img_url:
                    candidates.append(img_url.replace("cdn.javmiku.com/", "cdn.javnorth.com/"))
                if "cdn.javnorth.com/" in img_url:
                    candidates.append(img_url.replace("cdn.javnorth.com/", "cdn.javmiku.com/"))
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, headers=headers) as h:
                    for cand in dict.fromkeys(candidates):
                        try:
                            r = await h.get(cand)
                            if r.status_code == 200 and len(r.content) >= 2000:
                                with open(fpath, "wb") as f:
                                    f.write(r.content)
                                return fpath
                        except httpx.HTTPError:
                            continue
                return None

        results = await asyncio.gather(*[_dl_one(i, u) for i, u in enumerate(img_urls)])
        for r in results:
            if r and os.path.exists(r):
                tmp_files.append(r)
        tmp_files.sort()
        if not tmp_files:
            raise Exception("No se pudieron descargar las imágenes.")
        downloaded = len(tmp_files)
        title_short = page_title[:60] if page_title else url.split("/")[-2]
        ready: list[str] = []
        for fpath in tmp_files:
            if fpath.lower().endswith(".webp"):
                out_jpg = fpath[:-5] + ".jpg"
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "ffmpeg", "-y", "-i", fpath, "-q:v", "2", out_jpg,
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                    await asyncio.wait_for(proc.wait(), timeout=15)
                    if os.path.exists(out_jpg) and os.path.getsize(out_jpg) > 0:
                        try: os.remove(fpath)
                        except: pass
                        ready.append(out_jpg)
                    else:
                        ready.append(fpath)
                except Exception:
                    ready.append(fpath)
            else:
                ready.append(fpath)
        if as_pdf:
            pdf_path = os.path.join(DOWNLOAD_DIR, f"{task_id}_comic.pdf")
            tmp_files.append(pdf_path)
            await safe_edit(msg,
                f"╭ Task By → 「{uname}」\n┊ 📕 Creando PDF ({downloaded} páginas)...\n"
                f"╰ Mode     : #ComicPDF\n\n{BOT_SIGNATURE}")
            await _images_to_pdf(ready, pdf_path)
            pdf_size = os.path.getsize(pdf_path) / (1024 * 1024)
            pdf_name = re.sub(r"[^\w\- ]+", "", title_short, flags=re.UNICODE).strip()
            pdf_name = (pdf_name[:80] or "comic") + ".pdf"
            await client.send_document(
                chat_id=message.chat.id, document=pdf_path, file_name=pdf_name,
                caption=(f"📖 <b>{title_short}</b>\n📕 {downloaded} páginas\n"
                          f"📦 {pdf_size:.1f} MB\n\n{BOT_SIGNATURE}"),
                parse_mode=enums.ParseMode.HTML)
        else:
            album_caption = f"📖 <b>{title_short}</b>\n🖼️ {downloaded} páginas\n\n{BOT_SIGNATURE}"
            batches = [ready[i:i+10] for i in range(0, len(ready), 10)]
            for batch_num, batch in enumerate(batches, 1):
                if active_tasks.get(task_id) == "CANCELLED":
                    break
                await safe_edit(msg,
                    f"╭ Task By → 「{uname}」\n┊ ⬆️ Álbum {batch_num}/{len(batches)}...\n"
                    f"╰ Mode     : #ComicScraper\n\n{BOT_SIGNATURE}")
                media_group = []
                for fi, fpath in enumerate(batch):
                    cap = album_caption if batch_num == 1 and fi == 0 else None
                    parse = enums.ParseMode.HTML if cap else None
                    try:
                        media_group.append(InputMediaPhoto(fpath, caption=cap, parse_mode=parse))
                    except Exception:
                        media_group.append(InputMediaDocument(fpath, caption=cap, parse_mode=parse))
                try:
                    await client.send_media_group(message.chat.id, media_group)
                except Exception:
                    for fi, fpath in enumerate(batch):
                        cap = album_caption if batch_num == 1 and fi == 0 else None
                        try:
                            await client.send_document(message.chat.id, fpath,
                                caption=cap, parse_mode=enums.ParseMode.HTML)
                        except Exception:
                            pass
        _stats["downloads"] += 1
        if owned_msg:
            try: await msg.delete()
            except Exception: pass
        else:
            await safe_edit(msg,
                f"╭ Task By → 「{uname}」\n┊ ✅ {downloaded} páginas\n"
                f"┊ 📖 {title_short}\n╰ Mode     : #ComicScraper\n\n{BOT_SIGNATURE}")
            await asyncio.sleep(5)
            try: await msg.delete()
            except Exception: pass
    except Exception as e:
        is_cancel = "USER_CANCELLED" in str(e)
        err = "🛑 Cancelado." if is_cancel else f"❌ Error: {str(e)[:300]}"
        try:
            await safe_edit(msg, f"╭ Task By → 「{uname}」\n┊ {err}\n╰──────────────\n\n{BOT_SIGNATURE}")
        except Exception:
            pass
    finally:
        active_tasks.pop(task_id, None)
        for f in tmp_files:
            try: os.remove(f)
            except Exception: pass
