#!/usr/bin/env bash
# =============================================================================
# COBRA - Issue #1: Definir estructura del repositorio
#
# Crea las carpetas del proyecto con .gitkeep, el .gitattributes y agrega
# al .gitignore existente una sección para artefactos de GnuCOBOL.
#
# Uso: ejecutar desde la raíz del repo clonado
#   chmod +x setup_estructura.sh && ./setup_estructura.sh
#
# Es idempotente: se puede correr varias veces sin duplicar nada.
# =============================================================================
set -euo pipefail

if [[ ! -d .git ]]; then
  echo "Error: ejecuta este script desde la raíz del repositorio." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Carpetas
# ---------------------------------------------------------------------------
echo ">> Creando carpetas..."
carpetas=(
  src
  copybooks
  data/entrada
  data/salida
  tests/fixtures
  tests/golden
  api
  scripts
  bin
  .github/workflows
)

for dir in "${carpetas[@]}"; do
  mkdir -p "$dir"
  # bin/ y data/salida/ se ignoran; su .gitkeep se re-incluye en el .gitignore
  if [[ -z "$(ls -A "$dir")" ]]; then
    touch "$dir/.gitkeep"
    echo "   + $dir/"
  else
    echo "   = $dir/ (ya tiene contenido)"
  fi
done

# ---------------------------------------------------------------------------
# .gitattributes
# ---------------------------------------------------------------------------
echo ">> Escribiendo .gitattributes..."
cat > .gitattributes <<'EOF'
# Finales de línea LF en todo el repo (evita problemas entre Windows y WSL)
* text=auto eol=lf

# COBOL: reconocimiento de lenguaje en GitHub
*.cbl linguist-language=COBOL
*.cob linguist-language=COBOL
*.cpy linguist-language=COBOL

# Scripts de shell siempre con LF, o no corren en Linux
*.sh  text eol=lf

# Archivos de datos de longitud fija: sin conversión de finales de línea
# para que las comparaciones contra los golden sean byte a byte
*.dat -text
*.txt text eol=lf
tests/fixtures/** -text
tests/golden/**   -text

# Los fixtures y golden no cuentan en las estadísticas de lenguajes
tests/fixtures/** linguist-generated
tests/golden/**   linguist-generated
EOF

# ---------------------------------------------------------------------------
# .gitignore: sección COBOL
# ---------------------------------------------------------------------------
MARCA="# --- GnuCOBOL ---"
if grep -qF "$MARCA" .gitignore 2>/dev/null; then
  echo ">> .gitignore ya tiene la sección de GnuCOBOL, se omite."
else
  echo ">> Agregando sección de GnuCOBOL al .gitignore..."
  cat >> .gitignore <<'EOF'

# --- GnuCOBOL ---
# Ejecutables y módulos compilados
bin/*
!bin/.gitkeep
*.so
*.o
*.dll
*.exe

# Archivos intermedios de cobc (-save-temps, -t)
*.c.h
*.c.l*.h
*.i
*.lst

# Archivos generados por el batch
data/salida/*
!data/salida/.gitkeep
*.idx
*.bak
*.log
EOF
fi

echo ">> Listo. Revisa con: git status"