# ═══════════════════════════════════════════════════════════════════
#  BOT DESCARGAS — Dockerfile de producción
# ═══════════════════════════════════════════════════════════════════
FROM python:3.11-slim

# ─── METADATOS ───
LABEL maintainer="Dodriandx1"
LABEL description="Bot de descargas multimedia para Telegram"

# ─── VARIABLES DE ENTORNO ───
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=America/Guayaquil

# ─── DEPENDENCIAS DEL SISTEMA ───
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Multimedia
    ffmpeg \
    # Descargas
    aria2 \
    megatools \
    curl \
    wget \
    # Imágenes (para cómics y miniaturas)
    imagemagick \
    # Compilación
    build-essential \
    git \
    # Fuentes (para marcas de agua)
    fonts-dejavu \
    fonts-liberation \
    # Utilidades
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# ─── IMAGEMAGICK: permitir PDF (por seguridad lo bloquea por defecto) ───
RUN sed -i 's/policy domain="coder" rights="none" pattern="PDF"/policy domain="coder" rights="read|write" pattern="PDF"/' \
    /etc/ImageMagick-6/policy.xml 2>/dev/null || true

# ─── DIRECTORIO DE TRABAJO ───
WORKDIR /app

# ─── INSTALAR DEPENDENCIAS PYTHON (capa cacheable) ───
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─── COPIAR CÓDIGO ───
COPY . .

# ─── CREAR DIRECTORIOS NECESARIOS ───
RUN mkdir -p /tmp/downloads /app/watermarks /app/cookies && \
    chmod 777 /tmp/downloads

# ─── USUARIO NO-ROOT (seguridad) ───
# Comentado por ahora porque algunos VPS tienen problemas con permisos.
# Descomentar en producción si es necesario.
# RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
# USER botuser

# ─── HEALTHCHECK ───
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD pgrep -f "python main.py" || exit 1

# ─── COMANDO PRINCIPAL ───
CMD ["python", "main.py"]
