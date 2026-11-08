"""Parser mínimo de copybooks COBOL en formato fijo.

Lee un archivo .cpy y calcula, para cada campo, su offset, longitud en bytes,
tipo de almacenamiento y los valores válidos declarados en sus niveles 88.

Soporta el subconjunto que usa COBRA:
  - PIC con X, A, 9, S, V y repeticiones (n)
  - USAGE DISPLAY, COMP-3 / PACKED-DECIMAL, COMP / BINARY
  - Grupos, FILLER, REDEFINES y niveles 88 (VALUE, listas, THRU)

Cualquier otra cláusula (OCCURS, SIGN, JUSTIFIED, COMP-5, ...) produce un
error explícito en lugar de calcular un layout equivocado.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

# Tipos de almacenamiento
ALFANUMERICO = "X"
ZONED = "DISPLAY"      # numérico, un dígito ASCII por byte
PACKED = "COMP-3"      # BCD empaquetado
BINARIO = "BINARY"     # entero big-endian (default de GnuCOBOL)
GRUPO = "GRUPO"

_USAGE = {
    "DISPLAY": ZONED,
    "COMP-3": PACKED,
    "COMPUTATIONAL-3": PACKED,
    "PACKED-DECIMAL": PACKED,
    "COMP": BINARIO,
    "COMPUTATIONAL": BINARIO,
    "BINARY": BINARIO,
    "COMP-4": BINARIO,
    "COMPUTATIONAL-4": BINARIO,
}

_IGNORAR = {"IS", "ARE"}
_NO_SOPORTADO = {
    "OCCURS", "SIGN", "JUSTIFIED", "JUST", "SYNCHRONIZED", "SYNC",
    "BLANK", "RENAMES", "COMP-1", "COMP-2", "COMP-5", "COMP-X",
    "COMPUTATIONAL-5", "POINTER", "INDEX",
}


class CopybookError(Exception):
    pass


@dataclass
class Condicion:
    """Un nivel 88: nombre y lista de rangos (lo, hi) válidos."""
    nombre: str
    rangos: list[tuple[object, object]]

    def acepta(self, valor) -> bool:
        return any(lo <= valor <= hi for lo, hi in self.rangos)


@dataclass
class Campo:
    nivel: int
    nombre: str
    tipo: str = GRUPO
    digitos: int = 0          # numéricos: total de 9s (incluye decimales)
    escala: int = 0           # numéricos: dígitos después de V
    signo: bool = False
    caracteres: int = 0       # alfanuméricos: longitud declarada
    redefine: str | None = None
    condiciones: list[Condicion] = field(default_factory=list)
    hijos: list["Campo"] = field(default_factory=list)
    offset: int = 0
    longitud: int = 0
    en_redefines: bool = False  # el campo o un ancestro es un REDEFINES

    @property
    def es_filler(self) -> bool:
        return self.nombre == "FILLER"

    @property
    def es_numerico(self) -> bool:
        return self.tipo in (ZONED, PACKED, BINARIO)

    def acepta(self, valor) -> bool:
        """True si no hay 88 declarados o si el valor cumple alguno."""
        return not self.condiciones or any(c.acepta(valor) for c in self.condiciones)


@dataclass
class Registro:
    nombre: str
    raiz: Campo

    @property
    def longitud(self) -> int:
        return self.raiz.longitud

    def campos(self, incluir_redefines: bool = False) -> list[Campo]:
        """Campos elementales en orden de posición.

        Por defecto excluye los que están dentro de un REDEFINES: son otra
        vista de los mismos bytes y escribirlos duplicaría información.
        """
        salida: list[Campo] = []

        def recorrer(c: Campo):
            if c.en_redefines and not incluir_redefines:
                return
            if c.tipo == GRUPO:
                for h in c.hijos:
                    recorrer(h)
            else:
                salida.append(c)

        recorrer(self.raiz)
        return salida

    def campo(self, nombre: str) -> Campo:
        for c in self.campos(incluir_redefines=True):
            if c.nombre == nombre:
                return c
        raise KeyError(nombre)


# ---------------------------------------------------------------------------
# Lectura del formato fijo
# ---------------------------------------------------------------------------

def _texto_programa(fuente: str) -> str:
    """Extrae el área de programa (cols 8-72) sin comentarios."""
    lineas = []
    for linea in fuente.splitlines():
        if len(linea) >= 7 and linea[6] in "*/":
            continue
        area = linea[7:72]
        lineas.append(_quitar_comentario(area))
    return " ".join(lineas)


def _quitar_comentario(texto: str) -> str:
    """Quita un comentario '*>' que no esté dentro de una literal."""
    comilla = None
    for i, ch in enumerate(texto):
        if comilla:
            if ch == comilla:
                comilla = None
        elif ch in "\"'":
            comilla = ch
        elif texto.startswith("*>", i):
            return texto[:i]
    return texto


_TOKEN = re.compile(r'"[^"]*"|\'[^\']*\'|[^\s]+')


def _sentencias(texto: str) -> list[list[str]]:
    """Separa por punto final (un punto seguido de espacio o fin)."""
    partes = re.split(r"\.(?=\s|$)", texto)
    return [_TOKEN.findall(p) for p in partes if p.strip()]


# ---------------------------------------------------------------------------
# PIC y literales
# ---------------------------------------------------------------------------

def _expandir_pic(pic: str) -> str:
    return re.sub(r"(.)\((\d+)\)", lambda m: m.group(1) * int(m.group(2)), pic.upper())


def _aplicar_pic(campo: Campo, pic: str):
    p = _expandir_pic(pic)
    if not re.fullmatch(r"[SXA9V]+", p):
        raise CopybookError(f"{campo.nombre}: PIC '{pic}' no soportada (solo X, A, 9, S, V)")
    if "X" in p or "A" in p:
        if set(p) - {"X", "A"}:
            raise CopybookError(f"{campo.nombre}: PIC '{pic}' mezcla alfanumérico y numérico")
        campo.tipo = ALFANUMERICO
        campo.caracteres = len(p)
        return
    campo.signo = p.startswith("S")
    p = p.lstrip("S")
    if p.count("V") > 1 or "S" in p:
        raise CopybookError(f"{campo.nombre}: PIC '{pic}' inválida")
    entero, _, decimal = p.partition("V")
    campo.tipo = ZONED
    campo.digitos = len(entero) + len(decimal)
    campo.escala = len(decimal)


def _literal(token: str):
    t = token.upper()
    if token[0] in "\"'":
        return token[1:-1]
    if t in ("SPACE", "SPACES"):
        return " "
    if t in ("ZERO", "ZEROS", "ZEROES"):
        return Decimal(0)
    try:
        return Decimal(token)
    except Exception:
        raise CopybookError(f"literal no soportada: {token}") from None


def _parsear_values(tokens: list[str]) -> list[tuple[object, object]]:
    rangos = []
    i = 0
    while i < len(tokens):
        lo = _literal(tokens[i])
        hi = lo
        if i + 2 < len(tokens) and tokens[i + 1].upper() in ("THRU", "THROUGH"):
            hi = _literal(tokens[i + 2])
            i += 2
        rangos.append((lo, hi))
        i += 1
    return rangos


# ---------------------------------------------------------------------------
# Construcción del árbol
# ---------------------------------------------------------------------------

def _parsear_entrada(tokens: list[str]) -> Campo | Condicion:
    nivel = int(tokens[0])
    resto = tokens[1:]
    nombre = "FILLER"
    if resto and resto[0].upper() not in _USAGE and resto[0].upper() not in (
        "PIC", "PICTURE", "REDEFINES", "VALUE", "VALUES", "USAGE"
    ):
        nombre = resto[0].upper()
        resto = resto[1:]

    if nivel == 88:
        if not resto or resto[0].upper() not in ("VALUE", "VALUES"):
            raise CopybookError(f"88 {nombre}: falta VALUE")
        valores = [t for t in resto[1:] if t.upper() not in _IGNORAR]
        if "WHEN" in (t.upper() for t in valores):
            valores = valores[: [t.upper() for t in valores].index("WHEN")]
        return Condicion(nombre, _parsear_values(valores))

    campo = Campo(nivel=nivel, nombre=nombre)
    usage = None
    i = 0
    while i < len(resto):
        t = resto[i].upper()
        if t in _IGNORAR:
            i += 1
        elif t in ("PIC", "PICTURE"):
            i += 1
            if resto[i].upper() == "IS":
                i += 1
            _aplicar_pic(campo, resto[i])
            i += 1
        elif t == "USAGE":
            i += 1
        elif t in _USAGE:
            usage = _USAGE[t]
            i += 1
        elif t == "REDEFINES":
            campo.redefine = resto[i + 1].upper()
            i += 2
        elif t in ("VALUE", "VALUES"):
            # Valor inicial: no afecta el layout. Se salta la literal.
            i += 1
            if i < len(resto) and resto[i].upper() == "IS":
                i += 1
            i += 1
        elif t in _NO_SOPORTADO:
            raise CopybookError(f"{nombre}: cláusula {t} no soportada")
        else:
            raise CopybookError(f"{nombre}: token inesperado '{resto[i]}'")

    if usage and usage != ZONED:
        if campo.tipo == GRUPO:
            raise CopybookError(f"{nombre}: USAGE {usage} en un grupo no soportado")
        if campo.tipo == ALFANUMERICO:
            raise CopybookError(f"{nombre}: USAGE {usage} requiere PIC numérica")
        campo.tipo = usage
    return campo


def _longitud_elemental(c: Campo) -> int:
    if c.tipo == ALFANUMERICO:
        return c.caracteres
    if c.tipo == ZONED:
        return c.digitos
    if c.tipo == PACKED:
        return c.digitos // 2 + 1
    if c.tipo == BINARIO:
        # Tamaños de GnuCOBOL (binary-size 1-2-4-8)
        for maximo, nbytes in ((2, 1), (4, 2), (9, 4), (18, 8)):
            if c.digitos <= maximo:
                return nbytes
        raise CopybookError(f"{c.nombre}: BINARY de más de 18 dígitos")
    raise AssertionError(c.tipo)


def _calcular(c: Campo, offset: int, en_redefines: bool):
    c.offset = offset
    c.en_redefines = en_redefines
    if c.tipo != GRUPO:
        c.longitud = _longitud_elemental(c)
        return
    if not c.hijos:
        raise CopybookError(f"{c.nombre}: grupo sin campos (¿falta PIC?)")
    cursor = offset
    posiciones: dict[str, Campo] = {}
    for h in c.hijos:
        if h.redefine:
            original = posiciones.get(h.redefine)
            if original is None:
                raise CopybookError(f"{h.nombre}: REDEFINES de '{h.redefine}', que no es un campo previo del mismo grupo")
            _calcular(h, original.offset, True)
            if h.longitud > original.longitud:
                raise CopybookError(f"{h.nombre}: mide {h.longitud} bytes, más que '{h.redefine}' ({original.longitud})")
        else:
            _calcular(h, cursor, en_redefines)
            cursor += h.longitud
            posiciones[h.nombre] = h
    c.longitud = cursor - offset


def parsear(fuente: str) -> list[Registro]:
    """Parsea el texto de un copybook y regresa sus registros de nivel 01."""
    registros: list[Registro] = []
    pila: list[Campo] = []
    for tokens in _sentencias(_texto_programa(fuente)):
        if not tokens[0].isdigit():
            raise CopybookError(f"se esperaba un número de nivel: {' '.join(tokens)}")
        entrada = _parsear_entrada(tokens)
        if isinstance(entrada, Condicion):
            if not pila:
                raise CopybookError(f"88 {entrada.nombre} sin campo padre")
            pila[-1].condiciones.append(entrada)
            continue
        if entrada.nivel in (1, 77):
            if entrada.redefine:
                raise CopybookError(f"{entrada.nombre}: REDEFINES en nivel 01 no soportado")
            registros.append(Registro(entrada.nombre, entrada))
            pila = [entrada]
            continue
        if not pila:
            raise CopybookError(f"{entrada.nombre}: nivel {entrada.nivel} fuera de un 01")
        while pila and pila[-1].nivel >= entrada.nivel:
            pila.pop()
        if not pila:
            raise CopybookError(f"{entrada.nombre}: jerarquía de niveles inválida")
        padre = pila[-1]
        if padre.tipo != GRUPO:
            raise CopybookError(f"{entrada.nombre}: '{padre.nombre}' tiene PIC y no puede tener campos")
        padre.hijos.append(entrada)
        pila.append(entrada)

    for r in registros:
        _calcular(r.raiz, 0, False)
    return registros


def cargar(ruta: str | Path, registro: str | None = None) -> Registro:
    """Lee un .cpy y regresa su registro (el único, o el indicado por nombre)."""
    registros = parsear(Path(ruta).read_text(encoding="utf-8"))
    if not registros:
        raise CopybookError(f"{ruta}: no contiene registros de nivel 01")
    if registro:
        for r in registros:
            if r.nombre == registro.upper():
                return r
        raise CopybookError(f"{ruta}: no existe el registro {registro}")
    if len(registros) > 1:
        nombres = ", ".join(r.nombre for r in registros)
        raise CopybookError(f"{ruta}: tiene varios registros ({nombres}); indica cuál")
    return registros[0]
