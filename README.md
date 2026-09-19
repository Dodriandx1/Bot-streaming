Aquí tienes el código completo y actualizado para tu archivo `README.md`, ajustado específicamente para la estructura de tu repositorio **DEMON2.0** (con `main.py` en la raíz y el script `start-worker.sh`):

```markdown
# DEMON2.0 - Telegram Downloader Bot

Bot descargador de medios para Telegram con soporte multi-plataforma, sistema de suscripciones, créditos, marca de agua personalizada y panel de administración.

**✪ Bot By → @The_canst & @Ryota_YT**

---

## 📋 Tabla de Contenidos

- [Despliegue en VPS (Contabo / Hostinger)](#-despliegue-en-vps-contabo--hostinger)
  - [Modo Worker con Docker](#-opción-docker-worker-recomendado)
  - [Modo Worker sin Docker (systemd)](#-opción-sin-docker-systemd)
- [Variables de Entorno](#-variables-de-entorno)
- [YouTube y Cookies](#-youtube-y-cookies)
- [Páginas de Cómics y Galerías](#-páginas-de-cómics-y-galerías)
- [Características](#-características)
- [Comandos](#-comandos)
- [Planes y Precios](#-planes-y-precios)
- [Sistema de Créditos y Referidos](#-sistema-de-créditos-y-referidos)
- [Marca de Agua (.ass)](#-marca-de-agua-ass)
- [Panel de Administración](#-panel-de-administración)
- [Arquitectura](#-arquitectura)
- [Solución de Problemas](#-solución-de-problemas)

---

## 🚀 Despliegue en VPS (Contabo / Hostinger)

Este bot es un **proceso persistente de Telegram**. En un VPS debe crearse como **Worker**, **Background Process** o **Supervisor Process**, **no** como sitio web. No necesita dominio, servidor web ni puerto público.

### Comando de inicio del Worker

```bash
python -u main.py
```

O si usas el script incluido:

```bash
bash start-worker.sh
```

### Variable recomendada para un Worker

```text
KEEP_ALIVE=false
```

`KEEP_ALIVE=false` evita abrir el puerto HTTP que solo es útil para previews de Replit. El bot seguirá funcionando normalmente porque Telegram usa su conexión de red **saliente** (long-polling), no necesita puerto abierto.

---

### 🐳 Opción Docker Worker (recomendado)

El `docker-compose.yml` incluido ya configura `KEEP_ALIVE=false` y reinicia el contenedor automáticamente.

**1.** Instala Docker y Docker Compose en el VPS:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**2.** Clona el repositorio:

```bash
git clone https://github.com/Dodrianxd1/DEMON2.0.git
cd DEMON2.0
cp .env.example .env
nano .env
```

**3.** Completa en `.env` al menos:

```env
API_ID=123456
API_HASH=abcdef0123456789abcdef0123456789
BOT_TOKEN=123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ADMIN_IDS=123456789
KEEP_ALIVE=false
```

**4.** Si YouTube solicita autenticación, exporta las cookies en formato Netscape y guárdalas como `cookies.txt` en la raíz:

```bash
# copia aquí tu cookies.txt exportado
chmod 600 cookies.txt
```

> ⚠️ **No subas `.env` ni `cookies.txt` a GitHub.** Añádelos a `.gitignore`.

**5.** Arranca el Worker:

```bash
docker compose up -d --build
docker compose logs -f telegram-bot
```

El volumen `bot-data` conserva usuarios autorizados, base de datos, marcas de agua y cookies al recrear el contenedor.

**6.** Para actualizar desde GitHub:

```bash
git pull
docker compose up -d --build
```

---

### 🛠️ Opción sin Docker (systemd)

Si prefieres correr el bot directamente sobre el VPS (Contabo / Hostinger / cualquier Debian-Ubuntu):

**1.** Instala dependencias del sistema:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg aria2 imagemagick nodejs npm git
```

**2.** Clona el repo y crea el entorno virtual:

```bash
git clone https://github.com/Dodrianxd1/DEMON2.0.git /opt/tg-bot
cd /opt/tg-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3.** Crea el archivo `.env`:

```bash
nano /opt/tg-bot/.env
```

Con las mismas variables descritas arriba.

**4.** Crea el servicio systemd `/etc/systemd/system/tg-bot.service`:

```ini
[Unit]
Description=Telegram Downloader Bot (DEMON2.0)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=tgbot
WorkingDirectory=/opt/tg-bot
EnvironmentFile=/opt/tg-bot/.env
ExecStart=/opt/tg-bot/venv/bin/python -u main.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/tg-bot.log
StandardError=append:/var/log/tg-bot.err

[Install]
WantedBy=multi-user.target
```

**5.** Habilítalo y arráncalo:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tg-bot
sudo systemctl status tg-bot
sudo journalctl -u tg-bot -f
```

**6.** El bot se reiniciará solo si el proceso cae (`Restart=always`).

---

## 🔧 Variables de Entorno

### Obligatorias

| Variable | Descripción |
|---|---|
| `API_ID` | API ID de Telegram ([my.telegram.org](https://my.telegram.org)) |
| `API_HASH` | API Hash de Telegram |
| `BOT_TOKEN` | Token del bot ([@BotFather](https://t.me/BotFather)) |
| `ADMIN_IDS` | IDs de admin separados por coma (el **primero** es el owner) |

### Recomendadas

| Variable | Descripción |
|---|---|
| `KEEP_ALIVE` | `false` en VPS (evita abrir puerto HTTP de Replit) |

### Opcionales

| Variable | Descripción |
|---|---|
| `MEGA_EMAIL` / `MEGA_PASSWORD` | Cuenta MEGA (para enlaces con cuota protegida) |
| `SOCIAL_USERNAME` / `SOCIAL_PASSWORD` | Credenciales para Instagram / Facebook / Twitter |
| `YOUTUBE_COOKIES_PATH` | Ruta a un `cookies.txt` (YouTube) |
| `YOUTUBE_COOKIES_B64` | Cookies en base64 (se materializan al arrancar) |
| `TWITCH_OAUTH` / `TWITCH_USER` / `TWITCH_PASS` | Credenciales Twitch |
| `AUTH_FILE` | Ruta al JSON de autorizados (default: `authorized_users.json`) |

### Archivos de estado (se crean solos)

- `bot_settings.json` — Configuración persistente (acceso libre, anti multi-cuenta)
- `authorized_users.json` — Usuarios autorizados con rol y plan
- `users_db.json` — Base de datos de usuarios (créditos, uso, referidos)
- `pending_payments.json` — Pagos en espera de aprobación
- `telefonos_registrados.json` — Hashes SHA-256 de teléfonos verificados
- `metrics.json` — Métricas del sistema
- `cookies.txt` / `crunchyroll_cookies.txt` — Cookies subidas vía `/cookies`
- `watermarks/` — Archivos `.ass` de marcas de agua
- `creds/crunchyroll/` — Credenciales de Crunchyroll (WVD, mp4.config, etc.)

---

## 🎬 YouTube

YouTube puede **bloquear la IP de un VPS** y pedir autenticación ("Sign in to confirm you're not a bot"). El bot busca cookies en este orden:

1. `YOUTUBE_COOKIES_PATH` (variable de entorno)
2. `cookies.txt` (raíz del repo)
3. `bot/cookies.txt`

También admite **`YOUTUBE_COOKIES_B64`** para proveedores que prefieren inyectarlas como variable protegida (base64).

Desde Telegram, un administrador puede enviar el archivo `cookies.txt` a `/cookies` y el bot lo guardará en la ruta correcta automáticamente.

### PO Token Provider (recomendado)

Desde 2025-2026 YouTube exige un **PO Token** para casi todos sus clientes (`web`, `web_safari`, `mweb`, `android`, `ios`). Sin él, las descargas devuelven "Requested format is not available" o quedan topadas a ~360p.

**Instalación:**

```bash
pip install bgutil-ytdlp-pot-provider

# Opción A — Docker
docker run -d --name bgutil-provider -p 4416:4416 brainicism/bgutil-ytdlp-pot-provider

# Opción B — Sin Docker
git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git
cd bgutil-ytdlp-pot-provider/server
npm install --production && npm install typescript
./node_modules/.bin/tsc
```

El bot lo detecta y arranca automáticamente si encuentra el binario.

---

## 📚 Páginas de Cómics y Galerías

Sitios soportados:

- `toonx.net`
- `jav.guru`
- `javmiku.com`
- `javnorth.com`
- `hentaiheroes.com`
- `nhentai.net`

### Uso

- Enviar directamente un enlace de la página (autodetección).
- O usar `/comic <url>` (envío en álbumes).
- O usar `/comicpdf <url>` (empaquetado en un solo PDF con ImageMagick).

El scraper extrae las imágenes en el **orden HTML original** y las envía en álbumes de Telegram (máx. 10 por grupo). Si una página no expone imágenes o requiere JavaScript, devolverá un **error explícito** en vez de entregar thumbnails incorrectas.

---

## ✨ Características

### 🎬 Descarga Multi-Plataforma

| Categoría | Plataformas |
|---|---|
| **Video/Audio** | YouTube, TikTok, Instagram, Twitter/X, Facebook, Reddit, Pinterest, Threads, Snapchat, Tumblr |
| **Audio** | Spotify (vía YouTube), SoundCloud |
| **Almacenamiento** | MEGA, MediaFire, Google Drive |
| **Anime** | Crunchyroll (1080p + subtítulos ES) |
| **Hosts de video** | StreamWish, VOE, VidHide, FileMoon, MixDrop, MP4Upload, StreamTape |
| **Torrents** | Magnet links y archivos `.torrent` (vía aria2c) |
| **Cómics** | ToonX, JAV Guru, JAVMiku, nHentai, HentaiHeroes |
| **Documentos** | PDFs, DOCX, archivos directos |

### ⚙️ Procesamiento Avanzado

- **Auto-Encode inteligente**: remux sin pérdida (`-c copy`) cuando el formato ya es compatible con Telegram; recodifica solo cuando es necesario (marca de agua o subtítulos).
- **Multi-cliente YouTube**: sistema de tiers (calidad → respaldo) con rotación de User-Agents para esquivar bloqueos.
- **Detección automática de pistas**: audio/subtítulos en español, quema de subtítulos con FFmpeg.
- **Marca de agua personalizada** (.ass): estática o animada estilo DVD.
- **Auto-actualización de yt-dlp** al arrancar.
- **Auto-reinicio supervisado**: si el worker de cola o el reseteo diario caen, se relanzan solos y notifican al admin por Telegram.

### 💰 Monetización

- Sistema de **planes** (Free, Básico, Premium, Pro).
- **Créditos** comprables o ganables por referidos.
- **Pasarelas**: Binance Pay y PayPal con aprobación manual del admin.
- **Programa de referidos** con bonus cruzado (5 créditos para ambos).

### 🛡️ Seguridad

- **Verificación anti multi-cuenta** por número de teléfono (opcional).
- **Límite vitalicio** de 5 descargas para plan Free.
- **Observabilidad** de uso por usuario/plataforma (`/obs`).
- **Control de acceso** libre o restringido, toggleable en vivo desde `/admin`.

---

## 📖 Comandos

### 🎵 Música y Audio

| Comando | Descripción |
|---|---|
| `/play <nombre>` | Descarga MP3 del top resultado de YouTube |
| `/playv <nombre>` | Descarga video del top resultado de YouTube |
| `/search <nombre>` | Panel con 5 resultados (botones 🎵/🎬) |
| `/audio <link>` | Extrae audio MP3 de un enlace |
| `/playlist <link>` | Descarga hasta 50 pistas de una playlist |

### 🎬 Video y Procesamiento

| Comando | Descripción |
|---|---|
| `/config` | Menú de ajustes FFmpeg (calidad, CRF, etc.) |
| `/encode <archivo/magnet>` | Recodifica un archivo o descarga un torrent |
| `/crearwm <texto>` | Genera tu propio `.ass` de marca de agua |
| `/spam on\|off` | Activa/desactiva tu marca de agua |
| *(enviar link)* | Descarga inteligente según la plataforma |

### 📕 Documentos, Cómics y Anime

| Comando | Descripción |
|---|---|
| `/pdf <link>` | Descarga PDF, DOCX o documentos de Drive |
| `/comic <link>` | Descarga páginas de un cómic/galería |
| `/comicpdf <link>` | Empaqueta la galería en un solo PDF |
| `/a <nombre>` | Consulta metadatos de anime (Jikan/AniList) |

### 💎 Planes y Perfil

| Comando | Descripción |
|---|---|
| `/plan` | Panel interactivo de planes, pagos y referidos |
| `/perfil` | Tu plan, créditos y uso por plataforma |

### ⚙️ Gestión

| Comando | Descripción |
|---|---|
| `/queue` | Estado de la cola de descargas |
| `/cancel` | Cancela todas tus descargas activas |
| `/ping` | Latencia del bot |
| `/coms` | Panel de ayuda completo |

### 🔐 Administradores

| Comando | Descripción |
|---|---|
| `/id` (reply) | Autoriza a un usuario |
| `/addid <ID>` | Autoriza por ID numérico |
| `/setplan <ID> <5\|10\|15>` | Asigna plan (5=Free, 10=Básico, 15=Pro) |
| `/rmid <ID>` | Revoca acceso |
| `/users` | Lista de usuarios autorizados |
| `/stat` | Panel de recursos (RAM, CPU, disco, red, uptime) |
| `/obs` | Observabilidad de uso y multi-cuenta |
| `/admin` | Panel de administración |
| `/admin` (reply) | Otorga rango admin |
| `/remadmin` (reply) | Retira rango admin |
| `/cookies` | Sube `cookies.txt` (YouTube, general) |
| `/crfiles` | Sube credenciales de Crunchyroll |
| `/getcode` | Obtiene el código fuente del bot |
| `/reset` | Limpia memoria, archivos temporales y stats |

---

## 💎 Planes y Precios

| Plan | Precio | Calidad máx. | Torrents | Publicidad |
|---|---|---|---|---|
| 🌱 **Free** | $0.00 | 480p | ❌ | ✅ |
| ⚡ **Básico** | $4.99/mes | 720p | ❌ | ❌ |
| 🌟 **Premium** | $9.99/mes | 1080p | ✅ | ❌ |
| 🔥 **Pro** | $19.99/mes | 4K | ✅ | ❌ |

**Plan Free:** 5 descargas vitalicias (no se renuevan diariamente).

**Métodos de pago:** Binance Pay (UID: `1121153030`) y PayPal. Tras pagar, el usuario envía comprobante y un admin aprueba manualmente desde `/admin` → 📋 Ver Pagos Pendientes.

---

## 🪙 Sistema de Créditos y Referidos

### Créditos

Se gastan **automáticamente** (1 por descarga) cuando:

1. Un usuario Free intenta bajar de una plataforma que requiere plan superior.
2. Un usuario Free ya agotó sus 5 descargas vitalicias.

**Paquetes de créditos** (comprables desde `/plan`):

| Créditos | Precio |
|---|---|
| 10 | $1.00 |
| 25 | $5.00 |
| 50 | $10.00 |
| 100 | $20.00 |

### Referidos

- Cada usuario tiene un enlace único: `t.me/<bot>?start=<uid>`
- Al unirse un amigo: **+5 créditos** para ambos.
- Se otorga **una sola vez** por usuario nuevo.

---

## 💧 Marca de Agua (.ass)

### Opción 1: Subir un `.ass` existente

Envía el archivo `.ass` como documento al bot → se guarda en `watermarks/<uid>_watermark.ass` y se activa automáticamente.

### Opción 2: Generar con `/crearwm`

```
/crearwm Mi Canal 2026
```

Luego, con botones inline eliges:

- 📍 Posición (9 ubicaciones)
- 🔹 Tamaño (22px, 32px, 48px)

Se genera con timestamp de Ecuador y se activa de inmediato.

### Aplicación

La marca de agua se quema con FFmpeg usando el filtro `ass` sobre la pista de video, obligando a recodificar (por eso se preserva la calidad original del resto). El estilo por defecto cubre las **10 horas** del video, por lo que aplica a cualquier duración.

**Activar/Desactivar manualmente:**

```
/spam on
/spam off
```

---

## 👑 Panel de Administración

Accesible con `/admin`:

- **📋 Ver Pagos Pendientes** — Aprueba o rechaza pagos de planes/créditos.
- **📊 Ver Uso (`/obs`)** — Top de usuarios por actividad, plataformas más usadas, cuentas sospechosas de multi-cuenta.
- **🔓/🔒 Alternar Acceso** — Libre (cualquiera) o Restringido (solo autorizados).
- **📱 Anti multi-cuenta** — Pide verificación por teléfono una sola vez al registrarse.
- **📊 Actualizar Métricas** — Refresca contadores.

> ℹ️ **Nota sobre IP:** la API de Bots de Telegram **jamás entrega la IP del usuario** al bot. Por eso la verificación anti multi-cuenta usa **número de teléfono** en lugar de IP.

---

## 🏗️ Arquitectura

### Flujo de descarga

```
Usuario → Handler de mensaje → _enforce_usage() (plan + créditos)
       ↓
  Detección de URL (MEGA / MF / GDrive / YouTube / Redes / Torrent / Cómic / PDF)
       ↓
  Cola (download_queue) → queue_worker → procesar_descarga()
       ↓
  Descarga → Procesamiento (remux o encode) → Subida con panel de progreso
       ↓
  Estadísticas (_stats) y limpieza de temporales
```

### Componentes clave

- **`_run_supervised()`** — Supervisa tareas de fondo; si caen, las relanza y avisa al admin.
- **Sistema de tiers de YouTube** — Ordena clientes (`web_safari`, `mweb`, `tv`, `android_vr`, `web_embedded`...) por capacidad real de calidad, agota un tier antes de caer al siguiente.
- **`encode_video()`** — Codificación con FFmpeg + parser de progreso en tiempo real.
- **`upload_smart_file()`** — Detección automática de tipo (video, audio, imagen, doc) con fallback a documento.
- **Auto-reinicio** — `while True` alrededor de `bot.run(main())` con backoff exponencial (5s → 120s).

### 🕒 Zona Horaria

Todo el bot usa `America/Guayaquil` (**UTC-5 fijo**, sin DST). Los reseteos diarios y las marcas de tiempo en `/stat`, `/perfil`, `/obs` y `/crearwm` usan hora de Ecuador, **no** la hora del servidor.

---

## 🐛 Solución de Problemas

### YouTube: "Requested format is not available"

YouTube exige **PO Token** para casi todos sus clientes desde 2025-2026. Soluciones:

1. **Instalar el PO Token provider** (ver [YouTube](#-youtube)) — es lo definitivo.
2. **Subir cookies** con `/cookies` — habilita el cliente `tv` y desbloquea calidades altas.
3. Sin ninguno de los dos, el bot cae a clientes de respaldo limitados (~360p-720p).

### "The page needs to be reloaded" en TVHTML5

Es un fallo específico del cliente `tv` que YouTube introdujo en agosto 2026. El bot ya lo trata como "cliente bloqueado" y pasa al siguiente automáticamente.

### Crunchyroll: DRM / login

- Sube `crunchyroll_cookies.txt` con `/cookies` (el nombre debe contener "crunchyroll").
- Requiere cuenta Premium para 1080p. Sin ella, solo trailers/preview.

### MEGA: "Cuota excedida" (-16)

- Configura `MEGA_EMAIL` y `MEGA_PASSWORD` en variables de entorno.
- Alternativa: usar otro mirror.

### Cola atascada

```
/cancel     # cancela las tuyas
/reset      # (admin) limpia todo y reinicia stats
```

### Ver CPU, RAM, red reales

```
/stat
```

Incluye medición real de ancho de banda (con caché de 5 min), núcleos físicos reales (no hilos) y hora de Ecuador.

### El bot se cae constantemente

El proceso principal tiene un **supervisor con backoff exponencial** (5s → 120s). Revisa los logs:

```bash
# Docker
docker compose logs -f telegram-bot

# systemd
journalctl -u tg-bot -f
```

Si el bot arranca pero se cae a los pocos segundos y reinicia infinitamente, normalmente es:

- `API_ID` / `API_HASH` inválidos
- `BOT_TOKEN` mal copiado (comillas extra, espacios)
- Sesión de Pyrogram corrupta → borra `/tmp/bot_session.session` (o el volumen `bot-data` en Docker)

---

## 📜 Créditos

**✪ Bot By → @The_canst & @Ryota_YT**

Construido con:

- [Pyrogram](https://docs.pyrogram.org/) — Cliente de Telegram
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Extracción de medios
- [FFmpeg](https://ffmpeg.org/) — Procesamiento de audio/video
- [aria2c](https://aria2.github.io/) — Descargas de torrents
- [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) — PO Token para YouTube
- [Jikan](https://jikan.moe/) / [AniList](https://anilist.co/) — Metadatos de anime

---

## ⚠️ Aviso Legal

Este bot está destinado a uso **personal y educativo**. El usuario es responsable de respetar los términos de servicio de cada plataforma y las leyes de derechos de autor aplicables en su jurisdicción. Los autores no se hacen responsables del uso indebido.
```

Copia todo el contenido de este bloque de código y pégalo directamente en el archivo `README.md` de tu repositorio `Dodrianxd1/DEMON2.0` en GitHub. Reemplazará el contenido actual con una documentación completa y profesional.
