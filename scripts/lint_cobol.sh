#!/usr/bin/env bash
# =============================================================================
# lint_cobol.sh - Verifica el formato fijo (reference format) de COBOL
#
#   Cols 1-6   Área de secuencia     : espacios o dígitos
#   Col  7     Indicador             : ' ' * / - D d
#   Cols 8-11  Área A                : DIVISION, SECTION, párrafos, FD/SD, 01, 77
#   Cols 12-72 Área B                : sentencias y niveles 02-49, 66, 88
#   Cols 73-80 Identificación        : cobc lo IGNORA en silencio -> error aquí
#
# Uso: scripts/lint_cobol.sh archivo.cbl [archivo.cpy ...]
# Sale con código 1 si encuentra algún error.
# =============================================================================
set -uo pipefail

if [[ $# -eq 0 ]]; then
  echo "Uso: $0 archivo.cbl [archivo.cpy ...]" >&2
  exit 2
fi

LC_ALL=C awk '
function err(msg) {
  printf "%s:%d: %s\n", FILENAME, FNR, msg
  errores++
}

FNR == 1 { en_procedure = 0 }

{
  linea = $0

  # Finales de línea de Windows
  if (linea ~ /\r$/) { err("final de línea CRLF (usa LF)"); sub(/\r$/, "", linea) }

  # Tabuladores: rompen el conteo de columnas según el editor
  if (index(linea, "\t") > 0) { err("tabulador encontrado (usa espacios)"); next }

  # Longitud: todo lo que pase de la columna 72 se ignora
  # cobc cuenta BYTES: en UTF-8 cada acento o ñ ocupa 2 columnas
  if (length(linea) > 72) {
    nota = (linea ~ /[^\001-\177]/) ? " (los acentos y la ñ cuentan como 2 columnas)" : ""
    err(sprintf("la línea mide %d columnas; el máximo es 72%s", length(linea), nota))
  }

  # Espacios al final
  if (linea ~ /[ ]+$/ && linea !~ /^[ ]*$/) err("espacios al final de la línea")

  if (length(linea) == 0) next

  # Área de secuencia (1-6)
  seq = substr(linea, 1, 6)
  if (seq !~ /^[ 0-9]*$/) err("columnas 1-6 deben ser espacios o dígitos")

  # Indicador (7)
  ind = substr(linea, 7, 1)
  if (ind != "" && index(" */-Dd", ind) == 0)
    err(sprintf("indicador inválido en columna 7: \"%s\"", ind))

  # Comentarios y continuaciones no se revisan más
  if (ind == "*" || ind == "/" || ind == "-") next

  resto = substr(linea, 8)
  if (resto ~ /^[ ]*$/) next

  # Columna donde empieza el código (8 = Área A)
  match(resto, /[^ ]/)
  col = RSTART + 7
  en_area_a = (col <= 11)

  texto = toupper(substr(resto, RSTART))
  sub(/\*>.*/, "", texto)           # quita comentarios en línea
  split(texto, tok, /[ .]+/)
  primero = tok[1]

  if (texto ~ /PROCEDURE[ ]+DIVISION/) {
    en_procedure = 1
    # El Makefile detecta los módulos buscando "PROCEDURE DIVISION USING"
    # en una sola línea; si la declaración se parte, el módulo no se detecta.
    if (texto !~ /\./)
      err("PROCEDURE DIVISION debe declararse completa en una sola línea (incluido USING ... y el punto)")
  }

  # Encabezados que DEBEN ir en Área A
  if (texto ~ /^[A-Z0-9-]+[ ]+(DIVISION|SECTION)/ || primero == "FD" || primero == "SD" \
      || primero == "01" || primero == "1" || primero == "77") {
    if (!en_area_a) err(sprintf("\"%s\" debe empezar en Área A (columnas 8-11), empieza en %d", primero, col))
    next
  }

  # Niveles que DEBEN ir en Área B
  if (primero ~ /^[0-9][0-9]?$/ && primero + 0 >= 2) {
    if (en_area_a) err(sprintf("nivel %s debe empezar en Área B (columna 12+), empieza en %d", primero, col))
    next
  }

  # En PROCEDURE DIVISION, solo párrafos van en Área A
  if (en_procedure && en_area_a) {
    if (texto !~ /^[A-Z0-9-]+[ ]*\.[ ]*$/ && texto !~ /^END[ ]+PROGRAM/)
      err(sprintf("sentencia en Área A (columna %d); las sentencias van en Área B (columna 12+)", col))
  }
}

END { exit (errores > 0) }
' "$@"

status=$?
if [[ $status -eq 0 ]]; then
  echo "lint: $# archivo(s) OK"
fi
exit $status
