#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Script de instalación inicial en el VPS
#  Ejecutar UNA SOLA VEZ después de clonar el repo.
# ═══════════════════════════════════════════════════════════════════

set -e

echo "🚀 Instalando Bot de Descargas..."

# ─── 1. Actualizar sistema ───
echo "📦 Actualizando sistema..."
apt-get update && apt-get upgrade -y

# ─── 2. Instalar Docker si no existe ───
if ! command -v docker &> /dev/null; then
    echo "🐳 Instalando Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    usermod -aG docker $USER
    echo "✅ Docker instalado"
else
    echo "✅ Docker ya está instalado"
fi

# ─── 3. Instalar Docker Compose plugin ───
if ! docker compose version &> /dev/null; then
    echo "🔧 Instalando Docker Compose..."
    apt-get install -y docker-compose-plugin
fi

# ─── 4. Crear carpetas necesarias ───
mkdir -p /root/bot-descargas
mkdir -p /root/bot-descargas/cookies
mkdir -p /root/bot-descargas/watermarks
mkdir -p /root/bot-descargas/logs
chmod 755 /root/bot-descargas/*

# ─── 5. Verificar .env ───
cd /root/bot-descargas
if [ ! -f .env ]; then
    echo "⚠️  No existe .env. Copiando desde .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "📝 Edita /root/bot-descargas/.env con tus credenciales"
        nano .env
    else
        echo "❌ No hay .env ni .env.example. Créalo manualmente."
        exit 1
    fi
fi

# ─── 6. Login a GitHub Container Registry ───
echo "🔐 Login a GitHub Container Registry..."
echo "Necesitas un Personal Access Token (PAT) con permisos: read:packages"
read -p "GitHub Username: " GH_USER
read -sp "GitHub PAT: " GH_TOKEN
echo ""
echo "$GH_TOKEN" | docker login ghcr.io -u "$GH_USER" --password-stdin

# ─── 7. Levantar el bot ───
echo "🚀 Levantando bot..."
docker compose pull
docker compose up -d

# ─── 8. Verificar ───
sleep 5
docker compose ps
docker compose logs --tail=30

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  ✅ INSTALACIÓN COMPLETADA"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Comandos útiles:"
echo "  docker compose logs -f     # Ver logs en vivo"
echo "  docker compose restart     # Reiniciar el bot"
echo "  docker compose down        # Apagar el bot"
echo "  docker compose up -d       # Encender el bot"
