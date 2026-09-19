"""
╔══════════════════════════════════════════════════════════════════╗
║  BOT DESCARGAS — Punto de Entrada Principal                       ║
║  Arquitectura modular con auto-recuperación y queue worker        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import asyncio
import traceback
import httpx

# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACIÓN (debe importarse primero)
# ═══════════════════════════════════════════════════════════════════
try:
    from config.settings import (
        API_ID, API_HASH, BOT_TOKEN, ADMIN_ID,
        DOWNLOAD_DIR, BOT_SIGNATURE, now_ec,
    )
    print("[main] ✓ config.settings cargado")
except Exception as e:
    print(f"[main] ❌ ERROR CRÍTICO en config.settings: {e}")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════
# 2. CLIENTE DE PYROGRAM
# ═══════════════════════════════════════════════════════════════════
from pyrogram import Client

bot = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="/tmp",
    workers=8,
    sleep_threshold=30,
    max_concurrent_transmissions=4,
)


# ═══════════════════════════════════════════════════════════════════
# 3. IMPORTACIÓN DE HANDLERS (con tolerancia a fallos)
# ═══════════════════════════════════════════════════════════════════
# Cada importación registra los @bot.on_message / @bot.on_callback_query
# automáticamente. Si un módulo no existe todavía, no rompe el arranque.

_handlers_loaded = []
_handlers_failed = []

def _try_import(module_path: str, label: str):
    """Intenta importar un módulo y registra si tuvo éxito o no."""
    try:
        __import__(module_path, fromlist=["*"])
        _handlers_loaded.append(label)
        print(f"[main] ✓ {label} cargado")
        return True
    except ModuleNotFoundError as e:
        _handlers_failed.append((label, f"no encontrado: {e}"))
        print(f"[main] ⚠ {label} omitido (aún no existe)")
        return False
    except Exception as e:
        _handlers_failed.append((label, str(e)))
        print(f"[main] ❌ {label} falló al cargar: {e}")
        traceback.print_exc()
        return False


# Handlers de comandos y mensajes (los más importantes)
_try_import("handlers.commands", "handlers.commands")
_try_import("handlers.messages", "handlers.messages")
_try_import("handlers.callbacks", "handlers.callbacks")

# Handlers de FFmpeg (config, watermark, etc.)
_try_import("ffmpeg_try_import("config.ffmpeg_config", "config.ffmpeg_config")_config", "ffmpeg_config")


# ═══════════════════════════════════════════════════════════════════
# 4. CONEXIÓN DE LA COLA CON EL PROCESADOR
# ═══════════════════════════════════════════════════════════════════
# La cola (core.queue) necesita saber QUÉ función usar para procesar
# cada tarea. Se la inyectamos aquí, después de importar los handlers.

try:
    from core.queue import queue_worker, set_process_callback
    print("[main] ✓ core.queue cargado")
except Exception as e:
    print(f"[main] ❌ ERROR CRÍTICO en core.queue: {e}")
    sys.exit(1)

try:
    from handlers.messages import procesar_descarga
    set_process_callback(procesar_descarga)
    print("[main] ✓ Cola conectada a procesar_descarga")
except Exception as e:
    print(f"[main] ⚠ No se pudo conectar la cola (handlers.messages): {e}")


# ═══════════════════════════════════════════════════════════════════
# 5. TAREAS DE FONDO CON AUTO-RECUPERACIÓN
# ═══════════════════════════════════════════════════════════════════

async def _run_supervised(name: str, coro_fn, cooldown: float = 5.0):
    """
    Envuelve tareas de fondo (queue_worker, daily_reset_loop) con
    auto-recuperación. Si una tarea se cae, se reinicia sola tras
    una pausa y notifica al admin.
    """
    while True:
        try:
            await coro_fn()
            # Si la tarea termina sin error (no debería), se relanza.
            print(f"[supervisor] '{name}' terminó inesperadamente, relanzando...")
        except asyncio.CancelledError:
            raise  # Apagado real del bot: no se absorbe
        except Exception as e:
            print(f"[supervisor] '{name}' se cayó: {e!r} — reiniciando en {cooldown:.0f}s")
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>Auto-recuperación</b>\n"
                    f"┊ Tarea: <code>{name}</code>\n"
                    f"┊ Error: <code>{str(e)[:300]}</code>\n"
                    f"┊ Se reinició solo.\n\n{BOT_SIGNATURE}",
                    parse_mode="html",
                )
            except Exception:
                pass
        await asyncio.sleep(cooldown)


async def _daily_reset_loop():
    """Resetea los contadores diarios a medianoche (hora Ecuador)."""
    try:
        from core.database import user_db
    except Exception:
        print("[daily_reset] core.database no disponible, saltando.")
        return

    last = now_ec().date()
    try:
        user_db.reset_contadores_diarios()
    except Exception as e:
        print(f"[daily_reset] error inicial: {e}")

    while True:
        await asyncio.sleep(1800)  # chequea cada 30 min
        today = now_ec().date()
        if today != last:
            try:
                user_db.reset_contadores_diarios()
                last = today
                print("[daily_reset] Contadores reiniciados")
            except Exception as e:
                print(f"[daily_reset] error: {e}")


# ═══════════════════════════════════════════════════════════════════
# 6. FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

async def main():
    async with bot:
        me = await bot.get_me()
        print("═" * 60)
        print(f"  🚀 BOT INICIADO")
        print(f"  🤖 Username : @{me.username}")
        print(f"  🆔 Bot ID   : {me.id}")
        print(f"  👑 Admin ID : {ADMIN_ID}")
        print(f"  📁 Descargas: {DOWNLOAD_DIR}")
        print("═" * 60)

        # ── Estado de los handlers ──
        if _handlers_loaded:
            print(f"[main] Handlers activos: {', '.join(_handlers_loaded)}")
        if _handlers_failed:
            print(f"[main] Handlers NO cargados:")
            for label, err in _handlers_failed:
                print(f"       - {label}: {err}")

        # ── Notificar al admin que arrancó ──
        if ADMIN_ID:
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"✅ <b>Bot iniciado correctamente</b>\n"
                    f"┊ @{me.username}\n"
                    f"┊ Handlers: {len(_handlers_loaded)} cargados\n\n{BOT_SIGNATURE}",
                    parse_mode="html",
                )
            except Exception:
                pass

        # ── Registrar handlers de FFmpeg (si existen) ──
        try:
            from ffmpeg_config impofrom config.ffmpeg_config import register_ffmpeg_config_handlersrt register_ffmpeg_config_handlers
            from handlers.commands import is_admin
            register_ffmpeg_config_handlers(bot, is_admin, BOT_SIGNATURE)
            print("[main] ✓ Handlers de FFmpeg registrados")
        except Exception as e:
            print(f"[main] ⚠ Handlers de FFmpeg no registrados: {e}")

        # ── Lanzar tareas de fondo ──
        loop = asyncio.get_event_loop()
        loop.create_task(_run_supervised("queue_worker", queue_worker))
        loop.create_task(_run_supervised("daily_reset_loop", _daily_reset_loop))
        print("[main] ✓ Tareas de fondo iniciadas")

        # ── Esperar indefinidamente ──
        await asyncio.Event().wait()


# ═══════════════════════════════════════════════════════════════════
# 7. PUNTO DE ENTRADA CON SUPERVISOR DE ÚLTIMA INSTANCIA
# ═══════════════════════════════════════════════════════════════════

def _notify_crash_http(error: Exception):
    """Notifica al admin por HTTP directo (sin depender de Pyrogram)."""
    if not BOT_TOKEN or not ADMIN_ID:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": ADMIN_ID,
                "text": (
                    f"🔴 <b>El bot se cayó por completo</b>\n"
                    f"┊ Error: <code>{str(error)[:300]}</code>\n"
                    f"┊ Reiniciando automáticamente...\n\n{BOT_SIGNATURE}"
                ),
                "parse_mode": "html",
            },
            timeout=10,
        )
    except Exception:
        pass


if __name__ == "__main__":
    # ── Validación de credenciales ──
    if not API_ID or API_ID == 0:
        print("❌ ERROR: Configura API_ID en los Secrets")
        sys.exit(1)
    if not API_HASH:
        print("❌ ERROR: Configura API_HASH en los Secrets")
        sys.exit(1)
    if not BOT_TOKEN:
        print("❌ ERROR: Configura BOT_TOKEN en los Secrets")
        sys.exit(1)

    # ── Bucle de auto-reinicio con backoff exponencial ──
    _restart_wait = 5
    while True:
        print("🚀 Iniciando bot...")
        _start_ts = time.time()
        try:
            bot.run(main())
            print("[supervisor] bot.run() terminó sin excepción. Reiniciando...")
        except KeyboardInterrupt:
            print("🛑 Detenido manualmente (Ctrl+C).")
            break
        except Exception as e:
            print(f"[supervisor] El bot se cayó por completo: {e!r}")
            _notify_crash_http(e)

        # Si el bot estuvo vivo > 60s, reseteamos el backoff
        if time.time() - _start_ts > 60:
            _restart_wait = 5

        print(f"[supervisor] Reintentando en {_restart_wait}s...")
        time.sleep(_restart_wait)
        _restart_wait = min(_restart_wait * 2, 120)
