import os
import re
import json
import struct
import base64
import asyncio
import httpx
from Crypto.Cipher import AES
from Crypto.Util import Counter

_MEGA_API = "https://g.api.mega.co.nz/cs"
_MEGA_CHUNK = 4 * 1024 * 1024

# ─── UTILIDADES BASE64 Y AES ───
def _mega_b64decode(s: str) -> bytes:
    s = s.replace('-', '+').replace('_', '/')
    s += '=' * (-len(s) % 4)
    return base64.b64decode(s)

def _mega_b64encode(b: bytes) -> str:
    return base64.b64encode(b).decode().replace('+', '-').replace('/', '_').rstrip('=')

def _a32(b: bytes) -> list:
    b += b'\x00' * (-len(b) % 4)
    return list(struct.unpack('>' + 'I' * (len(b) // 4), b))

def _a32_bytes(a: list) -> bytes:
    return struct.pack('>' + 'I' * len(a), *a)

def _aes_cbc_enc_a32(data, key):
    c = AES.new(_a32_bytes(key), AES.MODE_CBC, iv=b'\x00' * 16)
    return _a32(c.encrypt(_a32_bytes(data)))

def _aes_cbc_dec_a32(data, key):
    c = AES.new(_a32_bytes(key), AES.MODE_CBC, iv=b'\x00' * 16)
    return _a32(c.decrypt(_a32_bytes(data)))

def _mega_prepare_key(password: str) -> list:
    pw = _a32(password.encode('utf-8'))
    pkey = [0x93C467E3, 0x7DB0C7A4, 0xD1BE3F81, 0x0152CB56]
    for _ in range(0x10000):
        for i in range(0, len(pw), 4):
            block = (pw[i:i+4] + [0, 0, 0, 0])[:4]
            pkey = _aes_cbc_enc_a32(pkey, block)
    return pkey

def _mega_stringhash(s: str, aes_key: list) -> str:
    h = [0, 0, 0, 0]
    for i, v in enumerate(_a32(s.encode('utf-8'))):
        h[i % 4] ^= v
    for _ in range(0x4000):
        h = _aes_cbc_enc_a32(h, aes_key)
    return _mega_b64encode(_a32_bytes([h[0], h[2]]))

def _mega_parse_url(url: str):
    m = re.search(r'mega\.nz/file/([^#\s]+)#([^\s&]+)', url)
    if m: return m.group(1), m.group(2)
    m = re.search(r'mega\.nz/#!([^!\s]+)!([^\s&]+)', url)
    if m: return m.group(1), m.group(2)
    return None, None

def _mega_decode_attrs(at_b64: str, aes_key_bytes: bytes) -> str:
    raw = _mega_b64decode(at_b64)
    raw += b'\x00' * (-len(raw) % 16)
    plain = AES.new(aes_key_bytes, AES.MODE_CBC, iv=b'\x00' * 16).decrypt(raw)
    plain = plain.decode('utf-8', errors='ignore').rstrip('\x00')
    if plain.startswith('MEGA'):
        try:
            return json.loads(plain[4:]).get('n', '')
        except Exception:
            pass
    return ''

async def _mega_api(payload: list, sid: str = '') -> list:
    params = {'id': 1}
    if sid: params['sid'] = sid
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(_MEGA_API, params=params, json=payload)
    return r.json()

# ─── DESCARGA PRINCIPAL ───
async def mega_download(url: str, dest_dir: str, task_id: str, progress_cb=None):
    """
    Descarga un archivo de MEGA a `dest_dir` y devuelve (path, title).
    Soporta enlaces públicos y con cuenta (opcional).
    """
    handle, key_b64 = _mega_parse_url(url)
    if not handle:
        raise ValueError("URL de MEGA no válida. Debe ser mega.nz/file/HANDLE#KEY")

    raw = _mega_b64decode(key_b64)
    if len(raw) < 32:
        raise ValueError("Clave MEGA inválida en el URL.")

    k = struct.unpack('>8I', raw[:32])
    aes_key_bytes = struct.pack('>4I', k[0]^k[4], k[1]^k[5], k[2]^k[6], k[3]^k[7])
    iv_int = (k[4] << 96) | (k[5] << 64)

    payload = [{"a": "g", "g": 1, "p": handle}]
    data = await _mega_api(payload)
    item = data[0]

    if isinstance(item, int):
        codes = {-2: "Enlace inválido o expirado.", -9: "Objeto no encontrado.",
                 -16: "Cuota de descarga excedida.", -18: "Recurso no disponible."}
        raise Exception(f"MEGA error {item}: {codes.get(item, 'desconocido')}")

    dl_url = item.get('g')
    total = item.get('s', 0)
    if not dl_url:
        raise Exception("MEGA no devolvió URL de descarga.")

    filename = _mega_decode_attrs(item.get('at', ''), aes_key_bytes) or f"mega_{handle}"
    dest_path = os.path.join(dest_dir, f"{task_id}_{filename}")

    ctr = Counter.new(128, initial_value=iv_int, little_endian=False)
    cipher = AES.new(aes_key_bytes, AES.MODE_CTR, counter=ctr)

    async with httpx.AsyncClient(timeout=None, follow_redirects=True) as hclient:
        async with hclient.stream('GET', dl_url) as resp:
            downloaded = 0
            with open(dest_path, 'wb') as f:
                async for chunk in resp.aiter_bytes(_MEGA_CHUNK):
                    await asyncio.sleep(0)
                    orig_len = len(chunk)
                    if orig_len % 16:
                        chunk += b'\x00' * (16 - orig_len % 16)
                    decrypted = cipher.decrypt(chunk)[:orig_len]
                    f.write(decrypted)
                    downloaded += orig_len
                    if progress_cb and total > 0:
                        await progress_cb(downloaded, total)

    title = filename.rsplit('.', 1)[0] if '.' in filename else filename
    return dest_path, title
