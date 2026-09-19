"""
Handlers de Callback Query (botones inline)
─────────────────────────────────────────────
Perfil, planes, pagos, admin, reporte de bugs, marca de agua y encode.
"""

import os
import json
import time
import asyncio
from datetime import timedelta
from pyrogram import Client, filters, enums
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config.ffmpeg_config import set_config_value
from config.settings import ADMIN_ID, BOT_SIGNATURE, PLANES, PLAN_HIERARCHY, now_ec
from core.database import user_db, credit_system, payment_system, referral_system
from core.utils import get_readable_size

# ─── ESTADOS ───
_bug_sessions: dict = {}
_wm_ass_pending: dict = {}

# ─── IMPORTAR FUNCIONES DE AUTORIZACIÓN ───
try:
    from handlers.commands import is_admin, is_user_authorized, get_user_plan, authorized_users
except ImportError:
    def is_admin(uid): return uid == ADMIN_ID
    def is_user_authorized(uid): return True
    def get_user_plan(uid): return user_db.get_user(uid).get("plan", "free")
    authorized_users = {}


# ═══════════════════════════════════════════════════════════════════
#  CERRAR PANEL (universal)
# ═══════════════════════════════════════════════════════════════════

@bot.on_callback_query(filters.regex(r"^close_panel$"))
async def cb_close_panel(client: Client, cb: CallbackQuery):
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.answer()


# ═══════════════════════════════════════════════════════════════════
#  PERFIL
# ═══════════════════════════════════════════════════════════════════

@bot.on_callback_query(filters.regex(r"^show_profile$"))
async def cb_show_profile(client: Client, cb: CallbackQuery):
    uid = cb.from_user.id
    user = user_db.get_user(uid)
    plan = user.get("plan", "free")
    plan_info = PLANES.get(plan, PLANES["free"])

    text = (
        f"╭─「 👤 <b>Mi Perfil</b> 」\n"
        f"├──────────────────────────\n"
        f"┊ 🆔 <b>ID:</b> <code>{uid}</code>\n"
        f"┊ 💎 <b>Plan:</b> {plan_info['nombre']}\n"
        f"┊ 🪙 <b>Créditos:</b> {user.get('creditos', 0)}\n"
        f"┊ 📊 <b>Usos totales:</b> {user.get('total_descargas', 0)}\n"
        f"┊ 📺 <b>Calidad máx:</b> {plan_info.get('calidad_maxima', '480p')}\n"
        f"╰──────────────────────────\n\n{BOT_SIGNATURE}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 Ver Planes", callback_data="panel_plan_list")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="close_panel")],
    ])
    try:
        await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
    except Exception:
        pass
    await cb.answer()


# ═══════════════════════════════════════════════════════════════════
#  REPORTE DE BUGS
# ═══════════════════════════════════════════════════════════════════

@bot.on_callback_query(filters.regex(r"^report_bug$"))
async def cb_report_bug(client: Client, cb: CallbackQuery):
    uid = cb.from_user.id
    if not is_user_authorized(uid):
        return await cb.answer("⛔ No autorizado.", show_alert=True)
    uname = cb.from_user.username or cb.from_user.first_name or str(uid)
    _bug_sessions[str(uid)] = {"step": "awaiting_bugreport", "username": uname}
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="bugreport_cancel")]])
    await cb.message.edit_text(
        f"╭─「 🐛 Reportar Bug 」\n┊\n"
        f"┊ Escribe y envía la descripción del problema:\n"
        f"╰─ Se enviará a los administradores.\n\n{BOT_SIGNATURE}",
        reply_markup=kb)
    await cb.answer()


@bot.on_callback_query(filters.regex(r"^bugreport_cancel$"))
async def cb_report_bug_cancel(client: Client, cb: CallbackQuery):
    _bug_sessions.pop(str(cb.from_user.id), None)
    await cb.message.edit_text(f"❌ Reporte cancelado.\n\n{BOT_SIGNATURE}")
    await cb.answer()


# ═══════════════════════════════════════════════════════════════════
#  PANEL DE PLANES Y PAGOS
# ═══════════════════════════════════════════════════════════════════

@bot.on_callback_query(filters.regex(r"^panel_plan_(.+)$"))
async def cb_panel_plan(client: Client, cb: CallbackQuery):
    action = cb.matches[0].group(1)
    uid = cb.from_user.id

    try:
        if action == "main":
            user = user_db.get_user(uid)
            plan = user.get("plan", "free")
            plan_info = PLANES.get(plan, PLANES["free"])
            text = (
                f"╭─「 💳 <b>Membresía</b> 」\n"
                f"┊ 👤 Usuario: <code>{uid}</code>\n"
                f"┊ 💎 Plan: {plan_info['nombre']}\n"
                f"┊ 🪙 Créditos: {user.get('creditos', 0)}\n"
                f"╰──────────────────────────\n\n{BOT_SIGNATURE}")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Ver Planes", callback_data="panel_plan_list")],
                [InlineKeyboardButton("💳 Comprar Créditos", callback_data="panel_plan_cred")],
                [InlineKeyboardButton("🤝 Referidos", callback_data="panel_plan_ref")],
                [InlineKeyboardButton("❌ Cerrar", callback_data="close_panel")],
            ])
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        elif action == "list":
            text = "╭─「 💎 PLANES DISPONIBLES 」\n┊\n"
            kb_rows = []
            for plan_id, plan in PLANES.items():
                if plan_id == "free" or plan_id.startswith("creditos_"):
                    continue
                icon = "🔵" if plan_id == "basico" else "🟣" if plan_id == "premium" else "⭐"
                text += (
                    f"┊ {icon} <b>{plan['nombre']}</b>\n"
                    f"┊   💰 ${plan['precio']:.2f}/mes\n"
                    f"┊   📺 {plan['calidad_maxima']}\n┊\n")
                kb_rows.append([InlineKeyboardButton(
                    f"{icon} {plan['nombre']} — ${plan['precio']:.2f}",
                    callback_data=f"panel_plan_chk:{plan_id}")])
            text += f"╰──────────────────────────\n\n{BOT_SIGNATURE}"
            kb_rows.append([InlineKeyboardButton("⬅️ Volver", callback_data="panel_plan_main")])
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup(kb_rows))

        elif action == "cred":
            user = user_db.get_user(uid)
            text = (f"╭─「 💳 Créditos 」\n┊\n"
                    f"┊ <b>Saldo:</b> {user.get('creditos', 0)} créditos\n┊\n")
            kb_rows = []
            for pkg_id, pkg in credit_system.paquetes.items():
                text += f"┊ 📦 {pkg['creditos']} créditos — ${pkg['precio']:.2f}\n"
                kb_rows.append(InlineKeyboardButton(
                    f"📦 {pkg_id} Créditos",
                    callback_data=f"panel_plan_buyc:{pkg_id}"))
            text += f"╰──────────────────────────\n\n{BOT_SIGNATURE}"
            kb_layout = [kb_rows[i:i+2] for i in range(0, len(kb_rows), 2)]
            kb_layout.append([InlineKeyboardButton("⬅️ Volver", callback_data="panel_plan_main")])
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup(kb_layout))

        elif action == "ref":
            user = user_db.get_user(uid)
            try:
                me = await client.get_me()
                bot_username = me.username
            except Exception:
                bot_username = "TuBot"
            text = (
                f"╭─「 🤝 Referidos 」\n┊\n"
                f"┊ <b>Tu enlace:</b> t.me/{bot_username}?start={uid}\n┊\n"
                f"┊ 🪙 Vos: <b>+{referral_system.bonus_referidor} créditos</b>\n"
                f"┊ 🪙 Tu invitado: <b>+{referral_system.bonus_referido} créditos</b>\n┊\n"
                f"┊ 👥 Referidos: {len(user.get('referidos', []))}\n"
                f"╰──────────────────────────\n\n{BOT_SIGNATURE}")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="panel_plan_main")]])
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        elif action.startswith("chk:"):
            plan_id = action.split(":", 1)[1]
            if plan_id not in PLANES:
                return await cb.answer("Plan no encontrado", show_alert=True)
            plan = PLANES[plan_id]
            text = (
                f"╭─「 💳 Confirmar Compra 」\n┊\n"
                f"┊ <b>Plan:</b> {plan['nombre']}\n"
                f"┊ <b>Precio:</b> ${plan['precio']:.2f} USD\n"
                f"╰─ Selecciona método de pago:\n\n{BOT_SIGNATURE}")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔶 Binance Pay", callback_data=f"panel_plan_pay:binance:{plan_id}")],
                [InlineKeyboardButton("💳 PayPal", callback_data=f"panel_plan_pay:paypal:{plan_id}")],
                [InlineKeyboardButton("⬅️ Volver", callback_data="panel_plan_list")],
            ])
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        elif action.startswith("buyc:"):
            pkg_id = action.split(":", 1)[1]
            pkg = credit_system.paquetes.get(pkg_id)
            if not pkg:
                return await cb.answer("Paquete no encontrado", show_alert=True)
            text = (
                f"╭─「 🪙 Comprar {pkg['creditos']} Créditos 」\n"
                f"┊ <b>Precio:</b> ${pkg['precio']:.2f} USD\n"
                f"┊ <b>Tu ID:</b> <code>{uid}</code>\n"
                f"╰─ Selecciona método:\n\n{BOT_SIGNATURE}")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔶 Binance Pay", callback_data=f"panel_plan_pay:binance:creditos_{pkg_id}")],
                [InlineKeyboardButton("💳 PayPal", callback_data=f"panel_plan_pay:paypal:creditos_{pkg_id}")],
                [InlineKeyboardButton("⬅️ Volver", callback_data="panel_plan_cred")],
            ])
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        elif action.startswith("pay:"):
            _, metodo, plan_id = action.split(":", 2)
            info = payment_system.get_payment_info(plan_id, metodo)
            if not info:
                return await cb.answer("Método no válido", show_alert=True)
            nombre_plan = PLANES.get(plan_id, {}).get("nombre", plan_id)

            # Guardar pago pendiente
            try:
                pending_file = "pending_payments.json"
                pending = {}
                if os.path.exists(pending_file):
                    with open(pending_file, "r") as f:
                        pending = json.load(f)
                pending[str(uid)] = {
                    "plan": plan_id, "nombre_plan": nombre_plan,
                    "metodo": metodo, "precio": info["precio"],
                    "fecha": now_ec().isoformat(),
                }
                with open(pending_file, "w") as f:
                    json.dump(pending, f, indent=2)
            except Exception as e:
                print(f"[panel_plan/pay] error: {e}")

            kb_buttons = []
            if metodo == "binance":
                text = (
                    f"╭─「 🔶 Binance Pay 」\n┊\n"
                    f"┊ <b>Plan:</b> {nombre_plan}\n"
                    f"┊ <b>Monto:</b> ${info['precio']:.2f} USDT\n"
                    f"┊ <b>UID:</b> <code>{info['uid']}</code>\n"
                    f"╰─ Copia el UID y transfiere.\n\n{BOT_SIGNATURE}")
            else:
                text = (
                    f"╭─「 💳 PayPal 」\n┊\n"
                    f"┊ <b>Plan:</b> {nombre_plan}\n"
                    f"┊ <b>Monto:</b> ${info['precio']:.2f} USD\n"
                    f"╰─ Presiona el botón para pagar.\n\n{BOT_SIGNATURE}")
                kb_buttons.append([InlineKeyboardButton("💳 Pagar en PayPal", url=info["link"])])

            from urllib.parse import quote
            mensaje = f"Hola, pagué ${info['precio']} por {nombre_plan}. Mi ID: {uid}."
            kb_buttons.append([InlineKeyboardButton(
                "✅ Ya pagué",
                url=f"https://t.me/Ryota_YT?text={quote(mensaje)}")])
            kb_buttons.append([InlineKeyboardButton(
                "⬅️ Volver",
                callback_data=f"panel_plan_chk:{plan_id}" if not plan_id.startswith("creditos_") else "panel_plan_cred")])
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup(kb_buttons))

    except Exception as e:
        print(f"[panel_plan] error: {e}")
    finally:
        await cb.answer()


# ═══════════════════════════════════════════════════════════════════
#  PANEL DE ADMIN
# ═══════════════════════════════════════════════════════════════════

def _load_bot_settings():
    try:
        if os.path.exists("bot_settings.json"):
            with open("bot_settings.json", "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"acceso_libre": True, "anti_multicuenta": False}


def _save_bot_settings(settings: dict):
    with open("bot_settings.json", "w") as f:
        json.dump(settings, f, indent=2)


def _admin_panel_text_kb():
    settings = _load_bot_settings()
    acceso_libre = settings.get("acceso_libre", True)
    anti_mc = settings.get("anti_multicuenta", False)

    text = (
        f"╭─「 👑 PANEL DE ADMINISTRACIÓN 」\n┊\n"
        f"┊ 👥 <b>Usuarios:</b> {len(user_db.users)}\n"
        f"┊ 🔓 <b>Acceso:</b> {'Libre' if acceso_libre else 'Restringido'}\n"
        f"┊ 📱 <b>Anti multi-cuenta:</b> {'Activado' if anti_mc else 'Desactivado'}\n"
        f"╰──────────────────────────\n\n{BOT_SIGNATURE}")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Ver Pagos Pendientes", callback_data="admin_list_pending")],
        [InlineKeyboardButton(
            f"{'🔒 Restringir' if acceso_libre else '🔓 Liberar'} Acceso",
            callback_data="admin_toggle_acceso")],
        [InlineKeyboardButton(
            f"{'📴 Desactivar' if anti_mc else '📱 Activar'} Anti multi-cuenta",
            callback_data="admin_toggle_multicuenta")],
        [InlineKeyboardButton("🔄 Actualizar", callback_data="admin_refresh_stats")],
        [InlineKeyboardButton("❌ Cerrar", callback_data="close_panel")],
    ])
    return text, kb


@bot.on_callback_query(filters.regex(r"^admin_(refresh_stats|list_pending)$"))
async def cb_admin_actions(client: Client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("Acceso denegado.", show_alert=True)
    action = cb.matches[0].group(1)

    if action == "refresh_stats":
        text, kb = _admin_panel_text_kb()
        try:
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
        except Exception:
            pass

    elif action == "list_pending":
        pending = {}
        if os.path.exists("pending_payments.json"):
            with open("pending_payments.json", "r") as f:
                try: pending = json.load(f)
                except Exception: pass
        text = "╭─「 📥 PAGOS PENDIENTES 」\n┊\n"
        kb_rows = []
        if not pending:
            text += "┊ <i>No hay pagos pendientes.</i>\n"
        else:
            for uid_str, data in pending.items():
                text += f"┊ 🆔 <code>{uid_str}</code> — <b>{data['nombre_plan']}</b> (${data['precio']})\n"
                kb_rows.append([
                    InlineKeyboardButton("✅ Aprobar",
                        callback_data=f"admin_approve:{uid_str}:{data['plan']}"),
                    InlineKeyboardButton("❌ Rechazar",
                        callback_data=f"admin_reject:{uid_str}"),
                ])
        text += f"╰──────────────────────────\n\n{BOT_SIGNATURE}"
        kb_rows.append([InlineKeyboardButton("⬅️ Volver", callback_data="admin_refresh_stats")])
        try:
            await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup(kb_rows))
        except Exception:
            pass
    await cb.answer()


@bot.on_callback_query(filters.regex(r"^admin_toggle_acceso$"))
async def cb_admin_toggle_acceso(client: Client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("Acceso denegado.", show_alert=True)
    settings = _load_bot_settings()
    settings["acceso_libre"] = not settings.get("acceso_libre", True)
    _save_bot_settings(settings)
    estado = "LIBRE 🔓" if settings["acceso_libre"] else "RESTRINGIDO 🔒"
    await cb.answer(f"Acceso: {estado}", show_alert=True)
    text, kb = _admin_panel_text_kb()
    try:
        await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
    except Exception:
        pass


@bot.on_callback_query(filters.regex(r"^admin_toggle_multicuenta$"))
async def cb_admin_toggle_multicuenta(client: Client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("Acceso denegado.", show_alert=True)
    settings = _load_bot_settings()
    settings["anti_multicuenta"] = not settings.get("anti_multicuenta", False)
    _save_bot_settings(settings)
    estado = "ACTIVADO 📱" if settings["anti_multicuenta"] else "DESACTIVADO 📴"
    await cb.answer(f"Anti multi-cuenta: {estado}", show_alert=True)
    text, kb = _admin_panel_text_kb()
    try:
        await cb.message.edit_text(text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
    except Exception:
        pass


@bot.on_callback_query(filters.regex(r"^admin_(approve|reject):(.+)$"))
async def cb_admin_gestion_pago(client: Client, cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return await cb.answer("Acceso denegado.", show_alert=True)
    accion = cb.matches[0].group(1)
    params = cb.matches[0].group(2)
    pending = {}
    if os.path.exists("pending_payments.json"):
        with open("pending_payments.json", "r") as f:
            try: pending = json.load(f)
            except Exception: pass

    if accion == "approve":
        uid_str, plan_id = params.split(":", 1)
        uid_int = int(uid_str)
        if plan_id.startswith("creditos_"):
            pkg_id = plan_id.split("creditos_", 1)[1]
            resultado = credit_system.comprar_creditos(uid_int, pkg_id)
            if uid_str in pending:
                del pending[uid_str]
                with open("pending_payments.json", "w") as f:
                    json.dump(pending, f, indent=2)
            if resultado:
                await cb.answer(f"✅ {resultado['total_creditos']} créditos", show_alert=True)
                try:
                    await client.send_message(uid_int,
                        f"🎉 <b>¡Pago Aprobado!</b>\n\n"
                        f"🪙 Se acreditaron <b>{resultado['total_creditos']} créditos</b>.\n\n{BOT_SIGNATURE}",
                        parse_mode=enums.ParseMode.HTML)
                except Exception:
                    pass
        else:
            user_db.update_user(uid_int, {
                "plan": plan_id,
                "fecha_renovacion": (now_ec() + timedelta(days=30)).isoformat(),
                "descargas_mes": 0,
            })
            if uid_str in pending:
                del pending[uid_str]
                with open("pending_payments.json", "w") as f:
                    json.dump(pending, f, indent=2)
            await cb.answer(f"✅ Plan activado", show_alert=True)
            try:
                nombre = PLANES.get(plan_id, {}).get("nombre", plan_id)
                await client.send_message(uid_int,
                    f"🎉 <b>¡Plan Activado!</b>\n\n📦 <b>Plan {nombre}</b> por 30 días.\n\n{BOT_SIGNATURE}",
                    parse_mode=enums.ParseMode.HTML)
            except Exception:
                pass

    elif accion == "reject":
        uid_str = params
        if uid_str in pending:
            del pending[uid_str]
            with open("pending_payments.json", "w") as f:
                json.dump(pending, f, indent=2)
        await cb.answer(f"Solicitud rechazada.", show_alert=True)

    await cb_admin_actions(client, cb)


# ═══════════════════════════════════════════════════════════════════
#  MARCA DE AGUA — Botones /crearwm
# ═══════════════════════════════════════════════════════════════════

_ASS_POS_LABELS = {
    7: "↖ Arriba Izq", 8: "⬆ Arriba Centro", 9: "↗ Arriba Der",
    4: "⬅ Centro Izq", 5: "✦ Centro", 6: "➡ Centro Der",
    1: "↙ Abajo Izq", 2: "⬇ Abajo Centro", 3: "↘ Abajo Der",
}


def _wm_ass_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↖", callback_data="wmass_pos:7"),
         InlineKeyboardButton("⬆", callback_data="wmass_pos:8"),
         InlineKeyboardButton("↗", callback_data="wmass_pos:9")],
        [InlineKeyboardButton("⬅", callback_data="wmass_pos:4"),
         InlineKeyboardButton("✦", callback_data="wmass_pos:5"),
         InlineKeyboardButton("➡", callback_data="wmass_pos:6")],
        [InlineKeyboardButton("↙", callback_data="wmass_pos:1"),
         InlineKeyboardButton("⬇", callback_data="wmass_pos:2"),
         InlineKeyboardButton("↘", callback_data="wmass_pos:3")],
        [InlineKeyboardButton("🔹 Chico", callback_data="wmass_size:22"),
         InlineKeyboardButton("🔸 Mediano", callback_data="wmass_size:32"),
         InlineKeyboardButton("🔶 Grande", callback_data="wmass_size:48")],
        [InlineKeyboardButton("✅ Guardar", callback_data="wmass_save")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="wmass_cancel")],
    ])


def _wm_ass_preview_text(sess: dict) -> str:
    pos_label = _ASS_POS_LABELS.get(sess.get("alignment", 9), "—")
    return (
        f"╭─「 🖋️ Crear Marca de Agua 」\n┊\n"
        f"┊ 📝 Texto    : <b>{sess.get('texto', '')}</b>\n"
        f"┊ 📍 Posición : <b>{pos_label}</b>\n"
        f"┊ 🔠 Tamaño   : <b>{sess.get('fontsize', 32)}px</b>\n"
        f"╰─ Ajusta con los botones.\n\n{BOT_SIGNATURE}")


@bot.on_callback_query(filters.regex(r"^wmass_pos:(\d)$"))
async def cb_wmass_pos(client: Client, cb: CallbackQuery):
    uid = str(cb.from_user.id)
    sess = _wm_ass_pending.get(uid)
    if not sess:
        return await cb.answer("Sesión expirada, usa /crearwm", show_alert=True)
    sess["alignment"] = int(cb.matches[0].group(1))
    try:
        await cb.message.edit_text(_wm_ass_preview_text(sess),
                                    parse_mode=enums.ParseMode.HTML,
                                    reply_markup=_wm_ass_kb())
    except Exception:
        pass
    await cb.answer()


@bot.on_callback_query(filters.regex(r"^wmass_size:(\d+)$"))
async def cb_wmass_size(client: Client, cb: CallbackQuery):
    uid = str(cb.from_user.id)
    sess = _wm_ass_pending.get(uid)
    if not sess:
        return await cb.answer("Sesión expirada", show_alert=True)
    sess["fontsize"] = int(cb.matches[0].group(1))
    try:
        await cb.message.edit_text(_wm_ass_preview_text(sess),
                                    parse_mode=enums.ParseMode.HTML,
                                    reply_markup=_wm_ass_kb())
    except Exception:
        pass
    await cb.answer()


@bot.on_callback_query(filters.regex(r"^wmass_cancel$"))
async def cb_wmass_cancel(client: Client, cb: CallbackQuery):
    _wm_ass_pending.pop(str(cb.from_user.id), None)
    await cb.message.edit_text(f"❌ Cancelado.\n\n{BOT_SIGNATURE}")
    await cb.answer()


@bot.on_callback_query(filters.regex(r"^wmass_save$"))
async def cb_wmass_save(client: Client, cb: CallbackQuery):
    uid = str(cb.from_user.id)
    sess = _wm_ass_pending.pop(uid, None)
    if not sess:
        return await cb.answer("Sesión expirada", show_alert=True)
    try:
        from ffmpeg_config import set_config_value
    except ImportError:
        return await cb.answer("ffmpeg_config no disponible", show_alert=True)

    def build_ass(text, alignment, fontsize):
        safe = (text or "Watermark").replace("\r", "").replace("\n", "\\N")
        return (
            "[Script Info]\r\nScriptType: v4.00+\r\nPlayResX: 1920\r\nPlayResY: 1080\r\n"
            "ScaledBorderAndShadow: yes\r\nWrapStyle: 2\r\n\r\n"
            "[V4+ Styles]\r\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\r\n"
            f"Style: Watermark,Arial,{fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,"
            f"&H64000000,0,-1,0,0,100,100,0,0,1,2.0,1.0,{alignment},20,20,35,1\r\n\r\n"
            "[Events]\r\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\r\n"
            f"Dialogue: 0,0:00:00.00,10:00:00.00,Watermark,,0,0,0,,{safe}\r\n")

    bot_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ass_dir = os.path.join(bot_dir, "watermarks")
    os.makedirs(ass_dir, exist_ok=True)
    stamp = now_ec().strftime("%Y%m%d_%H%M%S")
    file_name = f"watermark_{uid}_{stamp}.ass"
    save_path = os.path.join(ass_dir, file_name)
    with open(save_path, "w", encoding="utf-8", newline="") as f:
        f.write(build_ass(sess["texto"], sess["alignment"], sess["fontsize"]))
    set_config_value(int(uid), "wm_ass_path", save_path)
    set_config_value(int(uid), "spam_wm", "Sí")
    await cb.answer("¡Marca de agua creada!", show_alert=True)
    try:
        await cb.message.edit_text(
            f"✅ <b>Marca de agua ACTIVADA.</b>\n📄 <code>{file_name}</code>\n\n{BOT_SIGNATURE}",
            parse_mode=enums.ParseMode.HTML)
    except Exception:
        pass
    try:
        await client.send_document(cb.message.chat.id, save_path,
            caption=f"📄 Tu archivo .ass.\n\n{BOT_SIGNATURE}")
    except Exception:
        pass
