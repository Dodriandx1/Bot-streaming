import os
import sys
import time
import asyncio
from datetime import timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import (
    ADMIN_ID, BOT_SIGNATURE, PLANES, PLAN_HIERARCHY, now_ec
)
from core.database import user_db
from core.utils import get_readable_size, get_readable_time, make_bar

# ─── SISTEMA DE AUTORIZACIÓN ───
import json
authorized_users = {}

def load_auth_users():
    global authorized_users
    if os.path.exists("authorized_users.json"):
        try:
            with open("authorized_users.json", "r") as f:
                authorized_users = json.load(f)
        except Exception:
            authorized_users = {}

def save_auth_users():
    with open("authorized_users.json", "w") as f:
        json.dump(authorized_users, f, indent=2)

load_auth_users()

def is_admin(uid: int) -> bool:
    if uid == ADMIN_ID: return True
    user_data = authorized_users.get(str(uid))
    return bool(user_data and user_data.get("role") == "admin")

def is_user_authorized(uid: int) -> bool:
    """Controla si un usuario puede usar el bot (libre o restringido)."""
    # Leer de bot_settings.json si existe
    try:
        with open("bot_settings.json", "r") as f:
            settings = json.load(f)
            if settings.get("acceso_libre", True):
                return True
    except Exception:
        return True  # Por defecto, libre
    return str(uid) in authorized_users or uid == ADMIN_ID

def get_user_plan(uid: int) -> str:
    user_data = user_db.get_user(uid)
    return user_data.get("plan", "free")


# ─── COMANDO /start ───
@bot.on_message(filters.command("start"))
async def cmd_start(client: Client, message: Message):
    uid = message.from_user.id
    name = message.from_user.first_name
    auth_status = "✅ Autorizado" if is_user_authorized(uid) else "⛔ No Autorizado"
    plan = get_user_plan(uid)
    creditos = user_db.get_user(uid).get("creditos", 0)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Mi Perfil", callback_data="show_profile")],
        [InlineKeyboardButton("💎 Ver Planes", callback_data="panel_plan_list")],
    ])

    await message.reply_text(
        f"🚀 ¡Hola, <b>{name}</b>!\n\n"
        f"Soy un bot descargador de medios con sistema de planes.\n\n"
        f"🆔 <b>Tu ID:</b> <code>{uid}</code>\n"
        f"🔐 <b>Estado:</b> {auth_status}\n"
        f"💎 <b>Plan:</b> {plan}\n"
        f"🪙 <b>Créditos:</b> {creditos}\n\n"
        f"<i>(Si no estás autorizado, envía tu ID al Admin)</i>\n\n"
        f"{BOT_SIGNATURE}",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=kb)


# ─── COMANDO /coms (ayuda) ───
@bot.on_message(filters.command(["coms", "help", "ayuda"]))
async def cmd_coms(client: Client, message: Message):
    uid = message.from_user.id
    if not is_user_authorized(uid):
        return

    text = (
        "╭─ 📋 <b>Panel de Comandos</b>\n"
        "├──────────────────────────\n"
        "┊ 🎵 <b>Música</b>\n"
        "┊ ├ /play &lt;nombre&gt; — MP3\n"
        "┊ ├ /playv &lt;nombre&gt; — Video\n"
        "┊ ├ /search &lt;nombre&gt; — Panel de resultados\n"
        "┊ ╰ /audio &lt;link&gt; — Extraer MP3\n"
        "┊\n"
        "┊ 🎬 <b>Video</b>\n"
        "┊ ├ Envía un link — Descarga inteligente\n"
        "┊ ├ /encode — Convertir/Torrent\n"
        "┊ ├ /crearwm &lt;texto&gt; — Marca de agua\n"
        "┊ ├ /spam on|off — Activar/desactivar\n"
        "┊ ╰ /config — Ajustes FFmpeg\n"
        "┊\n"
        "┊ 📕 <b>Documentos</b>\n"
        "┊ ├ /pdf &lt;link&gt; — PDF\n"
        "┊ ├ /comic &lt;link&gt; — Cómic\n"
        "┊ ╰ /a &lt;nombre&gt; — Info Anime\n"
        "┊\n"
        "┊ 💎 <b>Cuenta</b>\n"
        "┊ ├ /plan — Planes y pagos\n"
        "┊ ├ /perfil — Tu info\n"
        "┊ ╰ /queue — Estado de la cola\n"
    )
    if is_admin(uid):
        text += (
            "┊\n┊ 🔐 <b>Admin</b>\n"
            "┊ ├ /id (reply) — Autorizar\n"
            "┊ ├ /addid &lt;ID&gt; — Autorizar directo\n"
            "┊ ├ /setplan &lt;ID&gt; &lt;plan&gt;\n"
            "┊ ├ /users — Ver usuarios\n"
            "┊ ├ /stat — Estado del sistema\n"
            "┊ ╰ /admin — Panel de admin\n"
        )
    text += f"╰──────────────────────────\n\n{BOT_SIGNATURE}"

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cerrar Panel", callback_data="close_panel")]])
    await message.reply_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)


# ─── COMANDO /ping ───
@bot.on_message(filters.command(["ping", "Ping"]))
async def cmd_ping(client: Client, message: Message):
    if not is_user_authorized(message.from_user.id): return
    t1 = time.time()
    m = await message.reply_text("🏓 Calculando...")
    latency = (time.time() - t1) * 1000
    await m.edit_text(
        f"╭─ Ping\n┊ 🏓 Pong!\n┊ ⚡ Latencia : {latency:.0f} ms\n"
        f"╰─ Estado    : Online ✅\n\n{BOT_SIGNATURE}")


# ─── COMANDO /queue ───
@bot.on_message(filters.command(["queue", "Queue", "cola"]))
async def cmd_queue(client: Client, message: Message):
    if not is_user_authorized(message.from_user.id): return
    from core.queue import download_queue
    q_size = download_queue.qsize()
    status = "✅ Sin tareas pendientes" if q_size == 0 else f"⏳ {q_size} en espera"
    await message.reply_text(
        f"╭─ Cola de Descargas\n┊ {status}\n"
        f"╰──────────────────\n\n{BOT_SIGNATURE}")


# ─── COMANDO /perfil ───
@bot.on_message(filters.command(["perfil", "profile", "miperfil"]))
async def cmd_perfil(client: Client, message: Message):
    uid = message.from_user.id
    if not is_user_authorized(uid):
        return await message.reply_text("⛔ No estás autorizado.")

    user = user_db.get_user(uid)
    plan = user.get("plan", "free")
    plan_info = PLANES.get(plan, PLANES["free"])

    await message.reply_text(
        f"╭─「 👤 <b>Mi Perfil</b> 」\n"
        f"├──────────────────────────\n"
        f"┊ 🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"┊ 💎 <b>Plan:</b> {plan_info['nombre']}\n"
        f"┊ 🪙 <b>Créditos:</b> {user.get('creditos', 0)}\n"
        f"┊ 📊 <b>Usos:</b> {user.get('total_descargas', 0)}/{plan_info.get('limite_total', 5)}\n"
        f"┊ 📺 <b>Calidad máx:</b> {plan_info.get('calidad_maxima', '480p')}\n"
        f"╰──────────────────────────\n\n{BOT_SIGNATURE}",
        parse_mode=enums.ParseMode.HTML)


# ─── COMANDO /stat ───
@bot.on_message(filters.command(["stat", "Stat", "STAT"]))
async def cmd_stat(client: Client, message: Message):
    if not is_user_authorized(message.from_user.id): return
    import psutil, platform

    uptime = time.time() - time.time()  # Placeholder: usar start_time global
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    await message.reply_text(
        f"╭─「 📊 Estado del Sistema 」\n"
        f"┊ 🧠 RAM: {ram.percent}% ({get_readable_size(ram.used)}/{get_readable_size(ram.total)})\n"
        f"┊ 💽 Disco: {disk.percent}% ({get_readable_size(disk.used)}/{get_readable_size(disk.total)})\n"
        f"┊ 🖥️ Servidor: {platform.node() or 'bot'}\n"
        f"┊ ⚙️ Plataforma: {platform.system()} {platform.release()}\n"
        f"╰──────────────────\n\n{BOT_SIGNATURE}")


# ─── COMANDOS DE ADMIN ───
@bot.on_message(filters.command("id") & filters.reply)
async def cmd_auth_user(client: Client, message: Message):
    if not is_admin(message.from_user.id): return
    target = message.reply_to_message.from_user
    if target:
        authorized_users[str(target.id)] = {
            "role": "user", "username": target.username or "",
            "name": target.first_name or "", "plan": "free"
        }
        save_auth_users()
        await message.reply_text(
            f"✅ Acceso concedido a [{target.first_name}](tg://user?id={target.id})")

@bot.on_message(filters.command(["addid", "Addid"]))
async def cmd_add_by_id(client: Client, message: Message):
    if not is_admin(message.from_user.id): return
    parts = message.text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await message.reply_text("Uso: /addid <ID>")
    authorized_users[parts[1]] = {"role": "user", "username": "", "name": "", "plan": "free"}
    save_auth_users()
    await message.reply_text(f"✅ ID `{parts[1]}` autorizado.")

@bot.on_message(filters.command(["rmid", "removebyid"]))
async def cmd_remove_by_id(client: Client, message: Message):
    if not is_admin(message.from_user.id): return
    parts = message.text.strip().split()
    if len(parts) < 2: return await message.reply_text("Uso: /rmid <ID>")
    if parts[1] in authorized_users:
        del authorized_users[parts[1]]
        save_auth_users()
        await message.reply_text(f"❌ ID `{parts[1]}` eliminado.")

@bot.on_message(filters.command(["setplan"]))
async def cmd_setplan(client: Client, message: Message):
    if not is_admin(message.from_user.id): return
    parts = message.text.strip().split()
    if len(parts) < 3: return await message.reply_text("Uso: /setplan <ID> <free|basico|premium|pro>")
    uid_str, plan = parts[1], parts[2]
    if plan not in PLANES:
        return await message.reply_text(f"⚠️ Plan inválido. Opciones: {', '.join(PLANES.keys())}")
    user_db.update_user(int(uid_str), {"plan": plan})
    await message.reply_text(f"💎 Plan de `{uid_str}` actualizado a **{plan.upper()}**.")

@bot.on_message(filters.command("users"))
async def cmd_users(client: Client, message: Message):
    if not is_admin(message.from_user.id): return
    text = "╭─ Usuarios autorizados\n"
    count = 1
    for str_uid, info in authorized_users.items():
        role = " 🛡" if info.get("role") == "admin" else ""
        text += f"┊ {count}. {str_uid} [{info.get('plan', 'free')}]{role}\n"
        count += 1
    text += f"╰─ Total: {count - 1}\n\n{BOT_SIGNATURE}"
    await message.reply_text(text)


# ─── COMANDO /play (BÚSQUEDA + DESCARGA AUDIO) ───
@bot.on_message(filters.command(["play", "Play"]))
async def cmd_play(client: Client, message: Message):
    uid = message.from_user.id
    if not is_user_authorized(uid): return

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply_text("Uso: /play <nombre canción o artista>")

    query = parts[1].strip()
    uname = message.from_user.first_name
    task_id = f"{uid}_{int(time.time())}"
    msg = await message.reply_text(f"🔍 Buscando: <b>{query[:50]}</b>...",
                                     parse_mode=enums.ParseMode.HTML)

    from engines.music_engine import _yt_search, procesar_audio
    hits = await _yt_search(query, n=1)
    if not hits:
        return await msg.edit_text("❌ Sin resultados.")
    await msg.delete()
    asyncio.create_task(procesar_audio(client, message, hits[0]["url"], uname, task_id))
