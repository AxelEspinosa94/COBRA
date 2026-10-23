#!/usr/bin/env bash
# =============================================================================
# Backlog: Núcleo batch bancario en COBOL + capa API en Python (FastAPI)
#
# Requisitos:
#   - GitHub CLI instalado y autenticado:  gh auth login
#   - Ejecutar dentro del clon local del repositorio
#
# Uso:
#   ./issue_creator.sh                     # crea etiquetas, milestones e issues
#   PROJECT="Mi Board" ./issue_creator.sh  # además los agrega a un GitHub Project
#                                         # (usa el título exacto del Project)
# =============================================================================
set -euo pipefail

PROJECT="${PROJECT:-}"

# ---------------------------------------------------------------------------
# Etiquetas
# ---------------------------------------------------------------------------
echo ">> Creando etiquetas..."
gh label create "setup"    --color "BFD4F2" --description "Infraestructura y tooling" --force
gh label create "cobol"    --color "5319E7" --description "Código COBOL"              --force
gh label create "python"   --color "1D76DB" --description "Código Python"             --force
gh label create "api"      --color "0E8A16" --description "Capa API"                  --force
gh label create "testing"  --color "FBCA04" --description "Pruebas"                   --force
gh label create "ci"       --color "D93F0B" --description "Integración continua"      --force
gh label create "docs"     --color "C5DEF5" --description "Documentación"             --force
gh label create "datos"    --color "F9D0C4" --description "Datos de prueba"           --force

# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------
echo ">> Creando milestones..."
crear_milestone () {
  gh api "repos/{owner}/{repo}/milestones" -f title="$1" -f description="$2" >/dev/null 2>&1 \
    || echo "   (milestone '$1' ya existe, se omite)"
}
crear_milestone "M1 - Setup"           "Estructura del repo, compilación y CI"
crear_milestone "M2 - Núcleo batch"    "Procesamiento batch de cuentas y transacciones en COBOL"
crear_milestone "M3 - Pruebas batch"   "Pruebas de regresión y casos borde del batch"
crear_milestone "M4 - Capa API"        "Exposición del núcleo COBOL vía FastAPI"
crear_milestone "M5 - Documentación"   "README, arquitectura y demo"

# ---------------------------------------------------------------------------
# Helper para crear issues
# ---------------------------------------------------------------------------
crear_issue () {
  local titulo="$1" labels="$2" milestone="$3" body="$4"
  local args=(--title "$titulo" --label "$labels" --milestone "$milestone" --body "$body")
  [[ -n "$PROJECT" ]] && args+=(--project "$PROJECT")
  gh issue create "${args[@]}" >/dev/null
  echo "   + $titulo"
}

echo ">> Creando issues..."

# =============================================================================
# M1 - Setup
# =============================================================================
crear_issue "Definir estructura del repositorio" "setup" "M1 - Setup" "$(cat <<'EOF'
Crear la estructura base del proyecto.

**Estructura propuesta**
```
src/          programas COBOL (.cbl)
copybooks/    definiciones de registros (.cpy)
data/         archivos de entrada y salida de ejemplo
tests/        pruebas del batch y de la API
api/          servicio FastAPI
scripts/      utilidades (generador de datos, etc.)
```

**Criterios de aceptación**
- [ ] Carpetas creadas con un `.gitkeep` donde aplique
- [ ] `.gitignore` que excluya binarios compilados, archivos `.idx`/`.dat` generados y entornos virtuales
- [ ] `.gitattributes` marcando `*.cbl` y `*.cpy` como COBOL
EOF
)"

crear_issue "Makefile para compilar con GnuCOBOL" "setup,cobol" "M1 - Setup" "$(cat <<'EOF'
Automatizar la compilación de todos los programas.

**Criterios de aceptación**
- [ ] `make` compila todos los programas de `src/` a `bin/`
- [ ] Usa `cobc -x` para ejecutables y `cobc -m` para subprogramas llamables
- [ ] Incluye `-I copybooks` para resolver los `COPY`
- [ ] Targets `make clean`, `make run` y `make test`
- [ ] Compila con `-Wall` sin warnings
EOF
)"

crear_issue "Workflow de CI con GitHub Actions" "setup,ci" "M1 - Setup" "$(cat <<'EOF'
Compilar y probar en cada push y pull request.

**Criterios de aceptación**
- [ ] Workflow en `.github/workflows/ci.yml` sobre `ubuntu-latest`
- [ ] Instala GnuCOBOL con `apt-get install -y gnucobol`
- [ ] Ejecuta `make` y `make test`
- [ ] Job separado para la API (Python 3.12, `pytest`)
- [ ] Badge de estado en el README
EOF
)"

# =============================================================================
# M2 - Núcleo batch
# =============================================================================
crear_issue "Copybook del registro de cuenta" "cobol" "M2 - Núcleo batch" "$(cat <<'EOF'
Definir `copybooks/CUENTA.cpy`.

**Campos sugeridos**
- Número de cuenta (clave, `PIC X(10)`)
- Nombre del titular
- Tipo de cuenta (ahorro / cheques)
- Saldo (`PIC S9(11)V99 COMP-3`)
- Tasa de interés anual (`PIC 9V9(4) COMP-3`)
- Estatus (activa / bloqueada / cerrada) con niveles 88
- Fecha de última actualización

**Criterios de aceptación**
- [ ] Longitud de registro documentada en un comentario
- [ ] Niveles 88 para tipo y estatus
EOF
)"

crear_issue "Copybook del registro de transacción" "cobol" "M2 - Núcleo batch" "$(cat <<'EOF'
Definir `copybooks/TRANSACCION.cpy`.

**Campos sugeridos**
- ID de transacción
- Número de cuenta
- Tipo (depósito / retiro / transferencia / cargo por comisión) con niveles 88
- Importe (`COMP-3`)
- Cuenta destino (solo transferencias)
- Fecha y hora

**Criterios de aceptación**
- [ ] Registro de longitud fija documentado
- [ ] Copybook adicional `RECHAZO.cpy` con la transacción original + código y descripción del motivo
EOF
)"

crear_issue "Generador de datos de prueba en Python" "python,datos" "M2 - Núcleo batch" "$(cat <<'EOF'
Script `scripts/generar_datos.py` que produzca archivos de entrada realistas.

**Criterios de aceptación**
- [ ] Genera N cuentas y M transacciones en formato de longitud fija compatible con los copybooks
- [ ] Incluye casos inválidos a propósito (cuenta inexistente, saldo insuficiente, cuenta bloqueada, importe negativo)
- [ ] Semilla configurable para reproducibilidad
- [ ] Parámetros por línea de comandos (`argparse`)
EOF
)"

crear_issue "Programa de carga inicial del maestro de cuentas" "cobol" "M2 - Núcleo batch" "$(cat <<'EOF'
`src/CARGACTA.cbl`: convertir un archivo secuencial de cuentas en un archivo indexado (`ORGANIZATION IS INDEXED`).

**Criterios de aceptación**
- [ ] Clave primaria: número de cuenta
- [ ] Detecta y reporta claves duplicadas sin abortar
- [ ] Muestra totales de registros leídos, cargados y rechazados
- [ ] Verifica `FILE STATUS` después de cada operación de E/S
EOF
)"

crear_issue "Validación de transacciones" "cobol" "M2 - Núcleo batch" "$(cat <<'EOF'
Primer paso del batch diario: validar cada transacción contra el maestro.

**Reglas**
- Cuenta existe y está activa
- Importe mayor a cero
- Tipo de transacción válido
- Para transferencias: cuenta destino existe y es distinta a la origen

**Criterios de aceptación**
- [ ] Transacciones válidas pasan al siguiente paso
- [ ] Inválidas se escriben en el archivo de rechazos con código de motivo
- [ ] Códigos de motivo documentados en el README
EOF
)"

crear_issue "Aplicación de movimientos al maestro" "cobol" "M2 - Núcleo batch" "$(cat <<'EOF'
`src/PROCTRAN.cbl`: aplicar depósitos, retiros, transferencias y comisiones actualizando el maestro con `REWRITE`.

**Criterios de aceptación**
- [ ] Retiros con saldo insuficiente se rechazan (no se permiten sobregiros)
- [ ] Transferencias actualizan ambas cuentas o ninguna
- [ ] Aritmética con `COMP-3` y `ROUNDED` explícito donde aplique
- [ ] Contadores de control: transacciones aplicadas, rechazadas, importe total por tipo
EOF
)"

crear_issue "Cálculo de intereses diarios" "cobol" "M2 - Núcleo batch" "$(cat <<'EOF'
`src/INTERES.cbl`: calcular y abonar interés diario a cuentas de ahorro.

**Criterios de aceptación**
- [ ] Interés diario = saldo × tasa anual / 360 (documentar la convención usada)
- [ ] Solo cuentas de ahorro activas con saldo positivo
- [ ] Redondeo a 2 decimales con `ROUNDED`
- [ ] El interés abonado se registra como movimiento para auditoría
EOF
)"

crear_issue "Reporte de cierre diario" "cobol" "M2 - Núcleo batch" "$(cat <<'EOF'
`src/REPCIERRE.cbl`: reporte impreso de ancho fijo (132 columnas).

**Contenido**
- Encabezado con fecha de proceso y número de página
- Detalle por cuenta: saldo inicial, movimientos, intereses, saldo final
- Cortes de control por tipo de cuenta con subtotales
- Totales generales y resumen de rechazos por motivo

**Criterios de aceptación**
- [ ] Importes editados con máscara (`ZZZ,ZZZ,ZZ9.99-`)
- [ ] Salto de página cada N líneas con encabezado repetido
- [ ] Cuadre: saldo inicial + movimientos + intereses = saldo final
EOF
)"

crear_issue "Script orquestador del batch diario" "setup,cobol" "M2 - Núcleo batch" "$(cat <<'EOF'
`scripts/batch_diario.sh`, equivalente simplificado a un JCL.

**Criterios de aceptación**
- [ ] Ejecuta en orden: validación → aplicación → intereses → reporte
- [ ] Detiene la cadena si un paso termina con `RETURN-CODE` distinto de 0
- [ ] Respalda el maestro antes de modificarlo
- [ ] Log con hora de inicio y fin de cada paso
EOF
)"

# =============================================================================
# M3 - Pruebas batch
# =============================================================================
crear_issue "Pruebas de regresión con archivos golden" "testing,cobol" "M3 - Pruebas batch" "$(cat <<'EOF'
Comparar la salida del batch contra resultados esperados versionados.

**Criterios de aceptación**
- [ ] Datos de entrada fijos en `tests/fixtures/`
- [ ] Salidas esperadas (maestro final, rechazos, reporte) en `tests/golden/`
- [ ] `make test` corre el batch completo y compara con `diff`
- [ ] Falla con mensaje claro indicando qué archivo difiere
EOF
)"

crear_issue "Casos borde del procesamiento" "testing,cobol" "M3 - Pruebas batch" "$(cat <<'EOF'
Cubrir escenarios que suelen romper sistemas financieros.

**Casos**
- [ ] Retiro exactamente igual al saldo
- [ ] Transferencia a la misma cuenta
- [ ] Cuenta bloqueada a mitad del lote
- [ ] Importes con redondeo en el límite (x.xx5)
- [ ] Archivo de transacciones vacío
- [ ] Saldo cercano al máximo del `PIC`
EOF
)"

# =============================================================================
# M4 - Capa API
# =============================================================================
crear_issue "Definir contrato de la API" "api,docs" "M4 - Capa API" "$(cat <<'EOF'
Documentar los endpoints antes de implementarlos.

**Endpoints propuestos**
- `GET  /cuentas/{numero}` → consulta de saldo y estatus
- `POST /transacciones` → registra una transacción para el siguiente batch
- `POST /batch/ejecutar` → dispara el batch diario
- `GET  /batch/ultimo-reporte` → devuelve el último reporte de cierre
- `GET  /health`

**Criterios de aceptación**
- [ ] Esquemas de request/response definidos con Pydantic
- [ ] Códigos de error y mensajes documentados
EOF
)"

crear_issue "Subprograma COBOL de consulta de cuenta" "cobol,api" "M4 - Capa API" "$(cat <<'EOF'
`src/CONSCTA.cbl`: programa que recibe un número de cuenta y devuelve sus datos en un formato fácil de parsear.

**Criterios de aceptación**
- [ ] Recibe el número de cuenta por argumento de línea de comandos
- [ ] Imprime el resultado en una sola línea delimitada (o JSON simple) a stdout
- [ ] Return code distinto para "no encontrada" y para error de E/S
- [ ] Abre el maestro en modo `INPUT` (solo lectura)
EOF
)"

crear_issue "Servicio FastAPI que invoca los programas COBOL" "python,api" "M4 - Capa API" "$(cat <<'EOF'
Implementar `api/main.py`.

**Criterios de aceptación**
- [ ] Invoca los ejecutables COBOL con `subprocess.run` y timeout
- [ ] Traduce return codes COBOL a códigos HTTP (404, 409, 500)
- [ ] `POST /transacciones` escribe el registro en formato de longitud fija compatible con el copybook
- [ ] Bloqueo para evitar ejecutar el batch dos veces simultáneamente
- [ ] Logging estructurado de cada invocación
EOF
)"

crear_issue "Pruebas de la API con pytest" "testing,python,api" "M4 - Capa API" "$(cat <<'EOF'
**Criterios de aceptación**
- [ ] Tests con `TestClient` de FastAPI
- [ ] Prueba de punta a punta: registrar transacción → ejecutar batch → consultar saldo actualizado
- [ ] Casos de error: cuenta inexistente, payload inválido, batch en ejecución
- [ ] Se ejecutan en el job de CI
EOF
)"

crear_issue "Dockerfile con GnuCOBOL y Python" "setup,api" "M4 - Capa API" "$(cat <<'EOF'
Empaquetar todo para que cualquiera pueda correrlo con un comando.

**Criterios de aceptación**
- [ ] Imagen basada en Debian/Ubuntu con GnuCOBOL y Python 3.12
- [ ] Compila los programas COBOL durante el build
- [ ] `docker compose up` levanta la API en el puerto 8000
- [ ] Volumen para persistir los archivos de datos
EOF
)"

# =============================================================================
# M5 - Documentación
# =============================================================================
crear_issue "README completo del proyecto" "docs" "M5 - Documentación" "$(cat <<'EOF'
**Contenido**
- [ ] Descripción y motivación (modernización de sistemas legados)
- [ ] Diagrama de arquitectura (Mermaid): API → programas COBOL → archivos indexados
- [ ] Flujo del batch diario paso a paso
- [ ] Instrucciones: compilar, correr el batch, levantar la API, correr pruebas
- [ ] Tabla de códigos de rechazo
- [ ] Ejemplo de reporte de cierre
EOF
)"

crear_issue "Demo y ejemplos de uso" "docs" "M5 - Documentación" "$(cat <<'EOF'
**Criterios de aceptación**
- [ ] Colección de requests de ejemplo (`curl` o archivo `.http`)
- [ ] GIF o captura del flujo completo en el README
- [ ] Sección de "decisiones de diseño" explicando por qué COBOL + API en lugar de reescribir
EOF
)"

echo ">> Listo."