import asyncio
import time
import httpx
import sys
from pyrogram import Client

from config.settings import API_ID, API_HASH, BOT_TOKEN, ADMIN_ID
from core.queue import queue_worker, set_process_callback

# Inicializamos el cliente de Pyrogram
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workdir="/tmp")

# ─── IMPORTACIÓN DE HANDLERS (Aquí irán los tuyos) ───
# from handlers import commands, callbacks, messages
# Nota: Como aún no los hemos creado, dejamos esto comentado.

async def _run_supervised(name: str, coro_fn, cooldown: float = 5.0):
    """Envoltura de auto-recuperación para tareas de fondo."""
    while True:
        try:
            await coro_fn()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[supervisor] '{name}' se cayó: {e!r} — reiniciando en {cooldown:.0f}s")
            try:
                await bot.send_message(ADMIN_ID, f"⚠️ Auto-recuperación: {name} se cayó. Error: {str(e)[:300]}")
            except Exception:
                pass
        await asyncio.sleep(cooldown)

async def main():
    # Aquí inyectamos la función que procesará las descargas desde los handlers
    # set_process_callback(procesar_descarga)
    
    async with bot:
        me = await bot.get_me()
        print(f"Bot iniciado ✓ — @{me.username} (ID: {me.id})")
        
        # Registrar handlers
        # register_handlers(bot) 

        # Iniciar tareas de fondo
        asyncio.get_event_loop().create_task(_run_supervised("queue_worker", queue_worker))
        await asyncio.Event().wait()

if __name__ == "__main__":
    if not API_ID or not API_HASH or not BOT_TOKEN:
        print("❌ ERROR: Configura API_ID, API_HASH y BOT_TOKEN en los Secrets")
        sys.exit(1)

    _restart_wait = 5
    while True:
        _start_ts = time.time()
        try:
            bot.run(main())
            print("[supervisor] bot.run() terminó. Reiniciando...")
        except KeyboardInterrupt:
            print("🛑 Detenido manualmente.")
            break
        except Exception as e:
            print(f"[supervisor] El bot se cayó por completo: {e!r}")
            try:
                httpx.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": ADMIN_ID, "text": f"🔴 El bot se cayó. Reiniciando..."},
                    timeout=10
                )
            except Exception:
                pass

        if time.time() - _start_ts > 60:
            _restart_wait = 5
        time.sleep(_restart_wait)
        _restart_wait = min(_restart_wait * 2, 120)
