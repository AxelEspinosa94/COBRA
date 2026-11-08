"""Codificación y decodificación de registros COBOL de longitud fija.

Convierte entre diccionarios de Python ({"CTA-SALDO": Decimal("10.50"), ...})
y los bytes exactos que GnuCOBOL lee y escribe para un copybook.

Reglas:
  - Alfanuméricos: ASCII, rellenos con espacios a la derecha. Los acentos se
    quitan ("Peña" -> "Pena") para que cada carácter ocupe un byte.
  - Numéricos: nunca se redondea ni se trunca en silencio. Si un valor tiene
    más decimales o más dígitos de los que caben, es un error.
  - COMP-3: nibble de signo C (+), D (-) o F (sin signo), como GnuCOBOL.
  - BINARY: big-endian, tamaños 1-2-4-8 de GnuCOBOL.
"""

from __future__ import annotations

import unicodedata
from decimal import Decimal, InvalidOperation

from .copybook import ALFANUMERICO, BINARIO, PACKED, ZONED, Campo, Registro


class ValorInvalido(ValueError):
    def __init__(self, campo: str, mensaje: str):
        super().__init__(f"{campo}: {mensaje}")
        self.campo = campo


# ---------------------------------------------------------------------------
# Texto
# ---------------------------------------------------------------------------

def a_ascii(texto: str) -> str:
    """Quita acentos y diacríticos: 'Peña Núñez' -> 'Pena Nunez'."""
    normal = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in normal if not unicodedata.combining(ch))


def _codificar_texto(c: Campo, valor) -> bytes:
    texto = a_ascii("" if valor is None else str(valor))
    try:
        datos = texto.encode("ascii")
    except UnicodeEncodeError:
        raise ValorInvalido(c.nombre, f"carácter no ASCII en '{valor}'") from None
    if len(datos) > c.longitud:
        raise ValorInvalido(c.nombre, f"'{texto}' mide {len(datos)}, el máximo es {c.longitud}")
    return datos.ljust(c.longitud, b" ")


# ---------------------------------------------------------------------------
# Números
# ---------------------------------------------------------------------------

def _a_decimal(c: Campo, valor) -> Decimal:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return Decimal(0)
    try:
        d = Decimal(str(valor).strip())
    except InvalidOperation:
        raise ValorInvalido(c.nombre, f"'{valor}' no es un número") from None
    if not d.is_finite():
        raise ValorInvalido(c.nombre, f"'{valor}' no es un número finito")
    return d


def _entero_escalado(c: Campo, valor) -> int:
    """Convierte 1500.5 con escala 2 en 150050, validando que quepa."""
    d = _a_decimal(c, valor)
    escalado = d.scaleb(c.escala)
    if escalado != escalado.to_integral_value():
        raise ValorInvalido(c.nombre, f"{d} tiene más de {c.escala} decimales")
    n = int(escalado)
    if n < 0 and not c.signo:
        raise ValorInvalido(c.nombre, f"{d} es negativo y el campo no tiene signo (S)")
    if len(str(abs(n))) > c.digitos:
        enteros = c.digitos - c.escala
        raise ValorInvalido(c.nombre, f"{d} no cabe en {enteros} enteros y {c.escala} decimales")
    return n


def empacar_comp3(n: int, digitos: int, signo: bool) -> bytes:
    """Empaca un entero en BCD: 12345 (S9(5)) -> 0x12 0x34 0x5C."""
    nibble_signo = ("D" if n < 0 else "C") if signo else "F"
    cifras = str(abs(n)).zfill(digitos) + nibble_signo
    if len(cifras) % 2:
        cifras = "0" + cifras
    return bytes.fromhex(cifras)


def desempacar_comp3(datos: bytes, campo: str = "?") -> int:
    cifras = datos.hex().upper()
    cuerpo, signo = cifras[:-1], cifras[-1]
    if not cuerpo.isdigit() or signo not in "ABCDEF":
        raise ValorInvalido(campo, f"COMP-3 corrupto: {cifras}")
    n = int(cuerpo)
    return -n if signo in "BD" else n


def _codificar_numero(c: Campo, valor) -> bytes:
    n = _entero_escalado(c, valor)
    if c.tipo == PACKED:
        return empacar_comp3(n, c.digitos, c.signo)
    if c.tipo == BINARIO:
        return n.to_bytes(c.longitud, "big", signed=c.signo)
    if c.tipo == ZONED:
        if c.signo:
            raise ValorInvalido(c.nombre, "S9 en DISPLAY (signo sobreimpreso) no está soportado; usa COMP-3")
        return str(n).zfill(c.digitos).encode("ascii")
    raise AssertionError(c.tipo)


def _decodificar_numero(c: Campo, datos: bytes) -> Decimal:
    if c.tipo == PACKED:
        n = desempacar_comp3(datos, c.nombre)
    elif c.tipo == BINARIO:
        n = int.from_bytes(datos, "big", signed=c.signo)
    elif c.tipo == ZONED:
        texto = datos.decode("ascii", errors="replace")
        if c.signo or not texto.isdigit():
            raise ValorInvalido(c.nombre, f"DISPLAY no numérico: '{texto}'")
        n = int(texto)
    else:
        raise AssertionError(c.tipo)
    return Decimal(n).scaleb(-c.escala)


# ---------------------------------------------------------------------------
# Registros
# ---------------------------------------------------------------------------

def codificar_campo(c: Campo, valor) -> bytes:
    if c.tipo == ALFANUMERICO:
        return _codificar_texto(c, valor)
    return _codificar_numero(c, valor)


def decodificar_campo(c: Campo, datos: bytes):
    if c.tipo == ALFANUMERICO:
        return datos.decode("ascii", errors="replace").rstrip(" ")
    return _decodificar_numero(c, datos)


def codificar(registro: Registro, valores: dict) -> bytes:
    """Arma los bytes de un registro.

    Los campos que no vengan en `valores` quedan en espacios (alfanuméricos)
    o en cero (numéricos). FILLER siempre va en espacios.
    """
    buf = bytearray(b" " * registro.longitud)
    for c in registro.campos():
        if c.es_filler:
            continue
        datos = codificar_campo(c, valores.get(c.nombre))
        assert len(datos) == c.longitud, (c.nombre, len(datos), c.longitud)
        buf[c.offset : c.offset + c.longitud] = datos
    return bytes(buf)


def decodificar(registro: Registro, datos: bytes, incluir_redefines: bool = False) -> dict:
    if len(datos) != registro.longitud:
        raise ValueError(f"se esperaban {registro.longitud} bytes y llegaron {len(datos)}")
    return {
        c.nombre: decodificar_campo(c, datos[c.offset : c.offset + c.longitud])
        for c in registro.campos(incluir_redefines)
        if not c.es_filler
    }


def valor_para_88(c: Campo, valor):
    """Normaliza un valor para compararlo contra los VALUE de sus 88."""
    if c.tipo == ALFANUMERICO:
        return a_ascii("" if valor is None else str(valor)).ljust(c.longitud)[: c.longitud]
    return _a_decimal(c, valor)


def leer_archivo(registro: Registro, ruta, incluir_redefines: bool = False) -> list[dict]:
    """Lee un archivo secuencial de registros fijos (sin saltos de línea)."""
    with open(ruta, "rb") as f:
        datos = f.read()
    if len(datos) % registro.longitud:
        raise ValueError(
            f"{ruta}: {len(datos)} bytes no es múltiplo de {registro.longitud} "
            f"(¿copybook equivocado o archivo con saltos de línea?)"
        )
    n = registro.longitud
    return [decodificar(registro, datos[i : i + n], incluir_redefines) for i in range(0, len(datos), n)]
