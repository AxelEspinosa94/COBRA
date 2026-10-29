# =============================================================================
# COBRA - Makefile
#
#   make              compila todo (lint + programas + módulos)
#   make info         muestra qué se detectó como ejecutable y como módulo
#   make lint         revisa el formato fijo de .cbl y .cpy
#   make run PROG=X   ejecuta bin/X        (default: DEMO)
#   make test         compara la salida de cada programa con tests/golden/
#   make golden PROG=X  guarda la salida actual de X como esperada
#   make clean        borra binarios y temporales
#   make DEBUG=1      compila con chequeos en tiempo de ejecución (-debug -g)
#
# Convención:
#   - Todo src/*.cbl se compila como ejecutable (cobc -x) ...
#   - ... excepto los subprogramas (PROCEDURE DIVISION USING), que se
#     compilan como módulos llamables con CALL (cobc -m -> bin/NOMBRE.so)
# =============================================================================

SRC_DIR   := src
COPY_DIR  := copybooks
BIN_DIR   := bin
GOLDEN    := tests/golden

# Subprogramas llamables: se detectan solos. Un programa es módulo si su
# PROCEDURE DIVISION recibe parámetros (USING). Se ignoran comentarios.
#   make MODULOS_EXTRA="X Y"   fuerza otros como módulo
#   make MODULOS="X Y"         reemplaza la detección por completo
MODULOS   ?= $(basename $(notdir $(shell grep -lE \
               '^.{6} .*PROCEDURE[[:space:]]+DIVISION[[:space:]]+USING' \
               $(SRC_DIR)/*.cbl 2>/dev/null)))
MODULOS   += $(MODULOS_EXTRA)

COBC      := cobc
COBFLAGS  := -fixed -Wall -Wcolumn-overflow -Werror -I $(COPY_DIR)
ifeq ($(DEBUG),1)
  COBFLAGS += -debug -g
endif

# Flags que cobc pasa a gcc. El default de Ubuntu agrega -D_FORTIFY_SOURCE=2,
# que choca con el de gcc y ensucia la salida con un warning inofensivo.
export COB_CFLAGS ?= -pipe -finline-functions

# Los CALL dinámicos buscan los .so en esta ruta
export COB_LIBRARY_PATH := $(abspath $(BIN_DIR))

# -----------------------------------------------------------------------------
FUENTES     := $(wildcard $(SRC_DIR)/*.cbl)
COPYBOOKS   := $(wildcard $(COPY_DIR)/*.cpy)
PROGRAMAS   := $(basename $(notdir $(FUENTES)))
EJECUTABLES := $(filter-out $(MODULOS),$(PROGRAMAS))

BIN_EXE     := $(addprefix $(BIN_DIR)/,$(EJECUTABLES))
BIN_MOD     := $(addprefix $(BIN_DIR)/,$(addsuffix .so,$(MODULOS)))

PROG ?= DEMO

.PHONY: all info lint run test golden clean

all: lint $(BIN_MOD) $(BIN_EXE)

info:
	@echo "cobc         : $$($(COBC) --version | head -1)"
	@echo "Ejecutables  : $(or $(EJECUTABLES),(ninguno))"
	@echo "Módulos      : $(or $(strip $(MODULOS)),(ninguno))"
	@echo "Copybooks    : $(or $(notdir $(COPYBOOKS)),(ninguno))"
	@echo "Flags        : $(COBFLAGS)"

lint:
	@bash scripts/lint_cobol.sh $(FUENTES) $(COPYBOOKS)

# Ejecutables. Dependen de todos los copybooks: si cambia uno, se recompila.
$(BIN_DIR)/%: $(SRC_DIR)/%.cbl $(COPYBOOKS) | $(BIN_DIR)
	$(COBC) -x $(COBFLAGS) -o $@ $<

# Módulos llamables
$(BIN_DIR)/%.so: $(SRC_DIR)/%.cbl $(COPYBOOKS) | $(BIN_DIR)
	$(COBC) -m $(COBFLAGS) -o $@ $<

$(BIN_DIR):
	@mkdir -p $@

run: all
	@./$(BIN_DIR)/$(PROG)

# Para cada tests/golden/NOMBRE.out: ejecuta bin/NOMBRE y compara la salida
test: all
	@fallas=0; \
	for esperado in $(GOLDEN)/*.out; do \
	  [ -e "$$esperado" ] || { echo "test: no hay archivos en $(GOLDEN)/"; exit 0; }; \
	  prog=$$(basename "$$esperado" .out); \
	  if ./$(BIN_DIR)/$$prog | diff -u "$$esperado" - > /dev/null; then \
	    echo "  OK    $$prog"; \
	  else \
	    echo "  FALLA $$prog"; \
	    ./$(BIN_DIR)/$$prog | diff -u "$$esperado" - | sed 's/^/        /'; \
	    fallas=$$((fallas + 1)); \
	  fi; \
	done; \
	[ $$fallas -eq 0 ] || { echo "test: $$fallas prueba(s) fallaron"; exit 1; }

# Genera o actualiza la salida esperada de un programa: make golden PROG=X
# Revisa el resultado antes de hacer commit: lo que quede aquí es "la verdad".
golden: all
	@mkdir -p $(GOLDEN)
	./$(BIN_DIR)/$(PROG) > $(GOLDEN)/$(PROG).out
	@echo "golden: $(GOLDEN)/$(PROG).out actualizado"

clean:
	rm -f $(BIN_DIR)/* $(SRC_DIR)/*.c $(SRC_DIR)/*.c.* $(SRC_DIR)/*.i $(SRC_DIR)/*.lst
	@touch $(BIN_DIR)/.gitkeep