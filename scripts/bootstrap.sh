#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== cloud-foundations-lab bootstrap =="

# Verificar dependencias
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker no esta instalado o no esta en PATH."
  echo "  macOS/Windows: instalar Docker Desktop."
  echo "  Linux: instalar Docker Engine + Compose plugin."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose no esta disponible."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "ERROR: python3 no esta instalado o no esta en PATH."
  exit 1
fi

# Nota para usuarios Windows
if grep -qi microsoft /proc/version 2>/dev/null || [[ "$(uname -r)" == *WSL* ]]; then
  echo "INFO: entorno WSL2 detectado."
  echo "      Asegurate de que Docker Desktop tiene WSL2 integration activada."
  echo "      Clonar el repo dentro de WSL2 (ej: ~/cloud-foundations-lab) mejora el rendimiento."
fi

# Instalar dependencias Python
if [ -f requirements.txt ]; then
  python3 -m pip install -r requirements.txt --quiet
  echo "Dependencias Python instaladas."
fi

# Crear .env desde .env.example si no existe
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Creado .env desde .env.example"
fi

# Crear directorios necesarios
mkdir -p data/raw/events data/raw/olist data/processed docs logs

# Crear documentacion desde templates si no existen
for doc in architecture decisions troubleshooting; do
  if [ ! -f "docs/${doc}.md" ] && [ -f "docs/templates/${doc}.md" ]; then
    cp "docs/templates/${doc}.md" "docs/${doc}.md"
    echo "Creado docs/${doc}.md desde template"
  fi
done

# Validar compose
docker compose config >/dev/null
echo "Compose valido."

echo
echo "Bootstrap completo. Proximos pasos:"
echo
echo "  1. Levantar servicios base:"
echo "       docker compose up -d postgres minio redis"
echo
echo "  2. Cargar base de datos:"
echo "       python scripts/load_postgres.py"
echo
echo "  3. Procesar eventos GitHub Archive:"
echo "       python scripts/process_events.py"
echo
echo "  4. Verificar todo:"
echo "       ./scripts/check.sh"
echo
echo "  Ver README.md para la lista completa de servicios y puertos."
