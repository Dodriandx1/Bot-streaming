import asyncio

# Cola global
download_queue: asyncio.Queue = asyncio.Queue()

# Referencia a la función de procesamiento (se inyectará desde main.py o handlers)
_process_task_callback = None

def set_process_callback(callback):
    global _process_task_callback
    _process_task_callback = callback

async def queue_worker():
    print("[worker] Cola iniciada, esperando tareas...")
    while True:
        item = await download_queue.get()
        try:
            client, message, url, uname, uid, label = item[:6]
            want_subs = item[6] if len(item) > 6 else False
            
            if _process_task_callback:
                await _process_task_callback(client, message, url, uname, uid, label, want_subs)
            else:
                print("[worker] Error: No hay callback de procesamiento configurado.")
        except Exception as e:
            print(f"[worker] error: {e}")
            try:
                _msg = locals().get("message")
                _un  = locals().get("uname", "?")
                if _msg is not None:
                    await _msg.reply_text(f"❌ Error inesperado: {str(e)[:200]}")
            except Exception:
                pass
        finally:
            download_queue.task_done()
