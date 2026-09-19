<div align="center">

# 🤖 Bot Descargas

**Bot de Telegram todo-en-uno para descargar contenido multimedia desde múltiples plataformas**

[![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Pyrogram](https://img.shields.io/badge/Pyrogram-2.0-009688?style=for-the-badge)](https://pyrogram.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.6-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

[Características](#-características) • [Instalación](#-instalación) • [Despliegue](#-despliegue) • [Comandos](#-comandos)

</div>

---

## 📖 Descripción

**Bot Descargas** es un bot de Telegram modular y altamente escalable que permite descargar contenido desde:

- ☁️ **Almacenamiento en la nube:** MEGA, MediaFire, Google Drive
- 🎥 **Redes sociales:** TikTok, Instagram, Twitter/X, Facebook, Reddit, Pinterest
- 🎵 **Música:** YouTube, Spotify, SoundCloud, playlists completas
- 🎬 **Streaming:** Crunchyroll, Viki, Tubi (con cookies)
- 🧲 **Torrents:** Magnet links y archivos `.torrent`
- 📕 **Documentos:** PDFs, cómics, mangas
- 🎞️ **Video hosts:** Streamwish, VOE, Filemoon, Vidhide, Mixdrop y más

Con **sistema de planes**, **créditos**, **referidos**, **pagos** y **procesamiento FFmpeg** integrado.

---

## ✨ Características

### 🎯 Descargas Inteligentes
- **Detección automática** de plataforma y motor adecuado
- **Cola de descargas** con límite de concurrencia (no satura el VPS)
- **Reintentos automáticos** y verificación de integridad
- **Progreso en tiempo real** con barras visuales y ETA

### 💎 Sistema de Monetización
- **4 planes:** Free, Básico, Premium, Pro
- **Sistema de créditos** para descargas extra
- **Programa de referidos** (5 créditos por invitación)
- **Pagos vía Binance Pay y PayPal**
- **Panel de admin** para aprobar pagos pendientes

### 🎬 Procesamiento Avanzado
- **Remux sin pérdida** de calidad (stream copy)
- **Encode H.264/H.265** con presets configurables
- **Juntar capítulos** con detección automática de Opening/Ending por huella de audio
- **Recorte de OP/ED** manual o automático
- **Marca de agua .ass personalizada** (estática o animada estilo DVD)
- **Subtítulos multi-idioma** con quema opcional

### 🔒 Seguridad y Estabilidad
- **Base de datos MongoDB** (sin corrupción de datos)
- **Auto-recuperación** de tareas de fondo
- **Supervisor con backoff exponencial** para crashes totales
- **Verificación anti multi-cuenta** por número de teléfono
- **Modo libre o restringido** configurable en vivo

### 🚀 DevOps
- **Docker** con todas las dependencias
- **CI/CD con GitHub Actions** (deploy automático en 2 minutos)
- **Healthcheck** automático
- **Rotación de logs** configurada

---

## 🏗️ Arquitectura

```
bot-descargas/
├── main.py                     # Punto de entrada
├── requirements.txt            # Dependencias Python
├── Dockerfile                  # Imagen Docker
├── docker-compose.yml          # Orquestación
├── .env                        # Variables de entorno (NO subir)
│
├── config/                     # Configuración
│   ├── settings.py             # Constantes globales
│   ├── ffmpeg_config.py        # Menú de calidad FFmpeg
│   └── ffmpeg_runner.py        # Constructor de comandos FFmpeg
│
├── core/                       # Núcleo del bot
│   ├── database.py             # MongoDB (usuarios, planes, pagos)
│   ├── queue.py                # Cola de descargas
│   ├── performance.py          # Optimizaciones (uvloop, caché, límites)
│   └── utils.py                # Utilidades generales
│
├── engines/                    # Motores de descarga
│   ├── mega_engine.py          # MEGA nativo (AES)
│   ├── torrent_engine.py       # aria2c para torrents
│   ├── social_engine.py        # TikTok, Instagram, Twitter
│   ├── streaming_engine.py     # Crunchyroll, Viki
│   ├── music_engine.py         # YouTube, Spotify, SoundCloud
│   ├── comic_engine.py         # Scraper de cómics
│   └── pdf_engine.py           # PDFs y documentos
│
├── processors/                 # Procesamiento multimedia
│   ├── uploader.py             # Subida inteligente a Telegram
│   └── video_processor.py      # FFmpeg (encode, remux, concat, cut)
│
└── handlers/                   # Handlers de Telegram
    ├── commands.py             # Comandos (/start, /play, /admin)
    ├── callbacks.py            # Botones inline
    └── messages.py             # Detección de enlaces
```

---

## 📋 Requisitos

| Componente | Versión mínima | Recomendado |
|---|---|---|
| Python | 3.11 | 3.11+ |
| FFmpeg | 5.0 | 6.0+ |
| aria2c | 1.36 | 1.37+ |
| MongoDB | 4.4 | 7.0 |
| RAM | 1 GB | 2 GB+ |
| Disco | 10 GB | 20 GB+ |

---

## 🚀 Instalación

### 📦 Instalación local (desarrollo)

**1. Clonar el repositorio:**

```bash
git clone https://github.com/tu-usuario/bot-descargas.git
cd bot-descargas
```

**2. Crear entorno virtual:**

```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**3. Instalar dependencias:**

```bash
pip install -r requirements.txt
```

**4. Instalar dependencias del sistema:**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y ffmpeg aria2 megatools imagemagick

# macOS
brew install ffmpeg aria2 megatools imagemagick
```

**5. Configurar variables de entorno:**

```bash
cp .env.example .env
nano .env
```

Rellena con tus datos:

```env
API_ID=12345678
API_HASH=tu_api_hash
BOT_TOKEN=tu_bot_token
ADMIN_IDS=123456789
MONGO_URI=mongodb+srv://usuario:password@cluster.mongodb.net/
```

**6. Ejecutar:**

```bash
python main.py
```

---

## 🐳 Despliegue

### Opción A: Docker Compose (recomendado)

**1. Preparar el VPS:**

```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Cerrar sesión y volver a entrar
exit
ssh usuario@tu-vps
```

**2. Clonar el repo en el VPS:**

```bash
mkdir -p /root/bot-descargas
cd /root/bot-descargas
git clone https://github.com/tu-usuario/bot-descargas.git .
```

**3. Crear `.env`:**

```bash
cp .env.example .env
nano .env  # Rellena tus credenciales
```

**4. Levantar el bot:**

```bash
docker compose up -d
docker compose logs -f
```

**5. Comandos útiles:**

```bash
docker compose logs -f       # Ver logs en vivo
docker compose restart       # Reiniciar bot
docker compose down          # Apagar bot
docker compose pull          # Actualizar imagen
docker compose up -d         # Aplicar actualización
```

### Opción B: CI/CD con GitHub Actions

**1. Configurar secrets en GitHub:**

Ve a **Settings → Secrets and variables → Actions** y añade:

| Secret | Descripción |
|---|---|
| `VPS_HOST` | IP del VPS |
| `VPS_USER` | Usuario SSH (`root`) |
| `VPS_SSH_KEY` | Clave privada SSH |
| `VPS_SSH_PORT` | Puerto SSH (opcional, default 22) |

**2. Habilitar permisos de Actions:**

**Settings → Actions → General → Workflow permissions** → `Read and write permissions`

**3. Hacer push a `main`:**

```bash
git add .
git commit -m "Update"
git push origin main
```

GitHub Actions construirá la imagen y desplegará automáticamente en tu VPS.

---

## 💻 Comandos

### 🎵 Música

| Comando | Descripción |
|---|---|
| `/play <nombre>` | Descargar canción como MP3 |
| `/playv <nombre>` | Descargar video musical |
| `/search <nombre>` | Buscar y elegir entre 5 resultados |
| `/audio <link>` | Extraer audio de un enlace |
| `/playlist <link>` | Descargar playlist completa (máx. 50) |

### 🎬 Video

| Comando | Descripción |
|---|---|
| Enviar link | Descarga inteligente automática |
| `/encode` | Convertir video (responder a un archivo) |
| `/encode <magnet>` | Descargar torrent |
| `/crearwm <texto>` | Crear marca de agua `.ass` |
| `/spam on\|off` | Activar/desactivar marca de agua |
| `/config` | Menú de calidad FFmpeg |
| `/recortar` | Recortar opening/ending |
| `/juntar` | Unir capítulos con detección de OP/ED |

### 📕 Documentos

| Comando | Descripción |
|---|---|
| `/pdf <link>` | Descargar PDF/documento |
| `/comic <link>` | Descargar cómic como álbum |
| `/comicpdf <link>` | Descargar cómic como PDF único |
| `/a <nombre>` | Buscar información de anime |

### 💎 Cuenta

| Comando | Descripción |
|---|---|
| `/start` | Iniciar el bot |
| `/plan` | Ver planes y comprar |
| `/perfil` | Ver tu perfil y uso |
| `/queue` | Estado de la cola |
| `/cancel` | Cancelar tus descargas |
| `/ping` | Latencia del bot |
| `/stat` | Estado del servidor |

### 👑 Admin

| Comando | Descripción |
|---|---|
| `/id` (reply) | Autorizar usuario |
| `/addid <ID>` | Autorizar por ID |
| `/rmid <ID>` | Revocar acceso |
| `/setplan <ID> <plan>` | Asignar plan |
| `/users` | Ver usuarios autorizados |
| `/admin` | Panel de administración |
| `/obs` | Observabilidad de uso |
| `/crfiles` | Subir cookies de Crunchyroll |
| `/cookies` | Subir cookies generales |
| `/reset` | Reiniciar bot |

---

## ⚙️ Configuración

### Planes disponibles

| Plan | Precio | Calidad | Torrents | Anuncios |
|---|---|---|---|---|
| **Free** | $0 | 480p | ❌ | ✅ |
| **Básico** | $4.99 | 720p | ❌ | ❌ |
| **Premium** | $9.99 | 1080p | ✅ | ❌ |
| **Pro** | $19.99 | 4K | ✅ | ❌ |

### Créditos

- **10 créditos:** $1 USD
- **25 créditos:** $5 USD
- **50 créditos:** $10 USD
- **100 créditos:** $20 USD

Los créditos permiten descargar 1 vez sin gastar el límite gratuito, o desbloquear plataformas de plan superior.

---

## 🔒 Legalidad

Este bot está diseñado para **uso personal** con contenido de acceso libre o mediante **credenciales propias del usuario** (cookies, cuentas Premium). 

**No incluye** ni promueve:
- Bypass de DRM (Widevine, FairPlay, PlayReady)
- Descarga de contenido protegido sin autorización
- Redistribución de material con copyright

El usuario es responsable de cumplir con los términos de servicio de cada plataforma y las leyes de su país.

---

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Add: nueva funcionalidad'`)
4. Push la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

---

## 📊 Estado del Proyecto

| Módulo | Estado |
|---|---|
| Modularización | ✅ Completado |
| MongoDB | ✅ Completado |
| Optimización (uvloop) | ✅ Completado |
| Docker + CI/CD | ✅ Completado |
| Motor MEGA | ✅ Completado |
| Motor Torrent | ✅ Completado |
| Motor Redes Sociales | ✅ Completado |
| Motor Música | ✅ Completado |
| Motor Crunchyroll | ✅ Completado (vía cookies) |
| Motor Cómics | ✅ Completado |
| Motor PDF | ✅ Completado |

---

## 📜 Licencia

Este proyecto está bajo la licencia **MIT**. Ver el archivo [LICENSE](LICENSE) para más detalles.

---

## 🙏 Créditos

- **Desarrollador:** [@Dodriandx1](https://github.com/Dodriandx1)
- **Contacto Telegram:** [@The_canst](https://t.me/The_canst) & [@Ryota_YT](https://t.me/Ryota_YT)
- **Tecnologías:** [Pyrogram](https://pyrogram.org/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [FFmpeg](https://ffmpeg.org/), [aria2](https://aria2.github.io/), [MongoDB](https://www.mongodb.com/)

---

<div align="center">

**⭐ Si este proyecto te fue útil, dale una estrella ⭐**

Hecho con ❤️ en Ecuador

</div>
